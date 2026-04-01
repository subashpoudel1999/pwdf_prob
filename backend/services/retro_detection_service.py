"""
Retrospective Debris Flow Detection Service.

For a selected historical fire this service:
  1. Loads sub-basin polygons from the cached Wildcat output (basins.geojson)
  2. Downloads NHDPlus HR stream network from the USGS ArcGIS REST API
     (layers 3 + 4: NetworkNHDFlowline + NonNetworkNHDFlowline)
  3. Loads WildCat-derived drainage segments (segments.geojson from wildcat cache)
  4. Builds per-basin stream line data (NHD ∪ WildCat, total length)
  5. Samples N_SAMPLE_POINTS random points per basin along those stream lines
  6. Uses Google Earth Engine to compute spectral change indices at each point
     (single sampleRegions call — points are tiny, no payload-size issues):
       · Primary source: Sentinel-2 (COPERNICUS/S2_SR_HARMONIZED, 10m)
       · Fallback: Landsat-8/9 (30m) when S2 has < 3 images in either period
     Change indices (convention from module7_stream_analysis.py):
       dNDWI = post_NDWI − pre_NDWI        (moisture increase → debris signal)
       dBSI  = post_BSI  − pre_BSI         (bare-soil increase → erosion signal)
       dNBR  = pre_NBR   − post_NBR        (burn-severity standard convention)
  7. Averages the sampled values per basin
  8. Normalises each index 0–1 across all basins with valid data
  9. Computes composite: debris_flow_score = 0.4·dNDWI_norm + 0.4·dBSI_norm + 0.2·dNBR_norm
 10. Returns an enriched GeoJSON FeatureCollection with per-basin scoring properties.

WHY POINTS, NOT CORRIDOR POLYGONS:
  Sending many complex buffered corridor polygons to GEE's reduceRegions() causes a
  "Request payload size exceeds the limit: 10485760 bytes" error.  Sending N=25 random
  Point geometries per basin uses a fraction of the bandwidth and stays well within GEE's
  request size limit regardless of basin count.

Sub-basin IDs follow the FIRENAME-{Segment_ID} format (e.g. DOLAN-42).
Modules 11 and 12 from the semi-automated project (point-level ML validation)
are intentionally not ported here — this is purely a visualisation scoring tool.
"""

import json
import logging
import math
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import ee
import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import mapping, MultiLineString, LineString
from shapely.ops import unary_union
import services.gee_service as gee_service

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).parent.parent          # fire_webapp/backend/
_WEBAPP_ROOT  = _BACKEND_ROOT.parent                   # fire_webapp/
_CACHE_ROOT   = _BACKEND_ROOT / "data" / "retro_cache"

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
# GEE hard cap: sampleRegions().getInfo() aborts at 5 000 output elements.
# We stay well below that by targeting at most GEE_ELEMENT_BUDGET rows total.
# n_per_basin is computed adaptively in _gee_compute() as:
#   n_per_basin = max(3, min(N_SAMPLE_POINTS_MAX, GEE_ELEMENT_BUDGET // n_with_streams))
# so total output rows ≈ n_with_streams × n_per_basin ≤ GEE_ELEMENT_BUDGET.
GEE_ELEMENT_BUDGET   = 4_500
N_SAMPLE_POINTS_MAX  = 25      # cap per basin — never exceed this even for small fires

# Random seed for reproducible point placement across runs
_SAMPLE_SEED = 42

# ERA5 storm detection: number of candidate peak days to retrieve from GEE
# (then grouped into ≤5 distinct storm events)
_ERA5_N_CANDIDATES = 20

# NHDPlus HR REST API endpoints (layers 3 = Network, 4 = NonNetwork flowlines)
_NHD_URL_LAYER3 = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/3/query"
)
_NHD_URL_LAYER4 = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/4/query"
)

# S2 cloud-filter threshold
S2_CLOUD_PCT_THRESHOLD = 50
# Minimum images in each period for S2 to be considered "sufficient"
S2_MIN_IMAGES = 3

# In-memory job store
_jobs: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Per-fire static configuration
# ---------------------------------------------------------------------------
# Date ranges reused verbatim from module3_gee_imagery.py (Dolan validation pipeline).
FIRE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "dolan": {
        "display_name": "Dolan Fire",
        "year": 2020,
        "location": "Big Sur, CA",
        "utm_epsg": 32610,
        # Default imagery windows (Jan 27 2021 Atmospheric River event)
        "pre_start":  "2020-10-01",
        "pre_end":    "2020-12-31",
        "post_start": "2021-01-28",
        "post_end":   "2021-03-15",
        # ERA5 storm search window: 2 months post-containment → 2 years post-fire
        "storm_search_start":   "2020-10-01",
        "storm_search_end":     "2022-10-01",
        # Earliest allowed pre-storm imagery start (fire must have settled spectrally)
        "post_fire_stable_date": "2020-10-01",
        "basins_geojson":   _BACKEND_ROOT / "data" / "dolan_wildcat_cache" / "basins.geojson",
        "segments_geojson": _BACKEND_ROOT / "data" / "dolan_wildcat_cache" / "segments.geojson",
        "perimeter_shp":    _WEBAPP_ROOT  / "wildcat" / "dolan-fire" / "inputs" / "dolan_perimeter.shp",
    },
}


