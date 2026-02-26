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

router = APIRouter()

# --- Franklin Fire services ---
PROJECTS_DIR = Path(__file__).parent.parent / "data" / "projects"
FRANKLIN_FIRE_BASINS = PROJECTS_DIR / "franklin-fire" / "assessment" / "basins.geojson"

wildcat_service = WildcatService(PROJECTS_DIR)
gis_service = GISService(FRANKLIN_FIRE_BASINS)

# --- Palisades Fire service ---
palisades_service = PalisadesService()


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
