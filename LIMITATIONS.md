# LIMITATIONS.md

**Purpose:** Honest disclosure of what this dashboard approximates, what it cannot do, and why the real Wildcat/pfdf pipeline could not be run for Palisades and Dolan fires.
**Audience:** Research paper authors, reviewers, and anyone interpreting the Dolan or Palisades results.
**Last updated:** March 2026

---

## 1. The Core Problem: We Could Not Run the Real Wildcat Model

The authoritative USGS debris-flow hazard tool is called **Wildcat**, implemented as a private Python package named `pfdf`. It is **not publicly available** — there is no pip install, no open-source repository, and no public API.

The Franklin Fire results in this dashboard are genuine Wildcat output, computed externally by someone with `pfdf` access and stored as a static file. The Palisades and Dolan results are **our own reimplementation** of the same published model equations using open-source tools (WhiteboxTools + rasterio + geopandas). These two pipelines are not methodologically equivalent.

---

## 2. What Wildcat Does That We Cannot Replicate

### 2.1 Basin Delineation

| | Wildcat (`pfdf`) | Our implementation |
|---|---|---|
| Tool | Internal `pfdf` watershed routines | WhiteboxTools `subbasins` |
| Algorithm | Undocumented internal flow routing | D8 flow direction → flow accumulation → stream extraction → subbasin delineation |
| Result | Wildcat-specific basin geometries | Different basin boundaries, shapes, and counts |

**Impact:** Even if every model formula were identical, the basin geometries would be different. Basin-level P, V, and H values from our pipeline cannot be spatially compared to Wildcat output for the same fire.

### 2.2 Slope Computation

| | Wildcat | Our implementation |
|---|---|---|
| Definition | Gradient of the **longest flow path** — a single representative slope value per basin channel | Arithmetic mean of **all DEM pixel slopes** within the basin polygon |

The Staley (2017) M1 formula specifies the longest-flow-path gradient. Using mean pixel slope systematically overestimates the terrain term T for basins with high intra-basin slope variability (e.g., steep headwalls above flat valley floors).

### 2.3 Soil Erodibility (Kf) — The Largest Single Error Source

| | Wildcat | Our implementation |
|---|---|---|
| Method | Queries STATSGO/SSURGO soil survey API per basin | Hardcoded `S = 0.15` for every basin |
| Range | Spatially variable, 0.05–0.55 depending on soil type | Fixed at 0.15 for all basins |

**This is the dominant driver of model saturation in the Dolan results.** At I15 = 40 mm/hr, the soil contribution alone is `(0.07 + 0.693 × 10) × 0.15 ≈ 1.1`, which when added to high fire severity and steep terrain pushes the logit well above +3, forcing P → 96–99% for nearly every basin. The calibration notebook confirmed ~98% of Dolan basins output H3 regardless of terrain differences between basins.

Without STATSGO/SSURGO integration, inter-basin probability spread is suppressed and model discrimination is near zero.

### 2.4 Burned Moderate-High Area (Bmh)

| | Wildcat | Our implementation |
|---|---|---|
| Method | Direct pixel count of burned moderate-high severity pixels within basin | `high_sev_ratio × total_area_km2` (a derived product, not a direct count) |

Using a fraction multiplied by area is a reasonable proxy but differs from a direct pixel-level area tally, especially for irregularly shaped basins where the ratio is computed from a potentially misaligned dNBR raster.

### 2.5 Relief

| | Wildcat | Our implementation |
|---|---|---|
| DEM used | Raw (unfilled) DEM | **Filled** DEM (after WhiteboxTools `fill_depressions`) |

Depression filling raises pit values to the surrounding pour-point elevation. In low-gradient coastal basins, this can meaningfully reduce the computed relief, underestimating the Gartner volume term.

---

## 3. The GEE DEM — Cache Ambiguity Bug

### What the GEE Dolan screen claims to do
Download a fresh 10m DEM from USGS 3DEP via Google Earth Engine, replacing the local 1.1 GB file.

### What actually happens if a cached result exists

Both the **local DEM** Dolan service and the **GEE DEM** Dolan service write to the **same** cache directory: `backend/data/dolan_cache/`. The cache metadata (`metadata.json`) records only the `burn_metric` used (dNBR / rdNBR / dNBR6) — **it does not record whether the DEM was sourced locally or from GEE.**

Consequence: if the local DEM analysis was previously run with `burn_metric=dnbr`, and you then trigger the GEE analysis with `burn_metric=dnbr` without explicitly forcing a re-run (i.e., without `?force=true` or clearing the cache via `DELETE /dolan/cache`), the GEE service will:

1. Find the existing `basins.geojson`
2. Return immediately with status `"Analysis complete! (Cached results loaded)"`
3. Never connect to GEE, never download a DEM

The output is **indistinguishable** from a genuine GEE run. There is no `dem_source` field in the output GeoJSON properties. There is no UI indicator showing whether the displayed basins came from a local or GEE DEM.

### How to guarantee a fresh GEE run
Clear the cache before triggering analysis:
```
DELETE /api/v1/dolan/cache
```
Then trigger:
```
POST /api/v1/gee/dolan/analyze
```
Only then will the GEE download step execute.

---

## 4. Model Formula Deviations

### 4.1 Staley (2017) M1 — Dolan

The Dolan implementation correctly uses the published M1 parameterized form:

