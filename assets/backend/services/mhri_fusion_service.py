"""
MHRI Fusion Service.

Bridges two previously separate projects:

  - fire_webapp2's Wildcat pipeline, which models post-wildfire debris-flow
    probability per catchment ("sub-basin") for a fire perimeter, at one
    probability value per rainfall scenario (P_0..P_3 in basins.geojson).

  - the ASBPA Multi-Hazard Resilience Index (MHRI), a 44-parameter, 1km
    raster index covering the 60 Pacific-coast counties of CA/OR/WA:
        MHRI = cbrt(H * E * S / AC) * 100
    where H/E/S/AC are the per-category means of min-max normalized
    parameter rasters (Hazard 'a*', Exposure 'b*', Susceptibility 'c*',
    Adaptive Capacity 'd*').

  MHRI already reserves one Hazard slot, a8_post_wildfire_debris_flow, for
  a static USGS county-level debris-flow probability raster. This module
  replaces that static value — for whichever 1km cells a user's AOI covers
  — with a live value derived from Wildcat's own catchment-level output,
  area-weighted onto the ASBPA 1km grid.

Data dependency: the required ASBPA raster subset (60 counties x 44
parameters, ~3.6 GB) ships inside this app at assets/asbpa_data/ — a
sibling of this backend/ folder — so the app is self-contained. Set the
ASBPA_DATA_DIR environment variable to point elsewhere instead, if needed.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import box as shapely_box

log = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).parent.parent
_WEBAPP_ROOT  = _BACKEND_ROOT.parent
_WILDCAT_DIR  = Path(os.environ.get("WILDCAT_DATA_DIR", str(_WEBAPP_ROOT / "wildcat")))

ASBPA_DIR = Path(os.environ.get("ASBPA_DATA_DIR", str(_WEBAPP_ROOT / "asbpa_data")))
_COUNTY_SHP    = ASBPA_DIR / "0. shapefiles" / "ALL_states_merged.shp"
_MASTER_CSV    = ASBPA_DIR / "0.master_raster_filepath_definitive.csv"
_STATS_CSV     = ASBPA_DIR / "0_calibration_analysis" / "parameter_statistics.csv"

# a* = Hazard, b* = Exposure, c* = Susceptibility, d* = Adaptive Capacity
_CATEGORY_BY_PREFIX = {"a": "H", "b": "E", "c": "S", "d": "AC"}
_A8_PARAM = "a8_post_wildfire_debris_flow"

# Grid cells smaller than this fraction of a 1km cell are dropped as
# slivers produced by reprojection rounding.
_MIN_CELL_FRACTION = 0.05


# ===========================================================================
# Cached reference data
# ===========================================================================

@lru_cache(maxsize=1)
def _county_boundaries() -> gpd.GeoDataFrame:
    if not _COUNTY_SHP.exists():
        raise FileNotFoundError(
            f"ASBPA county boundary file not found: {_COUNTY_SHP}. "
            "Set ASBPA_DATA_DIR to the ASBPA project root."
        )
    gdf = gpd.read_file(str(_COUNTY_SHP)).to_crs(epsg=4326)
    gdf["county_key"] = gdf["NAME"].astype(str) + ", " + gdf["STATE"].astype(str)
    return gdf


@lru_cache(maxsize=1)
def _param_table() -> pd.DataFrame:
    if not _MASTER_CSV.exists():
        raise FileNotFoundError(f"ASBPA master raster filepath CSV not found: {_MASTER_CSV}")
    df = pd.read_csv(str(_MASTER_CSV))
    return df.set_index("county")


@lru_cache(maxsize=1)
def _param_stats() -> Dict[str, Tuple[float, float]]:
    if not _STATS_CSV.exists():
        raise FileNotFoundError(f"ASBPA parameter statistics CSV not found: {_STATS_CSV}")
    df = pd.read_csv(str(_STATS_CSV))
    return {row["parameter"]: (float(row["min"]), float(row["max"])) for _, row in df.iterrows()}


@lru_cache(maxsize=1)
def _param_metadata() -> Dict[str, Dict[str, Any]]:
    """Display metadata per parameter: human name, unit, category, global range."""
    if not _STATS_CSV.exists():
        raise FileNotFoundError(f"ASBPA parameter statistics CSV not found: {_STATS_CSV}")
    df = pd.read_csv(str(_STATS_CSV))
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        param = row["parameter"]
        out[param] = {
            "name": row.get("name", param),
            "unit": row.get("unit", ""),
            "category": _param_category(param),
            "min": float(row["min"]),
            "max": float(row["max"]),
        }
    return out


def _param_category(param: str) -> Optional[str]:
    return _CATEGORY_BY_PREFIX.get(param[0]) if param else None


# ===========================================================================
# Coverage / AOI helpers
# ===========================================================================

def find_intersecting_counties(aoi_gdf: gpd.GeoDataFrame) -> List[str]:
    """Return ['County, ST', ...] for every ASBPA county the AOI touches."""
    counties = _county_boundaries()
    aoi_4326 = aoi_gdf.to_crs(epsg=4326)
    aoi_union = aoi_4326.geometry.union_all()
    hits = counties[counties.geometry.intersects(aoi_union)]
    return hits["county_key"].tolist()


def check_coverage(aoi_gdf: gpd.GeoDataFrame) -> bool:
    """True if the AOI overlaps at least one of the 60 ASBPA MHRI counties."""
    try:
        return len(find_intersecting_counties(aoi_gdf)) > 0
    except FileNotFoundError:
        log.warning("ASBPA county boundaries unavailable — skipping coverage check")
        return False


# ===========================================================================
# Grid construction + per-cell sampling
# ===========================================================================

def _county_param_path(county_key: str, param: str) -> Optional[Path]:
    table = _param_table()
    if county_key not in table.index:
        return None
    rel = table.loc[county_key, param]
    if not isinstance(rel, str) or not rel.strip():
        return None
    return ASBPA_DIR / rel


def _build_grid_cells(a8_path: Path, aoi_geom_native, native_crs) -> gpd.GeoDataFrame:
    """Build 1km grid-cell polygons (in the raster's native CRS) for every
    pixel of `a8_path` whose footprint intersects the AOI."""
    with rasterio.open(a8_path) as src:
        transform = src.transform
        width, height = src.width, src.height
        raster_crs = src.crs

    minx, miny, maxx, maxy = aoi_geom_native.bounds
    inv = ~transform
    col_min, row_max = inv * (minx, miny)
    col_max, row_min = inv * (maxx, maxy)

    c0 = max(0, int(np.floor(min(col_min, col_max))) - 1)
    c1 = min(width, int(np.ceil(max(col_min, col_max))) + 1)
    r0 = max(0, int(np.floor(min(row_min, row_max))) - 1)
    r1 = min(height, int(np.ceil(max(row_min, row_max))) + 1)

    cells = []
    for row in range(r0, r1):
        for col in range(c0, c1):
            x0, y0 = transform * (col, row)
            x1, y1 = transform * (col + 1, row + 1)
            cell = shapely_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            if not cell.intersects(aoi_geom_native):
                continue
            overlap = cell.intersection(aoi_geom_native)
            if overlap.area < cell.area * _MIN_CELL_FRACTION:
                continue
            cells.append({"row": row, "col": col, "geometry": cell})

    return gpd.GeoDataFrame(cells, crs=raster_crs)


def _sample_param_at_cells(param_path: Path, cells: gpd.GeoDataFrame) -> np.ndarray:
    """Sample a parameter raster at each cell's centroid (reprojecting the
    centroid into the raster's own CRS — county rasters aren't guaranteed to
    share one global grid)."""
    centroids = cells.geometry.centroid
    with rasterio.open(param_path) as src:
        pts = gpd.GeoSeries(centroids, crs=cells.crs).to_crs(src.crs)
        coords = [(p.x, p.y) for p in pts]
        nodata = src.nodata
        values = np.array([v[0] for v in src.sample(coords)], dtype="float64")
    if nodata is not None:
        values[values == nodata] = np.nan
    return values


def _rasterize_wildcat_probability(
    basins_gdf: gpd.GeoDataFrame, p_field: str, cells: gpd.GeoDataFrame,
) -> np.ndarray:
    """Area-weighted mean of `p_field` from Wildcat's catchment polygons onto
    each 1km grid cell. NaN where no catchment overlaps a cell.

    Uses geopandas.overlay (STRtree-backed) rather than a manual O(n*m)
    geometry loop, since a 700 km^2 AOI can carry thousands of catchments.
    """
    out = np.full(len(cells), np.nan, dtype="float64")

    basins = basins_gdf.to_crs(cells.crs)[["geometry", p_field]].dropna(subset=[p_field]).copy()
    if basins.empty:
        return out
    basins["geometry"] = basins.geometry.buffer(0)  # fix any self-intersections

    cells_idx = cells[["geometry"]].reset_index(drop=True).copy()
    cells_idx["_cell_id"] = cells_idx.index

    inter = gpd.overlay(cells_idx, basins, how="intersection")
    if inter.empty:
        return out

    inter["_area"] = inter.geometry.area
    inter["_weighted"] = inter["_area"] * inter[p_field]
    grouped = inter.groupby("_cell_id").agg(w=("_weighted", "sum"), a=("_area", "sum"))
    out[grouped.index.to_numpy()] = (grouped["w"] / grouped["a"]).to_numpy()
    return out


# ===========================================================================
# Public entry point
# ===========================================================================

def compute_mhri_grid(fire_id: str, i15_index: int = 0) -> Dict[str, Any]:
    """
    Compute the pixel-level MHRI grid for a Wildcat AOI, with the
    a8_post_wildfire_debris_flow indicator replaced (where covered) by
    Wildcat's own per-catchment debris-flow probability for I15 scenario
    `i15_index`.

    Requires the AOI to already have a perimeter (uploaded or catalog fire)
    and a completed Wildcat analysis (basins.geojson).

    Returns:
        {
          "fire_id", "i15_index", "p_field", "counties": [...],
          "cell_count", "mhri_grid": <GeoJSON FeatureCollection, EPSG:4326>,
        }
    """
    inp_dir = _WILDCAT_DIR / fire_id / "inputs"
    assess_dir = _WILDCAT_DIR / fire_id / "assessment"
    basins_path = assess_dir / "basins.geojson"
    if not basins_path.exists():
        raise FileNotFoundError(
            f"No Wildcat results for '{fire_id}'. Run Prepare + Analyze first."
        )

    perim_candidates = sorted(inp_dir.glob("*.shp"))
    if not perim_candidates:
        raise FileNotFoundError(f"No perimeter shapefile found for '{fire_id}'.")
    perim_path = next(
        (f for f in perim_candidates
         if any(k in f.stem.lower() for k in ("perimeter", "perim", "burn_bndy"))),
        perim_candidates[0],
    )

    aoi_gdf = gpd.read_file(str(perim_path))
    if aoi_gdf.crs is None:
        aoi_gdf = aoi_gdf.set_crs(epsg=32610)
    aoi_4326 = aoi_gdf.to_crs(epsg=4326)
    aoi_union_4326 = aoi_4326.geometry.union_all()

    counties = find_intersecting_counties(aoi_gdf)
    if not counties:
        raise ValueError(
            "This AOI falls outside the ASBPA 60-county MHRI coverage area "
            "(coastal CA/OR/WA) — debris-flow analysis is available, but MHRI "
            "fusion is not."
        )

    basins_gdf = gpd.read_file(str(basins_path))  # already cached as WGS84
    p_field = f"P_{i15_index}"
    if p_field not in basins_gdf.columns:
        raise ValueError(
            f"Rainfall scenario index {i15_index} not present in Wildcat results "
            f"(expected column '{p_field}')."
        )

    stats = _param_stats()
    all_cell_frames: List[pd.DataFrame] = []
    all_cell_geoms_4326: List[Any] = []

    for county_key in counties:
        a8_path = _county_param_path(county_key, _A8_PARAM)
        if a8_path is None or not a8_path.exists():
            log.warning("No a8 raster for county '%s' — skipping", county_key)
            continue

        with rasterio.open(a8_path) as src:
            native_crs = src.crs
        aoi_native = aoi_union_4326 if native_crs is None else gpd.GeoSeries(
            [aoi_union_4326], crs=4326
        ).to_crs(native_crs).iloc[0]

        cells = _build_grid_cells(a8_path, aoi_native, native_crs)
        if cells.empty:
            continue

        basins_native = basins_gdf.to_crs(native_crs)
        wildcat_prob = _rasterize_wildcat_probability(basins_native, p_field, cells)

        param_table = _param_table()
        if county_key not in param_table.index:
            continue
        param_cols = [c for c in param_table.columns]

        category_sums: Dict[str, np.ndarray] = {
            "H": np.zeros(len(cells)), "E": np.zeros(len(cells)),
            "S": np.zeros(len(cells)), "AC": np.zeros(len(cells)),
        }
        category_counts: Dict[str, np.ndarray] = {
            k: np.zeros(len(cells)) for k in category_sums
        }
        a8_normalized = None
        per_param_cols: Dict[str, np.ndarray] = {}

        for param in param_cols:
            cat = _param_category(param)
            if cat is None or param not in stats:
                continue
            ppath = _county_param_path(county_key, param)

            if param == _A8_PARAM:
                pmin, pmax = stats[param]
                static_vals = (
                    _sample_param_at_cells(ppath, cells) if ppath and ppath.exists()
                    else np.full(len(cells), np.nan)
                )
                static_norm = np.clip((static_vals - pmin) / (pmax - pmin), 0, 1)
                live_norm = np.clip((wildcat_prob - pmin) / (pmax - pmin), 0, 1)
                # Prefer the live Wildcat value wherever a catchment covers
                # the cell; fall back to the static USGS county raster.
                a8_normalized = np.where(~np.isnan(live_norm), live_norm, static_norm)
                a8_raw = np.where(~np.isnan(wildcat_prob), wildcat_prob, static_vals)
                valid = ~np.isnan(a8_normalized)
                category_sums["H"][valid]   += a8_normalized[valid]
                category_counts["H"][valid] += 1
                per_param_cols[f"raw_{param}"]  = a8_raw
                per_param_cols[f"norm_{param}"] = a8_normalized
                continue

            if ppath is None or not ppath.exists():
                continue
            vals = _sample_param_at_cells(ppath, cells)
            pmin, pmax = stats[param]
            if pmax == pmin:
                continue
            norm = np.clip((vals - pmin) / (pmax - pmin), 0, 1)
            valid = ~np.isnan(norm)
            category_sums[cat][valid]   += norm[valid]
            category_counts[cat][valid] += 1
            per_param_cols[f"raw_{param}"]  = vals
            per_param_cols[f"norm_{param}"] = norm

        with np.errstate(invalid="ignore", divide="ignore"):
            H  = category_sums["H"]  / np.where(category_counts["H"]  > 0, category_counts["H"],  np.nan)
            E  = category_sums["E"]  / np.where(category_counts["E"]  > 0, category_counts["E"],  np.nan)
            S  = category_sums["S"]  / np.where(category_counts["S"]  > 0, category_counts["S"],  np.nan)
            AC = category_sums["AC"] / np.where(category_counts["AC"] > 0, category_counts["AC"], np.nan)
            mhri = np.cbrt(H * E * S / AC) * 100

        df = pd.DataFrame({
            "county": county_key,
            "H": H, "E": E, "S": S, "AC": AC, "MHRI": mhri,
            "a8_value": a8_normalized if a8_normalized is not None else np.nan,
            "a8_source": np.where(
                ~np.isnan(wildcat_prob), "wildcat_live", "asbpa_static",
            ) if a8_normalized is not None else "none",
            **per_param_cols,
        })
        all_cell_frames.append(df)
        all_cell_geoms_4326.append(cells.to_crs(epsg=4326).geometry)

    if not all_cell_frames:
        raise ValueError("Could not build any MHRI grid cells for this AOI.")

    combined = pd.concat(all_cell_frames, ignore_index=True)
    combined_geom = pd.concat(all_cell_geoms_4326, ignore_index=True)
    out_gdf = gpd.GeoDataFrame(combined, geometry=combined_geom, crs=4326)
    out_gdf = out_gdf[out_gdf.intersects(aoi_union_4326)]
    out_gdf = out_gdf.dropna(subset=["MHRI"])

    return {
        "fire_id": fire_id,
        "i15_index": i15_index,
        "p_field": p_field,
        "counties": counties,
        "cell_count": int(len(out_gdf)),
        "mhri_grid": json.loads(out_gdf.to_json()),
        "param_metadata": _param_metadata(),
        "perimeter": json.loads(gpd.GeoDataFrame(geometry=[aoi_union_4326], crs=4326).to_json()),
    }
