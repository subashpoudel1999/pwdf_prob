"""
Default settings for the preprocessor
"""

# Required Datasets
perimeter = "perimeter"
dem = "dem"

# Recommended Datasets
dnbr = "dnbr"
severity = "severity"
kf = "kf"
evt = "evt"

# Optional Datasets
retainments = "retainments"
excluded = "excluded"
included = "included"
iswater = "iswater"
isdeveloped = "isdeveloped"

# Perimeter
buffer_km = 3

# DEM
resolution_limits_m = [6.5, 11]
resolution_check = "error"

# dNBR
dnbr_scaling_check = "error"
constrain_dnbr = True
dnbr_limits = [-2000, 2000]

# Burn Severity
severity_field = None
contain_severity = True
estimate_severity = True
severity_thresholds = [125, 250, 500]

# KF-factors
kf_field = None
constrain_kf = True
max_missing_kf_ratio = 0.05
missing_kf_check = "warn"
kf_fill = False
kf_fill_field = None

# EVT masks
water = [7292]
developed = [7296, 7297, 7298, 7299, 7300]
excluded_evt = []
