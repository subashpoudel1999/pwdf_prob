# Post-Wildfire Debris-Flow Dashboard — Architecture

**Last Updated:** March 2026
**Status:** Active Development

---

## Overview

A Flutter web application + Python FastAPI backend for running and visualising post-wildfire debris-flow hazard assessments. The system supports three fires at different stages of capability:

| Fire | Year | Location | Analysis Mode |
|---|---|---|---|
| Franklin | 2024 | Malibu, CA | Pre-computed (Wildcat USGS) |
| Palisades | 2021 | Pacific Palisades, CA | Live — local DEM + dNBR |
| Dolan | 2020 | Big Sur, CA | Live — local DEM *or* GEE DEM |

The app runs as **two separate processes** — Flutter frontend and Python backend — that communicate over HTTP. Restarting Flutter does not restart the backend.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Flutter Web App (port ~56075)                           │
│                                                          │
│  HomeScreen                                              │
│    ├── FranklinFireScreen  (pre-computed basins)         │
│    ├── PalisadesFireScreen (live WBT pipeline)           │
│    ├── DolanFireScreen     (live WBT + local DEM)        │
│    └── GeeDolanScreen      (live WBT + GEE DEM)          │
└───────────────────┬──────────────────────────────────────┘
                    │ HTTP / JSON (port 8000)
