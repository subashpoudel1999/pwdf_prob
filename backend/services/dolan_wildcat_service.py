"""
Dolan Fire — Real Wildcat/pfdf Pipeline Service.

Runs the official USGS Wildcat v1.1.0 assessment using pure Python kwargs.
No permanent configuration.py is maintained by this service — all settings are
passed directly as function arguments (kwargs override config per wildcat's
priority hierarchy).

Workflow per run:
  1. tempfile.mkdtemp()           — isolated working directory
  2. wildcat.initialize()         — empty config skeleton
  3. wildcat.preprocess()         — DEM conditioning, severity, Kf raster
  4. wildcat.assess()             — flow routing, network delineation, hazard models
  5. copy assessment/basins.geojson → backend cache
  6. shutil.rmtree(tmpdir)        — clean up

The assessment output uses index-based property names (P_0..P_3, H_0..H_3,
V_0..V_3 for the four I15 scenarios) which is exactly what the Flutter
attribute_panel.dart expects — no export/rename step needed.

Input files (perimeter, DEM, dNBR) live permanently in:
  fire_webapp/wildcat/dolan-fire/inputs/
and are never modified.
"""

import json
import logging
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, List

import geopandas as gpd
from pydantic import BaseModel

# ── paths ──────────────────────────────────────────────────────────────────────
_BACKEND_ROOT  = Path(__file__).parent.parent           # fire_webapp/backend/
_WEBAPP_ROOT   = _BACKEND_ROOT.parent                   # fire_webapp/
WILDCAT_INPUTS = _WEBAPP_ROOT / "wildcat" / "dolan-fire" / "inputs"
CACHE_DIR      = _BACKEND_ROOT / "data" / "dolan_wildcat_cache"

# ── in-memory job store ────────────────────────────────────────────────────────
_jobs: Dict[str, Dict] = {}

log = logging.getLogger(__name__)


# ── settings model (shared with routes.py) ─────────────────────────────────────

class WildcatSettings(BaseModel):
    """User-configurable Wildcat parameters sent from the Flutter UI."""
    # Rainfall scenarios — four I15 peak 15-min intensities (mm/hr)
    I15_mm_hr: List[float] = [16.0, 20.0, 24.0, 40.0]
    # Soil erodibility constant (no soil raster available for Dolan)
    kf: float = 0.2
    # Network delineation
    min_area_km2: float = 0.025
    # Basin filtering
    min_slope: float = 0.12
    min_burn_ratio: float = 0.25
    # Whether to locate outlet basin polygons (slow; False = no basins.geojson)
    locate_basins: bool = True
    # Preprocessing
    buffer_km: float = 3.0
    severity_thresholds: List[float] = [125.0, 250.0, 500.0]


# ── service ────────────────────────────────────────────────────────────────────

