# Post-Wildfire Debris Flow Hazard Dashboard
## Project Progress Presentation — March 2026

---

## Slide 1: What Is This Project?

**Goal:** A web application that assesses post-wildfire debris-flow hazard for California fire areas.

After a wildfire, burned hillslopes become highly susceptible to debris flows during rainstorms.
This tool helps emergency managers and scientists quickly identify which watersheds are most dangerous.

**Stack:**
- Frontend: Flutter Web (interactive maps, polygon drawing, real-time progress)
- Backend: Python / FastAPI (geospatial pipeline, hazard models)
- GIS Engine: WhiteboxTools (terrain analysis)
- Remote Data: Google Earth Engine (3DEP 10 m DEM)

---

## Slide 2: The Hazard Assessment Pipeline

Every fire area goes through the same **10-step automated pipeline**:

| Step | What It Does |
|------|-------------|
| 1 | Load fire perimeter, DEM, and burn-severity rasters |
| 2 | Reproject DEM to local UTM projection, clip to fire area |
| 3 | Fill topographic depressions (pit removal) |
| 4 | D8 flow direction — where does water flow? |
| 5 | Flow accumulation — how much upslope area drains to each cell? |
| 6 | Extract stream network (threshold: 0.15 km²) |
| 7 | Delineate sub-basins from stream network |
| 8 | Compute slope + burn severity per sub-basin |
| 9 | Run **Staley (2017) M1** probability model + **Gartner (2014)** volume model |
| 10 | Export results as GeoJSON |

**Outputs per basin:**
- `P_0` – `P_3`: debris-flow probability at 4 rainfall intensities (16, 20, 24, 40 mm/hr)
- `V_0` – `V_3`: estimated sediment volume (m³) at each intensity
- `H_0` – `H_3`: combined hazard class (0–3) using Cannon (2010)

---

## Slide 3: What Was Built — System Overview

The full system was built from scratch over the past ~4 weeks.

```
fire_webapp/
├── lib/                         Flutter frontend
│   ├── screens/
│   │   ├── home_screen.dart         → Fire selector dashboard
│   │   ├── franklin_fire_screen.dart→ Franklin Fire (pre-computed results)
│   │   ├── palisades_fire_screen.dart → Palisades Fire (live pipeline)
│   │   ├── dolan_fire_screen.dart   → Dolan Fire (live pipeline) ← NEW
│   │   ├── gee_dolan_screen.dart    → Dolan via Google Earth Engine ← NEW
│   │   ├── custom_analysis_screen.dart → Draw-your-own-zone analysis
│   │   └── area_prediction_screen.dart → Rainfall intensity tool
│   ├── widgets/attribute_panel.dart → Basin detail side panel
│   └── utils/geojson_parser.dart   → GeoJSON parsing + map rendering
│
├── backend/
│   ├── services/
│   │   ├── palisades_service.py     → Palisades pipeline (872 lines)
│   │   ├── dolan_service.py         → Dolan pipeline (872 lines) ← NEW
│   │   ├── gee_service.py           → GEE authentication + DEM download ← NEW
│   │   ├── dolan_gee_service.py     → Dolan pipeline via GEE ← NEW
│   │   ├── wildcat_service.py       → Pre-computed results loader
│   │   └── gis_service.py           → Spatial filtering (Shapely)
│   └── api/routes.py                → FastAPI endpoints (260 lines) ← NEW
│
├── notebooks/
│   ├── calibrate_dolan.ipynb        ← NEW
│   └── calibrate_dolan2.ipynb       ← NEW
│
└── assets/data/
    ├── fire_perimeter.shp           → Dolan Fire perimeter ← NEW
    └── dolan_inputs_all/            → dNBR, rdNBR, dNBR6 rasters ← NEW
```

---

## Slide 4: Fire #1 — Franklin Fire (Baseline)

- **Location:** Malibu, Los Angeles County
- **Status:** Pre-computed results from USGS Wildcat toolkit
- **Basins:** 51 delineated sub-basins
- **UI Features:**
  - 5 interactive map layers (probability, volume, hazard at each rainfall intensity)
  - Polygon drawing tool — user draws a zone, backend filters and re-summarizes that area
  - Hazard color ramp: green → yellow → orange → red
  - Side panel shows all model parameters for any clicked basin

