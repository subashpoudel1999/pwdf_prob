# Wildfire Debris-Flow Hazard Dashboard - Architecture

**Last Updated:** February 16, 2026
**Status:** Production Ready (MVP)

---

## Overview

This Flutter web application displays post-wildfire debris-flow hazard assessments for the Franklin Fire (2024) using results from the USGS Wildcat toolkit. The system serves pre-computed analysis results and provides spatial filtering for custom area analysis.

---

## System Architecture

### Technology Stack

**Frontend:**
- Flutter 3.x (Web/Mobile)
- flutter_map for interactive mapping
- http package for API communication
- Dart GeoJSON parsing utilities

**Backend:**
- FastAPI (Python 3.13)
- Shapely for spatial operations
- Pre-computed Wildcat results (basins.geojson)

**Data Source:**
- Wildcat USGS v1.1.0 pre-computed results
- Franklin Fire 2024 (Malibu, California)
- 51 debris-flow hazard basins

---

## Key Design Decision: Why Pre-Computed Results?

**The Challenge:**
Wildcat requires the private USGS package `pfdf>=3.0.0` which is not publicly available. This package provides core functionality for:
- Raster operations (`pfdf.raster.Raster`)
- Debris-flow models (Staley 2017, Gartner 2014, Cannon 2010)
- Segment/basin delineation
- Watershed analysis

**Our Solution:**
Instead of running Wildcat programmatically, we:
1. Use the existing pre-computed Franklin Fire analysis results
2. Serve `wildcat/franklin-fire/assessment/basins.geojson` via FastAPI
3. Implement spatial filtering (not full re-analysis) for custom polygons

This approach provides a working MVP while maintaining the ability to display real debris-flow hazard data.

---

## Backend Architecture

### Directory Structure

```
backend/
├── main.py                    # FastAPI app entry point
├── api/
│   └── routes.py              # API endpoints
├── services/
│   ├── wildcat_service.py     # Loads pre-computed results
│   └── gis_service.py         # Spatial filtering
└── data/
    └── projects/
        └── franklin-fire/
            ├── inputs/        # DEM, dNBR, severity, perimeter
            ├── preprocessed/  # Wildcat preprocessed rasters
            └── assessment/    # basins.geojson (KEY FILE)
```

### API Endpoints

**1. Get Franklin Fire Results**
```
GET /api/v1/fires/franklin-fire/results
```
Returns: GeoJSON FeatureCollection with 51 debris-flow hazard basins

**2. Get Fire Status**
```
GET /api/v1/fires/franklin-fire/status
```
Returns:
```json
{
  "fire_id": "franklin-fire",
  "status": "completed",
  "has_results": true,
  "feature_count": 51,
  "source": "pre-computed"
}
```

**3. Custom Area Analysis**
```
POST /api/v1/custom-analysis
Content-Type: application/json

{
  "polygon": {
    "type": "Polygon",
    "coordinates": [[[-118.71, 34.07], ...]]
  }
}
```
Returns: Filtered basins that intersect user polygon + statistics

**4. Get Fire Info**
```
GET /api/v1/fires/franklin-fire/info
```
Returns: Metadata about fire, data sources, model parameters

**5. Health Check**
```
GET /health
```
Returns: `{"status": "ok", "service": "wildcat-api"}`

---

## Data Format: basins.geojson

### Structure
```json
{
  "type": "FeatureCollection",
  "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4269"}},
  "features": [
    {
      "type": "Feature",
      "properties": {
        "Segment_ID": 4,
        "Area_km2": 0.17,
        "BurnRatio": 0.94,
        "Slope": 0.27,

        "H_0": 1.0,  "P_0": 0.14,  "V_0": 1574.25,
        "H_1": 1.0,  "P_1": 0.20,  "V_1": 1892.53,
        "H_2": 2.0,  "P_2": 0.28,  "V_2": 2235.32,
        "H_3": 2.0,  "P_3": 0.70,  "V_3": 3897.58,

        "Vmin_0_0": 205.03,  "Vmax_0_0": 12087.15,
        ...
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-118.702843, 34.072919], ...]]
      }
    }
  ]
}
```

### Key Properties

**Watershed Characteristics:**
- `Area_km2`: Basin catchment area
- `BurnRatio`: Proportion of burned area (0-1)
- `Slope`: Average slope gradient
- `DevAreaKm2`: Developed area in km²

**Hazard Results (for 4 rainfall intensities: 16, 20, 24, 40 mm/hr):**
- `H_0, H_1, H_2, H_3`: Combined hazard classification (1=Low, 2=Moderate, 3=High)
- `P_0, P_1, P_2, P_3`: Debris-flow probability (0-1)
- `V_0, V_1, V_2, V_3`: Potential sediment volume (m³)
- `Vmin_*_0, Vmax_*_0`: Volume confidence bounds (95% CI)