class DolanWildcatService:
    """Runs the real Wildcat pipeline for the Dolan Fire on demand."""

    # ── public interface ───────────────────────────────────────────────────────

    def start_analysis(
        self,
        force: bool = False,
        settings: WildcatSettings = None,
    ) -> Dict[str, Any]:
        """Start a full Wildcat analysis in a background thread.

        If cached results exist and force=False, returns immediately.
        Pass force=True to discard cached results and re-run from scratch.
        """
        if settings is None:
            settings = WildcatSettings()

        basins_path = CACHE_DIR / "basins.geojson"
        if not force and basins_path.exists():
            fake_id = "wc_cached_" + str(uuid.uuid4())[:6]
            _jobs[fake_id] = {
                "status": "completed",
                "step": 3,
                "message": "Wildcat analysis complete (cached results loaded)",
                "progress": 100,
                "basin_count": self._count_cached_basins(),
            }
            return {"job_id": fake_id, "cached": True}

        self.clear_cache()

        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = {
            "status": "running",
            "step": 0,
            "message": "Starting Wildcat pipeline...",
            "progress": 0,
            "error": None,
        }
        t = threading.Thread(
            target=self._run, args=(job_id, settings), daemon=True
        )
        t.start()
        return {"job_id": job_id, "cached": False}

    def get_status(self, job_id: str) -> Dict[str, Any]:
        if job_id not in _jobs:
            return {"status": "not_found", "error": f"Job {job_id} not found"}
        return dict(_jobs[job_id])

    def get_results(self) -> Dict[str, Any]:
        result_path = CACHE_DIR / "basins.geojson"
        if not result_path.exists():
            raise FileNotFoundError("No results yet — run analysis first.")
        with open(result_path, encoding="utf-8") as f:
            return json.load(f)

    def get_perimeter(self) -> Dict[str, Any]:
        perim_path = CACHE_DIR / "perimeter.geojson"
        if perim_path.exists():
            with open(perim_path, encoding="utf-8") as f:
                return json.load(f)
        perim_src = WILDCAT_INPUTS / "dolan_perimeter.shp"
        perim = gpd.read_file(str(perim_src)).to_crs(epsg=4326)[["geometry"]]
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        result = json.loads(perim.to_json())
        with open(perim_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
        return result

    def has_results(self) -> bool:
        return (CACHE_DIR / "basins.geojson").exists()

    def clear_cache(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for fname in ["basins.geojson", "segments.geojson", "perimeter.geojson"]:
            p = CACHE_DIR / fname
            if p.exists():
                p.unlink()

    # ── private pipeline ───────────────────────────────────────────────────────

    def _run(self, job_id: str, settings: WildcatSettings):
        tmpdir = tempfile.mkdtemp(prefix="wildcat_dolan_")
        try:
            self._step1_preprocess(job_id, settings, tmpdir)
            self._step2_assess(job_id, settings, tmpdir)
            self._step3_cache(job_id, tmpdir)
            _jobs[job_id].update({
                "status": "completed",
                "step": 3,
                "message": "Wildcat analysis complete!",
                "progress": 100,
                "basin_count": self._count_cached_basins(),
            })
        except Exception as exc:
            import traceback
            _jobs[job_id].update({
                "status": "failed",
                "error": str(exc),
                "message": f"Pipeline failed: {exc}",
            })
            log.error(traceback.format_exc())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _update(self, job_id: str, step: int, message: str, progress: int):
        _jobs[job_id].update({"step": step, "message": message, "progress": progress})

    def _step1_preprocess(
        self, job_id: str, settings: WildcatSettings, tmpdir: str
    ):
        self._update(
            job_id, 1,
            "Step 1/3 — wildcat.preprocess: conditioning DEM, estimating burn severity...",
            5,
        )
        import wildcat

        # Create an empty project skeleton (no configuration.py content needed
        # because all settings come from kwargs below).
        wildcat.initialize(project=tmpdir, config="empty", inputs=None)

        wildcat.preprocess(
            project=tmpdir,
            # Point to the permanent inputs folder; filenames are relative to it.
            inputs=str(WILDCAT_INPUTS),
            perimeter="dolan_perimeter.shp",
            dem="dolan_dem_3dep10m.tif",
            dnbr="dolan_dnbr.tif",
            # User-configurable parameters (kwargs override the empty config)
            kf=settings.kf,
            buffer_km=settings.buffer_km,
            severity_thresholds=list(settings.severity_thresholds),
            estimate_severity=True,
            constrain_dnbr=True,
            missing_kf_check="warn",
        )
        self._update(job_id, 1, "Step 1/3 — Preprocessing complete", 30)

    def _step2_assess(
        self, job_id: str, settings: WildcatSettings, tmpdir: str
    ):
        self._update(
            job_id, 2,
            "Step 2/3 — wildcat.assess: D8 flow routing, network delineation, "
            "Staley M1 / Gartner G14 / Cannon C10 models...",
            33,
        )
        import wildcat

        wildcat.assess(
            project=tmpdir,
            # Delineation
            min_area_km2=settings.min_area_km2,
            # Filtering
            min_slope=settings.min_slope,
            min_burn_ratio=settings.min_burn_ratio,
            # Hazard modeling
            I15_mm_hr=list(settings.I15_mm_hr),
            volume_CI=[0.95],
            durations=[15, 30, 60],
            probabilities=[0.5, 0.75],
            # Basin polygons (slow but needed for the map display)
            locate_basins=settings.locate_basins,
            parallelize_basins=False,
        )
        self._update(job_id, 2, "Step 2/3 — Assessment complete", 88)

    def _step3_cache(self, job_id: str, tmpdir: str):
        self._update(job_id, 3, "Step 3/3 — Saving results to cache...", 90)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        assessment_dir = Path(tmpdir) / "assessment"

        # Assessment output uses index-based names (P_0..P_3, H_0..H_3, V_0..V_3)
        # which matches exactly what Flutter's attribute_panel.dart expects.
        # No export/rename step is needed.
        src_basins = assessment_dir / "basins.geojson"
        if src_basins.exists():
            shutil.copy2(src_basins, CACHE_DIR / "basins.geojson")
        else:
            # locate_basins=False — fall back to segments (line features)
            src_segs = assessment_dir / "segments.geojson"
            if not src_segs.exists():
                raise FileNotFoundError(
                    "wildcat.assess produced neither basins.geojson nor "
                    "segments.geojson in the assessment folder. "
                    "Check that the input files are valid and preprocess succeeded."
                )
            shutil.copy2(src_segs, CACHE_DIR / "basins.geojson")

        src_segs = assessment_dir / "segments.geojson"
        if src_segs.exists():
            shutil.copy2(src_segs, CACHE_DIR / "segments.geojson")

        self._update(job_id, 3, "Step 3/3 — Done", 98)

    def _count_cached_basins(self) -> int:
        p = CACHE_DIR / "basins.geojson"
        if not p.exists():
            return 0
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return len(data.get("features", []))
        except Exception:
            return 0
