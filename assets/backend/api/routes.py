"""
API Routes — fire_webapp4 (Module 4: Wildcat x MHRI Fusion only).

This is a trimmed copy of fire_webapp2's api/routes.py: it keeps just the
endpoints the MHRI Fusion Flutter screen calls, so this standalone app
doesn't need the other three modules' services (Dolan/Retro/ML/CZU).

Flow:
  1. POST /wildcat/fires/upload                    — upload a user AOI
  2. POST /wildcat/fires/{fire_id}/prepare          — GEE DEM + dNBR download
  3. GET  /wildcat/prepare/status/{job_id}
  4. POST /wildcat/fires/{fire_id}/analyze          — run Wildcat pipeline
  5. GET  /wildcat/analyze/status/{job_id}
  6. GET  /wildcat/fires/{fire_id}/results          — debris-flow basins
  7. GET  /wildcat/fires/{fire_id}/perimeter        — AOI outline
  8. GET  /mhri/fires/{fire_id}/results             — fused MHRI grid
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Any, Dict, List

import services.wildcat_generic_service as _wg
import services.wildcat_fire_prep_service as _fp
import services.wildcat_upload_service as _up
import services.mhri_fusion_service as _mhri

router = APIRouter()


# ===========================================================================
# Wildcat run settings (sent from the Flutter "Run Wildcat" step)
# ===========================================================================

class WildcatSettings(BaseModel):
    """User-configurable Wildcat parameters sent from the Flutter UI."""
    I15_mm_hr: List[float] = [16.0, 20.0, 24.0, 40.0]
    kf: float = 0.2
    min_area_km2: float = 0.025
    min_slope: float = 0.12
    min_burn_ratio: float = 0.25
    locate_basins: bool = True
    buffer_km: float = 3.0
    severity_thresholds: List[float] = [125.0, 250.0, 500.0]


# ===========================================================================
# Wildcat Generic — analyze + status + results + perimeter
# ===========================================================================

class WildcatGenericAnalyzeRequest(BaseModel):
    force:    bool            = False
    settings: WildcatSettings = WildcatSettings()


@router.post("/wildcat/fires/{fire_id:path}/analyze")
def start_wildcat_fire_analysis(fire_id: str, request: WildcatGenericAnalyzeRequest):
    try:
        return _wg.start_analysis(fire_id, request.settings, force=request.force)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wildcat/analyze/status/{job_id}")
def get_wildcat_analyze_status(job_id: str):
    return _wg.get_status(job_id)


@router.get("/wildcat/fires/{fire_id:path}/results")
def get_wildcat_fire_results(fire_id: str):
    try:
        return _wg.get_results(fire_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/wildcat/fires/{fire_id:path}/perimeter")
def get_wildcat_fire_perimeter(fire_id: str):
    """Return a single fire's own perimeter (WGS84 GeoJSON) — used to draw
    the AOI outline on the map even when MHRI fusion isn't available."""
    try:
        return _wg.get_perimeter(fire_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


class WildcatPrepRequest(BaseModel):
    gee_project: str


@router.post("/wildcat/fires/{fire_id:path}/prepare")
def start_wildcat_fire_prep(fire_id: str, request: WildcatPrepRequest):
    """Download DEM + dNBR from GEE for a fire that only has a perimeter."""
    try:
        return _fp.start_data_prep(fire_id, request.gee_project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wildcat/prepare/status/{job_id}")
def get_wildcat_prep_status(job_id: str):
    return _fp.get_prep_status(job_id)


# ===========================================================================
# Wildcat x MHRI Fusion — user-uploaded AOI + pixel-level MHRI
# ===========================================================================

@router.post("/wildcat/fires/upload")
async def upload_wildcat_fire(
    file: UploadFile = File(...),
    name: str = Form(...),
    year: int = Form(...),
    fire_date: str = Form(...),
):
    """
    Upload a custom AOI/fire perimeter (GeoJSON or zipped Shapefile) plus its
    name/year/fire_date. Converts it into the same wildcat/<fire_id>/inputs/
    layout used by historical fires, so it immediately shows up as
    'needs_download' and can go through Prepare -> Analyze.

    Enforces a 700 km^2 area cap and reports whether the AOI falls inside the
    ASBPA 60-county MHRI coverage footprint (CA/OR/WA coastal counties).
    """
    try:
        data = await file.read()
        return _up.upload_custom_perimeter(
            data=data,
            filename=file.filename or "upload",
            name=name,
            year=year,
            fire_date=fire_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mhri/fires/{fire_id:path}/results")
def get_mhri_fusion_results(fire_id: str, i15_index: int = 0):
    """
    Compute the pixel-level MHRI grid for a Wildcat AOI, with the
    a8_post_wildfire_debris_flow indicator replaced by Wildcat's own
    per-catchment debris-flow probability (rainfall scenario `i15_index`)
    wherever a catchment covers a 1km cell.

    Requires the AOI to already have a completed Wildcat analysis
    (POST /wildcat/fires/{fire_id}/analyze).
    """
    try:
        return _mhri.compute_mhri_grid(fire_id, i15_index=i15_index)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