**Key discovery:** USGS Wildcat requires private package `pfdf>=3.0.0` (not publicly available).
Solved by serving the pre-computed `basins.geojson` and implementing custom spatial filtering.

---

## Slide 5: Fire #2 — Palisades Fire (Live Pipeline)

- **Location:** Pacific Palisades, Los Angeles, CA
- **Burn date:** May 2021
- **DEM:** 3DEP 10 m, stored locally (1.1 GB)
- **UTM Zone:** 11N (EPSG:32611)

**New features over Franklin:**
- Full live pipeline runs in the browser — user clicks "Run Analysis," watches 10 steps complete
- Real-time progress bar with animated step icons
- Zone analysis: user draws polygon → backend re-runs the full pipeline clipped to that zone
- Full-fire basins displayed at 40% opacity, zone basins at 100% opacity with white boundary
- Results cached — subsequent runs are instant

**Endpoints added:**
```
POST /api/v1/palisades/analyze
GET  /api/v1/palisades/status/{job_id}
GET  /api/v1/palisades/results
GET  /api/v1/palisades/perimeter
POST /api/v1/palisades/analyze-zone
GET  /api/v1/palisades/zone-results/{job_id}
```

---

## Slide 6: Fire #3 — Dolan Fire (NEW this period)

- **Location:** Big Sur coast, Monterey County, CA (~36.1°N, 121.4°W)
- **Burn date:** August 2020
- **UTM Zone:** 10N (EPSG:32610)
- **Burn severity metrics:** dNBR, rdNBR, dNBR6 (all three available)

**What was built:**
- `DolanService` — full 10-step pipeline adapted for Dolan geography (872 lines)
- `DolanFireScreen` — Flutter UI with configure → analyzing → results flow (1,475 lines)
- Burn metric selector: user can choose dNBR, rdNBR, or dNBR6 before running
- Same zone-analysis capability as Palisades
- Fire perimeter shapefile included as a bundled app asset

**Burn severity thresholds used:**

| Metric | Burned | High Severity |
|--------|--------|---------------|
| dNBR   | ≥ 100  | ≥ 500         |
| rdNBR  | ≥ 69   | ≥ 316         |
| dNBR6  | ≥ 4 (class) | ≥ 5 (class) |

---

## Slide 7: Major Technical Achievement — Google Earth Engine Integration (NEW)

### The Problem
The local DEM file for Dolan Fire is **1.1 GB**.
- GitHub blocks files > 100 MB → can't be committed
- Hardcoded Windows path → can't deploy to any server
- Every new fire would require a separate 1+ GB download

### The Solution: On-Demand DEM via Google Earth Engine

GEE hosts the full USGS 3DEP 10 m DEM for all of CONUS.
Instead of downloading the whole fire area upfront, we:
1. Authenticate with GEE using locally stored credentials
2. At analysis time, send the fire perimeter to GEE
3. GEE clips the DEM to perimeter + 1 km buffer (~20 MB download instead of 1.1 GB)
4. Download the clip as a GeoTIFF, proceed with normal pipeline

### What Was Built

**`gee_service.py`** (183 lines):
- `initialize()` — authenticate with local earthengine credentials
- `download_dem_clip()` — clip 3DEP DEM to any polygon, download as GeoTIFF
- `estimate_area_km2()` — check download size before requesting (safe limit: 700 km²)
- `test_connection()` — verify GEE is reachable and project ID is valid

**`DolanGeeService`** — inherits entire 10-step Dolan pipeline, overrides only Step 2:
```
OLD Step 2: open local dolan_dem_3dep10m.tif (1.1 GB)
NEW Step 2: call gee_service.download_dem_clip() → ~20 MB download
Steps 3–10: completely unchanged
```

**`GeeDolanScreen`** (1,910 lines) — new Flutter UI with 5 states:
1. **Connect** — user enters GEE project ID, app tests connection
2. **Configure** — choose burn metric, set parameters
3. **Draw Area** — optional: draw zone before full analysis
4. **Analyzing** — 10-step progress with GEE-specific step labels
5. **Results** — same interactive map as Dolan/Palisades screens

---

## Slide 8: GEE Screen — User Flow

