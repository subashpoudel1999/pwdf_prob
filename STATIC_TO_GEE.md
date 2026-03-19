# Migration Plan: Local Static Files → Google Earth Engine (GEE)

**Document purpose:** Complete technical plan for replacing local raster data files with
on-demand GEE downloads, enabling cloud deployment of the full-stack app.

**Status:** Planning only — no code has been changed yet.

---

## 1. Why We Are Doing This

Currently the backend cannot be deployed to any cloud server because:

| Problem | Detail |
|---|---|
| `dolan_dem_3dep10m.tif` | **1.1 GB** — GitHub blocks files > 100 MB |
| Palisades DEM | Stored at `C:\Users\J01040445\...\` — hardcoded Windows path |
| dNBR / rdNBR / dNBR6 rasters | Local files, not on server |
| WhiteboxTools path | `C:\Users\J01040445\...\WBT` — hardcoded Windows path |

The solution: pull all raster data from **Google Earth Engine** at analysis time,
clipped to only the area we need. The downloaded clip is ~15–30 MB instead of 1.1 GB.

---

## 2. What GEE Provides (Free, No Local Files Needed)

| Data we need | GEE Dataset ID | Notes |
|---|---|---|
| 10 m DEM (whole CONUS) | `USGS/3DEP/10m` | Same source as our local files |
| dNBR burn severity | `USFS/GTAC/MTBS/annual_burn_severity_mosaics/v1` | MTBS dNBR, all fires 1984–present |
| Fire perimeters | `USFS/GTAC/MTBS/burned_area_boundaries/v1` | Matches MTBS burn severity |

> **Important:** The MTBS dataset on GEE has dNBR but not rdNBR or dNBR6 as separate
> bands. Those would need to be computed from dNBR (rdNBR = dNBR / sqrt(abs(preNBR)),
> dNBR6 = classified thresholds). This is doable inside GEE before download.
> Alternatively, rdNBR and dNBR6 could remain as local uploads for now (they are only
> 3 MB each — small enough to store on any server).

---

## 3. Authentication Strategy

### What NOT to do
Do **not** ask website users to authenticate with GEE. That would require every visitor
to have a GEE account, which is impractical.

### What to do — Service Account (silent, backend-only)
1. Create a **Google Cloud Project** (free)
2. Enable the **Earth Engine API** on that project
3. Create a **Service Account** (a non-human credential for servers)
4. Download the Service Account **JSON key file**
5. Store the JSON content as an **environment variable** on the server: `GEE_SERVICE_ACCOUNT_KEY`
6. Backend authenticates silently on startup — users see nothing

```python
# How backend authentication looks in code
import ee
import json, os

key_json = json.loads(os.environ["GEE_SERVICE_ACCOUNT_KEY"])
credentials = ee.ServiceAccountCredentials(
    email=key_json["client_email"],
    key_data=json.dumps(key_json)
)
ee.Initialize(credentials)
```

This runs once when the server starts. No user interaction needed.

---

## 4. The New Data Download Step (Replaces Step 2)

Currently `_step2_reproject_clip()` reads the local DEM file. Under GEE, it becomes:

```
OLD:
  open local dolan_dem_3dep10m.tif (1.1 GB)
  clip to perimeter + 1000m buffer
  reproject to UTM Zone 10N

NEW:
  authenticate GEE (already done at startup)
  ee.Image("USGS/3DEP/10m")
      .clip(fire_perimeter_geometry_buffered_1000m)
      .reproject("EPSG:32610", scale=10)       ← reprojection done inside GEE
  getDownloadURL(format="GEO_TIFF")            ← download ~20 MB clipped GeoTIFF
  save to temp work_dir as "dem_clipped.tif"
  continue pipeline as normal (steps 3–10 unchanged)
```

**Steps 3–10 of the WhiteboxTools pipeline are completely unchanged.**
GEE only replaces the data acquisition part.

---

## 5. Size Estimate of GEE Downloads

The Dolan Fire area at 10m resolution:

```
DEM extent in current local file: 33,998 × 22,879 pixels (entire 3°×2° tile = 1.1 GB)
DEM extent clipped to fire + 1km:  ~3,000 × 4,000 pixels (estimated)
  = 12,000,000 pixels × 4 bytes (float32) = ~48 MB uncompressed
  = ~15–25 MB as compressed GeoTIFF          ← well within GEE download limits
