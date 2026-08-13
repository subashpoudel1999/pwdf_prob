# Deployment Status — fire_webapp4 (Wildcat × MHRI Fusion)

Last updated: 2026-07-31. Point a future Claude Code session at this file to resume.

## What this app is

Flutter web frontend + Python/FastAPI backend. Post-wildfire debris-flow hazard
(Wildcat pipeline) fused into the ASBPA Multi-Hazard Resilience Index (MHRI),
using Google Earth Engine for DEM/dNBR data.

## Deployment plan

- **Frontend**: Flutter web build → GitHub Pages (an existing GitHub site will
  be replaced with this build once confident it's ready — not done yet).
- **Backend**: Python/FastAPI → Google Cloud Run (replacing an earlier,
  never-finished Render.com plan — `render.yaml` is still in the repo but
  unused).

## GCP project

- Name: **Wildfire Backend**
- Project ID: `project-8c9919a8-7851-4078-909`
- Project number: `600531524448`
- Billing linked, Earth Engine registered and API enabled.
- Authenticated Google account: `poudelsubash89@gmail.com`
- `gcloud` CLI installed at:
  `C:\Users\Subash\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd`
  (not on PATH in fresh shells — invoke by full path, or refresh PATH from
  Machine+User env vars each session).

## Backend — deployed and working

- Service: `wildcat-mhri-backend`, region `us-west1`
- URL: **https://wildcat-mhri-backend-600531524448.us-west1.run.app**
- Runs as service account:
  `wildcat-render-backend@project-8c9919a8-7851-4078-909.iam.gserviceaccount.com`
  (a leftover from the earlier Render.com attempt, reused here)
- Config: `--no-cpu-throttling`, `--max-instances=1`, `--min-instances=0`,
  `--memory 2Gi`, `--timeout 600`, `--execution-environment=gen2`
- Env vars: `GEE_PROJECT_ID=project-8c9919a8-7851-4078-909`,
  `FIRE_DATA_DIR=/mnt/fire-data`
- GCS volume mount: `gs://wildcat-mhri-fire-data` mounted at `/mnt/fire-data`
  (holds dynamic per-fire data: uploaded perimeters, downloaded DEM/dNBR,
  Wildcat results — survives redeploys and instance scaling, unlike local disk)

**Confirmed working end-to-end** (2026-07-31): uploaded the bundled Malibu CA
shapefile → GEE prepare (DEM + dNBR download) → Wildcat analyze → got back
real debris-flow basin results. Full pipeline tested, not just health checks.

### IAM roles granted to `wildcat-render-backend@...` (on the project)
- `roles/earthengine.viewer` (already had, from earlier session)
- `roles/earthengine.writer` (added — needed for `getDownloadURL()`)
- `roles/serviceusage.serviceUsageConsumer` (added — needed to consume API quota)

### IAM roles granted to `600531524448-compute@developer.gserviceaccount.com`
- `roles/cloudbuild.builds.builder` (newer GCP projects don't auto-grant this)

### GCS bucket IAM
- `wildcat-render-backend@...` has `roles/storage.objectAdmin` on
  `gs://wildcat-mhri-fire-data`

## Redeploying the backend after a code change

`gcloud run deploy --source .` proved unreliable (non-deterministically picked
Buildpacks over the Dockerfile on one attempt, breaking the `-e ../wildcat`
relative install path). Use the explicit two-step form instead, from the repo
root (`c:\Users\Subash\Downloads\webapp`):

```powershell
$gcloud = "C:\Users\Subash\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

& $gcloud builds submit --tag us-west1-docker.pkg.dev/project-8c9919a8-7851-4078-909/cloud-run-source-deploy/wildcat-mhri-backend:latest --region=us-west1 .

& $gcloud run deploy wildcat-mhri-backend `
  --image us-west1-docker.pkg.dev/project-8c9919a8-7851-4078-909/cloud-run-source-deploy/wildcat-mhri-backend:latest `
  --region us-west1 `
  --allow-unauthenticated `
  --service-account wildcat-render-backend@project-8c9919a8-7851-4078-909.iam.gserviceaccount.com `
  --set-env-vars GEE_PROJECT_ID=project-8c9919a8-7851-4078-909,FIRE_DATA_DIR=/mnt/fire-data `
  --add-volume=name=fire-data,type=cloud-storage,bucket=wildcat-mhri-fire-data `
  --add-volume-mount=volume=fire-data,mount-path=/mnt/fire-data `
  --execution-environment=gen2 `
  --memory 2Gi `
  --timeout 600 `
  --no-cpu-throttling `
  --max-instances=1
```

A `.gcloudignore` at the repo root keeps the upload small (excludes Flutter
source, `.venv`, the large `.docx`, etc.) — don't delete it.

## Code changes made this session (uncommitted — see `git status`)

1. **City shapefile dropdown** ([lib/screens/mhri_fusion_screen.dart](lib/screens/mhri_fusion_screen.dart),
   [pubspec.yaml](pubspec.yaml)): added a dropdown of 15 bundled California city
   shapefiles (`assets/CA_city_shapefiles/`) above the manual upload widget on
   the AOI screen, wired into the same upload path a manual file pick uses.

2. **`FIRE_DATA_DIR` refactor** (4 backend files: `wildcat_generic_service.py`,
   `wildcat_fire_prep_service.py`, `wildcat_upload_service.py`,
   `mhri_fusion_service.py`): separated the bundled, read-only wildcat
   package/static catalog (`WILDCAT_DATA_DIR`) from dynamic per-fire output
   data (`FIRE_DATA_DIR`), so the latter can be pointed at the GCS volume
   mount on Cloud Run without shadowing the Python package source. Defaults
   to old behavior (same directory) when `FIRE_DATA_DIR` isn't set — no
   change for local dev or Render.

**Nothing from this session has been committed to git yet.**

## Known remaining limitation

Job *status* tracking (`_jobs`/`_prep_jobs` dicts in the service modules) is
still in-process memory, not GCS — only the underlying fire *data* is
durable. Mitigated with `--max-instances=1` so there's never a second
instance to disagree with. If this app ever needs to serve multiple
concurrent users reliably, that job-status tracking should move to GCS or
Firestore too — not done.

## Still open / next steps

1. **Deploy frontend to GitHub Pages.** User already has an existing GitHub
   site; it'll be replaced once this build is confident/ready. Need:
   `flutter build web --dart-define=BACKEND_URL=https://wildcat-mhri-backend-600531524448.us-west1.run.app/api/v1 --base-href /<repo-name>/`
   then publish `build/web` (e.g. via a `gh-pages` branch or GitHub Actions).
2. **Lock down CORS** in [assets/backend/main.py](assets/backend/main.py) —
   currently `allow_origins=["*"]`, should be restricted to the real GitHub
   Pages origin once known.
3. Commit the uncommitted changes listed above, when ready.
