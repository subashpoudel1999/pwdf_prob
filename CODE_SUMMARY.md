# CODE_SUMMARY.md

**Purpose:** Honest technical audit of what the code actually does vs. what it claims to do.
**Audience:** Research paper review and self-correction.
**Last updated:** 2026-03-23

---

## 1. The Three Fires — What Kind of Analysis Runs

| Fire | Mode | What actually happens |
|---|---|---|
| **Franklin Fire** | Pre-computed | A static `basins.geojson` file produced offline by the actual USGS `pfdf`/Wildcat tool is loaded from disk and served as-is. No model runs at request time. |
| **Palisades Fire** | Live re-implementation | A custom Python re-implementation of the pipeline runs using WhiteboxTools. This is **not** Wildcat/pfdf. |
| **Dolan Fire (local)** | Live re-implementation | Same as Palisades — custom Python re-implementation. |
| **Dolan Fire (GEE)** | Live re-implementation | Same pipeline as Dolan local, but DEM is fetched from USGS 3DEP via Google Earth Engine instead of from a local 1.1 GB file. |

**Key implication:** Franklin Fire results are from the authoritative Wildcat tool. Palisades and Dolan results are from our own re-implementation. The two are **not** methodologically equivalent.

---

## 2. The "Wildcat Model" — What It Actually Is

"Wildcat" (USGS `pfdf` package) is a complete pipeline that includes:
1. Watershed delineation from a DEM
2. Per-basin extraction of terrain, soil, and fire severity parameters
3. Staley (2017) M1 logistic regression for debris-flow probability
4. Gartner (2014) OLS regression for debris-flow volume
5. Cannon (2010) combined hazard classification

We have reimplemented parts 1, 2, 3, 4, and 5 ourselves.
We do **not** use the `pfdf` package for Palisades or Dolan.

---

## 3. Model Formulas — What Is Coded vs. What Is Published

### 3.1 Staley (2017) M1 Logistic Regression

**Published M1 (parameterized form):**
```
logit = B0 + (B1 + c1*R15)*T + (B2 + c2*R15)*F + (B3 + c3*R15)*S
P = 1 / (1 + exp(-logit))
```
Where:
- `T` = terrain term = `sin(2 * slope_rad)`
- `F` = fire term = fraction high-severity burned (Bmh / basin area)
- `S` = soil erodibility (Kf factor, from STATSGO/SSURGO)
- `R15` = 15-min rainfall accumulation = `I15 * (15/60)` mm
- `B0 = -3.63`, `B1 = 0.41`, `B2 = 0.67`, `B3 = 0.07`
- `c1 = 0.369`, `c2 = 0.603`, `c3 = 0.693`

