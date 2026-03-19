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
import json
import zipfile

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


def initialize(project_id: str) -> None:
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


def test_connection(project_id: str) -> dict:
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


def download_dem_clip(
    perimeter_gdf: gpd.GeoDataFrame,
    buffer_m: int,
    out_path: str,
) -> str:
    """
    Download a 10m DEM from GEE (USGS 3DEP) clipped to perimeter + buffer_m metres.

    Raises ValueError if the area exceeds MAX_DOWNLOAD_AREA_KM2 (hard limit before
    even attempting the download — prevents silent GEE failures on large areas).

    The downloaded file is a GeoTIFF in UTM (metric CRS matching the fire location).
    The caller is responsible for any further reprojection if needed.
    """
    if not _initialized_project:
        raise RuntimeError("GEE not initialised. Call gee_service.initialize(project_id) first.")

    # Hard area check — fail fast with a clear message before hitting GEE
    result = check_area(perimeter_gdf, buffer_m)
    if not result["ok"]:
        raise ValueError(result["message"])

    # Buffer in projected UTM CRS — keep in UTM for the download too.
    # Downloading in UTM at scale=10m is safe and avoids GEE pixel-budget issues
    # that occur when mixing EPSG:4326 (geographic) with a metric scale value.
    centroid_lon = perimeter_gdf.to_crs(epsg=4326).geometry.centroid.iloc[0].x
    utm_epsg = _utm_epsg_from_lon(centroid_lon)
    buffered_utm = perimeter_gdf.to_crs(epsg=utm_epsg).buffer(buffer_m)
    buffered_wgs84 = buffered_utm.to_crs(epsg=4326)
    b = buffered_wgs84.total_bounds  # [minx, miny, maxx, maxy] in WGS84 for GEE region

    region = ee.Geometry.Rectangle([float(b[0]), float(b[1]), float(b[2]), float(b[3])])

    dem = ee.ImageCollection("USGS/3DEP/10m_collection").mosaic().select("elevation")

    url = dem.getDownloadURL({
        "scale": 10,
        "crs": f"EPSG:{utm_epsg}",   # download in UTM — metric CRS, no pixel-budget ambiguity
        "region": region,
        "format": "GEO_TIFF",
        "filePerBand": False,
    })

    response = requests.get(url, timeout=600)
    response.raise_for_status()

    # GEE now returns a raw GeoTIFF (Content-Type: image/tiff), not a ZIP.
    # Handle both formats for safety: TIFF magic bytes are b'II' or b'MM'.
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    magic = response.content[:2]
    if magic in (b"II", b"MM"):
        # Raw GeoTIFF — write directly
        with open(out_path, "wb") as dst:
            dst.write(response.content)
    elif magic == b"PK":
        # Legacy ZIP wrapper — extract the .tif
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
            f"The area may exceed GEE's per-request size limit. "
            f"Try drawing a smaller polygon.\nResponse preview: {snippet}"
        )

    return out_path


def _utm_epsg_from_lon(lon: float) -> int:
    """Return the UTM zone EPSG code (north hemisphere) for a given longitude."""
    zone = int((lon + 180) / 6) + 1
    return 32600 + zone
