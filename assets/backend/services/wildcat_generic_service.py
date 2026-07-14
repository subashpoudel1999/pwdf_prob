"""
Wildcat Generic Service.

Runs the Wildcat pipeline (preprocess → assess) for ANY fire whose inputs
directory contains a perimeter SHP, a DEM .tif, and a dNBR .tif.

Input files are auto-detected by keyword matching — works for both
Tier-1 fires (Dolan, Franklin) with their custom naming and for
CSV fires whose perimeters were copied as {slug}_perimeter.shp and
whose DEM/dNBR will be downloaded via GEE as {slug}_dem.tif / {slug}_dnbr.tif.

Results are cached at:
  wildcat/{fire_id}/assessment/basins.geojson   ← Flutter reads this
  wildcat/{fire_id}/assessment/segments.geojson
  wildcat/{fire_id}/assessment/outlets.geojson
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)

_WEBAPP_ROOT  = Path(__file__).parent.parent.parent   # fire_webapp2/
_WILDCAT_DIR  = _WEBAPP_ROOT / "wildcat"

_jobs: Dict[str, Dict] = {}
_active_by_fire: Dict[str, str] = {}   # fire_id -> job_id, while a run is in flight


# ── Public interface ──────────────────────────────────────────────────────────

def start_analysis(
    fire_id: str,
    settings,            # WildcatSettings (imported at call site to avoid circular)
    force: bool = False,
) -> Dict[str, Any]:
    """Start a Wildcat analysis for any fire.  Returns {job_id, cached}."""
    inp_dir  = _WILDCAT_DIR / fire_id / "inputs"
    cache    = _WILDCAT_DIR / fire_id / "assessment" / "basins.geojson"

    if not inp_dir.exists():
        raise FileNotFoundError(
            f"No inputs directory for fire '{fire_id}' — "
            f"expected: {inp_dir}"
        )

    files = _find_inputs(inp_dir)
    missing = [k for k, v in files.items() if v is None]
    if missing:
        raise FileNotFoundError(
            f"Fire '{fire_id}' is missing: {', '.join(missing)}. "
            "Run data prep (GEE download) first."
        )

    if not force and cache.exists():
        fake_id = "wc_cached_" + str(uuid.uuid4())[:6]
        _jobs[fake_id] = {
            "status": "completed", "step": 3, "progress": 100,
            "message": f"Wildcat analysis complete (cached results loaded).",
            "basin_count": _count_basins(cache),
        }
        return {"job_id": fake_id, "cached": True}

    # A run is already in flight for this fire (e.g. a double-click or retry) —
    # hand back the existing job instead of starting a second one, since two
    # concurrent threads writing the same assessment/ folder corrupts the output.
    existing_job_id = _active_by_fire.get(fire_id)
    if existing_job_id is not None:
        existing = _jobs.get(existing_job_id)
        if existing is not None and existing.get("status") == "running":
            return {"job_id": existing_job_id, "cached": False}
        _active_by_fire.pop(fire_id, None)

    # Clear old cache
    _clear_assessment(fire_id)

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status": "running", "step": 0, "progress": 0,
        "message": "Starting Wildcat pipeline...", "error": None,
    }
    _active_by_fire[fire_id] = job_id
    t = threading.Thread(
        target=_run, args=(job_id, fire_id, files, settings), daemon=True
    )
    t.start()
    return {"job_id": job_id, "cached": False}


def get_status(job_id: str) -> Dict[str, Any]:
    if job_id not in _jobs:
        return {"status": "not_found", "error": f"Job {job_id} not found"}
    return dict(_jobs[job_id])


def get_perimeter(fire_id: str) -> Dict[str, Any]:
    """Return just this fire's own perimeter as a GeoJSON FeatureCollection
    (WGS84), for AOIs that may fall outside the MHRI fusion coverage area
    and so never get a "perimeter" key from the MHRI endpoint."""
    import geopandas as gpd

    inp_dir = _WILDCAT_DIR / fire_id / "inputs"
    if not inp_dir.exists():
        raise FileNotFoundError(f"No inputs directory for fire '{fire_id}'.")
    files = _find_inputs(inp_dir)
    shp = files.get("perimeter")
    if shp is None:
        raise FileNotFoundError(f"No perimeter shapefile found for '{fire_id}'.")

    gdf = gpd.read_file(str(shp))
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=32610)
    gdf_4326 = gdf.to_crs(epsg=4326)
    return json.loads(gdf_4326.to_json())


def get_results(fire_id: str) -> Dict[str, Any]:
    path = _WILDCAT_DIR / fire_id / "assessment" / "basins.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"No results for fire '{fire_id}'. Run analysis first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_perimeters_cache = None


def invalidate_perimeter_cache() -> None:
    """Clear the in-memory perimeters cache so a freshly uploaded AOI shows
    up immediately on /wildcat/perimeters without a server restart."""
    global _perimeters_cache
    _perimeters_cache = None


def get_all_perimeters_geojson() -> dict:
    """Build perimeters GeoJSON from per-fire SHP inputs (25 m simplified, WGS84).

    Reads the same full-resolution SHP files used by the pipeline, applies a
    25 m Douglas-Peucker simplification in the native projected CRS (metres),
    then reprojects to EPSG:4326.  Result is cached in memory for the lifetime
    of the server process (~2.6 MB, vs 218-pt angular shapes from the old
    fires_perimeters.geojson).
    """
    global _perimeters_cache
    if _perimeters_cache is not None:
        return _perimeters_cache

    import geopandas as gpd

    catalog = {e["id"]: e for e in get_fire_catalog()}
    features = []

    if _WILDCAT_DIR.exists():
        for fire_dir in sorted(_WILDCAT_DIR.iterdir()):
            if not fire_dir.is_dir():
                continue
            inp = fire_dir / "inputs"
            if not inp.exists():
                continue
            files = _find_inputs(inp)
            shp = files.get("perimeter")
            if shp is None:
                continue

            fire_id = fire_dir.name
            try:
                gdf = gpd.read_file(str(shp))
                if gdf.crs is None:
                    gdf = gdf.set_crs(epsg=32610)  # fallback: UTM zone 10N
                # Simplify in native projected CRS (metres) for metric accuracy
                gdf["geometry"] = gdf.geometry.simplify(25, preserve_topology=True)
                gdf_4326 = gdf.to_crs(epsg=4326)
                entry = catalog.get(fire_id, {})
                for _, row in gdf_4326.iterrows():
                    if row.geometry is None:
                        continue
                    features.append({
                        "type": "Feature",
                        "geometry": row.geometry.__geo_interface__,
                        "properties": {
                            "id": fire_id,
                            "status": entry.get("status", "needs_download"),
                            "name": entry.get("name", fire_id),
                        },
                    })
            except Exception as e:
                log.warning("Perimeter read failed for %s: %s", fire_id, e)

    _perimeters_cache = {"type": "FeatureCollection", "features": features}
    log.info("Built perimeters from SHPs: %d features across %d fires",
             len(features), len(catalog))
    return _perimeters_cache


_history_cache = None  # cached, reprojected copy of fires_perimeters.geojson


def historical_burn_overlap(aoi_gdf) -> Dict[str, Any]:
    """How much of `aoi_gdf` overlaps a fire perimeter in our 2017-2024
    California catalog (`wildcat/fires_perimeters.geojson`, 292 fires).

    Exists because an uploaded "fire" perimeter is never validated against
    actual fire history — a Census place boundary or any other polygon goes
    through the same pipeline without error. This doesn't block anything;
    it gives the caller enough to show a non-fatal warning when an AOI has
    no record of having burned.

    Returns {"burned_pct": float, "matches": [{"name", "year", "overlap_pct"}, ...]}
    sorted by overlap_pct descending. Returns 0%/[] (not an error) if the
    reference catalog is unavailable.
    """
    global _history_cache
    import geopandas as gpd
    from shapely.ops import unary_union

    if _history_cache is None:
        catalog_path = _WILDCAT_DIR / "fires_perimeters.geojson"
        if not catalog_path.exists():
            log.warning("fires_perimeters.geojson not found — skipping burn-history check")
            return {"burned_pct": 0.0, "matches": []}
        _history_cache = gpd.read_file(str(catalog_path)).to_crs(epsg=5070)

    aoi = aoi_gdf.to_crs(epsg=5070)
    aoi_union = aoi.geometry.union_all()
    if aoi_union.area <= 0:
        return {"burned_pct": 0.0, "matches": []}

    hits = _history_cache[_history_cache.geometry.intersects(aoi_union)]
    if hits.empty:
        return {"burned_pct": 0.0, "matches": []}

    overlap_geom = aoi_union.intersection(unary_union(hits.geometry.tolist()))
    burned_pct = float(overlap_geom.area / aoi_union.area * 100)

    matches = []
    for _, row in hits.iterrows():
        overlap_pct = float(aoi_union.intersection(row.geometry).area / aoi_union.area * 100)
        if overlap_pct > 0.1:
            year = row["year"]
            year_is_nan = isinstance(year, float) and math.isnan(year)
            matches.append({
                "name": row["name"],
                "year": int(year) if year is not None and not year_is_nan else None,
                "overlap_pct": round(overlap_pct, 1),
            })
    matches.sort(key=lambda m: -m["overlap_pct"])

    return {"burned_pct": round(burned_pct, 1), "matches": matches}


def get_fire_catalog() -> list:
    """
    Return all fires whose inputs/ directory exists under wildcat/.
    Loads from fires_catalog.json if available (pre-computed by notebook 8),
    otherwise falls back to reading SHP files dynamically.
    """
    catalog_json = _WILDCAT_DIR / "fires_catalog.json"
    if catalog_json.exists():
        try:
            with open(catalog_json, encoding="utf-8") as f:
                catalog = json.load(f)
            # Refresh live fields — rasters and assessment may have appeared since JSON was written
            for entry in catalog:
                fire_id    = entry["id"]
                inp        = _WILDCAT_DIR / fire_id / "inputs"
                assessment = _WILDCAT_DIR / fire_id / "assessment" / "basins.geojson"
                entry["has_results"] = assessment.exists()
                entry["has_dem"]     = _has_dem(inp)
                entry["has_dnbr"]    = _has_dnbr(inp)
                # Recompute status from disk truth (overrides whatever the JSON says)
                entry["status"] = _compute_status(inp)
            return catalog
        except Exception as e:
            log.warning("Could not load fires_catalog.json: %s — falling back to dynamic", e)

    import geopandas as gpd

    fires = []
    if not _WILDCAT_DIR.exists():
        return fires

    for fire_dir in sorted(_WILDCAT_DIR.iterdir()):
        if not fire_dir.is_dir():
            continue
        inp = fire_dir / "inputs"
        if not inp.exists():
            continue

        files = _find_inputs(inp)
        if files["perimeter"] is None:
            continue   # no perimeter → not usable

        # Centroid + area from perimeter SHP
        lat, lon, area_km2, display_name = None, None, None, None
        try:
            gdf = gpd.read_file(str(files["perimeter"]))
            # If CRS is missing, assume UTM zone 10N (most CA fires)
            if gdf.crs is None:
                gdf = gdf.set_crs(epsg=32610)
            gdf_4326 = gdf.to_crs(epsg=4326)
            c = gdf_4326.geometry.centroid.iloc[0]
            # Guard: if reprojection silently failed, Y will still be UTM metres
            if -90 <= c.y <= 90 and -180 <= c.x <= 180:
                lat = round(c.y, 4)
                lon = round(c.x, 4)
            else:
                log.warning("Centroid for %s looks like UTM (%s, %s) — skipping",
                            fire_dir.name, c.y, c.x)
            area_km2 = round(gdf.to_crs(epsg=32610).geometry.area.sum() / 1e6, 1)
        except Exception as e:
            log.warning("Could not read centroid for %s: %s", fire_dir.name, e)

        has_dem        = files["dem"]  is not None
        has_dnbr       = files["dnbr"] is not None
        has_assessment = (fire_dir / "assessment" / "basins.geojson").exists()
        status         = "ready" if has_dem and has_dnbr else "needs_download"

        fires.append({
            "id":          fire_dir.name,
            "name":        _slug_to_name(fire_dir.name),
            "year":        _parse_year_from_slug(fire_dir.name),
            "location":    _guess_location(lat),
            "lat":         lat,
            "lon":         lon,
            "area_km2":    area_km2,
            "status":      status,
            "has_dem":     has_dem,
            "has_dnbr":    has_dnbr,
            "has_results": has_assessment,
        })

    # Sort: ready fires first, then by name
    fires.sort(key=lambda f: (0 if f["status"] == "ready" else 1, f["name"]))
    return fires


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _run(
    job_id: str,
    fire_id: str,
    files: Dict[str, Optional[Path]],
    settings,
):
    tmpdir = tempfile.mkdtemp(prefix=f"wildcat_{fire_id}_")
    try:
        import wildcat

        _upd(job_id, 1,
             "Step 1/3 — wildcat.preprocess: conditioning DEM, "
             "estimating burn severity...", 5)

        wildcat.initialize(project=tmpdir, config="empty", inputs=None)
        wildcat.preprocess(
            project=tmpdir,
            inputs=str(files["perimeter"].parent),
            perimeter=files["perimeter"].name,
            dem=files["dem"].name,
            dnbr=files["dnbr"].name,
            kf=settings.kf,
            buffer_km=settings.buffer_km,
            severity_thresholds=list(settings.severity_thresholds),
            estimate_severity=True,
            constrain_dnbr=True,
            missing_kf_check="warn",
        )
        _upd(job_id, 1, "Step 1/3 — Preprocessing complete", 30)

        _upd(job_id, 2,
             "Step 2/3 — wildcat.assess: D8 flow routing, network "
             "delineation, Staley M1 / Gartner G14 models...", 33)
        wildcat.assess(
            project=tmpdir,
            min_area_km2=settings.min_area_km2,
            min_slope=settings.min_slope,
            min_burn_ratio=settings.min_burn_ratio,
            I15_mm_hr=list(settings.I15_mm_hr),
            volume_CI=[0.95],
            durations=[15, 30, 60],
            probabilities=[0.5, 0.75],
            locate_basins=settings.locate_basins,
            parallelize_basins=False,
        )
        _upd(job_id, 2, "Step 2/3 — Assessment complete", 88)

        _upd(job_id, 3, "Step 3/3 — Saving results...", 90)
        _cache_results(fire_id, Path(tmpdir) / "assessment")

        _jobs[job_id].update({
            "status": "completed", "step": 3, "progress": 100,
            "message": "Wildcat analysis complete!",
            "basin_count": _count_basins(
                _WILDCAT_DIR / fire_id / "assessment" / "basins.geojson"
            ),
        })

    except Exception as exc:
        import traceback
        _jobs[job_id].update({
            "status": "failed", "error": str(exc),
            "message": f"Pipeline failed: {exc}",
        })
        log.error(traceback.format_exc())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if _active_by_fire.get(fire_id) == job_id:
            _active_by_fire.pop(fire_id, None)


def _upd(job_id: str, step: int, msg: str, pct: int):
    _jobs[job_id].update({"step": step, "message": msg, "progress": pct})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_inputs(inp_dir: Path) -> Dict[str, Optional[Path]]:
    """Auto-detect perimeter SHP, DEM tif, and dNBR tif in an inputs/ directory."""
    shp_files = sorted(inp_dir.glob("*.shp"))
    tif_files = sorted(inp_dir.glob("*.tif"))

    def match(files, keywords):
        for f in files:
            if any(k in f.stem.lower() for k in keywords):
                return f
        return files[0] if files else None

    return {
        "perimeter": match(shp_files, ["perimeter", "burn_bndy", "perim"]),
        "dem":       match(tif_files, ["dem", "3dep", "elev", "elevation"]),
        "dnbr":      match(tif_files, ["dnbr", "nbr"]),
    }


def _cache_results(fire_id: str, assessment_tmp: Path):
    """Copy Wildcat assessment outputs to cache, reprojecting to WGS84 (EPSG:4326).
    Wildcat outputs are in the input DEM's CRS (often UTM) — flutter_map requires
    geographic coordinates, so we reproject here before the app ever sees them.

    Re-reads each file after writing and verifies it actually landed in
    WGS84 with valid lon/lat bounds. This used to fall back to silently
    copying the raw (un-reprojected) file on any error, which is exactly how
    a race condition between two concurrent analyze runs once corrupted a
    cached result with UTM-meter coordinates and no error surfaced anywhere
    (see notebooks/wildcat_mhri_pipeline/04_reprojection_and_cache.ipynb).
    Concurrent runs are now prevented by `_active_by_fire`, but this check
    stays as a second line of defense against any other corruption mode."""
    import geopandas as gpd
    out = _WILDCAT_DIR / fire_id / "assessment"
    out.mkdir(parents=True, exist_ok=True)
    for fname in ["basins.geojson", "segments.geojson", "outlets.geojson"]:
        src = assessment_tmp / fname
        if not src.exists():
            continue

        gdf = gpd.read_file(str(src))
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=32610)  # assume UTM zone 10N if unset
        gdf_4326 = gdf.to_crs(epsg=4326)
        out_path = out / fname
        gdf_4326.to_file(str(out_path), driver="GeoJSON")

        check = gpd.read_file(str(out_path))
        if check.crs is None or check.crs.to_epsg() != 4326:
            raise RuntimeError(
                f"Cached {fname} is not in EPSG:4326 after reprojection "
                f"(got {check.crs}) — refusing to serve a corrupted cache."
            )
        minx, miny, maxx, maxy = check.total_bounds
        if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
            raise RuntimeError(
                f"Cached {fname} has out-of-range bounds {check.total_bounds.tolist()} "
                "after reprojection — looks like raw UTM coordinates leaked through."
            )
        log.info("Cached %s → WGS84 (%d features)", fname, len(gdf_4326))


def _clear_assessment(fire_id: str):
    assess_dir = _WILDCAT_DIR / fire_id / "assessment"
    if assess_dir.exists():
        for p in assess_dir.glob("*.geojson"):
            p.unlink()


def _count_basins(path: Path) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            return len(json.load(f).get("features", []))
    except Exception:
        return 0


def _has_dem(inp: Path) -> bool:
    return inp.exists() and any(
        k in f.stem.lower()
        for f in inp.glob("*.tif")
        for k in ("dem", "3dep", "elev", "elevation")
    )


def _has_dnbr(inp: Path) -> bool:
    return inp.exists() and any(
        k in f.stem.lower()
        for f in inp.glob("*.tif")
        for k in ("dnbr", "nbr", "burn", "severity")
    )


def _compute_status(inp: Path) -> str:
    if not inp.exists():
        return "needs_download"
    return "ready" if _has_dem(inp) and _has_dnbr(inp) else "needs_download"


def _slug_to_name(slug: str) -> str:
    """'abney_2017' → 'Abney'  |  'dolan-fire' → 'Dolan Fire'"""
    import re
    s = re.sub(r"[_-](\d{4})$", "", slug)      # strip trailing year
    s = s.replace("-", " ").replace("_", " ")
    return s.title()


def _parse_year_from_slug(slug: str) -> Optional[int]:
    import re
    m = re.search(r"(20\d{2}|19\d{2})", slug)
    return int(m.group(1)) if m else None


def _guess_location(lat: Optional[float]) -> str:
    if lat is None: return "California, USA"
    if lat > 42:    return "N. California, USA"
    if lat > 38:    return "C. California, USA"
    if lat > 35:    return "Big Sur / Central Coast, CA"
    return "S. California, USA"