```
User opens GEE Dolan Screen
         │
         ▼
  [1] Enter GEE Project ID
      → App pings GEE API to verify connection
      → Shows "Connected to project X. 3DEP 10m DEM is accessible."
         │
         ▼
  [2] Configure Analysis
      → Select burn metric (dNBR / rdNBR / dNBR6)
      → Optionally restrict to a drawn polygon
         │
         ▼
  [3] Run Analysis
      → Step 2 message: "Downloading 3DEP 10m DEM from Google Earth Engine..."
      → ~20 MB download (vs. 1.1 GB local file)
      → Steps 3–10 identical to local Dolan pipeline
         │
         ▼
  [4] Interactive Results Map
      → Basins colored by hazard class
      → Click any basin → side panel shows P, V, H at all 4 rainfall intensities
```

---

## Slide 9: Calibration Notebooks (NEW)

Two Jupyter notebooks created for model verification:

**`calibrate_dolan.ipynb`** and **`calibrate_dolan2.ipynb`**:
- Explore raw dNBR/rdNBR/dNBR6 distributions across the Dolan burn area
- Verify that Staley (2017) input variables fall within model calibration range
- Test basin-level slope statistics against expected Big Sur terrain
- Cross-check predicted probabilities against published Dolan post-fire assessments

---

## Slide 10: Deployment — GitHub Pages

The Flutter web app is deployed automatically via GitHub Actions:

```yaml
# .github/workflows/deploy.yml
# Triggers on every push to main
# Builds Flutter web → deploys to GitHub Pages
```

- Fixed deployment pipeline to use `peaceiris/actions-gh-pages` method
- Backend still requires a separate server (local or cloud)
- STATIC_TO_GEE.md documents the full plan for cloud-deploying the backend
  without local raster files

---

## Slide 11: Cumulative Lines of Code

| Component | Lines |
|-----------|-------|
| `dolan_service.py` | 872 |
| `gee_dolan_screen.dart` | 1,910 |
| `dolan_fire_screen.dart` | 1,475 |
| `gee_service.py` | 183 |
| `dolan_gee_service.py` | 147 |
| `routes.py` (new endpoints) | 260 |
| `STATIC_TO_GEE.md` | 325 |
| **New code this period** | **~5,200 lines** |

Plus the initial commit (~3,000+ lines for Palisades + Franklin + all infrastructure).

---

## Slide 12: Hazard Models Used

All three fires use the same published, peer-reviewed models:

### Staley et al. (2017) — Debris-Flow Probability
Logistic regression (Model M1):
```
P = 1 / (1 + exp(-(b0 + b1·X1 + b2·X2 + b3·X3)))
```
Where X1 = % burned area with steep slopes, X2 = high-severity burn fraction, X3 = rainfall intensity

### Gartner et al. (2014) — Debris-Flow Volume
OLS regression for sediment volume (m³):
```
log(V) = a·log(i15) + b·(burned_area) + c·(relief) + d
```

### Cannon et al. (2010) — Combined Hazard Class
H = 0 (Very Low) → 1 (Low) → 2 (Moderate) → 3 (High)
Based on combined P × V product at each rainfall intensity.

**Rainfall intensities tested:** 16, 20, 24, 40 mm/hr (15-minute peak)

---

## Slide 13: What's Next

**Immediate:**
- GEE service account setup for cloud deployment (no user auth required)
- Replace hardcoded WhiteboxTools path with platform-detected or pip-installed version
- Replace hardcoded Palisades DEM path with GEE download (same pattern as Dolan GEE)

**Upcoming:**
- Add more fire events (fully data-driven — any MTBS fire can be added)
- Rainfall scenario tool: enter a custom I15 → get real-time hazard update
- Export results to PDF report

---

## Summary

In the past 4 weeks, this project went from concept to a working multi-fire hazard dashboard:

| Milestone | Status |
|-----------|--------|
| Franklin Fire (pre-computed) | ✅ Complete |
| Palisades Fire (live pipeline) | ✅ Complete |
| Dolan Fire (live pipeline) | ✅ Complete — new this period |
| Google Earth Engine integration | ✅ Complete — new this period |
| Cloud deployment pathway | ✅ Documented |
| GitHub Pages deployment | ✅ Working |
| Model calibration notebooks | ✅ Complete — new this period |

The key advancement: the GEE integration eliminates the 1.1 GB local DEM dependency,
making the full pipeline deployable to any cloud server and scalable to any future fire.
