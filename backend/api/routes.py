"""
API Routes — fire_webapp2 (3-module version).

Modules:
  1. Dolan Fire × Real Wildcat  (/wildcat/dolan/*)
  2. Dolan Fire × Retro Detection  (/retro/*)
  3. Dolan Fire × Wildcat vs ML  (/ml/dolan/*)

GEE helpers (/gee/*) kept for the upcoming merge of GeeDolanScreen into module 1.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Any, Optional

import services.gee_service as gee_service
from services.dolan_gee_service import DolanGeeService
from services.dolan_wildcat_service import DolanWildcatService, WildcatSettings
from services.retro_detection_service import RetroDetectionService
from services.ml_comparison_service import MlComparisonService
from services.gee_feature_extraction_service import GeeFeatureExtractionService

router = APIRouter()

# --- Service instances ---
dolan_wildcat_service = DolanWildcatService()
retro_service = RetroDetectionService()
ml_comparison_service = MlComparisonService()
gee_extraction_service = GeeFeatureExtractionService()

# --- GEE Dolan instances (created per project_id) ---
_gee_dolan_instances: Dict[str, Any] = {}


def _gee_dolan(project_id: str) -> DolanGeeService:
    if project_id not in _gee_dolan_instances:
        _gee_dolan_instances[project_id] = DolanGeeService(project_id)
    return _gee_dolan_instances[project_id]


# ===========================================================================
# GEE helpers — connection test + area validation
# ===========================================================================

class GeeTestRequest(BaseModel):
    project_id: str


class GeeValidateAreaRequest(BaseModel):
    polygon: Dict[str, Any]
    buffer_m: int = 200


@router.post("/gee/test-connection")
def gee_test_connection(request: GeeTestRequest):
    try:
        result = gee_service.test_connection(request.project_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gee/validate-area")
def gee_validate_area(request: GeeValidateAreaRequest):
    try:
        from shapely.geometry import shape as shp_shape
        import geopandas as gpd
        geom = shp_shape(request.polygon)
        gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
        return gee_service.check_area(gdf, request.buffer_m)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================================================
# GEE Dolan — WhiteboxTools pipeline with DEM from USGS 3DEP via GEE
# (kept intact; will be merged into /wildcat/dolan/* in module 1)
# ===========================================================================

class GeeAnalyzeRequest(BaseModel):
    project_id: str


class GeeZoneRequest(BaseModel):
    project_id: str
    polygon: Dict[str, Any]


@router.post("/gee/dolan/analyze")
def start_gee_dolan_analysis(request: GeeAnalyzeRequest, burn_metric: str = "dnbr", force: bool = False):
    try:
        svc = _gee_dolan(request.project_id)
        return svc.start_analysis(force=force, burn_metric=burn_metric)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/status/{job_id}")
def get_gee_dolan_status(job_id: str):
    try:
        svc_list = list(_gee_dolan_instances.values())
        if not svc_list:
            raise HTTPException(status_code=404, detail="No GEE Dolan service initialised")
        return svc_list[-1].get_status(job_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/results")
def get_gee_dolan_results():
    try:
        svc_list = list(_gee_dolan_instances.values())
        if not svc_list:
            raise HTTPException(status_code=404, detail="No GEE Dolan service initialised")
        return svc_list[-1].get_results()
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/perimeter")
def get_gee_dolan_perimeter():
    try:
        svc_list = list(_gee_dolan_instances.values())
        if not svc_list:
            raise HTTPException(status_code=404, detail="No GEE Dolan service initialised")
        return svc_list[-1].get_perimeter()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gee/dolan/analyze-zone")
def start_gee_dolan_zone(request: GeeZoneRequest, burn_metric: str = ""):
    try:
        if not request.polygon or request.polygon.get("type") != "Polygon":
            raise HTTPException(status_code=400, detail="Invalid polygon geometry.")
        svc = _gee_dolan(request.project_id)
        return svc.start_zone_analysis(request.polygon, burn_metric=burn_metric)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/zone-results/{job_id}")
def get_gee_dolan_zone_results(job_id: str):
    try:
        svc_list = list(_gee_dolan_instances.values())
        if not svc_list:
            raise HTTPException(status_code=404, detail="No GEE Dolan service initialised")
        return svc_list[-1].get_zone_results(job_id)
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Module 1 — Dolan Fire × Real Wildcat (pfdf v1.1.0)
# ===========================================================================

class WildcatDolanAnalyzeRequest(BaseModel):
    force: bool = False
    settings: WildcatSettings = WildcatSettings()


class WildcatZoneRequest(BaseModel):
    polygon: Dict[str, Any]
    settings: WildcatSettings = WildcatSettings()


@router.get("/wildcat/dolan/perimeter")
def get_wildcat_dolan_perimeter():
    try:
        return dolan_wildcat_service.get_perimeter()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wildcat/dolan/analyze")
def start_wildcat_dolan_analysis(request: WildcatDolanAnalyzeRequest):
    try:
        return dolan_wildcat_service.start_analysis(
            force=request.force, settings=request.settings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wildcat/dolan/status/{job_id}")
def get_wildcat_dolan_status(job_id: str):
    return dolan_wildcat_service.get_status(job_id)


@router.get("/wildcat/dolan/results")
def get_wildcat_dolan_results():
    try:
        return dolan_wildcat_service.get_results()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wildcat/dolan/analyze-zone")
def start_wildcat_dolan_zone(request: WildcatZoneRequest):
    """
    Clip DEM + dNBR to a user-drawn polygon + 200 m buffer and run the full
    real Wildcat pipeline on the sub-area.  Returns a job_id for polling via
    GET /wildcat/dolan/status/{job_id}.  Results fetched via
    GET /wildcat/dolan/zone-results/{job_id}.
    """
    try:
        if not request.polygon or request.polygon.get("type") != "Polygon":
            raise HTTPException(
                status_code=400, detail="Invalid polygon. Must be GeoJSON Polygon geometry."
            )
        return dolan_wildcat_service.start_zone_analysis(
            polygon=request.polygon, settings=request.settings
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wildcat/dolan/zone-results/{job_id}")
def get_wildcat_dolan_zone_results(job_id: str):
    """Fetch results for a completed Wildcat zone analysis job."""
    try:
        return dolan_wildcat_service.get_zone_results(job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Module 2 — Dolan Fire × Retrospective Detection
# ===========================================================================

class RetroAnalyzeRequest(BaseModel):
    project_id: str
    force: bool = False
    pre_start:  Optional[str] = None
    pre_end:    Optional[str] = None
    post_start: Optional[str] = None
    post_end:   Optional[str] = None
    storm_date: Optional[str] = None


@router.post("/retro/{fire_id}/analyze")
def start_retro_analysis(fire_id: str, request: RetroAnalyzeRequest):
    try:
        return retro_service.start_analysis(
            fire_id=fire_id,
            project_id=request.project_id,
            force=request.force,
            pre_start=request.pre_start,
            pre_end=request.pre_end,
            post_start=request.post_start,
            post_end=request.post_end,
            storm_date=request.storm_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retro/{fire_id}/status/{job_id}")
def get_retro_status(fire_id: str, job_id: str):
    return retro_service.get_status(job_id)


@router.get("/retro/{fire_id}/results")
def get_retro_results(fire_id: str, storm_date: Optional[str] = None):
    try:
        return retro_service.get_results(fire_id, storm_date=storm_date)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retro/{fire_id}/storm-events")
def get_storm_events(fire_id: str, project_id: str, force: bool = False):
    try:
        return retro_service.get_storm_events(fire_id, project_id=project_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Module 3 — Dolan Fire × Wildcat vs ML
# ===========================================================================

@router.get("/ml/dolan/comparison")
def get_ml_comparison(use_cache: bool = True):
    try:
        return ml_comparison_service.get_comparison(use_cache=use_cache)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"ML model output file not found: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/dolan/pipeline-steps")
def get_ml_pipeline_steps():
    return {"steps": ml_comparison_service.get_pipeline_steps()}


@router.post("/ml/dolan/comparison/refresh")
def refresh_ml_comparison():
    ml_comparison_service.invalidate_cache()
    return {"status": "cache_cleared"}


class GeeExtractionRequest(BaseModel):
    gee_project: str
    redownload_dem: bool = False
    mode: str = "full"


@router.post("/ml/dolan/extract-features")
def start_gee_extraction(req: GeeExtractionRequest):
    try:
        return gee_extraction_service.start_extraction(
            gee_project=req.gee_project,
            redownload_dem=req.redownload_dem,
            mode=req.mode,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/dolan/extract-features/status/{job_id}")
def get_extraction_status(job_id: str):
    result = gee_extraction_service.get_status(job_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result["error"])
    return result
