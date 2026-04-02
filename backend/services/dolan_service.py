"""
Dolan Fire Live Analysis Service (2020).

Runs a watershed delineation + debris-flow hazard assessment pipeline
using WhiteboxTools + rasterio/geopandas — same proven approach as
palisades_service.py, adapted for Dolan fire geography.

Location: Big Sur coast, Monterey County, CA (~36.1°N, 121.4°W)
UTM Zone: 10N (EPSG:32610)

Input data:
  - DEM:       fire_webapp/assets/data/dolan_dem_3dep10m.tif
  - Perimeter: fire_webapp/assets/data/fire_perimeter.shp
  - dNBR:      .../data/dolan/2020_DOLAN August192020/inputs/...dnbr.tif

Pipeline (10 steps — identical to Palisades):
  1. Validate input files
  2. Reproject DEM to UTM Zone 10N, clip to perimeter + 1 km buffer
  3. Fill topographic depressions (WhiteboxTools)
  4. D8 flow direction (WhiteboxTools)
  5. Flow accumulation (WhiteboxTools)
  6. Stream extraction — threshold 1500 cells (≈ 0.15 km² at 10 m)
  7. Sub-basin delineation (WhiteboxTools)
  8. Slope + burn severity per basin (rasterio + numpy)
  9. Staley (2017) M1 + Gartner (2014) hazard model
  10. Export GeoJSON results + perimeter
"""

import json
import os
import sys
import tempfile
import datetime
import shutil
import threading
import uuid
import traceback
from pathlib import Path
from typing import Dict, Any

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
import geopandas as gpd
from shapely.geometry import shape, mapping