┌───────────────────▼──────────────────────────────────────┐
│  FastAPI Backend (port 8000)                             │
│                                                          │
│  /api/v1/fires/*         wildcat_service + gis_service   │
│  /api/v1/palisades/*     palisades_service               │
│  /api/v1/dolan/*         dolan_service                   │
│  /api/v1/gee/*           dolan_gee_service + gee_service │
└───────────────────┬──────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
   WhiteboxTools           Google Earth Engine
   (local binary)          (USGS 3DEP DEM)
```

---

## Technology Stack

**Frontend:**
- Flutter 3.x (Web target, `flutter run -d chrome`)
- `flutter_map` v8 — interactive Leaflet-based map
- `http` package — REST calls to backend

**Backend:**
- Python 3.13 / FastAPI + uvicorn
- WhiteboxTools (local binary at `WBT/`) — hydrological processing
- rasterio, geopandas, shapely, numpy — raster/vector GIS
- `earthengine-api` (`ee`) — GEE DEM acquisition

**External Services:**
- Google Earth Engine — USGS 3DEP 10m DEM on-demand download (requires prior `earthengine authenticate`)

---

## Directory Structure

```
fire_webapp/
├── lib/                          # Flutter frontend
│   ├── main.dart
│   ├── screens/
│   │   ├── home_screen.dart
│   │   ├── franklin_fire_screen.dart
│   │   ├── palisades_fire_screen.dart
│   │   ├── dolan_fire_screen.dart
│   │   ├── gee_dolan_screen.dart
│   │   ├── enhanced_map_screen.dart
│   │   ├── area_prediction_screen.dart
│   │   └── custom_analysis_screen.dart
│   ├── widgets/
│   │   ├── attribute_panel.dart
│   │   ├── area_selection_controls.dart
│   │   └── prediction_panel.dart
│   ├── services/
│   │   ├── wildcat_service.dart   # HTTP client for Franklin Fire
│   │   └── api_service.dart
│   ├── utils/
│   │   └── geojson_parser.dart    # GeoJSON → flutter_map + hazard colours
│   ├── models/
│   │   └── fire_data.dart
│   └── config/
│       └── app_config.dart
│
├── backend/
│   ├── main.py                    # FastAPI app entry point + CORS
│   ├── api/
│   │   └── routes.py              # All API endpoints
│   ├── services/
│   │   ├── wildcat_service.py     # Franklin Fire pre-computed results
│   │   ├── gis_service.py         # Spatial filtering (Franklin)
│   │   ├── palisades_service.py   # Live pipeline — Palisades (UTM 11N)
│   │   ├── dolan_service.py       # Live pipeline — Dolan (UTM 10N)
│   │   ├── dolan_gee_service.py   # Extends DolanService; GEE Step 2 override
│   │   └── gee_service.py         # GEE auth + DEM download helper
│   └── data/
│       ├── projects/
│       │   └── franklin-fire/
│       │       └── assessment/
│       │           └── basins.geojson   # 51-basin pre-computed result
│       ├── palisades_cache/             # basins.geojson, perimeter.geojson
│       └── dolan_cache/                 # basins.geojson, perimeter.geojson, metadata.json
│
├── assets/
│   └── data/
│       ├── fire_perimeter.shp           # Dolan Fire perimeter
│       ├── dolan_dem_3dep10m.tif        # Local DEM (~1.1 GB, optional with GEE)
│       ├── dolan_inputs_all/
│       │   ├── *_dnbr.tif
│       │   ├── *_rdnbr.tif
│       │   └── *_dnbr6.tif
│       └── 20??_*.json                  # Reference fire catalog (Wildcat outputs)
│
└── notebooks/
    └── calibrate_dolan2.ipynb           # MTBS vs local dNBR calibration
```

---

## Fire Analysis Modes

### Mode 1 — Pre-Computed (Franklin Fire)

The Franklin Fire analysis was run externally using the Wildcat USGS v1.1.0 toolkit (which requires the private `pfdf` package). The backend simply serves `basins.geojson` and performs spatial filtering for user-drawn polygons. No live computation.

### Mode 2 — Live Local Pipeline (Palisades + Dolan)

The full 10-step pipeline runs on-demand in a background thread:

| Step | Description | Tool |
|---|---|---|
| 1 | Validate input files | — |
| 2 | Reproject DEM to UTM, clip to perimeter + buffer | rasterio |
| 3 | Fill topographic depressions | WhiteboxTools |
| 4 | D8 flow direction | WhiteboxTools |
| 5 | D8 flow accumulation | WhiteboxTools |
| 6 | Extract stream network | WhiteboxTools |
| 7 | Delineate sub-basins, vectorise, clip, filter by area | WhiteboxTools + geopandas |
| 8 | Zonal slope + burn severity per basin | rasterio + numpy |
| 9 | Staley (2017) M1 + Gartner (2014) + Cannon (2010) | numpy |
| 10 | Export GeoJSON to cache | json |

Results are cached in `backend/data/{fire}_cache/basins.geojson`. Re-analysis is triggered with `force=True`.

**Pipeline parameters:**

| Parameter | Palisades | Dolan |
|---|---|---|
| UTM zone | 11N (EPSG:32611) | 10N (EPSG:32610) |
| DEM buffer | 500 m | 1000 m |
| Stream threshold | 250 cells ≈ 0.025 km² | 1500 cells ≈ 0.15 km² |
| Basin area filter | 0.01 – 8.0 km² | 0.01 – 3.0 km² |

### Mode 3 — Live GEE Pipeline (Dolan GEE)

`DolanGeeService` inherits `DolanService` and overrides only Step 2. Instead of opening the local 1.1 GB GeoTIFF, it:

1. Authenticates with GEE using locally stored credentials (`earthengine authenticate`)
2. Downloads USGS 3DEP 10m DEM clipped to perimeter + 1 km buffer (~20 MB) via `getDownloadURL()`
3. Reprojects to UTM 10N

Steps 3–10 are identical to Mode 2. The `gee_service` module enforces a 700 km² hard limit before attempting any download.

---

## Debris-Flow Models

### Staley (2017) M1 — Likelihood

Logistic regression for debris-flow probability P:

```
R15 = I15 × (15/60)   # 15-min rainfall accumulation (mm)
T   = sin(2 × slope_rad)   # terrain term
F   = high_sev_ratio        # fraction of basin with high-severity burn
S   = 0.15                  # soil erodibility Kf (constant — see Limitations)

logit = -3.63 + (0.41 + 0.369×R15)×T + (0.67 + 0.603×R15)×F + (0.07 + 0.693×R15)×S
P = 1 / (1 + exp(-logit))
```

### Gartner (2014) — Volume

OLS regression for peak sediment volume V (m³). **Note: the Dolan and Palisades implementations differ:**

**Dolan** (`dolan_service.py`):
```
log10(V) = -0.699 + 0.989×log10(I15) + 0.369×log10(Bmh_km2) + 1.223×log10(Relief_m)
```
where `Bmh_km2 = high_sev_ratio × area_km2` and `Relief_m = max − min elevation`.

**Palisades** (`palisades_service.py`):
```
log10(V) = -1.87 + 0.56×log10(I15) + 0.97×log10(Area_km2) + 0.61×high_sev_ratio
```

### Cannon (2010) — Hazard Classification

**Dolan** (P-only thresholds):

| H | Condition |
|---|---|
| 3 | P ≥ 0.60 |
| 2 | P ≥ 0.40 |
| 1 | P ≥ 0.20 |
| 0 | P < 0.20 |

**Palisades** (joint P + V thresholds):

| H | Condition |
|---|---|
| 3 | P ≥ 0.60 **and** V ≥ 1000 m³ |
| 2 | P ≥ 0.40 **or** V ≥ 500 m³ |
| 1 | P ≥ 0.20 **or** V ≥ 100 m³ |
| 0 | otherwise |

**Rainfall scenarios:** I15 ∈ [16, 20, 24, 40] mm/hr → properties P_0…P_3, V_0…V_3, H_0…H_3

---

## API Reference

All routes are under the `/api/v1` prefix. The backend runs on port 8000.

### Franklin Fire

| Method | Path | Description |
|---|---|---|
| GET | `/fires/{fire_id}/results` | GeoJSON basins (pre-computed) |
| GET | `/fires/{fire_id}/status` | Job status + feature count |
| GET | `/fires/{fire_id}/info` | Fire metadata |
| POST | `/custom-analysis` | Filter basins to user polygon |

### Palisades Fire

| Method | Path | Description |
|---|---|---|
| POST | `/palisades/analyze` | Start full pipeline (`?force=true` to re-run) |
| GET | `/palisades/status/{job_id}` | Poll progress (step 1–10, 0–100%) |
| GET | `/palisades/results` | Cached basins GeoJSON |
| GET | `/palisades/perimeter` | Fire perimeter GeoJSON (WGS84) |
| POST | `/palisades/analyze-zone` | Re-run pipeline clipped to user polygon |
| GET | `/palisades/zone-results/{job_id}` | Zone analysis results |
| POST | `/palisades/custom-analysis` | Spatial filter only (no re-analysis) |
| DELETE | `/palisades/cache` | Clear cached results |

### Dolan Fire (local DEM)

| Method | Path | Description |
|---|---|---|
| POST | `/dolan/analyze` | Start full pipeline (`?burn_metric=dnbr\|rdnbr\|dnbr6`) |
| GET | `/dolan/status/{job_id}` | Poll progress |
| GET | `/dolan/results` | Cached basins GeoJSON |
| GET | `/dolan/perimeter` | Fire perimeter GeoJSON |
| GET | `/dolan/available-inputs` | List available burn severity datasets |
| GET | `/dolan/preview/{dataset}` | Georeferenced PNG overlay (base64) |
| POST | `/dolan/analyze-zone` | Re-run pipeline clipped to user polygon |
| GET | `/dolan/zone-results/{job_id}` | Zone analysis results |
| DELETE | `/dolan/cache` | Clear cached results |

### GEE Routes (Dolan via Google Earth Engine)

| Method | Path | Description |
|---|---|---|
| POST | `/gee/test-connection` | Validate GEE credentials + project ID |
| POST | `/gee/validate-area` | Check polygon fits within 700 km² DEM limit |
| POST | `/gee/dolan/analyze` | Start GEE-based full pipeline |
| GET | `/gee/dolan/status/{job_id}` | Poll progress |
| GET | `/gee/dolan/results` | Results (shares dolan cache) |
| GET | `/gee/dolan/perimeter` | Fire perimeter GeoJSON |
| GET | `/gee/dolan/available-inputs` | Burn severity dataset list |
| POST | `/gee/dolan/analyze-zone` | Re-run pipeline (GEE DEM + user polygon) |
| GET | `/gee/dolan/zone-results/{job_id}` | Zone results |

---

## Frontend Screens

| Screen | Route / Entry | Description |
|---|---|---|
| `HomeScreen` | App root | Navigation hub — featured fire cards + Palisades button |
| `FranklinFireScreen` | Home card | Pre-computed Franklin Fire map + polygon draw |
| `PalisadesFireScreen` | App bar button | Live Palisades analysis, progress bar, zone draw |
| `DolanFireScreen` | Home card | Live Dolan analysis, burn metric selector (dNBR / rdNBR / dNBR6) |
| `GeeDolanScreen` | Home card | GEE-based Dolan analysis, GEE project ID input |
| `EnhancedMapScreen` | Home card | General enhanced map viewer |
| `AreaPredictionScreen` | Home card | Area-based prediction tool |
| `CustomAnalysisScreen` | Home | Custom polygon filter for Franklin Fire |

### Zone Analysis Flow (Palisades + Dolan)

1. User draws polygon on map → Flutter sends `POST /palisades/analyze-zone` or `/dolan/analyze-zone`
2. Backend clips DEM to polygon + buffer, runs full 10-step WBT pipeline in background thread
3. Results saved as `zone_{job_id}.geojson` in cache dir
4. Flutter polls `GET /*/status/{job_id}` until `status == "completed"`
5. Flutter fetches `GET /*/zone-results/{job_id}`
6. Map: full fire basins dimmed (40% opacity), zone basins at full opacity, white boundary outline

### Key flutter_map Notes

- `Polygon` has no `onTap` — basin selection uses `MapOptions.onTap` + ray-casting `_pointInPolygon()` in `geojson_parser.dart`
- `fitCamera` calls must be wrapped in `WidgetsBinding.instance.addPostFrameCallback`
- Hazard colour mapping in `geojson_parser.dart`:
  - P_3 ≥ 0.60 → Red (High)
  - P_3 ≥ 0.40 → Orange (Moderate)
  - P_3 ≥ 0.20 → Yellow (Low)
  - P_3 < 0.20 → Green (Very Low)

---

## Input Data

| Fire | File | Source | Notes |
|---|---|---|---|
| Palisades | `2021_PALISADES_May152021_dem.tif` | Local | Hardcoded absolute path in `palisades_service.py` |
| Palisades | `*_dnbr.tif` | MTBS | Same folder |
| Palisades | `*_burn_bndy.shp` | MTBS | Same folder |
| Dolan | `dolan_dem_3dep10m.tif` | 3DEP (local) | ~1.1 GB; not needed when using GEE mode |
| Dolan | `dolan_inputs_all/*_dnbr.tif` | MTBS | 3 metrics: dNBR, rdNBR, dNBR6 |
| Dolan | `fire_perimeter.shp` | MTBS | In `assets/data/` |
| Franklin | `basins.geojson` | Wildcat v1.1.0 | 51 features, pre-computed |

---

## Known Assumptions and Limitations

These are baked into the current code — relevant for any research use:

1. **Constant Kf = 0.15** — soil erodibility is hardcoded for all basins in both Palisades and Dolan. Real values from STATSGO/SSURGO vary 0.05–0.55 and are the primary driver of inter-basin probability spread.
2. **Mean pixel slope** — Staley (2017) specifies the gradient of the longest flow path; the code uses the arithmetic mean of all DEM pixels in the basin.
3. **Gartner implementations differ between fires** — Dolan uses `Bmh_km2` + `Relief_m`; Palisades uses total `Area_km2` + raw `high_sev_ratio`. Volume values are not directly comparable.
4. **Hazard classification differs between fires** — Dolan uses P-only thresholds; Palisades uses joint P+V thresholds. H values are not comparable across fires.
5. **Fixed I15 design storms** — [16, 20, 24, 40] mm/hr are adopted from wildcat config, not derived from site-specific IDF curves.
6. **Silent fallback values** — basins that throw exceptions during zonal stats are replaced with hardcoded default values rather than flagged as invalid.

---

## Running the Application

### Backend

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**If port 8000 is already in use (WinError 10013):**
```powershell
Stop-Process -Id (netstat -ano | Select-String ':8000.*LISTENING' | ForEach-Object { ($_ -split '\s+')[-1] }) -Force
```

### Frontend

```bash
flutter run -d chrome
```

### GEE Setup (one-time per machine)

```bash
pip install earthengine-api
earthengine authenticate
```

Then provide your GEE project ID (e.g. `ee-yourname`) in the GEE Dolan screen.

---

## Calibration Notebooks

`notebooks/calibrate_dolan2.ipynb` — compares MTBS burn severity (downloaded from GEE) against local dNBR files for the Dolan Fire, and validates Staley P predictions against Wildcat reference output.

**Key findings from the calibration:**
- MTBS and local dNBR are highly correlated for burn fraction (r = 0.982) — MTBS can substitute local dNBR
- MTBS classifies ~75% more moderate-high severity area than the dNBR ≥ 500 threshold
- Both sources produce near-identical, heavily saturated P predictions (≈ 98% H3) for the Dolan Fire, confirming that the constant Kf assumption dominates at high burn severity

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `WinError 10013` on uvicorn start | Port 8000 still in use | Kill with PowerShell command above |
| 404 on `/dolan/*` endpoints | Backend not restarted after code changes | Restart uvicorn — Flutter restart is not enough |
| `CRSError: EPSG code unknown` in notebook | Conda `proj.db` version mismatch | Set `PROJ_DATA` before importing rasterio (handled in cell-setup) |
| GEE `ValueError: Zone area too large` | Polygon exceeds 700 km² | Draw a smaller polygon |
| Basins not displaying | Analysis not yet run, or cache missing | Trigger analysis via the fire screen first |
| Zone analysis stuck at 0% | Backend not restarted after adding zone endpoints | Restart uvicorn |

---

## Credits

**Debris-Flow Models:** Staley et al. (2017), Gartner et al. (2014), Cannon et al. (2010)
**Pre-computed Franklin Fire results:** Wildcat USGS v1.1.0
**DEM source (GEE mode):** USGS 3DEP 10m (`USGS/3DEP/10m_collection`)
**Burn severity:** MTBS (Monitoring Trends in Burn Severity)
**Hydrological processing:** WhiteboxTools (open-source)
