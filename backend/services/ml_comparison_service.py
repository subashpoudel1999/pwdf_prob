"""
ML Comparison Service — Dolan Fire (2020)

Two modes controlled by the `use_cache` flag:

  use_cache=True  (default)
    Reads all pre-computed notebook outputs instantly.
    ML section is based on the full 492-basin training+test dataset.
    ML map section uses live inference on 47 GIS-delineated basins WITH geometries.

  use_cache=False  (live pipeline)
    Re-runs Random Forest v3 predict_proba on dolan_basins_features_live.csv.
    All computation happens in this request (model load + inference + stats).
    Produces the same 47-basin GeoJSON but with freshly computed probabilities.
    Wildcat data is always read from cache (it never changes).

Data paths:
  Wildcat basins  : backend/data/dolan_wildcat_cache/basins.geojson
  ML model        : c_dolan_ml_model/outputs/models/rf_model_v3{.pkl, _meta.pkl}
  Live features   : c_dolan_ml_model/outputs/features/dolan_basins_features_live.csv
  Basin shapes    : c_dolan_ml_model/outputs/basins/dolan_basins.shp  (47 basins, EPSG:4326)
  Pre-computed    : c_dolan_ml_model/outputs/evaluation/{predictions, metrics, importances}
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_DIR   = Path(__file__).parent.parent
_WILDCAT_CACHE = _BACKEND_DIR / "data" / "dolan_wildcat_cache" / "basins.geojson"

_ML_DIR        = Path(r"C:\Users\J01040445\Downloads\1. Wildfire folders\c_dolan_ml_model")
_MODEL_PKL     = _ML_DIR / "outputs" / "models" / "rf_model_v3.pkl"
_META_PKL      = _ML_DIR / "outputs" / "models" / "rf_model_v3_meta.pkl"
_LIVE_FEAT_CSV = _ML_DIR / "outputs" / "features" / "dolan_basins_features_live.csv"
_BASINS_SHP    = _ML_DIR / "outputs" / "basins"    / "dolan_basins.shp"

_PREDS_CSV     = _ML_DIR / "outputs" / "evaluation" / "dolan_predictions_v3.csv"
_METRICS_CSV   = _ML_DIR / "outputs" / "evaluation" / "model_metrics_v3.csv"
_IMP_CSV       = _ML_DIR / "outputs" / "evaluation" / "feature_importances_v3.csv"

# Staley (2017) M1 coefficients
STALEY_COEFS = {
    "b0": -3.63, "b1": 0.41, "b2": 0.26,
    "b3":  0.67, "b4": 0.60, "b5": 0.07, "b6": 0.69,
}

WILDCAT_SCENARIOS = [
    {"label": "I15 = 16 mm/hr", "i15": 16, "idx": 0},
    {"label": "I15 = 20 mm/hr", "i15": 20, "idx": 1},
    {"label": "I15 = 24 mm/hr", "i15": 24, "idx": 2},
    {"label": "I15 = 40 mm/hr", "i15": 40, "idx": 3},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _risk_tier(p: float) -> str:
    if p < 0.25: return "Low"
    if p < 0.50: return "Moderate"
    if p < 0.75: return "High"
    return "Very High"


def _histogram_bins(values: List[float], n_bins: int = 20) -> List[Dict]:
    edges = [i / n_bins for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for v in values:
        idx = min(int(v * n_bins), n_bins - 1)
        counts[idx] += 1
    return [{"lo": round(edges[i], 3), "hi": round(edges[i + 1], 3), "count": counts[i]}
            for i in range(n_bins)]


def _staley_logit(T: float, F: float, S: float, R15: float) -> float:
    c = STALEY_COEFS
    return (c["b0"]
            + (c["b1"] + c["b2"] * R15) * T
            + (c["b3"] + c["b4"] * R15) * F
            + (c["b5"] + c["b6"] * R15) * S)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Pipeline steps (returned to frontend for animation)
# ---------------------------------------------------------------------------
PIPELINE_STEPS = [
    "Loading Wildcat basins.geojson — 886 pfdf-delineated basins…",
    "Reconstructing Staley M1 step-by-step for each basin × 4 scenarios…",
    "Loading RF model v3 and feature matrix (dolan_basins_features_live.csv)…",
    "Running predict_proba on 47 GIS-delineated basins…",
    "Joining predictions with basin geometries (dolan_basins.shp)…",
    "Computing risk distributions, histograms, and comparison stats…",
]


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class MlComparisonService:

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}   # keyed by "cached" | "live"

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_comparison(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Return the full comparison payload.

        use_cache=True  → reads pre-computed CSVs (near-instant).
        use_cache=False → re-runs RF inference on live features (seconds).

        Both modes always include ml.live_geojson: the 47-basin GeoJSON with
        freshly-computed or cached ML probabilities for map rendering.
        """
        cache_key = "cached" if use_cache else "live"
        if cache_key not in self._cache:
            self._cache[cache_key] = self._build(use_cache=use_cache)
        return self._cache[cache_key]

    def invalidate_cache(self) -> None:
        self._cache.clear()

    def get_pipeline_steps(self) -> List[str]:
        return PIPELINE_STEPS

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, use_cache: bool) -> Dict[str, Any]:
        wildcat = self._build_wildcat_section()
        ml      = self._build_ml_section(use_cache=use_cache)
        return {
            "wildcat": wildcat,
            "ml":      ml,
            "staley_m1_coefficients": STALEY_COEFS,
            "pipeline_mode": "cached" if use_cache else "live",
        }

    # ── Wildcat section ────────────────────────────────────────────────

    def _build_wildcat_section(self) -> Dict[str, Any]:
        with open(_WILDCAT_CACHE, encoding="utf-8") as fh:
            geojson = json.load(fh)

        features     = geojson["features"]
        basin_count  = len(features)
        in_perim_cnt = sum(1 for f in features if f["properties"].get("IsInPerim") == 1)
        burned_cnt   = sum(1 for f in features if f["properties"].get("IsBurned")  == 1)
        steep_cnt    = sum(1 for f in features if f["properties"].get("IsSteep")   == 1)

        risk_dist_by_scenario:  Dict[str, Dict[str, int]]            = {}
        prob_hist_by_scenario:  Dict[str, List[Dict]]                = {}
        stats_by_scenario:      Dict[str, Dict]                      = {}

        for sc in WILDCAT_SCENARIOS:
            idx   = sc["idx"]
            p_key = f"P_{idx}"
            probs = [
                f["properties"].get(p_key, 0.0) or 0.0
                for f in features
                if f["properties"].get(p_key) is not None
            ]

            risk_dist: Dict[str, int] = {"Low": 0, "Moderate": 0, "High": 0, "Very High": 0}
            for p in probs:
                risk_dist[_risk_tier(p)] += 1

            risk_dist_by_scenario[str(idx)] = risk_dist
            prob_hist_by_scenario[str(idx)] = _histogram_bins(probs)
            stats_by_scenario[str(idx)] = {
                "mean":            round(float(np.mean(probs)), 4),
                "median":          round(float(np.median(probs)), 4),
                "p75":             round(float(np.percentile(probs, 75)), 4),
                "p90":             round(float(np.percentile(probs, 90)), 4),
                "high_risk_count": risk_dist["High"] + risk_dist["Very High"],
            }

        # Per-basin Staley M1 step-by-step
        basin_details = []
        for feat in features:
            p      = feat["properties"]
            seg_id = p.get("Segment_ID")
            T      = p.get("Terrain_M1", 0.0) or 0.0
            F      = p.get("Fire_M1",    0.0) or 0.0
            S      = p.get("Soil_M1",    0.0) or 0.0
            scenarios_detail = []
            for sc in WILDCAT_SCENARIOS:
                idx     = sc["idx"]
                R15     = p.get(f"R_{idx}_0", 0.0) or 0.0
                I15     = p.get(f"I_{idx}_0", 0.0) or 0.0
                logit   = _staley_logit(T, F, S, R15)
                P_calc  = _sigmoid(logit)
                P_stored = p.get(f"P_{idx}", 0.0) or 0.0
                V_stored = p.get(f"V_{idx}")
                H_stored = p.get(f"H_{idx}")
                Bmh      = p.get("Bmh_km2")
                Relief   = p.get("Relief_m")
                V_calc   = None
                if I15 and Bmh and Relief and I15 > 0 and Bmh > 0 and Relief > 0:
                    log_v  = (-0.699
                              + 0.989 * math.log10(max(I15, 0.01))
                              + 0.369 * math.log10(max(Bmh, 1e-9))
                              + 1.223 * math.log10(max(Relief, 0.1)))
                    V_calc = round(10 ** log_v, 1)
                scenarios_detail.append({
                    "scenario_idx": idx,
                    "i15":          round(I15, 1),
                    "r15":          round(R15, 4),
                    "T":            round(T, 4),
                    "F":            round(F, 4),
                    "S":            round(S, 4),
                    "T_term": round((STALEY_COEFS["b1"] + STALEY_COEFS["b2"] * R15) * T, 4),
                    "F_term": round((STALEY_COEFS["b3"] + STALEY_COEFS["b4"] * R15) * F, 4),
                    "S_term": round((STALEY_COEFS["b5"] + STALEY_COEFS["b6"] * R15) * S, 4),
                    "logit":        round(logit, 4),
                    "P_calc":       round(P_calc, 4),
                    "P_stored":     round(P_stored, 4),
                    "V_calc":       V_calc,
                    "V_stored":     round(V_stored, 1) if V_stored is not None else None,
                    "H":            int(H_stored) if H_stored is not None else None,
                    "bmh_km2":      round(Bmh, 4) if Bmh is not None else None,
                    "relief_m":     round(Relief, 1) if Relief is not None else None,
                    "risk_tier":    _risk_tier(P_stored),
                })
            basin_details.append({
                "segment_id": seg_id,
                "area_km2":   round(p.get("Area_km2", 0.0) or 0.0, 4),
                "is_burned":  p.get("IsBurned", 0),
                "is_steep":   p.get("IsSteep",  0),
                "in_perim":   p.get("IsInPerim", 0),
                "scenarios":  scenarios_detail,
            })

        return {
            "basin_count":           basin_count,
            "in_perimeter_count":    in_perim_cnt,
            "burned_count":          burned_cnt,
            "steep_count":           steep_cnt,
            "scenarios":             WILDCAT_SCENARIOS,
            "risk_dist_by_scenario": risk_dist_by_scenario,
            "prob_hist_by_scenario": prob_hist_by_scenario,
            "stats_by_scenario":     stats_by_scenario,
            "basin_details":         basin_details,
            "geojson":               geojson,
        }

    # ── ML section ────────────────────────────────────────────────────

    def _build_ml_section(self, use_cache: bool) -> Dict[str, Any]:
        """
        Always includes:
          - live_geojson      : 47-basin GeoJSON with ML_Prob (for map)
          - live_predictions  : list of 47 basin predictions with probs
          - predictions       : full 492-basin list (pre-computed CSV)
          - metrics           : model performance from metrics CSV
          - feature_importances
          - probability_histogram (all 492)
          - pipeline_mode     : "cached" | "live"
        """
        # ── Live inference on 47 basins (always run, fast ~50ms) ──────
        live_geojson, live_predictions, threshold = self._run_live_inference()

        # ── Pre-computed / training-set data ─────────────────────────
        if use_cache:
            preds, metrics_dict, feature_imps, prob_hist, risk_dist = \
                self._load_precomputed()
        else:
            # Re-compute stats from live data + re-load model metrics
            preds, metrics_dict, feature_imps, prob_hist, risk_dist = \
                self._compute_from_live(live_predictions, threshold)

        return {
            "pipeline_mode":        "cached" if use_cache else "live",
            "basin_count":          len(preds),
            "live_basin_count":     len(live_predictions),
            "metrics":              metrics_dict,
            "risk_distribution":    risk_dist,
            "predictions":          preds,
            "live_predictions":     live_predictions,
            "live_geojson":         live_geojson,
            "feature_importances":  feature_imps,
            "probability_histogram": prob_hist,
        }

    # ── Live inference ────────────────────────────────────────────────

    def _run_live_inference(self):
        """
        Load RF model + live features → predict_proba → join with geometries.
        Returns (geojson_dict, predictions_list, threshold).
        ~50ms on first call.
        """
        import joblib
        import geopandas as gpd

        rf   = joblib.load(_MODEL_PKL)
        meta = joblib.load(_META_PKL)
        feat_cols = meta["feature_cols"]
        threshold = float(meta["threshold"])

        feat_df = pd.read_csv(_LIVE_FEAT_CSV)
        X       = feat_df[feat_cols]
        probs   = rf.predict_proba(X)[:, 1]
        preds   = (probs >= threshold).astype(int)

        basins_gdf = gpd.read_file(str(_BASINS_SHP)).to_crs(epsg=4326)

        # Align by Sub_ID order (both should be DOLAN-1…DOLAN-47 sorted)
        basins_gdf = basins_gdf.merge(
            feat_df[["Sub_ID"]].assign(
                ML_Prob=probs.round(4),
                ML_Pred=preds,
                Risk_Category=[_risk_tier(p) for p in probs],
                Probability_Pct=np.round(probs * 100, 1),
            ),
            on="Sub_ID",
            how="left",
        )

        geojson_str = basins_gdf[
            ["Sub_ID", "Segment_ID", "Area_km2", "ML_Prob",
             "ML_Pred", "Risk_Category", "Probability_Pct", "geometry"]
        ].to_json()
        geojson = json.loads(geojson_str)

        live_predictions = []
        for _, row in basins_gdf.iterrows():
            live_predictions.append({
                "sub_basin_id":   str(row["Sub_ID"]),
                "probability":    round(float(row["ML_Prob"]),  4),
                "probability_pct": round(float(row["Probability_Pct"]), 1),
                "predicted":      int(row["ML_Pred"]),
                "risk_category":  str(row["Risk_Category"]),
            })

        return geojson, live_predictions, threshold

    # ── Pre-computed loader ───────────────────────────────────────────

    def _load_precomputed(self):
        preds_df  = pd.read_csv(_PREDS_CSV)
        metrics_r = pd.read_csv(_METRICS_CSV).iloc[0]
        imp_df    = pd.read_csv(_IMP_CSV)

        preds = []
        for _, row in preds_df.iterrows():
            preds.append({
                "sub_basin_id":    str(row["Sub-basin ID"]),
                "probability":     round(float(row["Probability"]),     4),
                "probability_pct": round(float(row.get("Probability_Pct", row["Probability"] * 100)), 1),
                "predicted":       int(row["Debris_Flow_Predicted"]),
                "observed":        int(row["Debris_Flow_Observed"]),
                "risk_category":   str(row["Risk_Category"]),
            })

        risk_dist = {t: 0 for t in ["Low", "Moderate", "High", "Very High"]}
        for p in preds:
            risk_dist[p["risk_category"]] = risk_dist.get(p["risk_category"], 0) + 1

        metrics_dict = {
            "model_name":  "Random Forest v3",
            "trained_on":  "Dolan Fire 2020",
            "n_features":  int(metrics_r.get("N_Features", 37)),
            "threshold":   round(float(metrics_r.get("Threshold",        0.4947)), 4),
            "auc_roc":     round(float(metrics_r.get("AUC_ROC",          0.0)),    4),
            "auc_pr":      round(float(metrics_r.get("AUC_PR",           0.0)),    4),
            "accuracy":    round(float(metrics_r.get("Accuracy",         0.0)),    4),
            "precision":   round(float(metrics_r.get("Precision",        0.0)),    4),
            "recall":      round(float(metrics_r.get("Recall_HitRate",   0.0)),    4),
            "far":         round(float(metrics_r.get("FAR",              0.0)),    4),
            "f1":          round(float(metrics_r.get("F1",               0.0)),    4),
            "tp_test":     int(metrics_r.get("TP", 0)),
            "tn_test":     int(metrics_r.get("TN", 0)),
            "fp_test":     int(metrics_r.get("FP", 0)),
            "fn_test":     int(metrics_r.get("FN", 0)),
            "train_n":     int(metrics_r.get("Train_n", 0)),
            "test_n":      int(metrics_r.get("Test_n",  0)),
        }

        top_imp = imp_df.sort_values("Importance_MDI", ascending=False).head(20)
        feature_imps = [
            {"feature":    str(r["Feature"]),
             "importance": round(float(r["Importance_MDI"]), 5),
             "category":   str(r["Category"])}
            for _, r in top_imp.iterrows()
        ]

        probs_all = preds_df["Probability"].tolist()
        prob_hist = _histogram_bins(probs_all)

        return preds, metrics_dict, feature_imps, prob_hist, risk_dist

    # ── Live-mode stats (when use_cache=False) ────────────────────────

    def _compute_from_live(self, live_predictions, threshold):
        """Derive metrics/stats from the live 47-basin inference."""
        import joblib

        meta      = joblib.load(_META_PKL)
        imp_df    = pd.read_csv(_IMP_CSV)

        probs = [p["probability"] for p in live_predictions]
        preds = live_predictions  # same format

        risk_dist = {"Low": 0, "Moderate": 0, "High": 0, "Very High": 0}
        for p in live_predictions:
            risk_dist[p["risk_category"]] += 1

        # Metrics come from the stored CSV (they describe training/test performance,
        # not the 47-basin live set which has no ground truth labels here)
        metrics_r = pd.read_csv(_METRICS_CSV).iloc[0]
        metrics_dict = {
            "model_name":  "Random Forest v3",
            "trained_on":  "Dolan Fire 2020",
            "n_features":  int(meta.get("n_features", 37)),
            "threshold":   round(float(meta.get("threshold", threshold)), 4),
            "auc_roc":     round(float(metrics_r.get("AUC_ROC",        0.0)), 4),
            "auc_pr":      round(float(metrics_r.get("AUC_PR",         0.0)), 4),
            "accuracy":    round(float(metrics_r.get("Accuracy",       0.0)), 4),
            "precision":   round(float(metrics_r.get("Precision",      0.0)), 4),
            "recall":      round(float(metrics_r.get("Recall_HitRate", 0.0)), 4),
            "far":         round(float(metrics_r.get("FAR",            0.0)), 4),
            "f1":          round(float(metrics_r.get("F1",             0.0)), 4),
            "tp_test":     int(metrics_r.get("TP", 0)),
            "tn_test":     int(metrics_r.get("TN", 0)),
            "fp_test":     int(metrics_r.get("FP", 0)),
            "fn_test":     int(metrics_r.get("FN", 0)),
            "train_n":     int(metrics_r.get("Train_n", 0)),
            "test_n":      int(metrics_r.get("Test_n",  0)),
        }

        top_imp = imp_df.sort_values("Importance_MDI", ascending=False).head(20)
        feature_imps = [
            {"feature":    str(r["Feature"]),
             "importance": round(float(r["Importance_MDI"]), 5),
             "category":   str(r["Category"])}
            for _, r in top_imp.iterrows()
        ]

        prob_hist = _histogram_bins(probs)

        return preds, metrics_dict, feature_imps, prob_hist, risk_dist
