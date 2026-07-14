"""
Default assessment settings
"""

# Required rasters
perimeter_p = "perimeter"
dem_p = "dem"
dnbr_p = "dnbr"
severity_p = "severity"
kf_p = "kf"

# Optional masks
retainments_p = "retainments"
excluded_p = "excluded"
included_p = "included"
iswater_p = "iswater"
isdeveloped_p = "isdeveloped"

# Unit conversions
dem_per_m = 1

# Network delineation
min_area_km2 = 0.025
min_burned_area_km2 = 0.01
max_length_m = 500

# Filtering
max_area_km2 = 8
max_exterior_ratio = 0.95
min_burn_ratio = 0.25
min_slope = 0.12
max_developed_area_km2 = 0.025
max_confinement = 174
confinement_neighborhood = 4
flow_continuous = True

# Remove specific segments
remove_ids = []

# Hazard modeling
I15_mm_hr = [16, 20, 24, 40]
volume_CI = [0.95]
durations = [15, 30, 60]
probabilities = [0.5, 0.75]

# Basins
locate_basins = True
parallelize_basins = False
