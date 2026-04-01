"""
GEE Feature Extraction Service — Dolan Fire (2020)

Runs the full 4a notebook pipeline as a background job with step-by-step progress
and visualization images streamed back to the Flutter client.

Pipeline (10 steps):
  1.  GEE auth + connection test
  2.  Load fire perimeter + sub-basins → define GEE ROI
  3.  Download USGS 3DEP 10m DEM via geedim (auto-tiling, 2–5 min)
  4.  Run WhiteboxTools terrain analysis (slope / curvature / TWI / SPI)
  5.  Extract terrain zonal statistics per basin
  6.  Fetch Landsat-8 dNBR from GEE → download raster → viz
  7.  Extract ERA5-Land rainfall + soil moisture via GEE reduceRegions
  8.  Fetch NOAA Atlas 14 design storms per basin centroid
  9.  Fetch SoilGrids soil properties per basin centroid
  10. Assemble feature matrix → run RF v3 inference → return live GeoJSON

All paths follow the notebook (4a_gee_and_feature_extraction.ipynb) exactly.
Visualizations are returned as base64-encoded PNG strings in the status payload.
"""

from __future__ import annotations

import matplotlib
matplotlib.use('Agg')  # Force non-interactive backend for thread safety

import base64
import io
import json
import math
import subprocess
import threading
import time
import urllib.request
import uuid
import warnings
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


import numpy as np
import pandas as pd
import requests



warnings.filterwarnings("ignore")

# ── Path constants ────────────────────────────────────────────────────────────
_ML_DIR      = Path(r"C:\Users\J01040445\Downloads\1. Wildfire folders\c_dolan_ml_model")
_PERIM_SHP   = _ML_DIR / "data" / "perimeter" / "fire_perimeter.shp"
_BASINS_SHP  = _ML_DIR / "outputs" / "basins"   / "dolan_basins.shp"
_WBT_DIR     = Path(r"C:\wbt_dolan")
_WBT_EXE     = Path(r"C:\Users\J01040445\Downloads\1. Wildfire folders\WBT") / "whitebox_tools.exe"
_OUT_DIR     = _ML_DIR / "outputs" / "features"
_MODEL_PKL   = _ML_DIR / "outputs" / "models"   / "rf_model_v3.pkl"
_META_PKL    = _ML_DIR / "outputs" / "models"   / "rf_model_v3_meta.pkl"
_DEM_OUT     = _OUT_DIR / "gee_dem_live.tif"
_DNBR_OUT    = _OUT_DIR / "gee_dnbr_live.tif"
_FEAT_CSV    = _OUT_DIR / "dolan_basins_features_live.csv"

_STORM_DATE  = "2021-01-28"   # atmospheric river that triggered Dolan debris flows
_TOTAL_STEPS = 10

# ── Job store ─────────────────────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}


def _blank_job() -> Dict[str, Any]:
    return {
        "status":      "running",
        "step":        0,
        "total_steps": _TOTAL_STEPS,
        "step_name":   "Initializing…",
        "message":     "",
        "progress":    0,
        "elapsed_sec": 0,
        "started_at":  time.time(),
        "visualizations": {},
        "error":       None,
    }


# ─────────────────────────────────────────────────────────────────────────────

