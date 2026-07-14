"""
Google Earth Engine helper service.

Handles authentication (using locally stored credentials from `earthengine authenticate`)
and on-demand DEM download clipped to a fire area.

Usage:
    import services.gee_service as gee_service
    gee_service.initialize("your-gee-project-id")
    dem_path = gee_service.download_dem_clip(perimeter_gdf, buffer_m=1000, out_path="/tmp/dem.tif")
"""

import io
import math
import os
import shutil
import tempfile
import zipfile
from typing import Optional

import ee
import geopandas as gpd
import requests
from pathlib import Path

# Module-level state — only initialise once per project per process
_initialized_project: str = ""

# GEE getDownloadURL() hard limit.
# At 10 m resolution, Float32 (4 bytes/pixel):
#   1 km² = 10,000 pixels × 4 bytes = 40 KB uncompressed
#   800 km² ≈ 32 MB uncompressed  ← GEE's stated per-band limit
# We use 700 km² as a conservative safe limit with margin.
MAX_DOWNLOAD_AREA_KM2 = 700.0

# Sentinel written into ocean/lake pixels masked out by land_mask_image().
# pfdf (the hydrology engine behind Wildcat) reads NoData directly from each
# GeoTIFF's tag — see pfdf.watershed's module docstring: a raster with NO
# NoData tag defaults to treating value 0 as NoData, which is exactly wrong
# for a DEM that has real near-zero elevations along the coast. Writing an
# explicit, unambiguous sentinel (and tagging it) avoids that footgun.
WATER_SENTINEL = -9999.0


def _configured_project_id(project_id: Optional[str] = None) -> str:
    configured = (project_id or os.environ.get("GEE_PROJECT_ID") or "").strip()
    if not configured:
        raise RuntimeError(
            "GEE project ID is not configured. Set GEE_PROJECT_ID in the "
            "backend environment."
        )
    return configured


def _legacy_initialize(project_id: Optional[str] = None) -> str:
    """
    Initialise GEE using locally stored credentials.
    The user must have already run `earthengine authenticate` on this machine.
    Credentials are stored at ~/.config/earthengine/credentials (Linux/Mac)
    or C:\\Users\\<user>\\.config\\earthengine\\credentials (Windows).
    """
    global _initialized_project
    if _initialized_project == project_id:
        return  # Already initialised with same project — skip
    ee.Initialize(project=project_id)
    _initialized_project = project_id