```

GEE's `getDownloadURL()` limit is ~32 MB per band. Our clipped DEM is under that.
For larger fires or higher buffer distances, we may need `ee.batch.Export` to Google
Drive (async, adds ~2–5 min wait). This is an edge case — most fires will be fine.

---

## 6. Handling the Burn Severity Data (dNBR / rdNBR / dNBR6)

### Option A — Keep local (simplest, recommended for now)
The dNBR, rdNBR, dNBR6 tif files are **only 3 MB each**. They can simply be:
- Committed to GitHub (well under the 100 MB limit)
- Or uploaded to the server once as part of deployment

No GEE needed for burn severity. Only the DEM needs GEE.

### Option B — Fetch from GEE MTBS dataset (future improvement)
```python
# Compute dNBR from MTBS on GEE
mtbs = ee.ImageCollection("USFS/GTAC/MTBS/annual_burn_severity_mosaics/v1")
fire_year_image = mtbs.filter(ee.Filter.calendarRange(2020, 2020, "year")).mosaic()
dnbr_band = fire_year_image.select("Severity")  # or dNBR band depending on collection
```
This would make the system work for **any fire, any year** with zero local data files.
Good target for v2.

---

## 7. WhiteboxTools on the Server

Currently: `WBT_DIR = Path(r"C:\Users\J01040445\Downloads\...\WBT")` — Windows only.

On a Linux server, WhiteboxTools installs via pip:
```bash
pip install whitebox
```
The `whitebox` Python package **automatically downloads** the correct WBT binary for
the operating system on first import. No manual installation needed.

```python
# New cross-platform WBT initialization
import whitebox
wbt = whitebox.WhiteboxTools()
# wbt.exe_path is set automatically by the package — no hardcoding
```

This replaces the current `WBT_DIR` path and `sys.path.insert()` pattern in both
`dolan_service.py` and `palisades_service.py`.

---

## 8. Full List of Code Changes Required

### 8.1 `backend/services/dolan_service.py`

| What changes | Current | New |
|---|---|---|
| WBT path | Hardcoded `C:\Users\...` | `import whitebox; wbt = whitebox.WhiteboxTools()` |
| DEM source | Local 1.1 GB `.tif` | GEE download clipped to perimeter |
| dNBR/rdNBR/dNBR6 | Local `.tif` files | Option A: small files committed to repo |
| Fire perimeter | Local `.shp` file | Option A: small file committed to repo |
| `_step2_reproject_clip()` | Reads local DEM | New: `_step2_download_from_gee()` |
| `_step2_reproject_clip_zone()` | Reads local DEM | Same GEE download, but clips to user polygon |
| `_wbt()` helper | Sets `wbt.exe_path` manually | Remove `exe_path` assignment |

### 8.2 `backend/services/palisades_service.py`

| What changes | Current | New |
|---|---|---|
| `_BASE` path | `C:\Users\J01040445\...\PALISADES May152021` | GEE for DEM, local for dNBR |
| `WBT_DIR` | Same hardcoded path | Same fix as dolan |
| DEM source | Local DEM in `_BASE` | GEE download |
| dNBR source | Local `.tif` in `_BASE` | Option A: small file committed to repo |

### 8.3 New file: `backend/services/gee_service.py`
A shared GEE helper module used by both dolan and palisades services:
```python
# Responsibilities:
# - authenticate_gee()         — initialize GEE with service account from env var
# - download_dem_clip(perimeter_geojson, buffer_m, epsg, scale, out_path)
# - is_authenticated() -> bool
```

### 8.4 `backend/requirements.txt`
```
earthengine-api>=0.1.390    # GEE Python client
```

### 8.5 Environment variables needed on server
```
GEE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"...","client_email":"...","private_key":"..."}
```

---

## 9. Deployment Architecture After Migration

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Repository                  │
│                                                     │
│  lib/          ← Flutter frontend code              │
│  backend/      ← FastAPI backend code               │
│  assets/data/  ← ONLY small files:                  │
│    fire_perimeter.shp  (380 KB)                     │
│    dolan_inputs_all/dnbr.tif   (3 MB)               │
│    dolan_inputs_all/rdnbr.tif  (3 MB)               │
│    dolan_inputs_all/dnbr6.tif  (2 MB)               │
└─────────────────────────────────────────────────────┘
          │                          │
          ▼                          ▼
  GitHub Actions               Cloud Server
  build Flutter web            (DigitalOcean $6/mo
  deploy to Pages              or Railway ~$5/mo)
          │                          │
          ▼                          │ on analysis request
  https://subashpoudel1999          │
  .github.io/pwdf_prob/             ▼
  (Flutter frontend)         Google Earth Engine
                             downloads clipped DEM
                             (~20 MB, ~15–30 sec)
                                     │
                                     ▼
                             WhiteboxTools pipeline
                             (steps 3–10, unchanged)
                                     │
                                     ▼
                             GeoJSON results → Flutter
```

