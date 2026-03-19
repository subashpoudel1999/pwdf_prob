"""
Dolan Fire analysis using Google Earth Engine for DEM acquisition.

Inherits the full 10-step WhiteboxTools pipeline from DolanService.
Only Step 2 is overridden: instead of opening a local 1.1 GB GeoTIFF,
the DEM is downloaded on-demand from USGS 3DEP via the GEE API,
clipped to the fire perimeter + 1 km buffer (~20 MB download).

Steps 3–10 (fill depressions, D8 flow direction, flow accumulation,
stream extraction, sub-basin delineation, slope/burn stats, Staley model,
GeoJSON export) are completely unchanged from the parent class.

Zone analysis also uses GEE for the clipped zone DEM.
"""

import geopandas as gpd
import rasterio
from rasterio.crs import CRS
from rasterio.mask import mask as rio_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
from shapely.geometry import mapping
from pathlib import Path

import services.gee_service as gee_service
from services.dolan_service import (
    DolanService,
    DOLAN_PERIMETER,
    DOLAN_UTM_EPSG,
)


class DolanGeeService(DolanService):
    """
    Dolan Fire pipeline that fetches the DEM from GEE at runtime.
    The local 1.1 GB dolan_dem_3dep10m.tif is NOT required.
    All other inputs (fire perimeter, burn severity rasters) are still read locally.
    """

    def __init__(self, gee_project_id: str):
        super().__init__()
        self.gee_project_id = gee_project_id

    # ------------------------------------------------------------------
    # Override Step 2 — full fire analysis
    # ------------------------------------------------------------------

    def _step2_reproject_clip(self, job_id: str, work_dir: Path):
        """Download DEM from GEE, reproject to UTM 10N, clip to perimeter + 1 km."""
        self._update(job_id, 2, "Connecting to Google Earth Engine...", 10)
        gee_service.initialize(self.gee_project_id)

        perim = gpd.read_file(str(DOLAN_PERIMETER))
        perim_utm = perim.to_crs(epsg=DOLAN_UTM_EPSG)
        perim_wgs84 = perim.to_crs(epsg=4326)

        self._update(job_id, 2, "Downloading 3DEP 10m DEM from GEE (clipped to fire area)...", 13)
        dem_wgs84_path = str(work_dir / "dem_wgs84_gee.tif")
        gee_service.download_dem_clip(perim_wgs84, buffer_m=1000, out_path=dem_wgs84_path)

        self._update(job_id, 2, "Reprojecting GEE DEM to UTM Zone 10N...", 18)
        dem_utm_path = str(work_dir / "dem_utm.tif")
        with rasterio.open(dem_wgs84_path) as src:
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

        # Clip to fire perimeter + 1 km buffer (same as original step 2)
        buffered = perim_utm.buffer(1000)
        dem_clipped_path = str(work_dir / "dem_clipped.tif")
        with rasterio.open(dem_utm_path) as src:
            out_image, out_transform = rio_mask(
                src, [mapping(g) for g in buffered.geometry],
                crop=True, filled=True, nodata=-9999,
            )
            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1], "width": out_image.shape[2],
                "transform": out_transform, "nodata": -9999,
            })
            with rasterio.open(dem_clipped_path, "w", **out_meta) as dst:
                dst.write(out_image)

        return dem_clipped_path, perim_utm, perim_wgs84

    # ------------------------------------------------------------------
    # Override Step 2 — zone analysis
    # ------------------------------------------------------------------

    def _step2_reproject_clip_zone(self, job_id: str, work_dir: Path, polygon_geojson: dict):
        """Download DEM from GEE for user-drawn zone, reproject to UTM 10N, clip to polygon + 200 m."""
        self._update(job_id, 2, "Connecting to Google Earth Engine for zone...", 10)
        gee_service.initialize(self.gee_project_id)

        from shapely.geometry import shape as shp_shape
        user_geom = shp_shape(polygon_geojson)
        perim_wgs84 = gpd.GeoDataFrame(geometry=[user_geom], crs="EPSG:4326")
        perim_utm = perim_wgs84.to_crs(epsg=DOLAN_UTM_EPSG)

        self._update(job_id, 2, "Downloading zone DEM from GEE (3DEP 10m)...", 13)
        dem_wgs84_path = str(work_dir / "dem_wgs84_gee.tif")
        gee_service.download_dem_clip(perim_wgs84, buffer_m=200, out_path=dem_wgs84_path)

        self._update(job_id, 2, "Reprojecting zone DEM to UTM Zone 10N...", 18)
        dem_utm_path = str(work_dir / "dem_utm.tif")
        with rasterio.open(dem_wgs84_path) as src:
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

        buffered = perim_utm.buffer(200)
        dem_clipped_path = str(work_dir / "dem_clipped.tif")
        with rasterio.open(dem_utm_path) as src:
            out_image, out_transform = rio_mask(
                src, [mapping(g) for g in buffered.geometry],
                crop=True, filled=True, nodata=-9999,
            )
            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1], "width": out_image.shape[2],
                "transform": out_transform, "nodata": -9999,
            })
            with rasterio.open(dem_clipped_path, "w", **out_meta) as dst:
                dst.write(out_image)

        return dem_clipped_path, perim_utm, perim_wgs84