# ---------------------------------------------------------------------------
# Public service class
# ---------------------------------------------------------------------------

class RetroDetectionService:
    """Runs the retrospective debris-flow detection pipeline for a given fire."""

    def start_analysis(
        self,
        fire_id: str,
        project_id: str,
        force: bool = False,
        pre_start: Optional[str] = None,
        pre_end: Optional[str] = None,
        post_start: Optional[str] = None,
        post_end: Optional[str] = None,
        storm_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        if fire_id not in FIRE_CONFIGS:
            raise ValueError(
                f"Unknown fire_id '{fire_id}'. Available: {list(FIRE_CONFIGS.keys())}"
            )
        # Determine cache file: default or per-storm
        cache_key = storm_date if storm_date else "default"
        cache_filename = (
            "retro_results.geojson" if cache_key == "default"
            else f"retro_{cache_key}.geojson"
        )
        cache_path = _CACHE_ROOT / fire_id / cache_filename
        if not force and cache_path.exists():
            fake_id = f"retro_cached_{uuid.uuid4().hex[:6]}"
            _jobs[fake_id] = {
                "status": "completed", "step": 5,
                "message": "Detection complete (cached results loaded)", "progress": 100,
                "storm_date": storm_date, "cache_key": cache_key,
            }
            return {"job_id": fake_id, "cached": True, "storm_date": storm_date}

        cfg = FIRE_CONFIGS[fire_id]
        job_id = uuid.uuid4().hex[:8]
        _jobs[job_id] = {
            "status": "running", "step": 0,
            "message": "Starting retrospective detection pipeline...",
            "progress": 0, "error": None,
            # Window overrides (None → use fire config defaults)
            "pre_start":  pre_start  or cfg["pre_start"],
            "pre_end":    pre_end    or cfg["pre_end"],
            "post_start": post_start or cfg["post_start"],
            "post_end":   post_end   or cfg["post_end"],
            "storm_date": storm_date,
            "cache_key":  cache_key,
            "project_id": project_id,
        }
        t = threading.Thread(
            target=self._run, args=(job_id, fire_id), daemon=True
        )
        t.start()
        return {"job_id": job_id, "cached": False, "storm_date": storm_date}

    def get_status(self, job_id: str) -> Dict[str, Any]:
        if job_id not in _jobs:
            return {"status": "not_found", "error": f"Job {job_id} not found"}
        return dict(_jobs[job_id])

    def get_results(self, fire_id: str, storm_date: Optional[str] = None) -> Dict[str, Any]:
        if storm_date:
            path = _CACHE_ROOT / fire_id / f"retro_{storm_date}.geojson"
        else:
            path = _CACHE_ROOT / fire_id / "retro_results.geojson"
        if not path.exists():
            raise FileNotFoundError(
                f"No retro results for '{fire_id}' (storm_date={storm_date!r}) — run analysis first."
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def list_fires(self) -> list:
        return [
            {
                "fire_id": fid,
                "display_name": cfg["display_name"],
                "year": cfg["year"],
                "location": cfg["location"],
                "has_results": (_CACHE_ROOT / fid / "retro_results.geojson").exists(),
            }
            for fid, cfg in FIRE_CONFIGS.items()
        ]

    def clear_cache(self, fire_id: str):
        p = _CACHE_ROOT / fire_id / "retro_results.geojson"
        if p.exists():
            p.unlink()

    # -----------------------------------------------------------------------
    # Storm event detection via ERA5-Land Daily Aggregated (GEE)
    # -----------------------------------------------------------------------

    def get_storm_events(self, fire_id: str, project_id: str, force: bool = False) -> list:
        """Return top-5 storm events (sorted chronologically) within 2 years post-fire.

        Uses ECMWF/ERA5_LAND/DAILY_AGGR via GEE — reduces to a mean over the fire
        bounding box (ERA5 is 9 km resolution, so the whole Dolan area is a handful
        of pixels — very fast).  Results are cached in storm_events.json.

        Each returned dict:
          date              — peak precipitation day  "YYYY-MM-DD"
          peak_precip_mm    — ERA5 daily total on that day (mm)
          event_precip_mm   — sum of all days within ±3 days of peak (mm)
          pre_start/pre_end — suggested pre-storm imagery window
          post_start/post_end — suggested post-storm imagery window
        """
        if fire_id not in FIRE_CONFIGS:
            raise ValueError(f"Unknown fire_id '{fire_id}'")
        cfg = FIRE_CONFIGS[fire_id]
        cache_path = _CACHE_ROOT / fire_id / "storm_events.json"

        if not force and cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)

        gee_service.initialize(project_id)

        # Use basins file for the bounding box (perimeter shp may not always exist)
        basins_gdf = gpd.read_file(str(cfg["basins_geojson"])).to_crs(epsg=4326)
        minx, miny, maxx, maxy = basins_gdf.total_bounds
        fire_bbox = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        search_start      = cfg["storm_search_start"]
        search_end        = cfg["storm_search_end"]
        min_pre_start_str = cfg["post_fire_stable_date"]

        # Daily aggregated ERA5-Land precipitation over the fire bbox
        daily_col = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterDate(search_start, search_end)
            .filterBounds(fire_bbox)
            .select(["total_precipitation_sum"])
        )

        def _add_mean(img):
            val = img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=fire_bbox,
                scale=9000,
                maxPixels=1e9,
            ).get("total_precipitation_sum")
            return img.set("mean_precip", val)

        daily_with_mean = daily_col.map(_add_mean)
        sorted_col  = daily_with_mean.sort("mean_precip", False)
        top_n_list  = sorted_col.toList(_ERA5_N_CANDIDATES)

        # Extract dates + values (one getInfo() per item — matches notebook approach)
        candidates: list[dict] = []
        for i in range(_ERA5_N_CANDIDATES):
            try:
                img       = ee.Image(top_n_list.get(i))
                date_str  = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
                precip_m  = img.get("mean_precip").getInfo()
                if precip_m is None:
                    continue
                candidates.append({"date": date_str, "precip_mm": precip_m * 1000})
            except Exception as exc:
                log.warning("ERA5 candidate %d: %s", i, exc)

        if not candidates:
            log.warning("No ERA5 candidates found for %s — returning empty list", fire_id)
            return []

        # Group candidate days that fall within ±3 days of each other into one event,
        # pick the 5 events with the highest peak-day precipitation.
        by_precip       = sorted(candidates, key=lambda x: x["precip_mm"], reverse=True)
        used_dates: set = set()
        storm_events    = []

        for peak in by_precip:
            if peak["date"] in used_dates or len(storm_events) >= 5:
                break
            peak_dt     = datetime.strptime(peak["date"], "%Y-%m-%d")
            event_total = 0.0
            for c in candidates:
                c_dt = datetime.strptime(c["date"], "%Y-%m-%d")
                if abs((c_dt - peak_dt).days) <= 3:
                    used_dates.add(c["date"])
                    event_total += c["precip_mm"]

            # Imagery windows -------------------------------------------------
            # Pre-storm: up to 90 days before peak, but no earlier than the
            # post-fire stable date, and ending 7 days before the storm.
            pre_start_raw = (peak_dt - timedelta(days=90)).strftime("%Y-%m-%d")
            pre_start     = max(pre_start_raw, min_pre_start_str)
            pre_end       = (peak_dt - timedelta(days=7)).strftime("%Y-%m-%d")
            # Sanity: need at least 30-day pre window
            pre_start_dt  = datetime.strptime(pre_start, "%Y-%m-%d")
            pre_end_dt    = datetime.strptime(pre_end, "%Y-%m-%d")
            if (pre_end_dt - pre_start_dt).days < 30:
                log.info("Skipping storm %s — pre window too short", peak["date"])
                continue

            post_start = (peak_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            post_end   = (peak_dt + timedelta(days=45)).strftime("%Y-%m-%d")

            storm_events.append({
                "date":             peak["date"],
                "peak_precip_mm":   round(peak["precip_mm"], 1),
                "event_precip_mm":  round(event_total, 1),
                "pre_start":        pre_start,
                "pre_end":          pre_end,
                "post_start":       post_start,
                "post_end":         post_end,
            })

        # Return in chronological order for display
        storm_events.sort(key=lambda x: x["date"])

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(storm_events, f, indent=2)

        return storm_events

    # -----------------------------------------------------------------------
    # Pipeline orchestrator
    # -----------------------------------------------------------------------

    def _run(self, job_id: str, fire_id: str):
        try:
            cfg       = FIRE_CONFIGS[fire_id]
            job       = _jobs[job_id]
            fire_name = fire_id.upper()
            utm_epsg  = cfg["utm_epsg"]

            # Build an effective cfg with any window overrides stored in the job
            eff_cfg = dict(cfg)
            eff_cfg["pre_start"]  = job["pre_start"]
            eff_cfg["pre_end"]    = job["pre_end"]
            eff_cfg["post_start"] = job["post_start"]
            eff_cfg["post_end"]   = job["post_end"]

            cache_key      = job.get("cache_key", "default")
            cache_filename = (
                "retro_results.geojson" if cache_key == "default"
                else f"retro_{cache_key}.geojson"
            )

            # Step 1 — load basins & segments
            self._update(job_id, 1, "Step 1/5 — Loading WildCat sub-basin polygons and segments...", 5)
            basins = self._load_basins(cfg)
            if basins is None or len(basins) == 0:
                raise RuntimeError(
                    "No basin polygons found. Run the Wildcat analysis for this fire first "
                    "so that basins.geojson exists in the dolan_wildcat_cache."
                )
            basins_utm  = basins.to_crs(epsg=utm_epsg)
            segments_gdf = self._load_segments(cfg, utm_epsg)
            self._update(job_id, 1,
                f"Step 1/5 — Loaded {len(basins)} sub-basins, {len(segments_gdf)} WildCat segments", 12)

            # Step 2 — NHDPlus download / cache
            self._update(job_id, 2, "Step 2/5 — Downloading NHDPlus HR stream network from USGS...", 15)
            nhd_cache = _CACHE_ROOT / fire_id / "nhdplus_flowlines.gpkg"
            nhd_gdf   = self._get_nhd_flowlines(basins, nhd_cache, utm_epsg)
            self._update(job_id, 2,
                f"Step 2/5 — NHD loaded ({len(nhd_gdf)} segments)", 30)

            # Step 3 — build per-basin stream line data
            self._update(job_id, 3, "Step 3/5 — Building stream lines...", 32)
            stream_data = self._build_stream_data(basins_utm, nhd_gdf, segments_gdf, utm_epsg)
            n_with_streams = sum(1 for d in stream_data.values() if d["line"] is not None)
            n_pts = max(3, min(N_SAMPLE_POINTS_MAX, GEE_ELEMENT_BUDGET // max(1, n_with_streams)))
            self._update(job_id, 3,
                f"Step 3/5 — Stream data ready ({n_with_streams}/{len(basins)} basins have streams, "
                f"{n_pts} pts/basin → ~{n_with_streams * n_pts} total GEE rows)", 45)

            # Step 4 — GEE point sampling
            storm_label = (
                f" for storm {job.get('storm_date')}" if job.get("storm_date") else ""
            )
            self._update(job_id, 4,
                f"Step 4/5 — Sampling spectral change via GEE ({n_pts} pts/basin){storm_label}...", 47)
            gee_service.initialize(job["project_id"])
            raw_scores, point_records, imagery_source = self._gee_compute(
                eff_cfg, basins_utm, stream_data, utm_epsg, n_with_streams
            )
            self._update(job_id, 4,
                f"Step 4/5 — GEE complete (source: {imagery_source}, "
                f"{len(raw_scores)} basins, {len(point_records)} sample points)", 80)

            # Step 5 — normalise + composite
            self._update(job_id, 5, "Step 5/5 — Normalising indices and computing debris_flow_score...", 82)
            scored_geojson = self._build_output(
                basins, basins_utm, raw_scores, point_records,
                stream_data, imagery_source, fire_name, utm_epsg
            )

            out_dir  = _CACHE_ROOT / fire_id
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / cache_filename
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(scored_geojson, f, allow_nan=False)

            n_scored = sum(
                1 for feat in scored_geojson["features"]
                if feat["properties"].get("debris_flow_score") is not None
            )
            _jobs[job_id].update({
                "status": "completed", "step": 5,
                "message": (
                    f"Detection complete — {n_scored}/{len(basins)} sub-basins scored "
                    f"({n_pts} pts/basin via {imagery_source})"
                ),
                "progress": 100,
            })

        except Exception as exc:
            import traceback
            _jobs[job_id].update({
                "status": "failed", "error": str(exc),
                "message": f"Pipeline failed: {exc}",
            })
            log.error(traceback.format_exc())

    # -----------------------------------------------------------------------
    # Step 1 helpers — load data
    # -----------------------------------------------------------------------

    def _load_basins(self, cfg: Dict) -> Optional[gpd.GeoDataFrame]:
        p = Path(cfg["basins_geojson"])
        if not p.exists():
            return None
        gdf = gpd.read_file(str(p))
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        return gdf.to_crs(epsg=4326)

    def _load_segments(self, cfg: Dict, utm_epsg: int) -> gpd.GeoDataFrame:
        p = Path(cfg["segments_geojson"])
        if not p.exists():
            return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{utm_epsg}")
        gdf = gpd.read_file(str(p))
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        return gdf.to_crs(epsg=utm_epsg)

    # -----------------------------------------------------------------------
    # Step 2 — NHDPlus download
    # -----------------------------------------------------------------------

    def _get_nhd_flowlines(self, basins: gpd.GeoDataFrame,
                           cache_path: Path, utm_epsg: int) -> gpd.GeoDataFrame:
        """Return combined NHD flowlines for the fire bbox (cached after first download)."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            gdf = gpd.read_file(str(cache_path))
            return gdf.to_crs(epsg=utm_epsg)

        bounds = basins.to_crs(epsg=4326).total_bounds
        buf  = 0.01
        bbox = (bounds[0] - buf, bounds[1] - buf, bounds[2] + buf, bounds[3] + buf)
        all_features: list = []

        for layer_url in (_NHD_URL_LAYER3, _NHD_URL_LAYER4):
            offset = 0
            while True:
                params = {
                    "where": "1=1",
                    "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326", "outSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "OBJECTID,NHDPlusID,ReachCode,FType,LengthKM",
                    "f": "geojson",
                    "resultOffset": offset, "resultRecordCount": 2000,
                }
                try:
                    resp = requests.get(layer_url, params=params, timeout=120)
                    if resp.status_code != 200:
                        break
                    feats = resp.json().get("features", [])
                    if not feats:
                        break
                    all_features.extend(feats)
                    offset += len(feats)
                    if len(feats) < 2000:
                        break
                except requests.RequestException:
                    break

        if not all_features:
            return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{utm_epsg}")

        gdf = gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")
        # Drop case-insensitive duplicate columns before saving
        seen: Dict[str, str] = {}
        drop_cols = [
            col for col in gdf.columns
            if col.lower() in seen or seen.setdefault(col.lower(), col) != col
        ]
        if drop_cols:
            gdf = gdf.drop(columns=drop_cols)

        gdf.to_file(str(cache_path), driver="GPKG")
        return gdf.to_crs(epsg=utm_epsg)

    # -----------------------------------------------------------------------
    # Step 3 — build per-basin stream line data
    # -----------------------------------------------------------------------

    def _build_stream_data(
        self,
        basins_utm: gpd.GeoDataFrame,
        nhd_gdf:    gpd.GeoDataFrame,
        segments_gdf: gpd.GeoDataFrame,
        utm_epsg: int,
    ) -> Dict[Any, Dict[str, Any]]:
        """
        Returns {seg_id: {"line": shapely_geometry_utm | None, "length_m": float}}.

        "line" is the combined NHD + WildCat stream network within the basin,
        as a single (Multi)LineString in utm_epsg CRS.
        Used for random-point sampling (not buffered — keeps geometry simple).
        """
        if len(nhd_gdf) > 0 and nhd_gdf.crs.to_epsg() != utm_epsg:
            nhd_gdf = nhd_gdf.to_crs(epsg=utm_epsg)

        seg_col = None
        for candidate in ("Segment_ID", "segment_id"):
            if candidate in segments_gdf.columns:
                seg_col = candidate
                break

        result: Dict[Any, Dict[str, Any]] = {}
        for _, row in basins_utm.iterrows():
            seg_id    = row.get("Segment_ID") or row.get("segment_id")
            basin_geom = row.geometry

            line_geoms = []

            # NHD streams clipped to basin
            if len(nhd_gdf) > 0:
                try:
                    clipped = gpd.clip(nhd_gdf, basin_geom)
                    line_geoms.extend(clipped.geometry.tolist())
                except Exception:
                    pass

            # WildCat drainage segments for this basin
            if seg_col and len(segments_gdf) > 0:
                wc = segments_gdf[segments_gdf[seg_col] == seg_id]
                line_geoms.extend(wc.geometry.tolist())

            if not line_geoms:
                result[seg_id] = {"line": None, "length_m": 0.0}
                continue

            combined = unary_union(line_geoms)
            length_m = float(combined.length)
            result[seg_id] = {"line": combined, "length_m": round(length_m, 1)}

        return result

    # -----------------------------------------------------------------------
    # Step 4 — GEE computation via random stream-point sampling
    # -----------------------------------------------------------------------

    def _gee_compute(
        self,
        cfg: Dict,
        basins_utm: gpd.GeoDataFrame,
        stream_data: Dict,
        utm_epsg: int,
        n_with_streams: int = 0,
    ):
        """
        Returns (raw_scores_dict, imagery_source_str).

        Approach: sample N_SAMPLE_POINTS random points per basin along stream lines,
        convert to WGS84, and send them all as a single compact FeatureCollection to
        GEE's sampleRegions().  Points are orders of magnitude smaller than polygon
        corridor geometries — no payload-size issues.

        raw_scores_dict: {str(seg_id): {"dNDWI": float|None, "dBSI": float|None, "dNBR": float|None}}
        """
        pre_start  = cfg["pre_start"]
        pre_end    = cfg["pre_end"]
        post_start = cfg["post_start"]
        post_end   = cfg["post_end"]

        bounds_4326 = basins_utm.to_crs(epsg=4326).total_bounds
        aoi = ee.Geometry.Rectangle(bounds_4326.tolist())

        # Choose imagery source
        s2_pre_col  = self._s2_collection(aoi, pre_start,  pre_end)
        s2_post_col = self._s2_collection(aoi, post_start, post_end)
        s2_pre_n  = s2_pre_col.size().getInfo()
        s2_post_n = s2_post_col.size().getInfo()
        use_s2 = s2_pre_n >= S2_MIN_IMAGES and s2_post_n >= S2_MIN_IMAGES

        if use_s2:
            pre_img  = s2_pre_col.median()
            post_img = s2_post_col.median()
            scale = 10
            imagery_source = "sentinel2"
        else:
            pre_img  = self._l89_collection(aoi, pre_start,  pre_end).median()
            post_img = self._l89_collection(aoi, post_start, post_end).median()
            scale = 30
            imagery_source = "landsat89"

        change_stack = self._change_stack(pre_img, post_img)

        # Adaptive point count — keeps total GEE output rows ≤ GEE_ELEMENT_BUDGET.
        # e.g. 300 basins → 4500//300 = 15 pts each → 300×15 = 4500 rows (≤ cap).
        n_safe = max(1, n_with_streams)
        n_per_basin = max(3, min(N_SAMPLE_POINTS_MAX, GEE_ELEMENT_BUDGET // n_safe))
        log.info(
            "GEE sampling: %d basins with streams → %d pts/basin → ~%d total rows "
            "(budget %d)",
            n_with_streams, n_per_basin, n_with_streams * n_per_basin, GEE_ELEMENT_BUDGET,
        )

        # Build compact FeatureCollection of random sample points.
        # We also store every point's WGS84 coords locally (point_coords) keyed by
        # a sequential pt_idx string so we can reconstruct per-point positions from
        # the GEE response (GEE echoes back the pt_idx property alongside band values).
        rng = np.random.default_rng(seed=_SAMPLE_SEED)
        ee_features: List = []
        point_coords: Dict[str, tuple] = {}   # pt_idx -> (lon, lat, seg_id_str)
        pt_counter = 0

        for _, row in basins_utm.iterrows():
            seg_id = row.get("Segment_ID") or row.get("segment_id")
            data   = stream_data.get(seg_id, {})
            line   = data.get("line")
            if line is None or line.is_empty:
                continue

            pts_utm = self._sample_along_line(line, n_per_basin, rng)
            if not pts_utm:
                continue

            # Convert sampled points to WGS84 for GEE
            pts_gdf = gpd.GeoDataFrame(geometry=pts_utm, crs=f"EPSG:{utm_epsg}")
            pts_4326 = pts_gdf.to_crs(epsg=4326)

            for pt in pts_4326.geometry:
                idx = str(pt_counter)
                ee_features.append(
                    ee.Feature(
                        ee.Geometry.Point([pt.x, pt.y]),
                        {"seg_id": str(seg_id), "pt_idx": idx},
                    )
                )
                point_coords[idx] = (float(pt.x), float(pt.y), str(seg_id))
                pt_counter += 1

        if not ee_features:
            return {}, [], imagery_source

        fc = ee.FeatureCollection(ee_features)

        # sampleRegions returns one row per input point with band values added
        samples = change_stack.sampleRegions(
            collection=fc,
            scale=scale,
            geometries=False,
        )
        samples_info = samples.getInfo()

        def _safe_float(v) -> Optional[float]:
            if v is None:
                return None
            f = float(v)
            return None if (np.isnan(f) or np.isinf(f)) else f

        # Aggregate by seg_id AND build per-point records in one pass
        grouped: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: {"dNDWI": [], "dBSI": [], "dNBR": []}
        )
        point_records: List[Dict] = []

        for feat in samples_info.get("features", []):
            props = feat.get("properties", {})
            sid   = props.get("seg_id")
            pidx  = props.get("pt_idx")
            if sid is None:
                continue

            dndwi = _safe_float(props.get("dNDWI"))
            dbsi  = _safe_float(props.get("dBSI"))
            dnbr  = _safe_float(props.get("dNBR"))

            for key, val in (("dNDWI", dndwi), ("dBSI", dbsi), ("dNBR", dnbr)):
                if val is not None:
                    grouped[sid][key].append(val)

            # Reconstruct WGS84 coordinates from local lookup (GEE returns geometries=False)
            if pidx is not None and pidx in point_coords:
                lon, lat, _ = point_coords[pidx]
                point_records.append({
                    "lon": lon, "lat": lat, "seg_id": sid,
                    "dNDWI": dndwi, "dBSI": dbsi, "dNBR": dnbr,
                })

        raw_scores: Dict[str, Dict[str, Optional[float]]] = {}
        for sid, vals in grouped.items():
            raw_scores[sid] = {
                "dNDWI": float(np.mean(vals["dNDWI"])) if vals["dNDWI"] else None,
                "dBSI":  float(np.mean(vals["dBSI"]))  if vals["dBSI"]  else None,
                "dNBR":  float(np.mean(vals["dNBR"]))  if vals["dNBR"]  else None,
            }

        return raw_scores, point_records, imagery_source

    # -----------------------------------------------------------------------
    # GEE collection helpers — unchanged from original design
    # -----------------------------------------------------------------------

    @staticmethod
    def _s2_collection(aoi, start: str, end: str):
        def mask_s2_clouds(image):
            scl  = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        return (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", S2_CLOUD_PCT_THRESHOLD))
            .map(mask_s2_clouds)
            .select(["B2", "B3", "B4", "B8", "B11", "B12"])
        )

    @staticmethod
    def _l89_collection(aoi, start: str, end: str):
        bands_in  = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
        bands_out = ["B2",    "B3",    "B4",    "B8",    "B11",   "B12"]

        def mask_l89(image):
            qa = image.select("QA_PIXEL")
            return image.updateMask(
                qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
            )

        def prep(col_id):
            return (
                ee.ImageCollection(col_id)
                .filterBounds(aoi).filterDate(start, end)
                .map(mask_l89).select(bands_in, bands_out)
            )

        return prep("LANDSAT/LC08/C02/T1_L2").merge(prep("LANDSAT/LC09/C02/T1_L2"))

    @staticmethod
    def _change_stack(pre_img, post_img):
        """
        Returns a 3-band GEE image: dNDWI, dBSI, dNBR.
        Formulas match module7_stream_analysis.py safe_index exactly:
          NDWI  = (Green − NIR) / (Green + NIR)
          BSI   = (SWIR1 + Red − NIR − Blue) / (SWIR1 + Red + NIR + Blue)
          NBR   = (NIR − SWIR2) / (NIR + SWIR2)
        Change conventions (module7):
          dNDWI = post − pre
          dBSI  = post − pre
          dNBR  = pre  − post  ← standard dNBR
        All bands renamed B2..B12 (same for S2 and renamed L8/9).
        """
        def indices(img):
            b  = img.select("B2").toFloat()
            g  = img.select("B3").toFloat()
            r  = img.select("B4").toFloat()
            n  = img.select("B8").toFloat()
            s1 = img.select("B11").toFloat()
            s2 = img.select("B12").toFloat()
            ndwi = g.subtract(n).divide(g.add(n)).rename("NDWI")
            bsi  = (s1.add(r).subtract(n).subtract(b)).divide(
                    s1.add(r).add(n).add(b)).rename("BSI")
            nbr  = n.subtract(s2).divide(n.add(s2)).rename("NBR")
            return ee.Image.cat([ndwi, bsi, nbr])

        pre_idx  = indices(pre_img)
        post_idx = indices(post_img)
        dndwi = post_idx.select("NDWI").subtract(pre_idx.select("NDWI")).rename("dNDWI")
        dbsi  = post_idx.select("BSI").subtract(pre_idx.select("BSI")).rename("dBSI")
        dnbr  = pre_idx.select("NBR").subtract(post_idx.select("NBR")).rename("dNBR")
        return ee.Image.cat([dndwi, dbsi, dnbr])

    # -----------------------------------------------------------------------
    # Stream-point sampling helper
    # -----------------------------------------------------------------------

    @staticmethod
    def _sample_along_line(line_geom, n: int, rng) -> List:
        """
        Sample n random points along a Shapely (Multi)LineString.
        Uses the same rng instance passed in for reproducibility.
        Returns a list of Shapely Point objects.
        """
        total = line_geom.length
        if total <= 0 or n <= 0:
            return []
        positions = sorted(rng.uniform(0.0, total, n))
        return [line_geom.interpolate(pos) for pos in positions]

    # -----------------------------------------------------------------------
    # Step 5 — normalise + composite score + output assembly
    # -----------------------------------------------------------------------

    def _build_output(
        self,
        basins_wgs84:   gpd.GeoDataFrame,
        basins_utm:     gpd.GeoDataFrame,
        raw_scores:     Dict,
        point_records:  List[Dict],
        stream_data:    Dict,
        imagery_source: str,
        fire_name:      str,
        utm_epsg:       int,
    ) -> Dict[str, Any]:
        """
        Normalise raw index values 0–1 across all basins that returned data,
        compute composite score, and return an enriched GeoJSON FeatureCollection.
        """
        # Collect arrays for normalisation
        all_dndwi, all_dbsi, all_dnbr = [], [], []
        for vals in raw_scores.values():
            if vals.get("dNDWI") is not None: all_dndwi.append(vals["dNDWI"])
            if vals.get("dBSI")  is not None: all_dbsi.append(vals["dBSI"])
            if vals.get("dNBR")  is not None: all_dnbr.append(vals["dNBR"])

        def _norm_params(arr):
            if not arr:
                return 0.0, 1.0
            mn, mx = float(np.min(arr)), float(np.max(arr))
            return (mn, mn + 1e-9) if mx == mn else (mn, mx)

        ndwi_min, ndwi_max = _norm_params(all_dndwi)
        bsi_min,  bsi_max  = _norm_params(all_dbsi)
        nbr_min,  nbr_max  = _norm_params(all_dnbr)

        def _norm(val, vmin, vmax):
            return float(np.clip((val - vmin) / (vmax - vmin), 0.0, 1.0))

        def _clean(v):
            """Replace NaN/Inf with None so the dict is always JSON-safe."""
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v

        features = []
        for _, row in basins_wgs84.iterrows():
            seg_id  = row.get("Segment_ID") or row.get("segment_id")
            props   = {k: _clean(v) for k, v in
                       dict(row.drop("geometry", errors="ignore")).items()}
            props["sub_basin_id"] = f"{fire_name}-{seg_id}"

            sd  = stream_data.get(seg_id, {})
            props["stream_length_m"] = sd.get("length_m", 0.0)

            vals     = raw_scores.get(str(seg_id), {})
            has_data = bool(vals and vals.get("dNDWI") is not None)

            props["has_stream_data"] = has_data
            props["imagery_source"]  = imagery_source if has_data else None

            if has_data:
                r_ndwi = vals["dNDWI"]
                r_bsi  = vals["dBSI"]
                r_nbr  = vals["dNBR"]

                n_ndwi = _norm(r_ndwi, ndwi_min, ndwi_max) if r_ndwi is not None else None
                n_bsi  = _norm(r_bsi,  bsi_min,  bsi_max)  if r_bsi  is not None else None
                n_nbr  = _norm(r_nbr,  nbr_min,  nbr_max)  if r_nbr  is not None else None

                parts, weights = [], []
                if n_ndwi is not None: parts.append(0.4 * n_ndwi); weights.append(0.4)
                if n_bsi  is not None: parts.append(0.4 * n_bsi);  weights.append(0.4)
                if n_nbr  is not None: parts.append(0.2 * n_nbr);  weights.append(0.2)

                score = float(sum(parts) / sum(weights)) if parts else None

                props.update({
                    "debris_flow_score": round(score, 4) if score is not None else None,
                    "dNDWI_norm": round(n_ndwi, 4) if n_ndwi is not None else None,
                    "dBSI_norm":  round(n_bsi,  4) if n_bsi  is not None else None,
                    "dNBR_norm":  round(n_nbr,  4) if n_nbr  is not None else None,
                    "dNDWI_raw":  round(r_ndwi, 6) if r_ndwi is not None else None,
                    "dBSI_raw":   round(r_bsi,  6) if r_bsi  is not None else None,
                    "dNBR_raw":   round(r_nbr,  6) if r_nbr  is not None else None,
                })
            else:
                props.update({
                    "debris_flow_score": None,
                    "dNDWI_norm": None, "dBSI_norm": None, "dNBR_norm": None,
                    "dNDWI_raw":  None, "dBSI_raw":  None, "dNBR_raw":  None,
                })

            features.append({
                "type": "Feature",
                "geometry": mapping(row.geometry),
                "properties": props,
            })

        # Per-point GeoJSON — use the same normalization params so point colours
        # are consistent with basin polygon colours on the Flutter map.
        point_features = []
        for rec in point_records:
            r_ndwi = rec.get("dNDWI")
            r_bsi  = rec.get("dBSI")
            r_nbr  = rec.get("dNBR")

            n_ndwi = _norm(r_ndwi, ndwi_min, ndwi_max) if r_ndwi is not None else None
            n_bsi  = _norm(r_bsi,  bsi_min,  bsi_max)  if r_bsi  is not None else None
            n_nbr  = _norm(r_nbr,  nbr_min,  nbr_max)  if r_nbr  is not None else None

            parts, weights = [], []
            if n_ndwi is not None: parts.append(0.4 * n_ndwi); weights.append(0.4)
            if n_bsi  is not None: parts.append(0.4 * n_bsi);  weights.append(0.4)
            if n_nbr  is not None: parts.append(0.2 * n_nbr);  weights.append(0.2)
            pt_score = float(sum(parts) / sum(weights)) if parts else None

            point_features.append({
                "type": "Feature",
                "geometry": {
                    "type":        "Point",
                    "coordinates": [rec["lon"], rec["lat"]],
                },
                "properties": {
                    "sub_basin_id":      f"{fire_name}-{rec['seg_id']}",
                    "debris_flow_score": round(pt_score, 4) if pt_score is not None else None,
                    "dNDWI_norm":        round(n_ndwi, 4)  if n_ndwi  is not None else None,
                    "dBSI_norm":         round(n_bsi,  4)  if n_bsi   is not None else None,
                    "dNBR_norm":         round(n_nbr,  4)  if n_nbr   is not None else None,
                },
            })

        # Stream-line GeoJSON — convert UTM stream geometries to WGS84 for the map.
        # Each basin's combined (NHD + WildCat) line becomes one GeoJSON Feature.
        stream_features = []
        lines_utm   = [{"seg_id": sid, "geometry": d["line"]}
                       for sid, d in stream_data.items() if d.get("line") is not None]
        if lines_utm:
            streams_gdf = gpd.GeoDataFrame(lines_utm, crs=f"EPSG:{utm_epsg}")
            streams_wgs = streams_gdf.to_crs(epsg=4326)
            for _, srow in streams_wgs.iterrows():
                if srow.geometry is None or srow.geometry.is_empty:
                    continue
                stream_features.append({
                    "type": "Feature",
                    "geometry": mapping(srow.geometry),
                    "properties": {"seg_id": str(srow["seg_id"])},
                })

        return {
            "type": "FeatureCollection",
            "features": features,
            "sample_points": {
                "type": "FeatureCollection",
                "features": point_features,
            },
            "streams": {
                "type": "FeatureCollection",
                "features": stream_features,
            },
        }

    # -----------------------------------------------------------------------
    # Internal utility
    # -----------------------------------------------------------------------

    def _update(self, job_id: str, step: int, message: str, progress: int):
        _jobs[job_id].update({"step": step, "message": message, "progress": progress})