def _legacy_test_connection(project_id: str) -> dict:
    """
    Test that GEE can be reached and the project ID is valid.
    Returns {"success": True/False, "message": "..."}
    """
    try:
        initialize(project_id)
        # Lightweight check: get metadata of the 3DEP dataset
        info = ee.ImageCollection("USGS/3DEP/10m_collection").mosaic().bandNames().getInfo()
        if "elevation" in info:
            return {
                "success": True,
                "message": f"Connected to GEE project '{project_id}'. 3DEP 10m DEM is accessible.",
                "project_id": project_id,
            }
        return {"success": False, "message": "Connected but could not verify 3DEP dataset."}
    except ee.EEException as e:
        return {"success": False, "message": f"GEE error: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


def initialize(project_id: Optional[str] = None) -> str:
    """
    Initialise GEE for the configured project.

    Cloud Run supplies ambient service-account credentials. Local development
    still works with credentials created by `earthengine authenticate`.
    """
    global _initialized_project
    project_id = _configured_project_id(project_id)
    if _initialized_project == project_id:
        return project_id
    ee.Initialize(project=project_id)
    _initialized_project = project_id
    return project_id


def test_connection(project_id: Optional[str] = None) -> dict:
    """
    Test that GEE can be reached and the project ID is valid.
    Returns {"success": True/False, "message": "..."}
    """
    try:
        active_project = initialize(project_id)
        info = ee.ImageCollection("USGS/3DEP/10m_collection").mosaic().bandNames().getInfo()
        if "elevation" in info:
            return {
                "success": True,
                "message": f"Connected to GEE project '{active_project}'. 3DEP 10m DEM is accessible.",
                "project_id": active_project,
            }
        return {"success": False, "message": "Connected but could not verify 3DEP dataset."}
    except ee.EEException as e:
        return {"success": False, "message": f"GEE error: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


def estimate_area_km2(perimeter_gdf: gpd.GeoDataFrame, buffer_m: int) -> float:
    """
    Return the buffered area in km² that would be downloaded from GEE.
    Uses a projected CRS so the buffer and area calculation are accurate.
    """
    centroid_lon = perimeter_gdf.to_crs(epsg=4326).geometry.centroid.iloc[0].x
    utm_epsg = _utm_epsg_from_lon(centroid_lon)
    buffered = perimeter_gdf.to_crs(epsg=utm_epsg).buffer(buffer_m)
    return float(buffered.area.sum() / 1_000_000)


def check_area(perimeter_gdf: gpd.GeoDataFrame, buffer_m: int) -> dict:
    """
    Validate that the download area is within GEE's getDownloadURL() limit.
    Returns {"ok": True/False, "area_km2": float, "limit_km2": float, "message": str}
    """
    area = estimate_area_km2(perimeter_gdf, buffer_m)
    if area > MAX_DOWNLOAD_AREA_KM2:
        est_mb = area * 40_000 / 1_048_576  # 10m Float32: 40 KB per km²
        return {
            "ok": False,
            "area_km2": round(area, 1),
            "limit_km2": MAX_DOWNLOAD_AREA_KM2,
            "message": (
                f"Zone area is too large for direct GEE download "
                f"({area:.0f} km² ≈ {est_mb:.0f} MB uncompressed). "
                f"Maximum is {MAX_DOWNLOAD_AREA_KM2:.0f} km². "
                f"Please draw a smaller area."
            ),
        }
    return {
        "ok": True,
        "area_km2": round(area, 1),
        "limit_km2": MAX_DOWNLOAD_AREA_KM2,
        "message": f"Area is {area:.1f} km² — within the {MAX_DOWNLOAD_AREA_KM2:.0f} km² limit.",
    }


def _write_gee_response(response: requests.Response, out_path: str, nodata: float | None = None) -> None:
    """Write a getDownloadURL() response to disk, handling both the current
    raw-GeoTIFF format and the legacy ZIP-wrapped format.

    If `nodata` is given, tag the written GeoTIFF with that NoData value
    (only if it doesn't already have one) so downstream readers (pfdf) know
    which pixels to exclude from flow-routing — see WATER_SENTINEL.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    magic = response.content[:2]
    if magic in (b"II", b"MM"):
        with open(out_path, "wb") as dst:
            dst.write(response.content)
    elif magic == b"PK":
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            tif_names = [n for n in zf.namelist() if n.lower().endswith(".tif")]
            if not tif_names:
                raise RuntimeError(f"GEE ZIP contained no .tif. Contents: {zf.namelist()}")
            with zf.open(tif_names[0]) as src_tif, open(out_path, "wb") as dst:
                dst.write(src_tif.read())
    else:
        snippet = response.content[:400].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GEE returned an unrecognised response (not TIFF or ZIP). "
            f"The area may exceed GEE's per-request size limit.\n"
            f"Response preview: {snippet}"
        )

    if nodata is not None:
        ensure_nodata_tag(out_path, nodata)


def ensure_nodata_tag(path: str, nodata: float) -> None:
    """Tag a GeoTIFF with a NoData value if it doesn't already have one."""
    import rasterio
    with rasterio.open(path, "r+") as ds:
        if ds.nodata is None:
            ds.nodata = nodata


def _download_image_clip(
    image: "ee.Image",
    bounds_utm: tuple,
    utm_epsg: int,
    scale: int,
    out_path: str,
    nodata: float | None = None,
) -> str:
    """Download `image` clipped to a UTM bounding box in one shot (no tiling)."""
    minx, miny, maxx, maxy = bounds_utm
    region = ee.Geometry.Rectangle([minx, miny, maxx, maxy], proj=f"EPSG:{utm_epsg}", evenOdd=False)
    url = image.getDownloadURL({
        "scale": scale,
        "crs": f"EPSG:{utm_epsg}",
        "region": region,
        "format": "GEO_TIFF",
        "filePerBand": False,
    })
    response = requests.get(url, timeout=600)
    response.raise_for_status()
    _write_gee_response(response, out_path, nodata=nodata)
    return out_path


def _download_image_clip_tiled(
    image: "ee.Image",
    bounds_utm: tuple,
    utm_epsg: int,
    scale: int,
    out_path: str,
    max_area_km2: float,
    nodata: float | None = None,
) -> str:
    """Download `image` clipped to a UTM bounding box too large for a single
    getDownloadURL() request — split into a grid of sub-tiles each under
    max_area_km2, download each, then mosaic into one GeoTIFF at out_path."""
    import rasterio
    from rasterio.merge import merge as rio_merge

    minx, miny, maxx, maxy = bounds_utm
    width_m, height_m = maxx - minx, maxy - miny
    total_area_km2 = (width_m * height_m) / 1_000_000

    # 85% of the hard limit leaves margin for the safety check elsewhere.
    budget_km2 = max_area_km2 * 0.85
    n_tiles = max(1, math.ceil(total_area_km2 / budget_km2))
    cols = max(1, math.ceil(math.sqrt(n_tiles * width_m / height_m)))
    rows = max(1, math.ceil(n_tiles / cols))
    tile_w, tile_h = width_m / cols, height_m / rows

    tmpdir = tempfile.mkdtemp(prefix="gee_tiles_")
    try:
        tile_paths = []
        for i in range(cols):
            for j in range(rows):
                tile_bounds = (
                    minx + i * tile_w, miny + j * tile_h,
                    minx + (i + 1) * tile_w, miny + (j + 1) * tile_h,
                )
                tile_path = str(Path(tmpdir) / f"tile_{i}_{j}.tif")
                _download_image_clip(image, tile_bounds, utm_epsg, scale, tile_path, nodata=nodata)
                tile_paths.append(tile_path)

        srcs = [rasterio.open(p) for p in tile_paths]
        try:
            mosaic, transform = rio_merge(srcs, nodata=nodata)
            meta = srcs[0].meta.copy()
            meta.update({
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": transform,
                "nodata": nodata if nodata is not None else meta.get("nodata"),
            })
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(out_path, "w", **meta) as dst:
                dst.write(mosaic)
        finally:
            for s in srcs:
                s.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return out_path


def land_mask_image() -> "ee.Image":
    """
    Binary land mask built from JRC's Global Surface Water occurrence layer
    (1 = land, masked-out = permanent water — ocean, bays, large lakes).

    DEM elevation and dNBR over open water are not nodata by default — DEM
    is near-zero/flat, dNBR is Landsat noise — so Wildcat's D8 flow routing
    tries to delineate "catchments" over the ocean near a coastal AOI's
    buffer, producing degenerate/self-intersecting basin polygons right at
    the shoreline. Masking water out as real nodata before preprocess() runs
    makes flow-routing exclude those cells from the network entirely,
    which is the standard fix coastal-watershed hydrology tools use.
    """
    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    is_water = occurrence.gte(50).unmask(0)
    return is_water.eq(0).selfMask()


def mask_water_to_sentinel(image: "ee.Image") -> "ee.Image":
    """Mask `image` to land_mask_image(), then fill masked (water) pixels
    with WATER_SENTINEL instead of leaving them implicitly masked — GEE's
    GEO_TIFF export doesn't reliably propagate a mask into a GDAL NoData
    tag, so we write an explicit, unambiguous value and tag it ourselves
    (see ensure_nodata_tag, called from _write_gee_response)."""
    return image.updateMask(land_mask_image()).unmask(WATER_SENTINEL, sameFootprint=False)


def download_dem_clip(
    perimeter_gdf: gpd.GeoDataFrame,
    buffer_m: int,
    out_path: str,
    mask_water: bool = True,
) -> str:
    """
    Download a 10m DEM from GEE (USGS 3DEP) clipped to perimeter + buffer_m metres.

    Areas under MAX_DOWNLOAD_AREA_KM2 download in a single request. Larger
    areas (e.g. big fires like Dolan) are tiled into a grid of sub-requests
    and mosaicked locally — no fire is too large to fetch, it just takes
    longer for the biggest ones.

    The downloaded file is a GeoTIFF in UTM (metric CRS matching the fire location).
    The caller is responsible for any further reprojection if needed.

    `mask_water` (default True) masks ocean/lake pixels to nodata — see
    land_mask_image() for why this matters for coastal AOIs.
    """
    if not _initialized_project:
        raise RuntimeError("GEE not initialised. Call gee_service.initialize(project_id) first.")

    centroid_lon = perimeter_gdf.to_crs(epsg=4326).geometry.centroid.iloc[0].x
    utm_epsg = _utm_epsg_from_lon(centroid_lon)
    buffered_utm = perimeter_gdf.to_crs(epsg=utm_epsg).buffer(buffer_m)
    bounds_utm = tuple(float(v) for v in buffered_utm.total_bounds)  # [minx, miny, maxx, maxy] in UTM metres

    area_km2 = estimate_area_km2(perimeter_gdf, buffer_m)
    dem = ee.ImageCollection("USGS/3DEP/10m_collection").mosaic().select("elevation")
    nodata = None
    if mask_water:
        dem = mask_water_to_sentinel(dem)
        nodata = WATER_SENTINEL

    if area_km2 <= MAX_DOWNLOAD_AREA_KM2:
        return _download_image_clip(dem, bounds_utm, utm_epsg, 10, out_path, nodata=nodata)
    return _download_image_clip_tiled(
        dem, bounds_utm, utm_epsg, 10, out_path, MAX_DOWNLOAD_AREA_KM2, nodata=nodata,
    )


def _utm_epsg_from_lon(lon: float) -> int:
    """Return the UTM zone EPSG code (north hemisphere) for a given longitude."""
    zone = int((lon + 180) / 6) + 1
    return 32600 + zone
