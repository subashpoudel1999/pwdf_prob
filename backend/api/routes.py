"""
API Routes for Wildcat Debris-Flow Hazard Analysis.

Franklin Fire: serves pre-computed results + spatial filtering.
Palisades Fire: runs live watershed analysis via WhiteboxTools.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Any

from services.wildcat_service import WildcatService
from services.gis_service import GISService
from services.palisades_service import PalisadesService
from services.dolan_service import DolanService
import services.gee_service as gee_service
from services.dolan_gee_service import DolanGeeService

router = APIRouter()

# --- Franklin Fire services ---
PROJECTS_DIR = Path(__file__).parent.parent / "data" / "projects"
FRANKLIN_FIRE_BASINS = PROJECTS_DIR / "franklin-fire" / "assessment" / "basins.geojson"

wildcat_service = WildcatService(PROJECTS_DIR)
gis_service = GISService(FRANKLIN_FIRE_BASINS)

# --- Palisades Fire service ---
palisades_service = PalisadesService()

# --- Dolan Fire service ---
dolan_service = DolanService()


# --- GEE Dolan service (created per-request with caller's project ID) ---
# DolanGeeService instances are lightweight; the heavy work is in threads.
_gee_dolan_instances: Dict[str, Any] = {}  # project_id → DolanGeeService


def _gee_dolan(project_id: str) -> DolanGeeService:
    """Return (or create) a DolanGeeService for the given project ID."""
    if project_id not in _gee_dolan_instances:
        _gee_dolan_instances[project_id] = DolanGeeService(project_id)
    return _gee_dolan_instances[project_id]


# Request models
class CustomAnalysisRequest(BaseModel):
    polygon: Dict[str, Any]  # GeoJSON geometry


# ===========================================================================
# Franklin Fire endpoints
# ===========================================================================

@router.get("/fires/{fire_id}/results")
def get_fire_results(fire_id: str):
    """Get pre-computed Wildcat analysis results as GeoJSON."""
    try:
        return wildcat_service.get_results(fire_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get("/fires/{fire_id}/status")
def get_fire_status(fire_id: str):
    """Check if fire has analysis results and get metadata."""
    try:
        return wildcat_service.get_status(fire_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("/custom-analysis")
def analyze_custom_area(request: CustomAnalysisRequest):
    """Filter Franklin Fire basins to a user-defined polygon."""
    try:
        if not request.polygon or request.polygon.get("type") != "Polygon":
            raise HTTPException(
                status_code=400,
                detail="Invalid polygon. Must be GeoJSON Polygon geometry.",
            )
        filtered_basins = gis_service.filter_basins_by_polygon(request.polygon)
        stats = gis_service.get_polygon_statistics(request.polygon)
        return {
            "status": "success",
            "message": "Custom area analysis completed",
            "statistics": stats,
            "results": filtered_basins,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Custom analysis error: {str(e)}")


@router.get("/fires/{fire_id}/info")
def get_fire_info(fire_id: str):
    """Get metadata about a fire analysis."""
    if fire_id == "franklin-fire":
        return {
            "fire_id": "franklin-fire",
            "name": "Franklin Fire",
            "year": 2024,
            "location": "Malibu, California",
            "analysis_tool": "Wildcat USGS v1.1.0",
            "model_parameters": {
                "rainfall_intensities_mm_hr": [16, 20, 24, 40],
                "durations_min": [15, 30, 60],
            },
        }
    raise HTTPException(status_code=404, detail=f"Fire {fire_id} not found")


# ===========================================================================
# Palisades Fire endpoints — LIVE analysis via WhiteboxTools
# ===========================================================================

@router.post("/palisades/analyze")
def start_palisades_analysis(force: bool = False):
    """
    Start live watershed delineation + debris-flow hazard assessment
    for the 2021 Palisades Fire using WhiteboxTools.

    Pipeline:
      1. Load fire perimeter, DEM, dNBR
      2. Reproject to UTM 11N
      3. Fill DEM depressions (WhiteboxTools)
      4. D8 flow direction (WhiteboxTools)
      5. Flow accumulation (WhiteboxTools)
      6. Stream extraction (WhiteboxTools)
      7. Sub-basin delineation (WhiteboxTools)
      8. Slope + burn severity per basin (rasterio)
      9. Staley (2017) debris-flow probability model
      10. Gartner (2014) volume estimates + hazard classification

    Returns job_id for polling status.
    """
    try:
        result = palisades_service.start_analysis(force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/palisades/status/{job_id}")
def get_palisades_status(job_id: str):
    """
    Poll analysis progress.

    Returns:
        status: 'running' | 'completed' | 'error' | 'not_found'
        step: current step number (1-10)
        message: human-readable step description
        progress: 0-100
    """
    status = palisades_service.get_status(job_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status


@router.get("/palisades/results")
def get_palisades_results():
    """Get completed analysis results as GeoJSON FeatureCollection."""
    try:
        return palisades_service.get_results()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get("/palisades/perimeter")
def get_palisades_perimeter():
    """Get the Palisades Fire perimeter as GeoJSON (WGS84)."""
    try:
        return palisades_service.get_perimeter()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("/palisades/custom-analysis")
def palisades_custom_area(request: CustomAnalysisRequest):
    """Filter Palisades basins to a user-drawn polygon. Requires analysis first."""
    try:
        if not request.polygon or request.polygon.get("type") != "Polygon":
            raise HTTPException(
                status_code=400,
                detail="Invalid polygon. Must be GeoJSON Polygon geometry.",
            )
        if not palisades_service.has_results():
            raise HTTPException(status_code=404, detail="Run analysis first")
        filtered = palisades_service.filter_basins_by_polygon(request.polygon)
        return {"status": "success", "results": filtered}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Custom analysis error: {str(e)}")


@router.post("/palisades/analyze-zone")
def start_palisades_zone_analysis(request: CustomAnalysisRequest):
    """
    Re-run the full WhiteboxTools + debris-flow model pipeline clipped to a
    user-drawn polygon. Returns a job_id for polling via /palisades/status/{job_id}.
    Results fetched via /palisades/zone-results/{job_id}.
    """
    try:
        if not request.polygon or request.polygon.get("type") != "Polygon":
            raise HTTPException(
                status_code=400,
                detail="Invalid polygon. Must be GeoJSON Polygon geometry.",
            )
        result = palisades_service.start_zone_analysis(request.polygon)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zone analysis error: {str(e)}")


@router.get("/palisades/zone-results/{job_id}")
def get_palisades_zone_results(job_id: str):
    """Fetch results for a completed zone analysis job."""
    try:
        return palisades_service.get_zone_results(job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.delete("/palisades/cache")
def clear_palisades_cache():
    """Clear cached Palisades results to force a fresh analysis."""
    palisades_service.clear_cache()
    return {"status": "ok", "message": "Cache cleared. Next analysis will run fresh."}


# ===========================================================================
# Dolan Fire endpoints — LIVE analysis via WhiteboxTools (2020 fire)
# ===========================================================================

@router.get("/dolan/available-inputs")
def get_dolan_available_inputs():
    """Return metadata and legend info for all available Dolan burn severity datasets."""
    try:
        return dolan_service.get_available_inputs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dolan/preview/{dataset}")
def get_dolan_preview(dataset: str):
    """Return a georeferenced PNG overlay (base64) for a burn severity dataset."""
    try:
        return dolan_service.get_preview_image(dataset)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


@router.post("/dolan/analyze")
def start_dolan_analysis(force: bool = False, burn_metric: str = "dnbr"):
    """
    Start live watershed delineation + debris-flow hazard assessment
    for the 2020 Dolan Fire (Big Sur, CA) using WhiteboxTools.

    burn_metric: one of "dnbr", "rdnbr", "dnbr6"
    Returns job_id for polling status.
    """
    try:
        return dolan_service.start_analysis(force=force, burn_metric=burn_metric)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/dolan/status/{job_id}")
def get_dolan_status(job_id: str):
    """Poll Dolan analysis progress."""
    status = dolan_service.get_status(job_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status


@router.get("/dolan/results")
def get_dolan_results():
    """Get completed Dolan analysis results as GeoJSON FeatureCollection."""
    try:
        return dolan_service.get_results()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get("/dolan/perimeter")
def get_dolan_perimeter():
    """Get the Dolan Fire perimeter as GeoJSON (WGS84)."""
    try:
        return dolan_service.get_perimeter()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("/dolan/analyze-zone")
def start_dolan_zone_analysis(request: CustomAnalysisRequest, burn_metric: str = ""):
    """
    Re-run the full WhiteboxTools + debris-flow pipeline clipped to a user-drawn polygon.
    burn_metric: "dnbr" | "rdnbr" | "dnbr6" (defaults to metric used in last full analysis).
    Results fetched via /dolan/zone-results/{job_id}.
    """
    try:
        if not request.polygon or request.polygon.get("type") != "Polygon":
            raise HTTPException(
                status_code=400, detail="Invalid polygon. Must be GeoJSON Polygon geometry."
            )
        return dolan_service.start_zone_analysis(request.polygon, burn_metric=burn_metric)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zone analysis error: {str(e)}")


@router.get("/dolan/zone-results/{job_id}")
def get_dolan_zone_results(job_id: str):
    """Fetch results for a completed Dolan zone analysis job."""
    try:
        return dolan_service.get_zone_results(job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.delete("/dolan/cache")
def clear_dolan_cache():
    """Clear cached Dolan results to force a fresh analysis."""
    dolan_service.clear_cache()
    return {"status": "ok", "message": "Cache cleared. Next analysis will run fresh."}


# ===========================================================================
# GEE — Dolan Fire via Google Earth Engine DEM
# All existing /dolan/* routes are UNCHANGED. These are new, parallel routes.
# ===========================================================================

class GeeTestRequest(BaseModel):
    project_id: str


class GeeAnalyzeRequest(BaseModel):
    project_id: str


class GeeZoneRequest(BaseModel):
    project_id: str
    polygon: Dict[str, Any]


class GeeValidateAreaRequest(BaseModel):
    polygon: Dict[str, Any]   # GeoJSON Polygon geometry
    buffer_m: int = 200       # buffer to add around the polygon


@router.post("/gee/validate-area")
def gee_validate_area(request: GeeValidateAreaRequest):
    """
    Check whether a user-drawn polygon + buffer fits within GEE's direct download limit.
    Returns {"ok": bool, "area_km2": float, "limit_km2": float, "message": str}.
    Does NOT require GEE authentication — pure geometry calculation.
    """
    try:
        from shapely.geometry import shape as shp_shape
        import geopandas as gpd
        geom = shp_shape(request.polygon)
        gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
        return gee_service.check_area(gdf, request.buffer_m)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gee/test-connection")
def gee_test_connection(request: GeeTestRequest):
    """
    Test that the user's local GEE credentials are valid and the project ID works.
    The user must have already run `earthengine authenticate` on this machine.
    """
    try:
        result = gee_service.test_connection(request.project_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gee/dolan/analyze")
def start_gee_dolan_analysis(request: GeeAnalyzeRequest, burn_metric: str = "dnbr", force: bool = False):
    """
    Start Dolan Fire analysis using GEE for DEM download.
    The local 1.1 GB DEM file is NOT required — it is fetched from USGS 3DEP via GEE.
    Burn severity rasters (dNBR/rdNBR/dNBR6) are still read from local files.
    """
    try:
        svc = _gee_dolan(request.project_id)
        return svc.start_analysis(force=force, burn_metric=burn_metric)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/status/{job_id}")
def get_gee_dolan_status(job_id: str):
    """Poll GEE Dolan analysis progress (same job store as /dolan/status)."""
    try:
        return dolan_service.get_status(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/results")
def get_gee_dolan_results():
    """Fetch GEE Dolan analysis results (same cache as /dolan/results)."""
    try:
        return dolan_service.get_results()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/perimeter")
def get_gee_dolan_perimeter():
    """Fetch Dolan fire perimeter GeoJSON."""
    try:
        return dolan_service.get_perimeter()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gee/dolan/available-inputs")
def get_gee_dolan_available_inputs():
    """Return available burn severity datasets for GEE Dolan analysis."""
    try:
        return dolan_service.get_available_inputs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gee/dolan/analyze-zone")
def start_gee_dolan_zone(request: GeeZoneRequest, burn_metric: str = ""):
    """
    Start a zone analysis for Dolan Fire using GEE for DEM.
    Full WhiteboxTools pipeline re-run clipped to the user-drawn polygon.
    """
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
    """Fetch results for a completed GEE Dolan zone analysis job."""
    try:
        return dolan_service.get_zone_results(job_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