---

## 10. GEE Account Setup Steps (One-Time)

1. Go to https://earthengine.google.com → sign up (free, needs Google account)
2. Wait for approval (usually instant for academic/research use)
3. Go to https://console.cloud.google.com
4. Create a new project (e.g., `pwdf-analysis`)
5. Enable **Earth Engine API** on that project
6. Go to IAM → Service Accounts → Create Service Account
7. Give it a name (e.g., `pwdf-backend`)
8. Assign role: **Earth Engine Resource Viewer** (or Editor)
9. Create and download JSON key
10. Store the JSON content as `GEE_SERVICE_ACCOUNT_KEY` env variable on server
11. Register the service account in GEE:
    - Go to https://code.earthengine.google.com
    - Run: `ee.ServiceAccountCredentials(email, key)` — one time registration

---

## 11. Timeline and Risk Assessment

### Phase 1 — Code changes (local, no server yet)
| Task | Effort | Risk |
|---|---|---|
| Fix WhiteboxTools to use pip package | 30 min | Low — well documented |
| Create `gee_service.py` auth + download helper | 2–3 hrs | Medium — GEE API quirks |
| Modify `_step2` in dolan_service to call GEE | 2 hrs | Medium |
| Modify `_step2` in palisades_service to call GEE | 1 hr | Low — same pattern |
| Test locally with GEE downloading real data | 1–2 hrs | Medium — depends on GEE quota |

### Phase 2 — Server deployment
| Task | Effort | Risk |
|---|---|---|
| Provision DigitalOcean / Railway server | 30 min | Low |
| Set environment variables | 15 min | Low |
| Deploy and test end-to-end | 1–2 hrs | Medium — first deployment always has surprises |

### Known Risks
1. **GEE `getDownloadURL()` size limit**: If a fire's clip exceeds ~32 MB, must use
   `ee.batch.Export` → Google Drive → download. Adds async complexity.
   *Mitigation: test Dolan + Palisades clip sizes early.*

2. **GEE download latency**: Adds 15–30 sec to analysis start.
   *Mitigation: show "Fetching terrain data from GEE..." as Step 1 message. Acceptable.*

3. **GEE quota**: Free tier allows ~2,000 exports/day. More than enough for a research demo.
   *Mitigation: cache the downloaded DEM per fire (don't re-download if cache exists).*

4. **MTBS dNBR vs local dNBR**: If we later switch burn severity to GEE MTBS, the values
   may differ slightly from the local files (different processing version). Results could
   change. *Mitigation: keep local burn severity files for now (Option A above).*

---

## 12. Questions to Decide Before Starting

1. **Which server platform?** DigitalOcean Droplet ($6/mo, full VM) vs Railway (~$5/mo, PaaS)?
   - DigitalOcean: more control, easier for large/long-running jobs
   - Railway: easier deploy (git push → live), less setup

2. **Burn severity source?** Keep local 3 MB .tif files (Option A, simpler) or
   switch to GEE MTBS (Option B, no local files at all)?
   - Recommend Option A for now, Option B as a future improvement.

3. **Cache strategy for GEE downloads?** First run downloads from GEE and saves
   `dem_clipped.tif` in the cache dir. Subsequent runs reuse it (skip GEE).
   Clear cache when user changes settings. This avoids re-downloading the DEM
   every single analysis run.

---

## 13. Summary

| | Before | After |
|---|---|---|
| DEM | 1.1 GB local file, can't deploy | Downloaded from GEE at runtime (~20 MB clip) |
| Burn severity | 3 MB local files | Stay local (committed to repo) |
| Fire perimeter | Local .shp | Stay local (committed to repo) |
| WhiteboxTools | Hardcoded Windows path | pip package, cross-platform |
| Backend hosting | Local machine only | Any Linux server (Railway, DigitalOcean, etc.) |
| User auth needed | N/A | None — GEE service account is invisible to users |
| Extra cost | None | GEE free tier + server ~$6/month |
| Steps 3–10 (WBT pipeline) | Unchanged | Unchanged |

The core insight: **only Step 2 changes.** Everything after that — the WhiteboxTools
watershed delineation, the Staley model, the GeoJSON export — stays exactly the same.
GEE is just a smarter way to get the input DEM into the pipeline.