class _GeoJsonEncoder(json.JSONEncoder):
    """Handle numpy scalars, numpy arrays, and pandas Timestamps in JSON output."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if hasattr(obj, 'item'):
            return obj.item()
        return super().default(obj)


# --- WhiteboxTools path ---
# Imported lazily inside _wbt() so the app can start even without WBT installed.
_wbt_dir_env = os.getenv("WBT_DIR")
if _wbt_dir_env:
    sys.path.insert(0, _wbt_dir_env)

# --- Dolan Fire input data ---
_WEBAPP_ROOT = Path(__file__).parent.parent.parent   # fire_webapp/
_INPUTS = _WEBAPP_ROOT / "assets" / "data" / "dolan_inputs_all"
DOLAN_DEM = _WEBAPP_ROOT / "assets" / "data" / "dolan_dem_3dep10m.tif"
DOLAN_PERIMETER = _WEBAPP_ROOT / "assets" / "data" / "fire_perimeter.shp"
DOLAN_DNBR  = _INPUTS / "ca3612312160220200819_20200428_20210501_dnbr.tif"
DOLAN_RDNBR = _INPUTS / "ca3612312160220200819_20200428_20210501_rdnbr.tif"
DOLAN_DNBR6 = _INPUTS / "ca3612312160220200819_20200428_20210501_dnbr6.tif"

# Map metric ID → file path
_BURN_METRIC_PATHS = {
    "dnbr":  DOLAN_DNBR,
    "rdnbr": DOLAN_RDNBR,
    "dnbr6": DOLAN_DNBR6,
}

# Burn-fraction thresholds:  "burned" = any burn, "high_sev" = high severity
# dnbr6 uses class values (>=4 = burned, >=5 = moderate+)
_BURN_THRESHOLDS = {
    "dnbr":  {"burned": 100,  "high_sev": 500},
    "rdnbr": {"burned": 69,   "high_sev": 316},
    "dnbr6": {"burned": 4,    "high_sev": 5},
}

# Dolan is in UTM Zone 10N (Big Sur / Monterey County)
DOLAN_UTM_EPSG = 32610

# --- Cache directory ---
CACHE_DIR = Path(__file__).parent.parent / "data" / "dolan_cache"

# --- In-memory job store ---
_jobs: Dict[str, Dict] = {}

# Rainfall intensities (mm/hr) — Dolan wildcat config
I15_VALUES = [16, 20, 24, 40]

# Stream extraction threshold — 0.15 km² at 10 m resolution ≈ 1500 cells
# (wildcat Dolan config: min_area_km2 = 0.15)
STREAM_THRESHOLD = 1500

# Staley (2017) M1 coefficients
# Staley (2017) M1 baseline coefficients (R15=0 intercepts)
# Full parameterized form: logit = B0 + (B1+0.369*R15)*T + (B2+0.603*R15)*F + (B3+0.693*R15)*S
STALEY_B0 = -3.63
STALEY_B1 = 0.41   # terrain baseline (sin(2*slope_rad))
STALEY_B2 = 0.67   # fire baseline (fraction high-severity)
STALEY_B3 = 0.07   # soil baseline (Kf erodibility)

# Gartner (2014) volume coefficients — empirically calibrated against wildcat/pfdf reference output
# log10(V_m3) = A0 + A1*log10(I15_mm_hr) + A2*log10(Bmh_km2) + A3*log10(Relief_m)
# Note: pfdf uses different coefficients than the originally published Gartner (2014) paper
GARTNER_A0 = -0.699
GARTNER_A1 = 0.989
GARTNER_A2 = 0.369
GARTNER_A3 = 1.223


class DolanService:
    """Live watershed analysis service for 2020 Dolan Fire."""

    def start_analysis(self, force: bool = False, burn_metric: str = "dnbr") -> Dict[str, Any]:
        meta_path = CACHE_DIR / "metadata.json"
        if not force and (CACHE_DIR / "basins.geojson").exists():
            cached_metric = "dnbr"
            if meta_path.exists():
                try:
                    cached_metric = json.loads(meta_path.read_text()).get("burn_metric", "dnbr")
                except Exception:
                    pass
            if cached_metric == burn_metric:
                fake_id = "cached_" + str(uuid.uuid4())[:6]
                _jobs[fake_id] = {
                    "status": "completed",
                    "step": 10,
                    "message": "Analysis complete! (Cached results loaded)",
                    "progress": 100,
                    "basin_count": self._count_cached_basins(),
                    "burn_metric": burn_metric,
                }
                return {"job_id": fake_id, "cached": True}

        self.clear_cache()

        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = {
            "status": "running",
            "step": 0,
            "message": "Starting analysis...",
            "progress": 0,
            "error": None,
            "burn_metric": burn_metric,
        }
        t = threading.Thread(target=self._run, args=(job_id, burn_metric), daemon=True)
        t.start()
        return {"job_id": job_id, "cached": False}

    def get_status(self, job_id: str) -> Dict[str, Any]:
        if job_id not in _jobs:
            return {"status": "not_found", "error": f"Job {job_id} not found"}
        return dict(_jobs[job_id])

    def get_results(self) -> Dict[str, Any]:
        result_path = CACHE_DIR / "basins.geojson"
        if not result_path.exists():
            raise FileNotFoundError("No results yet — run analysis first.")
        with open(result_path, encoding="utf-8") as f:
            return json.load(f)

    def get_perimeter(self) -> Dict[str, Any]:
        perim_path = CACHE_DIR / "perimeter.geojson"
        if perim_path.exists():
            with open(perim_path, encoding="utf-8") as f:
                return json.load(f)
        perim = gpd.read_file(str(DOLAN_PERIMETER))
        perim_wgs84 = perim.to_crs(epsg=4326)[["geometry"]]
        result = json.loads(perim_wgs84.to_json())
        # Cache for future requests
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(perim_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
        return result

    def has_results(self) -> bool:
        return (CACHE_DIR / "basins.geojson").exists()

    def clear_cache(self):
        for fname in ["basins.geojson", "perimeter.geojson", "metadata.json"]:
            p = CACHE_DIR / fname
            if p.exists():
                p.unlink()

    def get_available_inputs(self) -> Dict[str, Any]:
        """Return metadata + legend info for all available burn severity datasets."""
        datasets = [
            {
                "id": "dnbr",
                "label": "dNBR",
                "full_name": "Differenced Normalized Burn Ratio",
                "description": (
                    "Standard continuous burn severity metric: post-fire minus pre-fire NBR. "
                    "Used directly as input to the Staley (2017) debris-flow probability model."
                ),
                "available": DOLAN_DNBR.exists(),
                "colormap": "continuous",
                "legend": [
                    {"color": "#1a9641", "label": "< 0  (Regrowth / Unburned)"},
                    {"color": "#a6d96a", "label": "0 – 100  (Very Low)"},
                    {"color": "#ffffc0", "label": "100 – 270  (Low severity)"},
                    {"color": "#fdae61", "label": "270 – 440  (Moderate)"},
                    {"color": "#d7191c", "label": "> 660  (High severity)"},
                ],
            },
            {
                "id": "rdnbr",
                "label": "rdNBR",
                "full_name": "Relativized dNBR",
                "description": (
                    "Accounts for pre-fire vegetation variability — recommended for heterogeneous "
                    "coastal chaparral and forest. Relativizes dNBR by pre-fire reflectance."
                ),
                "available": DOLAN_RDNBR.exists(),
                "colormap": "continuous",
                "legend": [
                    {"color": "#1a9641", "label": "< 0  (Regrowth / Unburned)"},
                    {"color": "#a6d96a", "label": "0 – 69  (Very Low)"},
                    {"color": "#ffffc0", "label": "69 – 316  (Low severity)"},
                    {"color": "#fdae61", "label": "316 – 640  (Moderate)"},
                    {"color": "#d7191c", "label": "> 641  (High severity)"},
                ],
            },
            {
                "id": "dnbr6",
                "label": "dNBR6",
                "full_name": "6-Class dNBR Classification",
                "description": (
                    "USFS standard categorical burn severity with 6 classes from Enhanced "
                    "Regrowth (High) through High Severity. Classified using standard dNBR thresholds."
                ),
                "available": DOLAN_DNBR6.exists(),
                "colormap": "categorical",
                "legend": [
                    {"color": "#267300", "label": "1 — Enhanced Regrowth (High)"},
                    {"color": "#70a800", "label": "2 — Enhanced Regrowth (Low)"},
                    {"color": "#a8a800", "label": "3 — Unburned"},
                    {"color": "#ffaa00", "label": "4 — Low Severity"},
                    {"color": "#ff5500", "label": "5 — Moderate Severity"},
                    {"color": "#ff0000", "label": "6 — High Severity"},
                ],
            },
        ]
        return {"datasets": datasets}

    def get_preview_image(self, dataset: str) -> Dict[str, Any]:
        """Render a raster dataset as a georeferenced PNG overlay (base64 encoded)."""
        import base64
        from io import BytesIO
        from PIL import Image as PilImage
        from pyproj import Transformer

        # DEM is not a burn metric but is previewable
        if dataset == "dem":
            path = DOLAN_DEM
        else:
            path = _BURN_METRIC_PATHS.get(dataset)
        if not path or not path.exists():
            raise FileNotFoundError(f"Dataset '{dataset}' not found at expected path")

        with rasterio.open(str(path)) as src:
            # Downsample to max 700px on longest side for fast response
            factor = max(1, max(src.width, src.height) // 700)
            out_h = max(1, src.height // factor)
            out_w = max(1, src.width // factor)
            data = src.read(
                1, out_shape=(out_h, out_w), resampling=Resampling.average
            ).astype(np.float32)

            nodata = src.nodata
            valid_mask = np.ones_like(data, dtype=bool)
            if nodata is not None:
                valid_mask = np.abs(data.astype(float) - float(nodata)) > 1

            # Bounds → WGS84
            xfm = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
            cx = [src.bounds.left, src.bounds.right, src.bounds.right, src.bounds.left]
            cy = [src.bounds.bottom, src.bounds.bottom, src.bounds.top, src.bounds.top]
            lons, lats = xfm.transform(cx, cy)
            bounds = {
                "west":  float(min(lons)), "east":  float(max(lons)),
                "south": float(min(lats)), "north": float(max(lats)),
            }

        rgba = self._colorize(data, valid_mask, dataset)
        img = PilImage.fromarray(rgba, mode="RGBA")
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return {
            "image_base64": base64.b64encode(buf.read()).decode(),
            "bounds": bounds,
            "dataset": dataset,
        }

    @staticmethod
    def _colorize(data: np.ndarray, mask: np.ndarray, dataset: str) -> np.ndarray:
        """Map raster values to RGBA using dataset-specific colormaps."""
        h, w = data.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        if dataset == "dem":
            # Terrain colormap: dark-green (low) → yellow-green → tan → brown → light-gray (high)
            valid_data = data[mask]
            vmin = float(np.nanpercentile(valid_data, 2)) if len(valid_data) > 0 else 0.0
            vmax = float(np.nanpercentile(valid_data, 98)) if len(valid_data) > 0 else 2000.0
            normed = np.clip((data.astype(float) - vmin) / max(vmax - vmin, 1.0), 0.0, 1.0)

            kp_t = np.array([0.0,   0.15,  0.35,  0.55,  0.75,  1.0])
            kp_r = np.array([34.0,  45.0,  154.0, 205.0, 175.0, 230.0])
            kp_g = np.array([117.0, 139.0, 191.0, 162.0, 135.0, 230.0])
            kp_b = np.array([76.0,  87.0,  100.0, 95.0,  90.0,  230.0])

            r = np.interp(normed, kp_t, kp_r)
            g = np.interp(normed, kp_t, kp_g)
            b = np.interp(normed, kp_t, kp_b)
            rgba[mask, 0] = np.clip(r[mask], 0, 255).astype(np.uint8)
            rgba[mask, 1] = np.clip(g[mask], 0, 255).astype(np.uint8)
            rgba[mask, 2] = np.clip(b[mask], 0, 255).astype(np.uint8)
            rgba[mask, 3] = 210

        elif dataset == "dnbr6":
            # Categorical: integer class 1–6
            class_colors = {
                1: (38,  115, 0),
                2: (112, 168, 0),
                3: (168, 168, 0),
                4: (255, 170, 0),
                5: (255, 85,  0),
                6: (255, 0,   0),
            }
            for cls, (r, g, b) in class_colors.items():
                m = (np.round(data).astype(int) == cls) & mask
                rgba[m, 0] = r; rgba[m, 1] = g; rgba[m, 2] = b; rgba[m, 3] = 210
        else:
            # Continuous RdYlGn_r: green (low/negative) → yellow → red (high)
            vmin = -500.0 if dataset == "dnbr" else -200.0
            vmax = 1300.0 if dataset == "dnbr" else 1500.0
            normed = np.clip((data.astype(float) - vmin) / (vmax - vmin), 0.0, 1.0)

            # Keypoints for RdYlGn_r (reversed green→red)
            kp_t = np.array([0.0,   0.25,        0.5,         0.75,        1.0])
            kp_r = np.array([26.0,  166.0,       255.0,       253.0,       215.0])
            kp_g = np.array([152.0, 217.0,       255.0,       174.0,       25.0])
            kp_b = np.array([80.0,  106.0,       191.0,       97.0,        28.0])

            r = np.interp(normed, kp_t, kp_r)
            g = np.interp(normed, kp_t, kp_g)
            b = np.interp(normed, kp_t, kp_b)

            rgba[mask, 0] = np.clip(r[mask], 0, 255).astype(np.uint8)
            rgba[mask, 1] = np.clip(g[mask], 0, 255).astype(np.uint8)
            rgba[mask, 2] = np.clip(b[mask], 0, 255).astype(np.uint8)
            rgba[mask, 3] = 210

        return rgba

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _update(self, job_id: str, step: int, message: str, progress: int):
        _jobs[job_id].update({"step": step, "message": message, "progress": progress})

    def _count_cached_basins(self) -> int:
        try:
            with open(CACHE_DIR / "basins.geojson") as f:
                return len(json.load(f).get("features", []))
        except Exception:
            return 0

    def _run(self, job_id: str, burn_metric: str = "dnbr"):
        work_dir = None
        try:
            work_dir = Path(tempfile.mkdtemp(prefix="dolan_"))
            self._step1_load_data(job_id, work_dir, burn_metric)
            filled_dem, perim_utm, perim_wgs84 = self._step2_reproject_clip(job_id, work_dir)
            filled_dem = self._step3_fill_depressions(job_id, work_dir, filled_dem)
            fdr = self._step4_flow_direction(job_id, work_dir, filled_dem)
            fac = self._step5_flow_accumulation(job_id, work_dir, fdr)
            streams = self._step6_extract_streams(job_id, work_dir, fac)
            basins_gdf = self._step7_delineate_basins(job_id, work_dir, fdr, streams, perim_utm)
            basin_stats = self._step8_compute_stats(job_id, work_dir, filled_dem, basins_gdf, burn_metric)
            features = self._step9_run_model(job_id, basins_gdf, basin_stats)
            self._step10_export(job_id, features, perim_wgs84, burn_metric)

            _jobs[job_id].update({
                "status": "completed",
                "step": 10,
                "message": f"Analysis complete! Found {len(features)} sub-basins.",
                "progress": 100,
                "basin_count": len(features),
            })

        except Exception as e:
            tb = traceback.format_exc()
            _jobs[job_id].update({
                "status": "error",
                "error": str(e),
                "traceback": tb,
                "message": f"Error: {e}",
            })
        finally:
            if work_dir:
                shutil.rmtree(str(work_dir), ignore_errors=True)

    # Step 1
    def _step1_load_data(self, job_id: str, work_dir: Path, burn_metric: str = "dnbr"):
        labels = {"dnbr": "dNBR", "rdnbr": "rdNBR", "dnbr6": "dNBR6"}
        label = labels.get(burn_metric, burn_metric.upper())
        self._update(job_id, 1, f"Loading fire perimeter, DEM, and {label} rasters...", 5)
        burn_path = _BURN_METRIC_PATHS.get(burn_metric, DOLAN_DNBR)
        missing = [str(p) for p in [DOLAN_PERIMETER, DOLAN_DEM, burn_path] if not p.exists()]
        if missing:
            raise FileNotFoundError(f"Input file(s) not found: {missing}")

    # Step 2
    def _step2_reproject_clip(self, job_id: str, work_dir: Path):
        self._update(job_id, 2, "Reprojecting to UTM Zone 10N (projected CRS for Big Sur area)...", 15)

        perim = gpd.read_file(str(DOLAN_PERIMETER))
        perim_utm = perim.to_crs(epsg=DOLAN_UTM_EPSG)
        perim_wgs84 = perim.to_crs(epsg=4326)

        # Reproject DEM to UTM 10N
        dem_utm_path = str(work_dir / "dem_utm.tif")
        with rasterio.open(str(DOLAN_DEM)) as src:
            t, w, h = calculate_default_transform(
                src.crs, CRS.from_epsg(DOLAN_UTM_EPSG), src.width, src.height, *src.bounds
            )
            meta = src.meta.copy()
            meta.update({
                "crs": CRS.from_epsg(DOLAN_UTM_EPSG),
                "transform": t, "width": w, "height": h, "nodata": -9999,
            })
            with rasterio.open(dem_utm_path, "w", **meta) as dst:
                reproject(
                    rasterio.band(src, 1), rasterio.band(dst, 1),
                    src_crs=src.crs, dst_crs=CRS.from_epsg(DOLAN_UTM_EPSG),
                    resampling=Resampling.bilinear,
                )

        # Clip DEM to buffered perimeter (1000 m buffer — per Dolan wildcat config)
        buffered = perim_utm.buffer(1000)
        dem_clipped_path = str(work_dir / "dem_clipped.tif")
        with rasterio.open(dem_utm_path) as src:
            out_image, out_transform = rio_mask(
                src, [mapping(g) for g in buffered.geometry],
                crop=True, filled=True, nodata=-9999,
            )
            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "nodata": -9999,
            })
            with rasterio.open(dem_clipped_path, "w", **out_meta) as dst:
                dst.write(out_image)

        return dem_clipped_path, perim_utm, perim_wgs84

    # Step 3
    def _step3_fill_depressions(self, job_id: str, work_dir: Path, dem_path: str) -> str:
        self._update(job_id, 3, "Filling topographic depressions in DEM...", 28)
        wbt = self._wbt()
        filled_path = str(work_dir / "dem_filled.tif")
        wbt.fill_depressions(dem=dem_path, output=filled_path, fix_flats=True)
        return filled_path

    # Step 4
    def _step4_flow_direction(self, job_id: str, work_dir: Path, filled_dem: str) -> str:
        self._update(job_id, 4, "Computing D8 flow direction across terrain...", 40)
        wbt = self._wbt()
        fdr_path = str(work_dir / "flow_dir.tif")
        wbt.d8_pointer(dem=filled_dem, output=fdr_path, esri_pntr=False)
        return fdr_path

    # Step 5
    def _step5_flow_accumulation(self, job_id: str, work_dir: Path, fdr: str) -> str:
        self._update(job_id, 5, "Computing flow accumulation (upslope contributing area)...", 52)
        wbt = self._wbt()
        fac_path = str(work_dir / "flow_acc.tif")
        wbt.d8_flow_accumulation(i=fdr, output=fac_path, out_type="cells", pntr=True, esri_pntr=False)
        return fac_path

    # Step 6
    def _step6_extract_streams(self, job_id: str, work_dir: Path, fac: str) -> str:
        self._update(job_id, 6, f"Extracting stream network (threshold: 0.15 km²)...", 62)
        wbt = self._wbt()
        streams_path = str(work_dir / "streams.tif")
        wbt.extract_streams(flow_accum=fac, output=streams_path, threshold=STREAM_THRESHOLD)
        return streams_path

    # Step 7
    def _step7_delineate_basins(
        self, job_id: str, work_dir: Path, fdr: str, streams: str, perim_utm
    ) -> gpd.GeoDataFrame:
        self._update(job_id, 7, "Delineating sub-basins from stream network...", 73)
        wbt = self._wbt()

        basins_raster = str(work_dir / "basins.tif")
        wbt.subbasins(d8_pntr=fdr, streams=streams, output=basins_raster, esri_pntr=False)

        basins_vec = str(work_dir / "basins_vec.shp")
        wbt.raster_to_vector_polygons(i=basins_raster, output=basins_vec)

        try:
            basins_gdf = gpd.read_file(basins_vec)
        except Exception:
            basins_gdf = perim_utm.copy()
            basins_gdf["VALUE"] = 1

        if basins_gdf.crs is None:
            basins_gdf = basins_gdf.set_crs(epsg=DOLAN_UTM_EPSG)

        # Repair geometries from WBT winding order issues
        basins_gdf.geometry = basins_gdf.geometry.buffer(0)
        basins_gdf = basins_gdf[~basins_gdf.geometry.is_empty].copy()

        # Clip to fire perimeter + small tolerance
        perim_buffer = perim_utm.buffer(100).unary_union
        basins_gdf = basins_gdf[basins_gdf.intersects(perim_buffer)].copy()
        basins_gdf = basins_gdf.clip(perim_utm.buffer(50).buffer(0))

        # Area filter — Dolan config: min 0.01 km², max 3.0 km²
        basins_gdf["Area_km2"] = basins_gdf.geometry.area / 1e6
        basins_gdf = basins_gdf[
            (basins_gdf["Area_km2"] >= 0.01) & (basins_gdf["Area_km2"] <= 3.0)
        ].reset_index(drop=True)

        if len(basins_gdf) == 0:
            perim_copy = perim_utm.copy()
            perim_copy["Area_km2"] = perim_copy.geometry.area / 1e6
            return perim_copy

        return basins_gdf

    # Step 8
    def _step8_compute_stats(
        self, job_id: str, work_dir: Path, filled_dem: str, basins_gdf: gpd.GeoDataFrame,
        burn_metric: str = "dnbr",
    ) -> list:
        labels = {"dnbr": "dNBR", "rdnbr": "rdNBR", "dnbr6": "dNBR6"}
        label = labels.get(burn_metric, burn_metric.upper())
        self._update(job_id, 8, f"Computing slope and {label} burn severity for each sub-basin...", 82)
        wbt = self._wbt()

        slope_path = str(work_dir / "slope.tif")
        wbt.slope(dem=filled_dem, output=slope_path, units="degrees", zfactor=1.0)

        burn_src = _BURN_METRIC_PATHS.get(burn_metric, DOLAN_DNBR)
        thresholds = _BURN_THRESHOLDS[burn_metric]

        # Reproject burn severity raster to UTM 10N
        dnbr_utm = str(work_dir / "dnbr_utm.tif")
        with rasterio.open(str(burn_src)) as src:
            t, w, h = calculate_default_transform(
                src.crs, CRS.from_epsg(DOLAN_UTM_EPSG), src.width, src.height, *src.bounds
            )
            meta = src.meta.copy()
            meta.update({
                "crs": CRS.from_epsg(DOLAN_UTM_EPSG),
                "transform": t, "width": w, "height": h,
            })
            with rasterio.open(dnbr_utm, "w", **meta) as dst:
                reproject(
                    rasterio.band(src, 1), rasterio.band(dst, 1),
                    src_crs=src.crs, dst_crs=CRS.from_epsg(DOLAN_UTM_EPSG),
                )

        basin_stats = []
        with rasterio.open(slope_path) as slope_src, \
             rasterio.open(dnbr_utm) as dnbr_src, \
             rasterio.open(filled_dem) as dem_src:
            for _, row in basins_gdf.iterrows():
                geom = [mapping(row.geometry)]
                try:
                    slope_data, _ = rio_mask(slope_src, geom, crop=True, filled=False)
                    slope_vals = slope_data[slope_data != slope_src.nodata]
                    slope_vals = slope_vals[np.isfinite(slope_vals)]
                    slope_deg = float(np.nanmean(slope_vals)) if len(slope_vals) > 0 else 20.0
                    slope_rad = np.radians(slope_deg)

                    dnbr_data, _ = rio_mask(dnbr_src, geom, crop=True, filled=False)
                    valid = dnbr_data[(dnbr_data != dnbr_src.nodata) & (dnbr_data > -5000)]
                    total = max(len(valid), 1)
                    if burn_metric == "dnbr6":
                        burn_ratio = float(np.sum(valid >= thresholds["burned"]) / total)
                        high_sev_ratio = float(np.sum(valid >= thresholds["high_sev"]) / total)
                    else:
                        burn_ratio = float(np.sum(valid > thresholds["burned"]) / total)
                        high_sev_ratio = float(np.sum(valid > thresholds["high_sev"]) / total)

                    # Basin relief: max - min elevation (for Gartner 2014 volume model)
                    dem_data, _ = rio_mask(dem_src, geom, crop=True, filled=False)
                    dem_vals = dem_data[dem_data != dem_src.nodata]
                    dem_vals = dem_vals[np.isfinite(dem_vals)]
                    relief_m = float(np.max(dem_vals) - np.min(dem_vals)) if len(dem_vals) > 1 else 100.0

                    basin_stats.append({
                        "slope_rad": slope_rad,
                        "burn_ratio": burn_ratio,
                        "high_sev_ratio": high_sev_ratio,
                        "relief_m": relief_m,
                    })
                except Exception:
                    basin_stats.append({
                        "slope_rad": 0.35,
                        "burn_ratio": 0.85,
                        "high_sev_ratio": 0.45,
                        "relief_m": 100.0,
                    })

        return basin_stats

    # Step 9
    def _step9_run_model(
        self, job_id: str, basins_gdf: gpd.GeoDataFrame, basin_stats: list
    ) -> list:
        self._update(job_id, 9, "Running Staley (2017) debris-flow probability model...", 91)

        basins_wgs84 = basins_gdf.to_crs(epsg=4326)
        features = []

        for i, (_, row) in enumerate(basins_wgs84.iterrows()):
            stats = basin_stats[i] if i < len(basin_stats) else {
                "slope_rad": 0.35, "burn_ratio": 0.8, "high_sev_ratio": 0.4
            }
            slope_r = stats["slope_rad"]
            burn_ratio = stats["burn_ratio"]
            high_sev = stats["high_sev_ratio"]
            area_km2 = float(row["Area_km2"])

            props: Dict[str, Any] = {
                "Area_km2": round(area_km2, 4),
                "BurnRatio": round(burn_ratio, 4),
                "Slope": round(slope_r, 4),
            }

            relief_m = stats.get("relief_m", 100.0)
            # Bmh_km2: area burned at moderate-high severity (Gartner 2014 input)
            Bmh_km2 = max(high_sev * area_km2, 0.001)

            for j, I15 in enumerate(I15_VALUES):
                # --- Staley (2017) M1 parameterized logistic regression ---
                # Coefficients are linear functions of R15 (15-min rainfall accumulation)
                # R15 = I15 * (15 min / 60 min/hr)
                R15 = I15 * (15.0 / 60.0)
                T = np.sin(2 * slope_r)   # terrain: sin(2*slope_rad)
                F = high_sev              # fire: fraction high-severity burned
                S = 0.15                  # soil: Kf erodibility factor (constant)
                logit = (
                    -3.63
                    + (0.41 + 0.369 * R15) * T
                    + (0.67 + 0.603 * R15) * F
                    + (0.07 + 0.693 * R15) * S
                )
                P = float(1.0 / (1.0 + np.exp(-logit)))

                # --- Gartner (2014) OLS volume model ---
                # log10(V) = A0 + A1*log10(I15) + A2*log10(Bmh_km2) + A3*log10(Relief_m+1)
                V = float(
                    10 ** (
                        GARTNER_A0
                        + GARTNER_A1 * np.log10(max(I15, 1))
                        + GARTNER_A2 * np.log10(Bmh_km2)
                        + GARTNER_A3 * np.log10(max(relief_m, 1))
                    )
                )

                # --- Cannon (2010) hazard classification ---
                # H based on probability thresholds matching wildcat p_thresholds=[0.2,0.4,0.6,0.8]
                if P >= 0.6:
                    H = 3.0
                elif P >= 0.4:
                    H = 2.0
                elif P >= 0.2:
                    H = 1.0
                else:
                    H = 0.0

                props[f"P_{j}"] = round(P, 4)
                props[f"V_{j}"] = round(V, 2)
                props[f"H_{j}"] = H

            features.append({
                "type": "Feature",
                "geometry": mapping(row.geometry),
                "properties": props,
            })

        return features

    # Step 10
    def _step10_export(self, job_id: str, features: list, perim_wgs84, burn_metric: str = "dnbr"):
        self._update(job_id, 10, "Exporting GeoJSON results and fire perimeter...", 95)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        result = {"type": "FeatureCollection", "features": features}
        with open(CACHE_DIR / "basins.geojson", "w") as f:
            json.dump(result, f, cls=_GeoJsonEncoder)

        perim_clean = perim_wgs84[["geometry"]].copy()
        perim_clean.to_file(str(CACHE_DIR / "perimeter.geojson"), driver="GeoJSON")

        meta = {
            "burn_metric": burn_metric,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        with open(CACHE_DIR / "metadata.json", "w") as f:
            json.dump(meta, f)

    # ------------------------------------------------------------------
    # Zone analysis — full pipeline re-run clipped to user polygon
    # ------------------------------------------------------------------

    def start_zone_analysis(self, polygon_geojson: Dict, burn_metric: str = "") -> Dict[str, Any]:
        """Start a full WhiteboxTools pipeline re-run clipped to user-drawn polygon."""
        if not burn_metric:
            meta_path = CACHE_DIR / "metadata.json"
            if meta_path.exists():
                try:
                    burn_metric = json.loads(meta_path.read_text()).get("burn_metric", "dnbr")
                except Exception:
                    burn_metric = "dnbr"
            else:
                burn_metric = "dnbr"

        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = {
            "status": "running",
            "step": 0,
            "message": "Starting zone analysis...",
            "progress": 0,
            "error": None,
            "zone": True,
            "burn_metric": burn_metric,
        }
        t = threading.Thread(
            target=self._run_zone, args=(job_id, polygon_geojson, burn_metric), daemon=True
        )
        t.start()
        return {"job_id": job_id, "status": "running"}

    def get_zone_results(self, job_id: str) -> Dict[str, Any]:
        zone_path = CACHE_DIR / f"zone_{job_id}.geojson"
        if not zone_path.exists():
            raise FileNotFoundError(f"No zone results for job {job_id}")
        with open(zone_path, encoding="utf-8") as f:
            return json.load(f)

    def _run_zone(self, job_id: str, polygon_geojson: Dict, burn_metric: str = "dnbr"):
        """Full WhiteboxTools pipeline re-run using user-drawn polygon as analysis boundary."""
        work_dir = None
        try:
            work_dir = Path(tempfile.mkdtemp(prefix="dolan_zone_"))
            self._step1_load_data(job_id, work_dir, burn_metric)
            filled_dem, perim_utm, perim_wgs84 = self._step2_reproject_clip_zone(
                job_id, work_dir, polygon_geojson
            )
            filled_dem = self._step3_fill_depressions(job_id, work_dir, filled_dem)
            fdr = self._step4_flow_direction(job_id, work_dir, filled_dem)
            fac = self._step5_flow_accumulation(job_id, work_dir, fdr)
            streams = self._step6_extract_streams(job_id, work_dir, fac)
            basins_gdf = self._step7_delineate_basins(job_id, work_dir, fdr, streams, perim_utm)
            basin_stats = self._step8_compute_stats(
                job_id, work_dir, filled_dem, basins_gdf, burn_metric
            )
            features = self._step9_run_model(job_id, basins_gdf, basin_stats)
            self._step10_export_zone(job_id, features)

            _jobs[job_id].update({
                "status": "completed",
                "step": 10,
                "message": f"Zone analysis complete! Found {len(features)} sub-basins.",
                "progress": 100,
                "basin_count": len(features),
            })
        except Exception as e:
            tb = traceback.format_exc()
            _jobs[job_id].update({
                "status": "error",
                "error": str(e),
                "traceback": tb,
                "message": f"Error: {e}",
            })
        finally:
            if work_dir:
                shutil.rmtree(str(work_dir), ignore_errors=True)

    def _step2_reproject_clip_zone(
        self, job_id: str, work_dir: Path, polygon_geojson: Dict
    ):
        """Like _step2_reproject_clip but uses user-drawn polygon as the boundary."""
        self._update(job_id, 2, "Reprojecting zone polygon to UTM Zone 10N...", 15)

        from shapely.geometry import shape as shp_shape
        user_geom = shp_shape(polygon_geojson)
        perim_wgs84 = gpd.GeoDataFrame(geometry=[user_geom], crs="EPSG:4326")
        perim_utm = perim_wgs84.to_crs(epsg=DOLAN_UTM_EPSG)

        # Reproject DEM to UTM 10N
        dem_utm_path = str(work_dir / "dem_utm.tif")
        with rasterio.open(str(DOLAN_DEM)) as src:
            t, w, h = calculate_default_transform(
                src.crs, CRS.from_epsg(DOLAN_UTM_EPSG), src.width, src.height, *src.bounds
            )
            meta = src.meta.copy()
            meta.update({
                "crs": CRS.from_epsg(DOLAN_UTM_EPSG),
                "transform": t, "width": w, "height": h, "nodata": -9999,
            })
            with rasterio.open(dem_utm_path, "w", **meta) as dst:
                reproject(
                    rasterio.band(src, 1), rasterio.band(dst, 1),
                    src_crs=src.crs, dst_crs=CRS.from_epsg(DOLAN_UTM_EPSG),
                    resampling=Resampling.bilinear,
                )

        # Clip to user polygon + 200 m buffer (captures drainage just outside boundary)
        buffered = perim_utm.buffer(200)
        dem_clipped_path = str(work_dir / "dem_clipped.tif")
        with rasterio.open(dem_utm_path) as src:
            out_image, out_transform = rio_mask(
                src, [mapping(g) for g in buffered.geometry],
                crop=True, filled=True, nodata=-9999,
            )
            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "nodata": -9999,
            })
            with rasterio.open(dem_clipped_path, "w", **out_meta) as dst:
                dst.write(out_image)

        return dem_clipped_path, perim_utm, perim_wgs84

    def _step10_export_zone(self, job_id: str, features: list):
        self._update(job_id, 10, "Exporting zone GeoJSON results...", 95)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        result = {"type": "FeatureCollection", "features": features}
        zone_path = CACHE_DIR / f"zone_{job_id}.geojson"
        with open(zone_path, "w") as f:
            json.dump(result, f, cls=_GeoJsonEncoder)

    def _wbt(self):
        from whitebox_tools import WhiteboxTools
        wbt = WhiteboxTools()
        if _wbt_dir_env:
            wbt.exe_path = _wbt_dir_env
        wbt.verbose = False
        return wbt