```
logit = -3.63 + (0.41 + 0.369×R15)×T + (0.67 + 0.603×R15)×F + (0.07 + 0.693×R15)×S
```

The only deviation is `S = 0.15` (constant) instead of spatially variable Kf. See § 2.3.

### 4.2 Staley (2017) M1 — Palisades

The Palisades implementation uses a **structurally different, non-published formula:**

```python
terrain   = 0.41 * sin(2 * slope_rad)
fire_term = 0.67 * high_sev
rainfall  = 0.07 * sqrt(I15 * burn_ratio)   # custom proxy — not M1
X = -3.63 + terrain + fire_term + rainfall
```

This is **not** the M1 formula. Differences:
- The R15 rainfall expansion `(Bi + ci × R15)` is absent — coefficients are fixed at their baseline values
- The soil term `S` (Kf) is entirely absent
- `burn_ratio` (any burned fraction) is used inside a `sqrt(I15 × burn_ratio)` proxy that has no basis in the published M1
- Results are not comparable to the Dolan implementation

### 4.3 Gartner (2014) — Different Equations Per Fire

The two live fires use different Gartner formulas and are **not comparable:**

**Dolan:**
```
log10(V) = -0.699 + 0.989×log10(I15) + 0.369×log10(Bmh_km2) + 1.223×log10(Relief_m)
```

**Palisades:**
```
log10(V) = -1.87 + 0.56×log10(I15) + 0.97×log10(Area_km2) + 0.61×high_sev_ratio
```

The Palisades formula mixes log-transformed terms (I15, Area) with a raw proportion (`high_sev_ratio` entered as 0–1), which is dimensionally inconsistent with OLS regression form.

### 4.4 Cannon (2010) — Different Classification Schemes Per Fire

**Dolan** uses probability-only thresholds (P ≥ 0.60 → H3, etc.).
**Palisades** uses joint P + V thresholds (both must exceed limits for H3).

A basin with P = 0.70 and V = 50 m³ is H3 in Dolan but H2 in Palisades.
H values are **not comparable across fires.**

---

## 5. Silent Failures — What the Output Hides

The output GeoJSON contains no data-quality flags. A basin that used fallback values (because raster extraction failed) looks identical to a basin with real data. The following information is used in the model but **not stored in output properties:**

| Information | Used in model | Stored in output |
|---|---|---|
| `high_sev_ratio` (F in M1) | Yes | No |
| `relief_m` (Dolan Gartner) | Yes | No |
| `Bmh_km2` (Dolan Gartner) | Yes | No |
| Whether fallback values were used | — | No |
| Whether DEM was local or GEE-derived | — | No |
| Which Gartner / Cannon variant was applied | — | No |

### Fallback values (substituted silently on raster extraction failure)

| Variable | Dolan fallback | Palisades fallback |
|---|---|---|
| `slope_rad` | 0.35 (≈ 20°) | 0.26 (≈ 15°) |
| `burn_ratio` | 0.85 | 0.85 |
| `high_sev_ratio` | 0.45 | 0.40 |
| `relief_m` | 100.0 | *(not used)* |

These are biased toward high severity and moderate slope — they will produce elevated P and V values for any basin where raster extraction fails.

---

## 6. What Has Not Been Validated

- **No validation against observed debris flows.** None of the three fires have been validated against a catalog of actual debris-flow occurrence or non-occurrence from the relevant post-fire seasons.
- **No validation against Wildcat for Palisades.** The Dolan calibration notebook compared our output to `pfdf` reference output for Dolan; no equivalent comparison exists for Palisades.
- **Burn severity thresholds not field-validated.** The dNBR > 500 "high severity" threshold follows USFS Key et al. (2006) convention but has not been validated against ground-truth Dolan or Palisades severity mapping.
- **Rainfall intensities are not location-specific.** I15 = [16, 20, 24, 40] mm/hr are used for both Big Sur (Dolan) and Los Angeles (Palisades) without NOAA Atlas 14 lookup per location.

---

## 7. Cross-Fire Comparability Summary

| Comparison | Valid? | Reason |
|---|---|---|
| Franklin H vs. Dolan H | No | Different tools (pfdf vs. custom); different Cannon schemes |
| Franklin H vs. Palisades H | No | Different tools |
| Dolan H vs. Palisades H | No | Different Cannon classification schemes (P-only vs. P+V joint) |
| Dolan P vs. Palisades P | No | Different Staley implementations (correct M1 vs. custom simplified) |
| Dolan V vs. Palisades V | No | Different Gartner formulas (Bmh+Relief vs. Area+fraction) |
| Dolan GEE vs. Dolan local | Yes | Identical model code; only DEM source differs |
| Dolan GEE vs. Dolan local (if cache not cleared) | No | GEE analysis silently serves local-DEM cached results |

---

## 8. What Would Be Required to Run the Real Wildcat Pipeline

1. **Access to the `pfdf` package** — contact USGS Landslide Hazards Program. Not publicly available.
2. **STATSGO/SSURGO soil API access** — required for spatially variable Kf per basin.
3. **Matching DEM preprocessing** — Wildcat's internal DEM handling (projection, snapping, fill method) would need to be reproduced exactly for basin geometries to match.
4. **Longest-flow-path slope computation** — requires channel delineation and path-length weighted slope, not mean pixel slope.

Until `pfdf` becomes available, any comparison between Wildcat (Franklin) and our reimplementation (Dolan / Palisades) is comparing fundamentally different pipelines, not just different fires.