**Rainfall Thresholds:**
- `I_*_*`: Rainfall intensity thresholds (mm/hr)
- `R_*_*`: Rainfall accumulation thresholds (mm)

---

## Frontend Architecture

### Key Screens

**1. Home Screen** ([home_screen.dart](lib/screens/home_screen.dart))
- Large Franklin Fire hero card
- Search functionality for other fires
- "Area Selection" tool card

**2. Franklin Fire Screen** ([franklin_fire_screen.dart](lib/screens/franklin_fire_screen.dart))
- Full Franklin Fire analysis display
- 5 map layer options: Satellite, Terrain, Dark, Topo, Standard
- Custom polygon drawing for sub-area analysis
- Interactive basin selection with attribute panel
- Hazard color-coding (red/orange/yellow/green by P_3)

**3. Custom Analysis Screen** ([custom_analysis_screen.dart](lib/screens/custom_analysis_screen.dart))
- Standalone polygon drawing tool
- Filters Franklin Fire basins to user area
- Displays hazard statistics

### Services

**WildcatService** ([lib/services/wildcat_service.dart](lib/services/wildcat_service.dart))
```dart
static Future<bool> hasResults(String fireId)
static Future<Map<String, dynamic>> fetchWildcatResults(String fireId)
static Future<String> getAnalysisStatus(String fireId)
static Future<Map<String, dynamic>> getFireInfo(String fireId)
```

### Utilities

**GeoJSON Parser** ([lib/utils/geojson_parser.dart](lib/utils/geojson_parser.dart))
- `parseGeoJson()`: Converts GeoJSON to Flutter map objects
- `getHazardColor()`: Maps P_3 probability to color
  - P_3 ≥ 0.7: Red (High)
  - P_3 ≥ 0.4: Orange (Moderate)
  - P_3 ≥ 0.2: Yellow (Low)
  - P_3 < 0.2: Green (Very Low)

---

## Running the Application

### 1. Start Backend

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Verify:**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/fires/franklin-fire/status
```

### 2. Start Flutter App

```bash
flutter run -d chrome
```

**Or for mobile:**
```bash
flutter run
```

---

## Testing

### Backend Tests

```bash
# Health check
curl http://localhost:8000/health

# Get Franklin Fire status
curl http://localhost:8000/api/v1/fires/franklin-fire/status

# Get results (51 basins)
curl http://localhost:8000/api/v1/fires/franklin-fire/results | jq '.features | length'

# Custom analysis
curl -X POST http://localhost:8000/api/v1/custom-analysis \
  -H "Content-Type: application/json" \
  -d @test_polygon.json