class GeeFeatureExtractionService:
    """Manages long-running GEE feature extraction jobs."""

    # ── Public API ────────────────────────────────────────────────────────────

    def start_extraction(self, gee_project: str,
                         redownload_dem: bool = False,
                         mode: str = "full") -> Dict:
        """
        mode='full'     — download everything fresh from GEE.
        mode='continue' — skip DEM + dNBR downloads if files exist;
                          re-run terrain/ERA5/NOAA/soil/ML from scratch.
        """
        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = _blank_job()
        t = threading.Thread(
            target=self._run,
            args=(job_id, gee_project, redownload_dem, mode),
            daemon=True,
        )
        t.start()
        return {"job_id": job_id, "status": "running", "mode": mode}

    def get_status(self, job_id: str) -> Dict:
        if job_id not in _jobs:
            return {"status": "not_found", "error": f"Job {job_id} not found"}
        j = dict(_jobs[job_id])
        j["elapsed_sec"] = int(time.time() - j["started_at"])
        return j

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update(self, job_id: str, step: int, step_name: str, message: str, progress: int):
        _jobs[job_id].update({
            "step":      step,
            "step_name": step_name,
            "message":   message,
            "progress":  progress,
        })

    def _add_viz(self, job_id: str, key: str, fig):
        """Encode a matplotlib figure as base64 PNG and store in job."""
        import matplotlib.pyplot as plt
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                    facecolor="#0D0B1F")
        plt.close(fig)
        b64 = base64.b64encode(buf.getvalue()).decode()
        _jobs[job_id]["visualizations"][key] = b64

    # ── Main pipeline ─────────────────────────────────────────────────────────

    def _run(self, job_id: str, gee_project: str, redownload_dem: bool, mode: str = "full"):
        try:
            ee, basins_gdf, roi_gee, roi_buffered = self._step1_gee_auth(job_id, gee_project)
            self._step2_load_perimeter(job_id, basins_gdf)
            self._step3_download_dem(job_id, ee, roi_buffered, redownload_dem, basins_gdf, mode)
            terrain_features = self._step4_terrain_analysis(job_id, basins_gdf)
            burn_features = self._step5_burn_severity(job_id, ee, roi_gee, roi_buffered, basins_gdf, mode)
            era5_features = self._step6_era5_rainfall(job_id, ee, roi_gee, basins_gdf)
            noaa_features = self._step7_noaa_atlas14(job_id, basins_gdf)
            soil_features = self._step8_soilgrids(job_id, basins_gdf)
            feat_csv_path = self._step9_assemble_features(
                job_id, basins_gdf, terrain_features, burn_features,
                era5_features, noaa_features, soil_features,
            )
            live_geojson = self._step10_run_inference(job_id, feat_csv_path, basins_gdf)
            _jobs[job_id].update({
                "status":      "complete",
                "progress":    100,
                "step_name":   "Complete",
                "message":     "Feature extraction and ML inference complete.",
                "live_geojson": live_geojson,
            })
        except Exception as exc:
            import traceback
            _jobs[job_id].update({
                "status":  "error",
                "error":   str(exc),
                "message": traceback.format_exc()[-500:],
            })

    # ── Step 1: GEE auth ──────────────────────────────────────────────────────

    def _step1_gee_auth(self, job_id: str, gee_project: str):
        import ee
        import geopandas as gpd
        self._update(job_id, 1, "GEE Authentication", f"Initializing GEE with project: {gee_project}…", 2)
        ee.Initialize(project=gee_project)

        self._update(job_id, 1, "GEE Authentication", "Testing connection — point query on Dolan area…", 5)
        test_pt  = ee.Geometry.Point([-121.45, 36.15])
        dem_test = ee.ImageCollection("USGS/3DEP/10m_collection").mosaic().select("elevation")
        elev     = dem_test.sample(test_pt, scale=10).first().get("elevation").getInfo()

        # Count Landsat scenes
        roi_buf  = test_pt.buffer(10000)
        l8_count = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                    .filterDate("2020-09-01", "2020-12-01")
                    .filterBounds(roi_buf)
                    .size().getInfo())

        self._update(job_id, 1, "GEE Authentication",
                     f"✓ Connected — elevation at test point: {elev:.0f} m | "
                     f"Landsat-8 post-fire scenes: {l8_count}", 8)

        # Build ROI from fire perimeter
        perim_wgs84 = gpd.read_file(str(_PERIM_SHP)).to_crs(epsg=4326)
        geom_geo    = perim_wgs84.geometry.values[0].__geo_interface__
        roi_gee     = ee.Geometry(geom_geo)
        roi_buffered = roi_gee.buffer(1000)

        basins_gdf = gpd.read_file(str(_BASINS_SHP)).to_crs(epsg=4326)
        return ee, basins_gdf, roi_gee, roi_buffered

    # ── Step 2: Perimeter overview viz ────────────────────────────────────────

    def _step2_load_perimeter(self, job_id: str, basins_gdf):
        import geopandas as gpd
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        self._update(job_id, 2, "Load Perimeter & Basins",
                     "Generating perimeter + basin overview…", 10)
        try:
            perim_wgs84 = gpd.read_file(str(_PERIM_SHP)).to_crs(epsg=4326)
            fig, ax = plt.subplots(figsize=(7, 6), facecolor="#0D0B1F")
            ax.set_facecolor("#0D0B1F")
            perim_wgs84.boundary.plot(ax=ax, color="#FF7043", linewidth=2, label="Fire perimeter")
            basins_gdf.boundary.plot(ax=ax, color="#80DEEA", linewidth=0.6,
                                     alpha=0.7, label=f"{len(basins_gdf)} sub-basins")
            basins_gdf.plot(ax=ax, color="#80DEEA", alpha=0.12)
            ax.set_title("Dolan Fire (2020) — Perimeter & Sub-Basins\n"
                         "(WGS84 / EPSG:4326)",
                         color="white", fontsize=11, pad=10)
            ax.tick_params(colors="white", labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor("#333")
            p1 = mpatches.Patch(color="#FF7043", label="Fire perimeter")
            p2 = mpatches.Patch(color="#80DEEA", alpha=0.7,
                                label=f"{len(basins_gdf)} GIS sub-basins")
            ax.legend(handles=[p1, p2], facecolor="#1a1a2e", labelcolor="white",
                      fontsize=9, loc="lower left")
            plt.tight_layout()
            self._add_viz(job_id, "perimeter", fig)
        except Exception:
            pass  # viz is optional

        self._update(job_id, 2, "Load Perimeter & Basins",
                     f"✓ {len(basins_gdf)} sub-basins loaded from dolan_basins.shp", 12)

    # ── Step 3: DEM download ──────────────────────────────────────────────────

    def _step3_download_dem(self, job_id: str, ee, roi_buffered,
                            redownload_dem: bool, basins_gdf, mode: str = "full"):
        import geedim as gd
        import rasterio
        import matplotlib.pyplot as plt
        import matplotlib.colors as mc

        skip_download = _DEM_OUT.exists() and (not redownload_dem or mode == "continue")
        if skip_download:
            reason = ("'Continue from downloads' mode" if mode == "continue"
                      else "Re-download DEM is off")
            self._update(job_id, 3, "Download DEM (GEE)",
                         f"✓ Using existing DEM: {_DEM_OUT.name} "
                         f"({_DEM_OUT.stat().st_size / 1e6:.1f} MB)\n"
                         f"  Reason: {reason}", 22)
        else:
            self._update(job_id, 3, "Download DEM (GEE)",
                         "Downloading USGS 3DEP 10m DEM via geedim (auto-tiling)…\n"
                         "This usually takes 2–5 minutes.", 14)
            dem_ee = ee.ImageCollection("USGS/3DEP/10m_collection").mosaic().select("elevation")
            gd_img = gd.MaskedImage(dem_ee)
            _OUT_DIR.mkdir(parents=True, exist_ok=True)
            gd_img.download(
                str(_DEM_OUT),
                region=roi_buffered,
                scale=10,
                crs="EPSG:32610",
                dtype="float32",
                overwrite=True,
                max_tile_size=32,
                max_requests=4,
            )
            self._update(job_id, 3, "Download DEM (GEE)",
                         f"✓ DEM downloaded ({_DEM_OUT.stat().st_size / 1e6:.1f} MB)", 21)

        # --- Visualization: DEM with basin outlines ---
        try:
            import rasterio
            from rasterio.plot import show as rio_show
            from rasterio.warp import calculate_default_transform, reproject, Resampling
            from rasterio.crs import CRS

            fig, ax = plt.subplots(figsize=(8, 6), facecolor="#0D0B1F")
            ax.set_facecolor("#111")
            with rasterio.open(str(_DEM_OUT)) as src:
                data = src.read(1, masked=True)
                valid = data.compressed()
                valid = valid[np.isfinite(valid)]
                rio_show(src, ax=ax, cmap="terrain", title="")
                raster_crs = src.crs

            # overlay basin boundaries in raster CRS
            basins_r = basins_gdf.to_crs(raster_crs)
            basins_r.boundary.plot(ax=ax, color="white", linewidth=0.5, alpha=0.6)

            ax.set_title(
                f"USGS 3DEP 10m DEM — Downloaded from GEE via geedim\n"
                f"Elevation range: {valid.min():.0f}–{valid.max():.0f} m  |  "
                f"Mean: {valid.mean():.0f} m",
                color="white", fontsize=10, pad=8,
            )
            ax.axis("off")
            plt.tight_layout()
            self._add_viz(job_id, "dem", fig)
        except Exception:
            pass

        self._update(job_id, 3, "Download DEM (GEE)",
                     "✓ DEM ready — terrain analysis next.", 22)

    # ── Step 4: WhiteboxTools terrain analysis ────────────────────────────────

    def _step4_terrain_analysis(self, job_id: str, basins_gdf) -> pd.DataFrame:
        import rasterio, rasterio.mask
        import matplotlib.pyplot as plt
        import matplotlib.colors as mc

        def run_wbt(tool, args):
            cmd = [str(_WBT_EXE), f"--run={tool}", f"--wd={_WBT_DIR}",
                   "--compress_rasters=false", "--max_procs=-1"] + args
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        terrain_files = {
            "slope.tif":   ("Slope",           ["--dem=dem_breached.tif", "-o=slope.tif", "--units=degrees"]),
            "plncurv.tif": ("PlanCurvature",   ["--dem=dem_breached.tif", "-o=plncurv.tif"]),
            "prfcurv.tif": ("ProfileCurvature",["--dem=dem_breached.tif", "-o=prfcurv.tif"]),
            "twi.tif":     ("WetnessIndex",    ["--sca=flow_acc.tif", "--slope=slope.tif", "-o=twi.tif"]),
            "spi.tif":     ("StreamPowerIndex",["--sca=flow_acc.tif", "--slope=slope.tif", "-o=spi.tif"]),
        }
        n = len(terrain_files)
        for i, (fname, (tool, args)) in enumerate(terrain_files.items()):
            fp = _WBT_DIR / fname
            pct = 24 + int(i / n * 8)
            if not fp.exists():
                self._update(job_id, 4, "Terrain Analysis (WhiteboxTools)",
                             f"Running {tool}…", pct)
                run_wbt(tool, args)
            else:
                self._update(job_id, 4, "Terrain Analysis (WhiteboxTools)",
                             f"✓ {fname} already exists, skipping.", pct)

        # --- Visualization: Slope map ---
        try:
            slope_path = _WBT_DIR / "slope.tif"
            if slope_path.exists():
                from rasterio.plot import show as rio_show
                from rasterio.windows import from_bounds
                # Pick the spotlight basin: steepest mean slope (most interesting)
                spotlight_idx = 0
                bas_r = basins_gdf.to_crs(
                    rasterio.open(str(slope_path)).crs)
                spotlight_geom = bas_r.iloc[spotlight_idx].geometry

                fig = plt.figure(figsize=(16, 5), facecolor="#0D0B1F")
                ax1 = fig.add_subplot(1, 3, 1)   # full slope map
                ax2 = fig.add_subplot(1, 3, 2)   # zoomed basin
                ax3 = fig.add_subplot(1, 3, 3)   # formula + histogram

                for ax in [ax1, ax2, ax3]:
                    ax.set_facecolor("#111")

                # --- ax1: full slope raster ---
                with rasterio.open(str(slope_path)) as src:
                    rio_show(src, ax=ax1, cmap="YlOrRd", title="")
                    bas_r.boundary.plot(ax=ax1, color="white",
                                        linewidth=0.4, alpha=0.4)
                    # highlight spotlight basin
                    bas_r.iloc[[spotlight_idx]].plot(
                        ax=ax1, facecolor="none",
                        edgecolor="#00E5FF", linewidth=1.5)
                ax1.set_title("Slope (°) — All Basins\n(cyan = spotlight basin)",
                              color="white", fontsize=9)
                ax1.axis("off")

                # --- ax2: zoomed-in spotlight basin ---
                with rasterio.open(str(slope_path)) as src:
                    b = spotlight_geom.bounds
                    pad = max((b[2]-b[0])*0.3, (b[3]-b[1])*0.3)
                    win = from_bounds(b[0]-pad, b[1]-pad,
                                      b[2]+pad, b[3]+pad, src.transform)
                    data_zoom = src.read(1, window=win, masked=True)
                    win_transform = src.window_transform(win)
                    valid_z = data_zoom.compressed()
                    valid_z = valid_z[np.isfinite(valid_z)]
                    ax2.imshow(data_zoom, cmap="YlOrRd",
                               vmin=0, vmax=float(np.nanpercentile(valid_z, 95))
                               if len(valid_z) > 0 else 45,
                               origin="upper", aspect="auto")
                    # draw basin boundary in pixel coords
                    from rasterio.transform import rowcol
                    xs, ys = spotlight_geom.exterior.xy
                    rows, cols = rowcol(win_transform, xs, ys)
                    ax2.plot(cols, rows, color="#00E5FF", linewidth=1.5)
                ax2.set_title(f"Zoom: Basin {spotlight_idx}\n"
                              f"({basins_gdf.iloc[spotlight_idx]['Sub_ID']})",
                              color="#00E5FF", fontsize=9)
                ax2.axis("off")

                # --- ax3: pixel histogram + formula ---
                with rasterio.open(str(slope_path)) as src:
                    m, _ = rasterio.mask.mask(
                        src, [spotlight_geom.__geo_interface__],
                        crop=True, nodata=np.nan)
                    pixels = m[0].flatten().astype(float)
                    pixels = pixels[np.isfinite(pixels)]

                if len(pixels) > 0:
                    mean_s  = float(np.nanmean(pixels))
                    max_s   = float(np.nanmax(pixels))
                    steep_p = float((pixels > 30).sum() / len(pixels) * 100)
                    ax3.hist(pixels, bins=20, color="#FF7043",
                             alpha=0.85, edgecolor="#222")
                    ax3.axvline(mean_s, color="#00E5FF", linewidth=2,
                                label=f"Mean = {mean_s:.1f}°")
                    ax3.axvline(30, color="#FFC107", linewidth=1.5,
                                linestyle="--", label="Steep threshold (30°)")
                    ax3.set_facecolor("#1a1a2e")
                    ax3.tick_params(colors="white", labelsize=8)
                    ax3.set_xlabel("Slope (°)", color="white", fontsize=8)
                    ax3.set_ylabel("Pixel count", color="white", fontsize=8)
                    ax3.legend(facecolor="#0D0B1F", labelcolor="white",
                               fontsize=7, loc="upper right")
                    formula = (
                        f"Slope_Mean  =  Σ slopeᵢ / N\n"
                        f"            =  {mean_s:.2f}°\n\n"
                        f"Slope_Max   =  {max_s:.1f}°\n"
                        f"Steep_Perc  =  pixels > 30° / N\n"
                        f"            =  {steep_p:.1f}%\n\n"
                        f"N = {len(pixels):,} pixels"
                    )
                    ax3.text(0.98, 0.98, formula,
                             transform=ax3.transAxes,
                             color="#00E5FF", fontsize=8, va="top", ha="right",
                             fontfamily="monospace",
                             bbox=dict(facecolor="#0D0B1F", alpha=0.7,
                                       edgecolor="#00E5FF22"))
                ax3.set_title("Slope distribution & formula\n(spotlight basin)",
                              color="white", fontsize=9)

                twi_path = _WBT_DIR / "twi.tif"
                plt.suptitle(
                    "WhiteboxTools Terrain Analysis — Dolan Fire\n"
                    "Left: all basins  |  Centre: spotlight basin  |  "
                    "Right: pixel distribution + feature formula",
                    color="white", fontsize=10, y=1.01)
                plt.tight_layout()
                self._add_viz(job_id, "terrain", fig)
        except Exception:
            pass

        # --- Zonal stats ---
        self._update(job_id, 4, "Terrain Analysis (WhiteboxTools)",
                     "Extracting zonal statistics per basin…", 33)

        def zonal(raster_path, basins, stats=("mean", "max", "std")):
            results = []
            with rasterio.open(str(raster_path)) as src:
                bas = basins.to_crs(src.crs)
                for _, row in bas.iterrows():
                    try:
                        m, _ = rasterio.mask.mask(src, [row.geometry.__geo_interface__],
                                                   crop=True, nodata=np.nan)
                        d = m[0].flatten().astype(float)
                        d = d[np.isfinite(d)]
                        if src.nodata is not None:
                            d = d[d != src.nodata]
                        if len(d) == 0:
                            results.append({s: np.nan for s in stats})
                        else:
                            results.append({
                                "mean": float(np.nanmean(d)),
                                "max":  float(np.nanmax(d)),
                                "std":  float(np.nanstd(d)),
                                "min":  float(np.nanmin(d)),
                            })
                    except Exception:
                        results.append({s: np.nan for s in stats})
            return results

        df = pd.DataFrame({"Sub_ID": basins_gdf["Sub_ID"].values})

        twi_s = zonal(_WBT_DIR / "twi.tif",   basins_gdf)
        df["TWI_Mean"]   = [r.get("mean", np.nan) for r in twi_s]
        df["TWI_Max"]    = [r.get("max",  np.nan) for r in twi_s]
        df["TWI_StdDev"] = [r.get("std",  np.nan) for r in twi_s]

        slp_s = zonal(_WBT_DIR / "slope.tif", basins_gdf)
        df["Slope_Mean"] = [r.get("mean", np.nan) for r in slp_s]

        spi_s = zonal(_WBT_DIR / "spi.tif",   basins_gdf)
        df["SPI_Mean"] = [r.get("mean", np.nan) for r in spi_s]
        df["SPI_Max"]  = [r.get("max",  np.nan) for r in spi_s]

        pc_s = zonal(_WBT_DIR / "plncurv.tif", basins_gdf)
        df["PlnCurv_M"]  = [r.get("mean", np.nan) for r in pc_s]
        df["PlnCurv_SD"] = [r.get("std",  np.nan) for r in pc_s]

        pr_s = zonal(_WBT_DIR / "prfcurv.tif", basins_gdf)
        df["PrfCurv_M"]  = [r.get("mean", np.nan) for r in pr_s]
        df["PrfCurv_SD"] = [r.get("std",  np.nan) for r in pr_s]

        # Basin morphometry from shapefile
        import geopandas as gpd
        bas_utm = basins_gdf.to_crs(epsg=32610)
        df["Basin_Rel"] = bas_utm.geometry.apply(
            lambda g: g.bounds[3] - g.bounds[1])  # approx relief from bbox
        areas   = bas_utm.geometry.area          # m²
        perims  = bas_utm.geometry.length        # m
        df["Circ_Ratio"]  = 4 * math.pi * areas / (perims ** 2)
        df["Elong_R"]     = 2 * np.sqrt(areas / math.pi) / perims
        df["Melton_R"]    = df["Basin_Rel"] / np.sqrt(areas)
        df["Relief_R"]    = df["Basin_Rel"] / perims
        df["Drain_Dens"]  = perims / (areas / 1e6)   # m / km²
        df["Steep_Perc"]  = [np.nan] * len(df)  # filled from slope raster below

        slp_steep = []
        with rasterio.open(str(_WBT_DIR / "slope.tif")) as src:
            bas_s = basins_gdf.to_crs(src.crs)
            for _, row in bas_s.iterrows():
                try:
                    m, _ = rasterio.mask.mask(src, [row.geometry.__geo_interface__],
                                               crop=True, nodata=np.nan)
                    d = m[0].flatten().astype(float)
                    d = d[np.isfinite(d)]
                    slp_steep.append(float((d > 30).sum() / max(len(d), 1)))
                except Exception:
                    slp_steep.append(np.nan)
        df["Steep_Perc"] = slp_steep

        self._update(job_id, 4, "Terrain Analysis (WhiteboxTools)",
                     f"✓ Terrain features extracted for {len(df)} basins.", 36)
        return df

    # ── Step 5: Burn severity (Landsat-8 via GEE) ─────────────────────────────

    def _step5_burn_severity(self, job_id: str, ee, roi_gee, roi_buffered,
                             basins_gdf, mode: str = "full") -> pd.DataFrame:
        import rasterio, rasterio.mask
        import matplotlib.pyplot as plt
        import matplotlib.colors as mc
        from rasterio.plot import show as rio_show

        self._update(job_id, 5, "Burn Severity (Landsat-8 / GEE)",
                     "Fetching Landsat-8 pre/post-fire imagery…", 37)

        def scale_l8(img):
            optical = img.select("SR_B.").multiply(0.0000275).add(-0.2)
            return img.addBands(optical, overwrite=True)

        def compute_nbr(img):
            nir  = img.select("SR_B5")
            swir = img.select("SR_B7")
            return nir.subtract(swir).divide(nir.add(swir)).rename("NBR")

        pre_col = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                   .filterDate("2020-04-01", "2020-07-01")
                   .filterBounds(roi_gee)
                   .filter(ee.Filter.lt("CLOUD_COVER", 30))
                   .map(scale_l8))
        post_col = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                    .filterDate("2020-09-15", "2020-12-01")
                    .filterBounds(roi_gee)
                    .filter(ee.Filter.lt("CLOUD_COVER", 30))
                    .map(scale_l8))

        pre_count  = pre_col.size().getInfo()
        post_count = post_col.size().getInfo()
        self._update(job_id, 5, "Burn Severity (Landsat-8 / GEE)",
                     f"Pre-fire scenes: {pre_count}  |  Post-fire scenes: {post_count}\n"
                     "Computing dNBR composite…", 40)

        pre_nbr  = compute_nbr(pre_col.median())
        post_nbr = compute_nbr(post_col.median())
        dnbr     = pre_nbr.subtract(post_nbr).multiply(1000).rename("dNBR")

        # Download dNBR raster — always fresh unless 'continue' mode + file exists
        if mode == "continue" and _DNBR_OUT.exists():
            self._update(job_id, 5, "Burn Severity (Landsat-8 / GEE)",
                         f"✓ Using existing dNBR raster: {_DNBR_OUT.name} "
                         f"({_DNBR_OUT.stat().st_size / 1e6:.1f} MB)\n"
                         "  (Continue mode — skipping GEE download)", 43)
        else:
            _DNBR_OUT.unlink(missing_ok=True)
            self._update(job_id, 5, "Burn Severity (Landsat-8 / GEE)",
                         "Downloading dNBR raster from GEE…", 42)
            url = dnbr.getDownloadURL({
                "region": roi_buffered,
                "scale":  30,
                "crs":    "EPSG:32610",
                "format": "GEO_TIFF",
            })
            tmp_zip = str(_DNBR_OUT).replace(".tif", ".zip")
            urllib.request.urlretrieve(url, tmp_zip)
            if zipfile.is_zipfile(tmp_zip):
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    tif_name = [n for n in zf.namelist() if n.endswith(".tif")][0]
                    zf.extract(tif_name, str(_OUT_DIR))
                    (Path(_OUT_DIR) / tif_name).rename(_DNBR_OUT)
                Path(tmp_zip).unlink(missing_ok=True)
            else:
                Path(tmp_zip).rename(_DNBR_OUT)

        # Visualize dNBR — full map + spotlight basin + severity breakdown
        try:
            from rasterio.windows import from_bounds as fb
            from rasterio.transform import rowcol

            # Choose spotlight: basin with highest mean dNBR (most burned)
            with rasterio.open(str(_DNBR_OUT)) as src:
                bas_r = basins_gdf.to_crs(src.crs)
                means = []
                for _, row in bas_r.iterrows():
                    try:
                        m, _ = rasterio.mask.mask(
                            src, [row.geometry.__geo_interface__],
                            crop=True, nodata=np.nan)
                        d = m[0].flatten().astype(float)
                        means.append(float(np.nanmean(d[np.isfinite(d)])))
                    except Exception:
                        means.append(0.0)
            spotlight_idx = int(np.argmax(means))
            spotlight_geom = bas_r.iloc[spotlight_idx].geometry

            fig = plt.figure(figsize=(16, 5), facecolor="#0D0B1F")
            ax1 = fig.add_subplot(1, 3, 1)
            ax2 = fig.add_subplot(1, 3, 2)
            ax3 = fig.add_subplot(1, 3, 3)
            for ax in [ax1, ax2, ax3]:
                ax.set_facecolor("#111")

            # ax1: full dNBR map
            with rasterio.open(str(_DNBR_OUT)) as src:
                full_data = src.read(1, masked=True)
                im = ax1.imshow(full_data, cmap="RdYlGn_r", vmin=0, vmax=800,
                                origin="upper", aspect="auto")
                bas_r.boundary.plot(ax=ax1, color="white",
                                    linewidth=0.3, alpha=0.4)
                bas_r.iloc[[spotlight_idx]].plot(
                    ax=ax1, facecolor="none",
                    edgecolor="#00E5FF", linewidth=1.5)
                plt.colorbar(im, ax=ax1, fraction=0.035, pad=0.02,
                             label="dNBR").ax.yaxis.label.set_color("white")
            ax1.set_title("Landsat-8 dNBR — All Basins\n"
                          "Pre: Apr–Jul 2020  |  Post: Sep–Dec 2020",
                          color="white", fontsize=9)
            ax1.axis("off")

            # ax2: zoomed spotlight basin
            with rasterio.open(str(_DNBR_OUT)) as src:
                b = spotlight_geom.bounds
                pad = max((b[2]-b[0])*0.4, (b[3]-b[1])*0.4)
                win = fb(b[0]-pad, b[1]-pad, b[2]+pad, b[3]+pad, src.transform)
                zoom_data = src.read(1, window=win, masked=True)
                win_t = src.window_transform(win)
                ax2.imshow(zoom_data, cmap="RdYlGn_r", vmin=0, vmax=800,
                           origin="upper", aspect="auto")
                xs, ys = spotlight_geom.exterior.xy
                rows, cols = rowcol(win_t, xs, ys)
                ax2.plot(cols, rows, color="#00E5FF", linewidth=2)
            ax2.set_title(
                f"Spotlight: {basins_gdf.iloc[spotlight_idx]['Sub_ID']}\n"
                f"(highest mean dNBR = {means[spotlight_idx]:.0f})",
                color="#00E5FF", fontsize=9)
            ax2.axis("off")

            # ax3: severity class breakdown + formula
            with rasterio.open(str(_DNBR_OUT)) as src:
                m, _ = rasterio.mask.mask(
                    src, [spotlight_geom.__geo_interface__],
                    crop=True, nodata=np.nan)
                pixels = m[0].flatten().astype(float)
                pixels = pixels[np.isfinite(pixels)]

            if len(pixels) > 0:
                n = len(pixels)
                bh  = float((pixels > 740).sum() / n * 100)
                bm  = float(((pixels > 436) & (pixels <= 740)).sum() / n * 100)
                bl  = float(((pixels > 100) & (pixels <= 436)).sum() / n * 100)
                bun = float((pixels <= 100).sum() / n * 100)
                cats   = ["Unburned\n(≤100)", "Low\n(101–436)",
                          "Moderate\n(437–740)", "High\n(>740)"]
                vals   = [bun, bl, bm, bh]
                colors = ["#4CAF50", "#FFEB3B", "#FF5722", "#B71C1C"]
                bars = ax3.bar(cats, vals, color=colors, alpha=0.85,
                               edgecolor="#222")
                for bar, v in zip(bars, vals):
                    ax3.text(bar.get_x() + bar.get_width()/2,
                             bar.get_height() + 0.5,
                             f"{v:.1f}%", ha="center", va="bottom",
                             color="white", fontsize=8)
                ax3.set_ylim(0, max(vals) * 1.25)
                ax3.set_facecolor("#1a1a2e")
                ax3.tick_params(colors="white", labelsize=7)
                ax3.set_ylabel("% of basin pixels", color="white", fontsize=8)
                formula = (
                    f"Burn_High  = pixels > 740  / N = {bh:.1f}%\n"
                    f"Burn_Mod   = 436 < d ≤ 740 / N = {bm:.1f}%\n"
                    f"Burn_HM    = pixels > 436  / N = {bh+bm:.1f}%\n\n"
                    f"N = {n:,} pixels  |  30 m/px"
                )
                ax3.text(0.98, 0.98, formula,
                         transform=ax3.transAxes,
                         color="#00E5FF", fontsize=7.5, va="top", ha="right",
                         fontfamily="monospace",
                         bbox=dict(facecolor="#0D0B1F", alpha=0.75,
                                   edgecolor="#00E5FF22"))
            ax3.set_title("Burn severity classes & formula\n(spotlight basin)",
                          color="white", fontsize=9)

            plt.suptitle(
                "Burn Severity — Dolan Fire 2020 (Landsat-8 via GEE)\n"
                "Left: all basins  |  Centre: highest-burn spotlight  |  "
                "Right: class breakdown + ML feature formulas",
                color="white", fontsize=10, y=1.01)
            plt.tight_layout()
            self._add_viz(job_id, "dnbr", fig)
        except Exception:
            pass

        # Per-basin burn stats
        self._update(job_id, 5, "Burn Severity (Landsat-8 / GEE)",
                     "Extracting burn severity per basin…", 46)
        burn_high, burn_mod, burn_hm, rdnbr_mean, burn_patch = [], [], [], [], []
        with rasterio.open(str(_DNBR_OUT)) as src:
            bas = basins_gdf.to_crs(src.crs)
            for _, row in bas.iterrows():
                try:
                    m, _ = rasterio.mask.mask(src, [row.geometry.__geo_interface__],
                                               crop=True, nodata=np.nan)
                    d = m[0].flatten().astype(float)
                    d = d[np.isfinite(d)]
                    if len(d) == 0:
                        burn_high.append(np.nan); burn_mod.append(np.nan)
                        burn_hm.append(np.nan); rdnbr_mean.append(np.nan)
                        burn_patch.append(np.nan)
                    else:
                        n   = len(d)
                        bh  = float((d > 740).sum() / n)
                        bm  = float(((d > 436) & (d <= 740)).sum() / n)
                        bhm = float((d > 436).sum() / n)
                        burn_high.append(bh); burn_mod.append(bm)
                        burn_hm.append(bhm)
                        rdnbr_mean.append(float(np.nanmean(d) / 100))
                        burn_patch.append(bhm)
                except Exception:
                    burn_high.append(np.nan); burn_mod.append(np.nan)
                    burn_hm.append(np.nan); rdnbr_mean.append(np.nan)
                    burn_patch.append(np.nan)

        df = pd.DataFrame({
            "Sub_ID":     basins_gdf["Sub_ID"].values,
            "Burn_High":  burn_high,
            "Burn_Mod":   burn_mod,
            "Burn_HM":    burn_hm,
            "RdNBR_Mean": rdnbr_mean,
            "Burn_Patch": burn_patch,
        })
        self._update(job_id, 5, "Burn Severity (Landsat-8 / GEE)",
                     f"✓ Burn severity extracted for {len(df)} basins.", 49)
        return df

    # ── Step 6: ERA5-Land rainfall + soil moisture ────────────────────────────

    def _step6_era5_rainfall(self, job_id: str, ee, roi_gee, basins_gdf) -> pd.DataFrame:
        self._update(job_id, 6, "ERA5-Land Rainfall (GEE)",
                     f"Querying ECMWF/ERA5_LAND/HOURLY — storm: {_STORM_DATE}…", 50)

        storm_dt     = datetime.strptime(_STORM_DATE, "%Y-%m-%d")
        window_start = (storm_dt - timedelta(days=15)).strftime("%Y-%m-%d")
        window_end   = (storm_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        era5 = (ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
                .filterDate(window_start, window_end)
                .filterBounds(roi_gee)
                .select(["total_precipitation_hourly", "volumetric_soil_water_layer_1"]))

        n_img = era5.size().getInfo()
        self._update(job_id, 6, "ERA5-Land Rainfall (GEE)",
                     f"✓ {n_img} hourly ERA5 images fetched (15-day window)\n"
                     "Computing rainfall features…", 53)

        # prcp_int60: max hourly on storm day
        storm_hourly = (era5.filterDate(_STORM_DATE, window_end)
                        .select("total_precipitation_hourly")
                        .max().multiply(1000).rename("prcp_int60"))

        # prcp_acc: 24-hour accumulation
        prcp_acc = (era5.filterDate(_STORM_DATE, window_end)
                    .select("total_precipitation_hourly")
                    .sum().multiply(1000).rename("prcp_acc"))

        # prcp_api: antecedent precipitation index (k=0.85)
        api_imgs = []
        for d in range(1, 15):
            d0 = (storm_dt - timedelta(days=d)).strftime("%Y-%m-%d")
            d1 = (storm_dt - timedelta(days=d - 1)).strftime("%Y-%m-%d")
            daily = (era5.filterDate(d0, d1)
                     .select("total_precipitation_hourly")
                     .sum().multiply(1000 * (0.85 ** d)))
            api_imgs.append(daily)
        prcp_api = ee.ImageCollection(api_imgs).sum().rename("prcp_api")

        # SM_Pre: soil moisture 24h before storm
        sm_date = (storm_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        sm_img  = (era5.filterDate(sm_date, _STORM_DATE)
                   .select("volumetric_soil_water_layer_1")
                   .mean().rename("SM_Pre"))

        combined = storm_hourly.addBands(prcp_acc).addBands(prcp_api).addBands(sm_img)

        # Convert basins to GEE FeatureCollection
        bas_wgs84 = basins_gdf.to_crs(epsg=4326)
        basin_feats = [
            ee.Feature(ee.Geometry(r.geometry.__geo_interface__), {"Sub_ID": r["Sub_ID"]})
            for _, r in bas_wgs84.iterrows()
        ]
        basins_fc = ee.FeatureCollection(basin_feats)

        self._update(job_id, 6, "ERA5-Land Rainfall (GEE)",
                     "Running reduceRegions per basin (ERA5 ~9 km res)…", 57)

        result = combined.reduceRegions(
            collection=basins_fc,
            reducer=ee.Reducer.mean(),
            scale=11132,
        ).getInfo()

        rows = []
        for feat in result["features"]:
            p = feat["properties"]
            rows.append({
                "Sub_ID":     p.get("Sub_ID", ""),
                "prcp_int60": p.get("prcp_int60", np.nan),
                "prcp_acc":   p.get("prcp_acc",   np.nan),
                "prcp_api":   p.get("prcp_api",   np.nan),
                "SM_Pre":     p.get("SM_Pre",     np.nan),
            })
        df = pd.DataFrame(rows)

        # ERA5 visualization: bar chart of prcp_int60 per basin
        try:
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, 2, figsize=(12, 4), facecolor="#0D0B1F")
            for ax in axes:
                ax.set_facecolor("#1a1a2e")

            vals_int = df["prcp_int60"].fillna(0).values
            vals_acc = df["prcp_acc"].fillna(0).values
            xs = np.arange(len(df))

            axes[0].bar(xs, vals_int, color="#80DEEA", width=1.0, alpha=0.85)
            axes[0].set_title(f"Max 60-min Rainfall Intensity\n(Storm: {_STORM_DATE})",
                              color="white", fontsize=10)
            axes[0].set_xlabel("Sub-basin index", color="white", fontsize=8)
            axes[0].set_ylabel("mm/hr", color="white", fontsize=8)
            axes[0].tick_params(colors="white")
            axes[0].axhline(np.nanmean(vals_int), color="#FF7043",
                            linestyle="--", linewidth=1.5, label=f"Mean: {np.nanmean(vals_int):.1f}")
            axes[0].legend(facecolor="#0D0B1F", labelcolor="white", fontsize=8)

            axes[1].bar(xs, vals_acc, color="#CE93D8", width=1.0, alpha=0.85)
            axes[1].set_title(f"24-hr Accumulated Rainfall\n(Storm: {_STORM_DATE})",
                              color="white", fontsize=10)
            axes[1].set_xlabel("Sub-basin index", color="white", fontsize=8)
            axes[1].set_ylabel("mm", color="white", fontsize=8)
            axes[1].tick_params(colors="white")

            sm_mean = df["SM_Pre"].mean()
            plt.suptitle(
                f"ERA5-Land Rainfall Features — Dolan Fire Watersheds\n"
                f"Pre-storm soil moisture: {sm_mean:.3f} m³/m³ (ERA5-Land layer 1, "
                f"24h before storm)",
                color="white", fontsize=10, y=1.02,
            )
            plt.tight_layout()
            self._add_viz(job_id, "era5", fig)
        except Exception:
            pass

        self._update(job_id, 6, "ERA5-Land Rainfall (GEE)",
                     f"✓ ERA5 features extracted. prcp_int60 mean: "
                     f"{df['prcp_int60'].mean():.2f} mm/hr", 60)
        return df

    # ── Step 7: NOAA Atlas 14 ─────────────────────────────────────────────────

    def _step7_noaa_atlas14(self, job_id: str, basins_gdf) -> pd.DataFrame:
        self._update(job_id, 7, "NOAA Atlas 14 Design Storms",
                     f"Fetching 10-yr return period intensities for "
                     f"{len(basins_gdf)} basin centroids…", 61)

        def get_atlas14(lat, lon):
            headers = {"User-Agent": "Mozilla/5.0 (Wildfire Research; Academic)"}
            url = (f"https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/fe_text_mean.csv"
                   f"?lat={lat}&lon={lon}&type=pf&data=intensity&units=metric&series=pds")
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    return {}
                lines = resp.text.strip().split("\n")
                data_lines, started = [], False
                for ln in lines:
                    if "ari (years):" in ln.lower():
                        started = True
                    if started and ln.strip():
                        data_lines.append(ln)
                if not data_lines:
                    return {}
                header = [h.strip().lower() for h in data_lines[0].split(",")]
                col10 = next(
                    (i for i, h in enumerate(header) if h in ("10", "10yr", "10-yr")),
                    None,
                )
                result = {}
                for ln in data_lines[1:]:
                    parts = ln.split(",")
                    dur = parts[0].strip().lower().replace(":", "")
                    if col10 and col10 < len(parts):
                        try:
                            result[dur] = float(parts[col10].strip())
                        except ValueError:
                            pass
                return result
            except Exception:
                return {}

        bas_wgs84 = basins_gdf.to_crs(epsg=4326)
        rows = []
        n = len(bas_wgs84)
        for i, (_, row) in enumerate(bas_wgs84.iterrows()):
            if i % 10 == 0:
                self._update(job_id, 7, "NOAA Atlas 14 Design Storms",
                             f"Basin {i+1}/{n} — fetching NOAA Atlas 14…", 61 + int(i / n * 5))
            c = row.geometry.centroid
            r = get_atlas14(c.y, c.x)
            rows.append({
                "Sub_ID":   row["Sub_ID"],
                "P15_10yr": r.get("15-min", np.nan),
                "P30_10yr": r.get("30-min", np.nan),
                "P60_10yr": r.get("60-min", np.nan),
            })
            time.sleep(0.05)  # gentle rate-limiting

        df = pd.DataFrame(rows)
        ok = df["P60_10yr"].notna().sum()
        self._update(job_id, 7, "NOAA Atlas 14 Design Storms",
                     f"✓ NOAA Atlas 14 fetched for {ok}/{n} basins.", 66)
        return df

    # ── Step 8: SoilGrids (Optimized via GEE Vectorization) ────────────────────

    def _step8_soilgrids(self, job_id: str, basins_gdf) -> pd.DataFrame:
        import ee
        self._update(job_id, 8, "SoilGrids v2.0 Soil Properties",
                     f"Fetching soil properties for {len(basins_gdf)} basins via GEE vectorized query…", 67)

        # 1. Convert basins to GEE FeatureCollection (Uses the same logic as your Step 6)
        bas_wgs84 = basins_gdf.to_crs(epsg=4326)
        basin_feats = [
            ee.Feature(ee.Geometry(r.geometry.__geo_interface__), {"Sub_ID": r["Sub_ID"]})
            for _, r in bas_wgs84.iterrows()
        ]
        basins_fc = ee.FeatureCollection(basin_feats)

        # 2. Access SoilGrids v2.0 layers directly in GEE
        # We average the 0-5cm, 5-15cm, and 15-30cm layers for a representative 0-30cm topsoil mean
        def get_topsoil_layer(prop_name):
            img = ee.Image(f"projects/soilgrids-isric/{prop_name}_mean")
            return (img.select([f"{prop_name}_0-5cm_mean", 
                               f"{prop_name}_5-15cm_mean", 
                               f"{prop_name}_15-30cm_mean"])
                    .reduce(ee.Reducer.mean())
                    .rename(prop_name))

        # Stack properties into one multi-band image: clay, sand, silt, soc, bdod
        # This allows us to fetch all data in a single "trip" to the GEE server
        properties = ['clay', 'sand', 'silt', 'soc', 'bdod']
        combined_soil_img = ee.Image.cat([get_topsoil_layer(p) for p in properties])

        self._update(job_id, 8, "SoilGrids v2.0 Soil Properties",
                     "Running GEE zonal statistics (250m scale)…", 69)

        # 3. Vectorized zonal statistics: calculates the mean value for every basin area simultaneously
        result = combined_soil_img.reduceRegions(
            collection=basins_fc,
            reducer=ee.Reducer.mean(),
            scale=250
        ).getInfo()

        # 4. Parse results with unit conversions matching your Random Forest v3 training
        rows = []
        for feat in result["features"]:
            p = feat["properties"]
            
            # Unit conversions: SoilGrids GEE assets use decigrams per kilogram (dg/kg)
            # Your model expects percentages (0-100). (val / 10) = percentage scale.
            clay = (p.get("clay", np.nan) or np.nan) / 10.0
            sand = (p.get("sand", np.nan) or np.nan) / 10.0
            silt = (p.get("silt", np.nan) or np.nan) / 10.0
            soc  = (p.get("soc",  np.nan) or np.nan) / 10.0 
            bdod = (p.get("bdod", np.nan) or np.nan) / 100.0 # cg/cm³ → g/cm³ (Bulk Density)

            # Maintain your specific USLE K_Factor and Soil Water Capacity formulas
            k_fac = 0.0017 * sand + 0.0036 * silt + 0.003 * clay if not np.isnan(clay) else np.nan
            
            rows.append({
                "Sub_ID":    p.get("Sub_ID", ""),
                "Clay_Perc": clay,
                "Sand_Perc": sand,
                "Silt_Perc": silt,
                "OM_Perc":   soc,
                "Ksat_Mean": bdod, # Using Bulk Density as the proxy consistent with your existing code
                "Soil_WHC":  silt + 0.5 * clay if not np.isnan(clay) else np.nan,
                "Soil_Depth": 30.0,
                "K_Factor":  k_fac,
            })

        df = pd.DataFrame(rows)
        ok = df["Clay_Perc"].notna().sum()
        self._update(job_id, 8, "SoilGrids v2.0 Soil Properties",
                     f"✓ Soil extraction complete. {ok}/{len(basins_gdf)} basins processed successfully.", 73)
        return df

    # ── Step 9: Assemble feature matrix ──────────────────────────────────────

    def _step9_assemble_features(
        self, job_id: str, basins_gdf,
        terrain_df: pd.DataFrame,
        burn_df: pd.DataFrame,
        era5_df: pd.DataFrame,
        noaa_df: pd.DataFrame,
        soil_df: pd.DataFrame,
    ) -> Path:
        import matplotlib.pyplot as plt

        self._update(job_id, 9, "Assemble Feature Matrix",
                     "Merging all feature tables → feature matrix CSV…", 74)

        merged = terrain_df.copy()
        for df in [burn_df, era5_df, noaa_df, soil_df]:
            merged = merged.merge(df, on="Sub_ID", how="left")

        # Ensure column order matches model expectations
        try:
            import joblib
            meta  = joblib.load(str(_META_PKL))
            feat_cols = meta["feature_cols"]
            present   = [c for c in feat_cols if c in merged.columns]
            missing   = [c for c in feat_cols if c not in merged.columns]
            if missing:
                for c in missing:
                    merged[c] = np.nan
        except Exception:
            feat_cols = list(merged.columns[1:])  # fallback

        merged.to_csv(str(_FEAT_CSV), index=False)

        # --- Visualization: feature overview ---
        try:
            key_features = ["TWI_Mean", "Slope_Mean", "Burn_HM", "RdNBR_Mean",
                            "prcp_int60", "Clay_Perc", "P60_10yr", "SPI_Mean"]
            key_features = [f for f in key_features if f in merged.columns]
            n_feats = len(key_features)
            cols = 4
            rows = math.ceil(n_feats / cols)
            fig, axes = plt.subplots(rows, cols, figsize=(14, 3.5 * rows),
                                     facecolor="#0D0B1F")
            axes = axes.flatten()
            for i, feat in enumerate(key_features):
                ax = axes[i]
                ax.set_facecolor("#1a1a2e")
                vals = merged[feat].dropna().values
                ax.hist(vals, bins=15, color="#7C4DFF", alpha=0.85, edgecolor="#333")
                ax.set_title(feat, color="white", fontsize=9)
                ax.tick_params(colors="white", labelsize=7)
                ax.axvline(np.nanmean(vals), color="#FF7043",
                           linestyle="--", linewidth=1.5)
                for spine in ax.spines.values():
                    spine.set_edgecolor("#333")
            for j in range(n_feats, len(axes)):
                axes[j].set_visible(False)
            plt.suptitle(
                f"Feature Distributions — {len(merged)} Dolan Fire Sub-basins\n"
                "(Red dashed = mean; {n_feats} of 37 ML features shown)",
                color="white", fontsize=11, y=1.01,
            )
            plt.tight_layout()
            self._add_viz(job_id, "features", fig)
        except Exception:
            pass

        n_ok = int(merged.notna().all(axis=1).sum())
        self._update(job_id, 9, "Assemble Feature Matrix",
                     f"✓ Feature matrix saved: {_FEAT_CSV.name}\n"
                     f"  {len(merged)} basins × {len(merged.columns)} columns  |  "
                     f"{n_ok} fully-complete rows", 82)
        return _FEAT_CSV

    # ── Step 10: RF inference → live GeoJSON ─────────────────────────────────

    def _step10_run_inference(self, job_id: str, feat_csv: Path,
                              basins_gdf) -> Dict:
        import joblib
        import geopandas as gpd
        import matplotlib.pyplot as plt

        self._update(job_id, 10, "ML Inference (RF v3)",
                     "Loading Random Forest model v3…", 83)

        rf   = joblib.load(str(_MODEL_PKL))
        meta = joblib.load(str(_META_PKL))
        feat_cols = meta["feature_cols"]
        threshold = float(meta["threshold"])

        self._update(job_id, 10, "ML Inference (RF v3)",
                     f"Running predict_proba on {len(basins_gdf)} basins "
                     f"(threshold={threshold:.4f})…", 87)

        feat_df = pd.read_csv(str(feat_csv))
        X       = feat_df[feat_cols]
        probs   = rf.predict_proba(X)[:, 1]
        preds   = (probs >= threshold).astype(int)

        def risk_tier(p: float) -> str:
            if p < 0.25:  return "Low"
            if p < 0.50:  return "Moderate"
            if p < 0.75:  return "High"
            return "Very High"

        basins_out = basins_gdf.to_crs(epsg=4326).copy()
        basins_out = basins_out.merge(
            feat_df[["Sub_ID"]].assign(
                ML_Prob=np.round(probs, 4),
                ML_Pred=preds,
                Risk_Category=[risk_tier(p) for p in probs],
                Probability_Pct=np.round(probs * 100, 1),
            ),
            on="Sub_ID", how="left",
        )

        cols = ["Sub_ID", "Segment_ID", "Area_km2",
                "ML_Prob", "ML_Pred", "Risk_Category", "Probability_Pct", "geometry"]
        cols = [c for c in cols if c in basins_out.columns]
        live_geojson = json.loads(basins_out[cols].to_json())

        # --- Visualization: probability map ---
        try:
            from matplotlib.colors import LinearSegmentedColormap
            cmap = LinearSegmentedColormap.from_list(
                "risk", [(0,"#4CAF50"),(0.25,"#FFC107"),(0.5,"#FF5722"),(1,"#B71C1C")])
            fig, ax = plt.subplots(figsize=(8, 6), facecolor="#0D0B1F")
            ax.set_facecolor("#111")
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=1))
            for _, row in basins_out.iterrows():
                p = float(row.get("ML_Prob", 0) or 0)
                color = cmap(p)
                xs = [c[0] for c in row.geometry.exterior.coords]
                ys = [c[1] for c in row.geometry.exterior.coords]
                ax.fill(xs, ys, color=color, alpha=0.8)
                ax.plot(xs, ys, color="white", linewidth=0.3, alpha=0.4)
            plt.colorbar(sm, ax=ax, label="Debris-flow probability",
                         fraction=0.03, pad=0.02).ax.yaxis.label.set_color("white")
            high = (preds == 1).sum()
            ax.set_title(
                f"RF v3 Debris-flow Probability — Fresh Inference\n"
                f"{len(probs)} basins  |  {high} predicted positive "
                f"(threshold={threshold:.2f})  |  Mean prob: {probs.mean():.2%}",
                color="white", fontsize=10, pad=8,
            )
            ax.axis("off")
            plt.tight_layout()
            self._add_viz(job_id, "ml_prob", fig)
        except Exception:
            pass

        self._update(job_id, 10, "ML Inference (RF v3)",
                     f"✓ Inference complete. {(preds==1).sum()} basins predicted "
                     f"positive out of {len(preds)} (threshold={threshold:.4f}).", 97)
        return live_geojson
