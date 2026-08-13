"""
Wildcat Fire Data Prep Service.

For any fire in the catalog:
  1. Fetches the fire perimeter from the USFS MTBS burned-area GEE collection
     (or uses the local SHP already present for Tier-1 fires).
  2. Downloads a USGS 3DEP 10m DEM clipped to perimeter + buffer via GEE.
  3. Downloads Landsat-8/9 dNBR (pre/post-fire composites) via GEE.
  4. Writes the three files to  wildcat/<fire_slug>/inputs/  so that
     WildcatGenericService can pick them up and run preprocess + assess.

All GEE work happens in a background thread; the caller polls get_prep_status().
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import tempfile
import threading
import urllib.request
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import geopandas as gpd
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).parent.parent
_WEBAPP_ROOT  = _BACKEND_ROOT.parent
# Bundled, read-only wildcat package + static catalog root.
_WILDCAT_DIR  = Path(os.environ.get("WILDCAT_DATA_DIR", str(_WEBAPP_ROOT / "wildcat")))
# Dynamic, per-fire output root — see the matching comment in
# wildcat_generic_service.py for why this is separate from _WILDCAT_DIR.
_FIRE_DATA_DIR = Path(os.environ.get("FIRE_DATA_DIR", str(_WILDCAT_DIR)))
# Optional extra catalog of fires (not shipped with this app — this module
# only needs the user's own uploaded AOI, which _scan_tier1_fires() already
# picks up from _WILDCAT_DIR). _scan_csv_fires() below no-ops if missing.
_SCAN_CSV     = _WEBAPP_ROOT / "module1_fire_scan_results.csv"

# ── In-memory job store ────────────────────────────────────────────────────────
_prep_jobs: Dict[str, Dict] = {}


# ── Fire catalog ──────────────────────────────────────────────────────────────

def _scan_tier1_fires() -> List[Dict]:
    """Fires already in wildcat/ with at least a perimeter present.

    DEM is always fetched live from GEE (never stored), so it's not a
    requirement here — only the perimeter needs to already exist locally.
    dNBR is also fetched live unless already cached (kept for a few
    well-known fires as fast demos)."""
    fires = []
    for fire_dir in sorted(_FIRE_DATA_DIR.iterdir()):
        if not fire_dir.is_dir():
            continue
        inp = fire_dir / "inputs"
        if not inp.exists():
            continue
        shp_files = list(inp.glob("*.shp"))
        tif_files  = list(inp.glob("*.tif"))
        has_dem   = any("dem" in f.stem.lower() or "elev" in f.stem.lower() for f in tif_files)
        has_dnbr  = any(k in f.stem.lower() for f in tif_files
                        for k in ("dnbr", "nbr", "burn", "severity"))
        if not shp_files:
            continue
        # Extract centroid + area
        try:
            gdf = gpd.read_file(str(shp_files[0])).to_crs(epsg=4326)
            c = gdf.geometry.centroid.iloc[0]
            area = gdf.to_crs(epsg=32610).geometry.area.sum() / 1e6
            lat, lon = round(c.y, 4), round(c.x, 4)
        except Exception:
            lat, lon, area = None, None, None

        slug = fire_dir.name
        fires.append({
            "id":             slug,
            "name":           _slug_to_display(slug),
            "year":           _guess_year_from_slug(slug),
            "location":       _guess_location(lat),
            "lat":            lat,
            "lon":            lon,
            "area_km2":       round(area, 1) if area else None,
            "status":         "ready" if (has_dem and has_dnbr) else "needs_download",
            "inputs_dir":     str(inp),
            "tier":           1,
        })
    return fires


def _scan_csv_fires() -> List[Dict]:
    """Fires from the ML pipeline CSV — need GEE download before analysis."""
    if not _SCAN_CSV.exists():
        return []
    df = pd.read_csv(str(_SCAN_CSV))
    fires = []
    for _, row in df.iterrows():
        fire_name = str(row.get("fire_name", "")).strip()
        year = int(row.get("year", 0))
        slug = f"{fire_name.lower()}_{year}"
        inp_dir = _FIRE_DATA_DIR / slug / "inputs"
        # Check if already downloaded
        shp_ok = len(list(inp_dir.glob("*.shp"))) > 0 if inp_dir.exists() else False
        tif_ok = len(list(inp_dir.glob("*.tif"))) >= 2 if inp_dir.exists() else False
        if shp_ok and tif_ok:
            status = "ready"
            tier   = 2
        else:
            status = "needs_download"
            tier   = 4
        fires.append({
            "id":         slug,
            "name":       fire_name.title(),
            "year":       year,
            "fire_date":  str(row.get("fire_date", "")),
            "location":   "California, USA",
            "lat":        None,
            "lon":        None,
            "area_km2":   None,
            "status":     status,
            "inputs_dir": str(inp_dir),
            "tier":       tier,
        })
    return fires


def get_fire_catalog() -> List[Dict]:
    """Return all fires: Tier-1 ready fires first, then CSV fires."""
    tier1  = _scan_tier1_fires()
    tier1_ids = {f["id"] for f in tier1}
    csv    = [f for f in _scan_csv_fires() if f["id"] not in tier1_ids]
    return tier1 + csv


# ── Data prep (background job) ────────────────────────────────────────────────

def start_data_prep(fire_id: str, gee_project: Optional[str] = None) -> Dict[str, Any]:
    """Start a GEE data-prep job for a fire.  Returns {job_id, fire_id}."""
    # Check if this fire is already in the catalog and ready
    catalog = {f["id"]: f for f in get_fire_catalog()}
    if fire_id not in catalog:
        raise ValueError(f"Fire '{fire_id}' not in catalog.")
    fire = catalog[fire_id]
    if fire["status"] == "ready":
        return {"job_id": None, "fire_id": fire_id, "already_ready": True}

    job_id = "prep_" + str(uuid.uuid4())[:8]
    _prep_jobs[job_id] = {
        "status":   "running",
        "fire_id":  fire_id,
        "step":     0,
        "message":  "Starting GEE data prep...",
        "progress": 0,
        "error":    None,
    }
    t = threading.Thread(
        target=_run_prep,
        args=(job_id, fire, gee_project),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "fire_id": fire_id, "already_ready": False}


def get_prep_status(job_id: str) -> Dict[str, Any]:
    if job_id not in _prep_jobs:
        return {"status": "not_found", "error": f"Job {job_id} not found"}
    return dict(_prep_jobs[job_id])


def _upd(job_id: str, step: int, msg: str, pct: int):
    _prep_jobs[job_id].update({"step": step, "message": msg, "progress": pct})
    log.info("[%s] step=%d (%d%%) %s", job_id, step, pct, msg)


def _run_prep(job_id: str, fire: Dict, gee_project: Optional[str] = None):
    """Background: fetch perimeter → DEM → dNBR → save to wildcat/<slug>/inputs/."""
    import ee
    import services.gee_service as gee_svc

    fire_id   = fire["id"]
    fire_name = fire["name"]
    fire_date = fire.get("fire_date", "")
    inp_dir   = Path(fire["inputs_dir"])
    inp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── Step 1: GEE auth ────────────────────────────────────────────────
        _upd(job_id, 1, "Authenticating with the configured GEE project...", 5)
        active_project = gee_svc.initialize(gee_project)
        _upd(job_id, 1, f"Connected to GEE project '{active_project}'.", 8)

        # ── Step 2: Fetch perimeter from MTBS ──────────────────────────────
        _upd(job_id, 2, f"Fetching {fire_name} perimeter from USFS MTBS...", 12)
        perim_path = _find_existing_perimeter(inp_dir) or (inp_dir / f"{fire_id}_perimeter.shp")
        if not perim_path.exists():
            perim_gdf = _fetch_mtbs_perimeter(ee, fire_name, fire_date)
            if perim_gdf is None:
                raise ValueError(
                    f"Could not find '{fire_name}' in the MTBS burned-area database. "
                    "The fire may not yet be in MTBS or the name may not match. "
                    "Please check the MTBS Fire Occurrence dataset for the exact name."
                )
            perim_gdf.to_file(str(perim_path))
            _upd(job_id, 2,
                 f"✓ Perimeter saved ({len(perim_gdf)} features, "
                 f"{perim_gdf.to_crs(32610).geometry.area.sum()/1e6:.1f} km²)",
                 22)
        else:
            perim_gdf = gpd.read_file(str(perim_path))
            _upd(job_id, 2, f"✓ Perimeter already present ({perim_path.name})", 22)

        # Prefer the real ignition date from the perimeter's own attributes
        # (MTBS shapefiles carry Ig_Date; some custom ones carry StartDate)
        # over the catalog's guessed/CSV fire_date — much more accurate for
        # the pre/post-fire Landsat windows in the dNBR step below.
        extracted_date = _extract_fire_date(perim_gdf)
        if extracted_date:
            fire_date = extracted_date
        elif not fire_date and fire.get("year"):
            # Last resort: no catalog date, no shapefile date — assume
            # mid-year so the ±365/180-day Landsat windows still have
            # reasonable coverage.
            fire_date = f"{fire['year']}-07-01"

        # ── Step 3: Download DEM ────────────────────────────────────────────
        dem_path = inp_dir / f"{fire_id}_dem_10m.tif"
        _upd(job_id, 3, "Downloading USGS 3DEP 10m DEM from GEE...", 28)
        if not dem_path.exists():
            gee_svc.download_dem_clip(
                perimeter_gdf=perim_gdf,
                buffer_m=3000,           # 3 km buffer — matches WildcatSettings default
                out_path=str(dem_path),
            )
            _upd(job_id, 3,
                 f"✓ DEM saved ({dem_path.stat().st_size/1e6:.1f} MB)", 55)
        else:
            _upd(job_id, 3, f"✓ DEM already present ({dem_path.name})", 55)

        # ── Step 4: Download dNBR ───────────────────────────────────────────
        dnbr_path = _find_existing_dnbr(inp_dir) or (inp_dir / f"{fire_id}_dnbr.tif")
        _upd(job_id, 4,
             f"Computing dNBR from Landsat-8/9 pre/post-fire composites...", 58)
        if not dnbr_path.exists():
            _download_dnbr(
                ee=ee,
                perim_gdf=perim_gdf,
                fire_date=fire_date,
                out_path=str(dnbr_path),
            )
            _upd(job_id, 4,
                 f"✓ dNBR saved ({dnbr_path.stat().st_size/1e6:.1f} MB)", 90)
        else:
            _upd(job_id, 4, f"✓ dNBR already present ({dnbr_path.name})", 90)

        # ── Done ────────────────────────────────────────────────────────────
        _prep_jobs[job_id].update({
            "status":   "completed",
            "step":     4,
            "message":  f"✓ {fire_name} data ready — perimeter, DEM, and dNBR downloaded.",
            "progress": 100,
        })

    except Exception as exc:
        import traceback
        _prep_jobs[job_id].update({
            "status":  "failed",
            "error":   str(exc),
            "message": f"Data prep failed: {exc}",
        })
        log.error(traceback.format_exc())


def _find_existing_perimeter(inp_dir: Path) -> Optional[Path]:
    """Find an already-present perimeter SHP regardless of naming convention.

    Tier-1 curated fires (e.g. dolan_perimeter.shp, fra2024-perimeter.shp)
    don't follow the `{fire_id}_perimeter.shp` pattern this job writes for
    freshly MTBS-fetched fires — match by keyword instead of exact name."""
    shp_files = sorted(inp_dir.glob("*.shp"))
    if not shp_files:
        return None
    for f in shp_files:
        if any(k in f.stem.lower() for k in ("perimeter", "perim", "burn_bndy")):
            return f
    return shp_files[0]


def _extract_fire_date(perim_gdf: gpd.GeoDataFrame) -> Optional[str]:
    """Pull the real ignition date from perimeter attributes, if present.

    MTBS-sourced shapefiles carry `Ig_Date`; some custom ones (e.g. the
    Franklin fire's) carry `StartDate`. Returns 'YYYY-MM-DD' or None.

    Two different representations show up here: geopandas/fiona converts
    a shapefile's native date field to a proper Timestamp, but a
    freshly-fetched MTBS feature from GEE (`_fetch_mtbs_perimeter`)
    carries Ig_Date as a raw milliseconds-since-epoch integer — treat
    bare numbers as epoch-ms, everything else as a normal date value."""
    if len(perim_gdf) == 0:
        return None
    row = perim_gdf.iloc[0]
    for col in ("Ig_Date", "ig_date", "StartDate", "start_date", "Fire_Date", "FireDiscoveryDateTime"):
        if col in perim_gdf.columns:
            val = row.get(col)
            if val is None or pd.isna(val):
                continue
            try:
                num = float(val)  # succeeds for int/float/numpy numeric types,
            except (TypeError, ValueError):
                num = None        # raises for Timestamp/datetime/str — fall through
            try:
                if num is not None:
                    return pd.to_datetime(num, unit="ms").strftime("%Y-%m-%d")
                return pd.Timestamp(val).strftime("%Y-%m-%d")
            except Exception:
                continue
    return None


def _find_existing_dnbr(inp_dir: Path) -> Optional[Path]:
    """Find an already-present dNBR tif regardless of naming convention.

    Curated fires (e.g. dolan_dnbr.tif, franklin_dnbr_2024_s2.tif) don't
    follow the `{fire_id}_dnbr.tif` pattern this job writes for freshly
    downloaded dNBR — match by keyword instead of exact name."""
    for f in sorted(inp_dir.glob("*.tif")):
        if any(k in f.stem.lower() for k in ("dnbr", "nbr")):
            return f
    return None


# ── MTBS perimeter fetch ──────────────────────────────────────────────────────

def _fetch_mtbs_perimeter(ee, fire_name: str, fire_date: str) -> Optional[gpd.GeoDataFrame]:
    """
    Query the USFS MTBS burned-area GEE collection for a fire perimeter.
    Filters by fire name (case-insensitive prefix match) and year derived
    from fire_date.

    MTBS collection: USFS/GTAC/MTBS/burned_area_boundaries/v1
    Key properties: Incid_Name, Ig_Date (milliseconds since epoch), State
    """
    mtbs = ee.FeatureCollection("USFS/GTAC/MTBS/burned_area_boundaries/v1")

    # Parse year from fire_date (formats: "11-08-2017", "2017-08-11", "2017")
    year = _parse_year(fire_date)
    if year:
        year_start = f"{year}-01-01"
        year_end   = f"{year + 1}-01-01"
        mtbs = mtbs.filter(ee.Filter.date(year_start, year_end))

    # Name filter — MTBS stores names in uppercase
    name_upper = fire_name.upper().strip()
    filtered = mtbs.filter(ee.Filter.stringContains("Incid_Name", name_upper))

    count = filtered.size().getInfo()
    log.info("MTBS query for '%s' (%s): %d features", name_upper, year, count)

    if count == 0:
        # Try without year restriction in case of date uncertainty
        filtered = mtbs.filter(ee.Filter.stringContains("Incid_Name", name_upper))
        count = filtered.size().getInfo()
        if count == 0:
            return None

    # Take the largest (by area) in case of duplicates
    largest = filtered.sort("BurnBndAc", False).first()

    # Export to GeoJSON via getInfo
    feat_info = largest.getInfo()
    if feat_info is None:
        return None

    geom = feat_info.get("geometry")
    props = feat_info.get("properties", {})
    if geom is None:
        return None

    from shapely.geometry import shape
    gdf = gpd.GeoDataFrame(
        [props],
        geometry=[shape(geom)],
        crs="EPSG:4326",
    )
    return gdf


# ── dNBR download ──────────────────────────────────────────────────────────────

def _download_dnbr(
    ee,
    perim_gdf: gpd.GeoDataFrame,
    fire_date: str,
    out_path: str,
    buffer_m: int = 3000,
    scale: int = 30,
) -> None:
    """
    Download Landsat-8/9 dNBR for a fire.

    Pre-fire window:  fire_date − 365 days  →  fire_date − 14 days
    Post-fire window: fire_date + 14 days   →  fire_date + 180 days

    Uses Collection-2 surface reflectance (SR_B5=NIR, SR_B7=SWIR2).
    Falls back to Landsat-7 if L8/L9 have no coverage (pre-2013 fires).
    """
    import zipfile as zf_lib
    import requests as req_lib

    # Build buffered ROI in WGS84
    centroid_lon = perim_gdf.to_crs(epsg=4326).geometry.centroid.iloc[0].x
    utm_epsg = 32600 + int((centroid_lon + 180) / 6) + 1
    buf_utm   = perim_gdf.to_crs(epsg=utm_epsg).buffer(buffer_m)
    buf_wgs84 = buf_utm.to_crs(epsg=4326)
    b = buf_wgs84.total_bounds   # [minx, miny, maxx, maxy]
    roi = ee.Geometry.Rectangle([float(b[0]), float(b[1]), float(b[2]), float(b[3])])

    # Date windows
    fire_dt    = _parse_fire_date(fire_date)
    pre_start  = (fire_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    pre_end    = (fire_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    post_start = (fire_dt + timedelta(days=14)).strftime("%Y-%m-%d")
    post_end   = (fire_dt + timedelta(days=180)).strftime("%Y-%m-%d")

    def scale_l8(img):
        return img.select("SR_B.").multiply(0.0000275).add(-0.2).copyProperties(img)

    def compute_nbr(img):
        nir  = img.select("SR_B5")
        swir = img.select("SR_B7")
        return nir.subtract(swir).divide(nir.add(swir)).rename("NBR")

    # Try Landsat-8/9 Collection-2
    l8_col_id = "LANDSAT/LC08/C02/T1_L2"
    l9_col_id = "LANDSAT/LC09/C02/T1_L2"

    pre_col = (
        ee.ImageCollection(l8_col_id).merge(ee.ImageCollection(l9_col_id))
        .filterBounds(roi)
        .filterDate(pre_start, pre_end)
        .filter(ee.Filter.lt("CLOUD_COVER", 20))
        .map(scale_l8)
    )
    post_col = (
        ee.ImageCollection(l8_col_id).merge(ee.ImageCollection(l9_col_id))
        .filterBounds(roi)
        .filterDate(post_start, post_end)
        .filter(ee.Filter.lt("CLOUD_COVER", 30))
        .map(scale_l8)
    )

    pre_n  = pre_col.size().getInfo()
    post_n = post_col.size().getInfo()
    log.info("Landsat L8/L9: pre=%d scenes, post=%d scenes", pre_n, post_n)

    # Fallback to Landsat-7 for very old fires
    if pre_n == 0 or post_n == 0:
        def compute_nbr_l7(img):
            nir  = img.select("SR_B4")
            swir = img.select("SR_B7")
            return nir.subtract(swir).divide(nir.add(swir)).rename("NBR")
        def scale_l7(img):
            return img.select("SR_B.").multiply(0.0000275).add(-0.2).copyProperties(img)
        l7_col_id = "LANDSAT/LE07/C02/T1_L2"
        pre_col  = (ee.ImageCollection(l7_col_id).filterBounds(roi)
                    .filterDate(pre_start, pre_end).filter(ee.Filter.lt("CLOUD_COVER",20))
                    .map(scale_l7))
        post_col = (ee.ImageCollection(l7_col_id).filterBounds(roi)
                    .filterDate(post_start, post_end).filter(ee.Filter.lt("CLOUD_COVER",30))
                    .map(scale_l7))
        pre_nbr_img  = compute_nbr_l7(pre_col.median())
        post_nbr_img = compute_nbr_l7(post_col.median())
    else:
        pre_nbr_img  = compute_nbr(pre_col.median())
        post_nbr_img = compute_nbr(post_col.median())

    dnbr = pre_nbr_img.subtract(post_nbr_img).multiply(1000).rename("dNBR")

    # Mask ocean/lake pixels to the same sentinel used for the DEM — dNBR
    # over open water is Landsat noise, and combined with a flat DEM there
    # it produces degenerate basin polygons right at the shoreline for
    # coastal AOIs. See gee_service.mask_water_to_sentinel / WATER_SENTINEL.
    import services.gee_service as gee_svc
    dnbr = gee_svc.mask_water_to_sentinel(dnbr)

    url = dnbr.getDownloadURL({
        "region": roi,
        "scale":  scale,
        "crs":    f"EPSG:{utm_epsg}",
        "format": "GEO_TIFF",
    })

    resp = req_lib.get(url, timeout=600)
    resp.raise_for_status()

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    magic = resp.content[:2]
    if magic in (b"II", b"MM"):
        with open(out_path, "wb") as f:
            f.write(resp.content)
    elif magic == b"PK":
        with zf_lib.ZipFile(io.BytesIO(resp.content)) as z:
            tifs = [n for n in z.namelist() if n.lower().endswith(".tif")]
            if not tifs:
                raise RuntimeError("GEE ZIP contained no .tif file")
            with z.open(tifs[0]) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
    else:
        preview = resp.content[:300].decode("utf-8", errors="replace")
        raise RuntimeError(f"Unexpected GEE response (not TIFF/ZIP): {preview}")

    gee_svc.ensure_nodata_tag(out_path, gee_svc.WATER_SENTINEL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_year(date_str: str) -> Optional[int]:
    """Extract year from various date string formats."""
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).year
        except ValueError:
            pass
    # Last resort: find 4-digit year
    import re
    m = re.search(r"(20\d{2}|19\d{2})", str(date_str))
    return int(m.group(1)) if m else None


def _parse_fire_date(date_str: str) -> datetime:
    """Parse a fire date string into a datetime object."""
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            pass
    raise ValueError(f"Cannot parse fire date: '{date_str}'")


def _slug_to_display(slug: str) -> str:
    return slug.replace("-fire", "").replace("-", " ").replace("_", " ").title() + " Fire"


def _guess_year_from_slug(slug: str) -> Optional[int]:
    import re
    m = re.search(r"(20\d{2}|19\d{2})", slug)
    return int(m.group(1)) if m else None


def _guess_location(lat: Optional[float]) -> str:
    if lat is None:
        return "California, USA"
    if lat > 42:  return "Northern California, USA"
    if lat > 38:  return "Central California, USA"
    if lat > 35:  return "Big Sur / Central Coast, CA"
    return "Southern California, USA"