```

### Expected Results

- **Health**: `{"status":"ok","service":"wildcat-api"}`
- **Status**: `{"fire_id":"franklin-fire","status":"completed","has_results":true,"feature_count":51,"source":"pre-computed"}`
- **Results**: 51 basin features with P_0, P_1, P_2, P_3 properties

---

## Understanding Wildcat Workflow

For reference, here's how Wildcat processes fire data (not implemented in MVP):

### 1. **Input Data**
- `perimeter`: Fire boundary shapefile
- `dem`: Digital Elevation Model (10m resolution)
- `dnbr`: Difference Normalized Burn Ratio raster
- `severity`: BARC4 burn severity raster
- `kf`: K-factor (soil erodibility), can be constant or raster

### 2. **Preprocess**
```bash
wildcat preprocess
```
- Buffers fire perimeter (3km default)
- Reprojects all rasters to DEM CRS
- Clips to buffered perimeter
- Constrains dNBR/severity values
- Creates water/development masks

**Output**: `preprocessed/` folder with cleaned rasters

### 3. **Assess**
```bash
wildcat assess
```
- Analyzes watershed (flow directions, slopes, relief)
- Delineates stream segment network
- Filters segments by physical criteria
- Applies debris-flow models:
  - **Staley 2017 M1**: Likelihood estimation
  - **Gartner 2014**: Potential sediment volumes
  - **Cannon 2010**: Combined hazard classification
- Locates terminal outlet basins

**Output**: `assessment/basins.geojson`, `segments.geojson`, `outlets.geojson`

### 4. **Export**
```bash
wildcat export
```
- Converts to desired format (Shapefile, GeoJSON, etc.)
- Filters properties for export
- Reprojects to WGS84 or other CRS

**Output**: `exports/` folder with final products

---

## Hazard Models

### Staley 2017 M1 (Debris-Flow Likelihood)

Estimates probability of debris-flow occurrence given a rainfall event:

**Inputs:**
- I₁₅: Peak 15-minute rainfall intensity (mm/hr)
- dNBR: Burn severity (via dNBR)
- K: Soil erodibility factor
- Terrain relief

**Output:** P (probability from 0 to 1)

### Gartner 2014 (Sediment Volume)

Estimates potential sediment volume:

**Inputs:**
- Burned catchment area
- Terrain relief
- Burn severity

**Output:** V (volume in m³) with 95% confidence interval

### Cannon 2010 (Combined Hazard)

Classifies combined hazard based on P and V:

- **Class 1 (Low)**: Low probability OR small volume
- **Class 2 (Moderate)**: Moderate P and V
- **Class 3 (High)**: High probability AND large volume

---

## Custom Analysis Implementation

Since we can't run Wildcat without the private `pfdf` package, custom analysis works via **spatial filtering**:

### How It Works

1. **User draws polygon** on Franklin Fire map
2. **Flutter sends GeoJSON** to `/api/v1/custom-analysis`
3. **Backend (GISService):**
   - Loads full Franklin Fire basins
   - Converts user polygon to Shapely geometry
   - Filters basins: `basin.intersects(user_polygon)`
   - Calculates statistics (count, area, hazard distribution)
4. **Returns filtered basins** to Flutter
5. **Flutter displays** only basins within custom area

### Limitations

- ✅ **Works**: Viewing basins within custom area
- ✅ **Works**: Getting hazard statistics for custom area
- ❌ **Doesn't Work**: Re-running Wildcat analysis with new DEM/perimeter
- ❌ **Doesn't Work**: Uploading completely new fire data

This is sufficient for the MVP - users can explore different sub-areas of the Franklin Fire.

---

## Future Enhancements

### If `pfdf` Becomes Available

1. **Full Wildcat Integration**
   - Call `from wildcat import preprocess, assess, export` directly
   - Upload fire data (DEM, dNBR, severity, perimeter)
   - Run live analysis, not just serve pre-computed results

2. **Multiple Fires**
   - Support fires beyond Franklin Fire
   - Database storage for analysis results
   - Fire library/catalog

3. **Real-Time Analysis**
   - Progress tracking during Wildcat runs
   - WebSocket updates for long-running assessments
   - Queue system for multiple analyses

### MVP Improvements

1. **Enhanced Visualization**
   - 3D terrain view
   - Animation of hazard scenarios
   - Volume visualization (graduated symbols)

2. **Export Features**
   - Download filtered GeoJSON
   - PDF report generation
   - CSV export of basin properties

3. **Comparison Tools**
   - Compare different rainfall scenarios
   - Compare custom areas
   - Historical fire comparisons

---

## Troubleshooting

### Backend Won't Start

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Fix:**
```bash
pip install fastapi uvicorn shapely
```

### Backend 404 on `/custom-analysis`

**Cause:** Backend didn't reload after code changes

**Fix:**
```bash
taskkill //F //IM python.exe
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Flutter Can't Connect to Backend

**Error:** `Failed to fetch Wildcat results: SocketException`

**Fix:**
1. Ensure backend is running: `curl http://localhost:8000/health`
2. Check CORS is enabled in `backend/main.py`
3. For mobile/other devices, update `lib/services/wildcat_service.dart`:
   ```dart
   static const String baseUrl = 'http://YOUR_IP:8000/api/v1';
   ```

### No Basins Displayed

**Cause:** basins.geojson file missing

**Fix:**
```bash
ls "backend/data/projects/franklin-fire/assessment/basins.geojson"
```
If missing, copy from wildcat folder:
```bash
cp "wildcat/franklin-fire/assessment/basins.geojson" \
   "backend/data/projects/franklin-fire/assessment/"
```

---

## File Manifest

### Backend (Python)
- `backend/main.py` - FastAPI app
- `backend/api/routes.py` - API endpoints
- `backend/services/wildcat_service.py` - Loads pre-computed results
- `backend/services/gis_service.py` - Spatial filtering
- `backend/requirements.txt` - Python dependencies

### Frontend (Flutter)
- `lib/screens/franklin_fire_screen.dart` - Main analysis screen
- `lib/screens/custom_analysis_screen.dart` - Custom polygon tool
- `lib/screens/home_screen.dart` - Landing page
- `lib/services/wildcat_service.dart` - Backend HTTP client
- `lib/utils/geojson_parser.dart` - GeoJSON parsing + hazard colors
- `lib/widgets/attribute_panel.dart` - Basin property display

### Data
- `wildcat/franklin-fire/assessment/basins.geojson` - Source data (268 KB, 51 features)
- `backend/data/projects/franklin-fire/` - Copy used by backend

---

## Credits

**Wildcat USGS Toolkit:** v1.1.0
**Franklin Fire Analysis:** June 2025
**Debris-Flow Models:**
- Staley et al. (2017) - Likelihood model
- Gartner et al. (2014) - Volume model
- Cannon et al. (2010) - Hazard classification

**Development Team:** Claude Code + User
**Institution:** USGS Landslide Hazards Program

---

## License

This application serves public USGS data. Wildcat toolkit is GPL-3.0 licensed.

---

**End of Documentation**