**Dolan implementation** ([dolan_service.py:671](backend/services/dolan_service.py#L671)):
```python
R15 = I15 * (15.0 / 60.0)
T = np.sin(2 * slope_r)
F = high_sev              # fraction high-severity burned
S = 0.15                  # HARDCODED CONSTANT — see Assumption A1
logit = -3.63 + (0.41 + 0.369*R15)*T + (0.67 + 0.603*R15)*F + (0.07 + 0.693*R15)*S
```
**Status:** Correct parameterized form. One known deviation: `S = 0.15` is constant (see § 5.1).

---

**Palisades implementation** ([palisades_service.py:540](backend/services/palisades_service.py#L540)):
```python
terrain  = STALEY_B1 * np.sin(2 * slope_r)
fire_term = STALEY_B2 * high_sev
rainfall = STALEY_B3 * np.sqrt(I15 * burn_ratio)   # ← NOT M1 formula
X = STALEY_B0 + terrain + fire_term + rainfall
P = 1.0 / (1.0 + np.exp(-X))
```

**This is NOT the published M1 formula.** Differences:
- The rainfall term uses `sqrt(I15 * burn_ratio)` — a custom proxy. Published M1 uses `(B3 + c3*R15) * S` where `S` is Kf.
- The soil term `S` is **entirely absent** from the Palisades implementation.
- `burn_ratio` (any burned area, dNBR > 100) is used in the rainfall proxy instead of `high_sev` (high-severity area) or Kf.
- There is no R15 expansion — the rainfall coefficient is fixed at `B3 = 0.07`.

**Conclusion:** Palisades uses a simplified/modified equation that is structurally different from M1. It should not be described as "Staley (2017) M1" in a paper without explicit clarification of these deviations.

---

### 3.2 Gartner (2014) OLS Volume Regression

These two fires use different equations. They cannot be directly compared.

**Dolan** ([dolan_service.py:681](backend/services/dolan_service.py#L681)):
```
log10(V) = -0.699 + 0.989*log10(I15) + 0.369*log10(Bmh_km2) + 1.223*log10(Relief_m)
```
Inputs:
- `Bmh_km2` = high_sev_ratio × Area_km2 (proxy for high-severity area in km²)
- `Relief_m` = max(DEM) − min(DEM) within basin (computed on filled DEM — see Assumption A6)

**Palisades** ([palisades_service.py:550](backend/services/palisades_service.py#L550)):
```
log10(V) = -1.87 + 0.56*log10(I15) + 0.97*log10(Area_km2) + 0.61*high_sev_ratio
```
Inputs:
- `Area_km2` = total basin area (not just burned area)
- `high_sev_ratio` = fraction high-severity (entered as a **proportion**, not log-transformed — this is dimensionally inconsistent with the other log-transformed terms)

**Known issues with the Palisades Gartner formula:**
1. Uses total area (`Area_km2`) where Gartner uses `Bmh` (burned moderate-high area). These are different quantities.
2. The `high_sev_ratio` term is used as a raw proportion (e.g., 0.8), not log-transformed, while all other predictors are log-transformed. This is inconsistent with the OLS regression form.
3. The coefficients (-1.87, 0.56, 0.97, 0.61) differ from both the published Gartner (2014) and the Dolan implementation.

---

### 3.3 Cannon (2010) Hazard Classification

The two live fires use different classification schemes. **They are not comparable.**

**Dolan** — probability-only thresholds ([dolan_service.py:692](backend/services/dolan_service.py#L692)):
```
H = 3 if P >= 0.60
H = 2 if P >= 0.40
H = 1 if P >= 0.20
H = 0 otherwise
```

**Palisades** — joint probability AND volume thresholds ([palisades_service.py:560](backend/services/palisades_service.py#L560)):
```
H = 3 if P >= 0.60 AND V >= 1000 m³
H = 2 if P >= 0.40 OR  V >= 500 m³
H = 1 if P >= 0.20 OR  V >= 100 m³
H = 0 otherwise
```

A basin with P = 0.70 and V = 50 m³ would be H3 in Dolan but H2 in Palisades.
A basin with P = 0.15 and V = 600 m³ would be H0 in Dolan but H2 in Palisades.

---

## 4. Pipeline Parameters — What Was Chosen and Why

| Parameter | Dolan | Palisades | Basis |
|---|---|---|---|
| UTM zone | 10N (EPSG:32610) | 11N (EPSG:32611) | Geography (correct) |
| DEM buffer | 1000 m | 500 m | Dolan: matches wildcat config; Palisades: arbitrary |
| Stream threshold | 1500 cells = 0.15 km² | 250 cells = 0.025 km² | Dolan: wildcat config; Palisades: 6× smaller |
| Min basin area | 0.01 km² | 0.01 km² | Both same |
| Max basin area | 3.0 km² | 8.0 km² | Dolan: tighter (Big Sur terrain); Palisades: wider |
| Zone analysis DEM buffer | 1000 m | 200 m | Palisades zone uses only 200m — may cut drainage context |
| Rainfall intensities I15 | [16, 20, 24, 40] mm/hr | [16, 20, 24, 40] mm/hr | Matches Wildcat defaults |
| Depression fill method | fill_depressions (WBT) | fill_depressions (WBT) | WBT default |
| Flow direction method | D8 | D8 | WBT default |
| Slope units | degrees (converted to radians) | degrees (converted to radians) | Correct |
| Resampling method | bilinear (DEM) | bilinear (DEM) | Appropriate |

---

## 5. Assumptions and Shortcuts — Full List

### A1. Constant Kf = 0.15 (Dolan only)

**Where:** [dolan_service.py:670](backend/services/dolan_service.py#L670)
**Code:** `S = 0.15`
**What it means:** The Staley M1 soil erodibility factor (Kf) is set to 0.15 for every basin in the Dolan fire area. This is the median value for silty clay loam in the RUSLE Kf table.
**What Wildcat does:** Looks up actual STATSGO/SSURGO soil data per basin and computes a spatially variable Kf.
**Impact:** This is a major driver of model saturation. At I15 = 40 mm/hr, the soil contribution alone is `(0.07 + 0.693 * (40*15/60)) * 0.15 ≈ 0.63`, which when combined with high fire severity gives logits well above +3.0, pushing P → 96% for almost every basin regardless of terrain. The calibration notebook confirmed ~98% of Dolan basins output H3.

---

### A2. No Soil Term in Palisades Staley Formula

**Where:** [palisades_service.py:540](backend/services/palisades_service.py#L540)
**What it means:** The Palisades Staley implementation has no `S` (Kf) term at all. The rainfall proxy `sqrt(I15 * burn_ratio)` is used instead, which conflates rainfall intensity with fire severity in a way that has no published basis in M1.

---

### A3. Bmh_km2 Is a Proxy, Not a Direct Measurement

**Where:** [dolan_service.py:661](backend/services/dolan_service.py#L661)
**Code:** `Bmh_km2 = max(high_sev * area_km2, 0.001)`
**What it means:** The area burned at moderate-to-high severity is computed by multiplying the *fraction* of high-severity pixels (from dNBR thresholding) by the *total* basin area. This is a reasonable approximation but is not a direct pixel-count area measurement.
**Floor value:** A minimum of 0.001 km² is enforced to prevent log10(0) errors. Any basin with zero high-severity pixels is given 0.001 km².

---

### A4. Relief Uses the Filled DEM

**Where:** [dolan_service.py:614](backend/services/dolan_service.py#L614)
**Code:** Relief is computed from `filled_dem` — the DEM after WhiteboxTools `fill_depressions`.
**Impact:** Depression filling raises pit values to match the surrounding pour point. Relief values in low-gradient basins with depressions will be slightly underestimated compared to using the raw DEM. For the steep Big Sur terrain this is likely minor.

---

### A5. Silent Fallback Values on Raster Extraction Failure

**Where:** [dolan_service.py:625](backend/services/dolan_service.py#L625), [palisades_service.py:516](backend/services/palisades_service.py#L516)

If the `rasterio.mask` operation fails for any basin (e.g., geometry outside raster extent, nodata-only patch), the code silently substitutes fixed "high severity" default values:

| | Dolan fallback | Palisades fallback |
|---|---|---|
| slope_rad | 0.35 (≈20°) | 0.26 (≈15°) |
| burn_ratio | 0.85 | 0.85 |
| high_sev_ratio | 0.45 | 0.40 |
| relief_m | 100.0 | *(no relief in Palisades)* |

**These fallbacks are not flagged in the output.** A basin using fallback values looks identical in the output GeoJSON to a basin with real raster data. There is no `data_quality` or `used_fallback` field in the output properties.

---

### A6. Basin Delineation Fallback — Entire Perimeter as One Basin

**Where:** [dolan_service.py:550](backend/services/dolan_service.py#L550), [palisades_service.py:462](backend/services/palisades_service.py#L462)
**Code:** If WhiteboxTools delineates zero basins after the area filter, the entire fire perimeter polygon is used as a single basin.
**Impact:** This is a last-resort fallback that would produce one coarse result for the whole fire area. It is not documented or flagged in the output.

---

### A7. dNBR Thresholds Are Fixed — Not Validated Against Field Data

**Where:** [dolan_service.py:90](backend/services/dolan_service.py#L90)

| Metric | "Burned" threshold | "High severity" threshold |
|---|---|---|
| dNBR | > 100 | > 500 |
| rdNBR | > 69 | > 316 |
| dNBR6 | class ≥ 4 | class ≥ 5 |

These thresholds follow USFS Key et al. (2006) conventions. They have **not** been validated against ground-truth Dolan Fire severity data. The calibration notebook showed that MTBS dNBR systematically produces ~75% more moderate-high burn area than the local dNBR raster for the same fire, suggesting the threshold choice has a large effect.

---

### A8. Stream Threshold Difference Creates Incomparable Basin Geometries

Dolan uses a 1500-cell (0.15 km²) stream threshold; Palisades uses a 250-cell (0.025 km²) threshold. This means:
- Palisades generates 6× more stream channels → smaller, more numerous basins
- Dolan generates larger, fewer basins
- Comparing H or P values across fires as if they represent equivalent spatial units is not valid.

---

### A9. Franklin Fire Uses the Actual Wildcat Tool Output

The Franklin Fire basins.geojson was generated by running the `pfdf` (Wildcat) Python package offline. The parameters used (stream threshold, Kf values, DEM source, Gartner formula variant) are whatever `pfdf` used internally. These parameters are **not documented** in this codebase. Comparing Franklin Fire outputs to Dolan or Palisades outputs requires knowing exactly what pfdf used.

---

### A10. No Validation Against Observed Debris Flows

None of the three fire analyses in this app have been validated against a catalog of actual debris-flow occurrence or non-occurrence. The Dolan calibration notebook compared our output against the `pfdf`/wildcat reference output for the same fire, but this is an implementation comparison, not a predictive skill assessment.

---

### A11. Palisades DEM Buffer for Zone Analysis Is Only 200m

**Where:** [palisades_service.py:261](backend/services/palisades_service.py#L261)
For a user-drawn zone analysis, the DEM is clipped to the polygon with only a 200m buffer. For the full-fire analysis, a 500m buffer is used. At 200m, drainage from outside the user-drawn polygon may be truncated, potentially affecting flow accumulation and sub-basin delineation for basins near the polygon boundary.

---

### A12. Rainfall Intensities Are Not Location-Specific

I15 = [16, 20, 24, 40] mm/hr are used for all fires. These correspond roughly to the 2-, 5-, 10-, and 25-year return period 15-minute storms from NOAA Atlas 14. However:
- No NOAA Atlas 14 lookup is performed per fire location
- The same four values are applied to Big Sur (Dolan) and Los Angeles (Palisades) despite different regional storm climatologies

---

## 6. Parameters Stored in Output vs. Parameters Used in Model

The GeoJSON properties stored per basin are:

| Property | Present | What it is |
|---|---|---|
| `Area_km2` | Both fires | Total basin area in km² |
| `BurnRatio` | Both fires | Fraction of basin with dNBR > threshold (any burn) |
| `Slope` | Both fires | Mean slope in **radians** |
| `P_0` – `P_3` | Both fires | Debris-flow probability at I15 = 16, 20, 24, 40 mm/hr |
| `V_0` – `V_3` | Both fires | Volume estimate (m³) at each I15 |
| `H_0` – `H_3` | Both fires | Hazard class (0–3) at each I15 |

**Not stored in output (but used in model):**
- `high_sev_ratio` (F in M1) — used but not stored
- `relief_m` (Dolan only) — used but not stored
- `Bmh_km2` (Dolan only) — used but not stored
- Whether fallback values were used

---

## 7. Cross-Fire Comparability Summary

| Comparison | Valid? |
|---|---|
| Franklin H values vs. Dolan H values | No — different tools, different hazard classification schemes |
| Franklin H values vs. Palisades H values | No — different tools |
| Dolan H values vs. Palisades H values | No — different Cannon thresholds (P-only vs. P+V joint) |
| Dolan P values vs. Palisades P values | No — different Staley implementations (M1 parameterized vs. custom simplified) |
| Dolan V values vs. Palisades V values | No — different Gartner formulas (Bmh+Relief vs. Area+fraction) |
| Dolan GEE vs. Dolan local | Yes — identical model code, only DEM source differs |

---

## 8. What "WhiteboxTools" Does and Does Not Do

WhiteboxTools (WBT) is used for steps 3–7 of the pipeline. It handles the terrain analysis reliably. However:

- WBT's `subbasins` tool produces basins that may include non-fire areas — the code clips to the fire perimeter + 50–100m buffer afterward (Step 7).
- WBT may strip the CRS from output rasters/shapefiles — the code reassigns the CRS after each WBT output read.
- WBT's vector polygon output may have invalid geometries (winding order issues) — the code applies `buffer(0)` to repair them silently.
- If WBT's shapefile output is unreadable, the perimeter is used as a fallback basin (see A6).

None of these fallbacks are reflected in the output.

---

## 9. Flutter Frontend — What It Displays vs. What It Shows

The Flutter app displays the following per basin in the attribute panel:
- `BurnRatio` — labeled as burn fraction
- `Slope` — in radians (this may be confusing to end users who expect degrees)
- `P_0` to `P_3` — probability values for each storm intensity
- `H_0` to `H_3` — hazard class 0–3

The UI does **not** display:
- Whether the basin used fallback values
- Which Gartner/Cannon variant was used for that fire
- Confidence intervals or uncertainty bounds on P or V
- The `high_sev_ratio` used in the model
