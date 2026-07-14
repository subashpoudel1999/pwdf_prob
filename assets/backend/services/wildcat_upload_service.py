"""
Wildcat Upload Service — MHRI Fusion module.

Lets a user supply their own AOI/fire perimeter (GeoJSON or a zipped
Shapefile) instead of picking one from the historical catalog. The
perimeter is converted/validated and written to wildcat/<fire_id>/inputs/
in the exact same layout the rest of the pipeline (wildcat_generic_service,
wildcat_fire_prep_service) already expects, so it behaves like any other
"needs_download" fire from that point on — Prepare fetches the DEM + MTBS
burn-severity mosaic for the given fire_date, then Analyze runs as normal.

Two checks are enforced here that the historical catalog doesn't need:
  1. Area cap (700 km^2) — keeps the per-pixel MHRI fusion step (which
     samples 44 county-scale rasters per 1km cell) tractable.
  2. ASBPA coverage check — the MHRI fusion module only has parameter
     rasters for the 60 Pacific-coast counties (CA/OR/WA); an AOI outside
     that footprint can still run Wildcat, but can never get an MHRI score.
"""

from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional

import geopandas as gpd

import services.wildcat_generic_service as _wg
import services.mhri_fusion_service as _mhri

log = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).parent.parent
_WEBAPP_ROOT  = _BACKEND_ROOT.parent
_WILDCAT_DIR  = Path(os.environ.get("WILDCAT_DATA_DIR", str(_WEBAPP_ROOT / "wildcat")))

_ALLOWED_SUFFIXES = {".geojson", ".json", ".zip"}

# Upload size cap — keeps the MHRI pixel-fusion step (43 county rasters x
# 1km cells across the AOI) computationally tractable.
MAX_AREA_KM2 = 700.0


def upload_custom_perimeter(
    data: bytes,
    filename: str,
    name: str,
    year: int,
    fire_date: str,
) -> Dict[str, Any]:
    """
    Convert an uploaded GeoJSON or zipped Shapefile into a perimeter SHP under
    wildcat/<fire_id>/inputs/, plus a meta.json recording name/year/fire_date.

    Returns {"id", "name", "year", "fire_date", "status", "area_km2",
    "in_mhri_coverage"} for the new catalog entry.
    Raises ValueError on bad input (caller should surface this as HTTP 400).
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(
            f"Unsupported file type '{suffix}'. Upload a .geojson/.json file "
            "or a .zip containing a Shapefile (.shp/.shx/.dbf)."
        )

    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if suffix == ".zip":
            gdf = _read_zipped_shapefile(data, tmp_dir)
        else:
            gdf = _read_geojson(data, tmp_dir)

        if gdf.empty:
            raise ValueError("Uploaded perimeter file contains no features.")

        geom_types = set(gdf.geometry.geom_type.dropna().unique())
        bad_types = geom_types - {"Polygon", "MultiPolygon"}
        if bad_types:
            raise ValueError(
                f"Perimeter must be Polygon/MultiPolygon geometry, found: {sorted(geom_types)}"
            )
        if gdf.crs is None:
            log.warning("Uploaded perimeter for '%s' has no CRS — assuming EPSG:4326", name)
            gdf = gdf.set_crs(epsg=4326)

        area_km2 = _area_km2(gdf)
        if area_km2 > MAX_AREA_KM2:
            raise ValueError(
                f"Uploaded perimeter is {area_km2:.1f} km², which exceeds the "
                f"{MAX_AREA_KM2:.0f} km² limit for the MHRI fusion module. "
                "Draw or upload a smaller area."
            )

        in_coverage = _mhri.check_coverage(gdf)
        burn_history = _wg.historical_burn_overlap(gdf)

        fire_id = _make_fire_id(name, year)
        inp_dir = _WILDCAT_DIR / fire_id / "inputs"
        inp_dir.mkdir(parents=True, exist_ok=True)

        out_shp = inp_dir / f"{fire_id}_perimeter.shp"
        gdf.to_file(str(out_shp))

    meta = {
        "name": name, "year": year, "fire_date": fire_date,
        "area_km2": round(area_km2, 2), "in_mhri_coverage": in_coverage,
        "historical_burn_pct": burn_history["burned_pct"],
        "historical_fire_matches": burn_history["matches"],
    }
    (inp_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    _wg.invalidate_perimeter_cache()

    return {"id": fire_id, "status": "needs_download", **meta}


def _area_km2(gdf: gpd.GeoDataFrame) -> float:
    """Geodesic-ish area via an equal-area projection (EPSG:5070, CONUS)."""
    return float(gdf.to_crs(epsg=5070).geometry.area.sum() / 1e6)


def _read_zipped_shapefile(data: bytes, tmp_dir: Path) -> gpd.GeoDataFrame:
    zip_path = tmp_dir / "upload.zip"
    zip_path.write_bytes(data)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Could not open uploaded zip file: {e}") from e

    shp_candidates = sorted(tmp_dir.rglob("*.shp"))
    if not shp_candidates:
        raise ValueError(
            "Zip file does not contain a .shp file. Make sure it includes "
            ".shp, .shx, and .dbf (and ideally .prj)."
        )
    try:
        return gpd.read_file(str(shp_candidates[0]))
    except Exception as e:
        raise ValueError(f"Could not read shapefile from zip: {e}") from e


def _read_geojson(data: bytes, tmp_dir: Path) -> gpd.GeoDataFrame:
    geojson_path = tmp_dir / "upload.geojson"
    geojson_path.write_bytes(data)
    try:
        return gpd.read_file(str(geojson_path))
    except Exception as e:
        raise ValueError(f"Could not read GeoJSON file: {e}") from e


def _make_fire_id(name: str, year: Optional[int]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "aoi"
    base = f"{slug}_{year}" if year else slug

    fire_id = base
    n = 2
    while (_WILDCAT_DIR / fire_id).exists():
        fire_id = f"{base}_{n}"
        n += 1
    return fire_id
