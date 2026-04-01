import pytest

from wildcat import version


@pytest.fixture
def empty_config():
    return f"# Configuration file for wildcat v{version()}\n\n"


@pytest.fixture
def default_config():
    return (
        f"# Configuration file for wildcat v{version()}\n"
        "\n"
        "# Note that this file only lists the most common configuration values.\n"
        "# For the complete list of configuration values, run:\n"
        "#\n"
        "#     wildcat initialize --config full\n"
        "\n"
        "#####\n"
        "# Folders\n"
        "# -------\n"
        "# These values specify the paths to the default folders that wildcat should use\n"
        "# when searching for files and saving results. Paths should either be absolute,\n"
        "# or relative to the folder containing this configuration file.\n"
        "#####\n"
        "\n"
        "# IO Folders\n"
        'inputs = r"inputs"\n'
        'preprocessed = r"preprocessed"\n'
        'assessment = r"assessment"\n'
        'exports = r"exports"\n'
        "\n"
        "\n"
        "#####\n"
        "# Preprocessing\n"
        "# -------------\n"
        "# These values determine the implementation of the preprocessor.\n"
        "#####\n"
        "\n"
        "# Datasets\n"
        'perimeter = r"perimeter"\n'
        'dem = r"dem"\n'
        'dnbr = r"dnbr"\n'
        'severity = r"severity"\n'
        'kf = r"kf"\n'
        'evt = r"evt"\n'
        "\n"
        "# Optional Datasets\n"
        'retainments = r"retainments"\n'
        'excluded = r"excluded"\n'
        "\n"
        "# Perimeter\n"
        "buffer_km = 3\n"
        "\n"
        "# dNBR\n"
        "dnbr_limits = [-2000, 2000]\n"
        "\n"
        "# Burn severity\n"
        "severity_thresholds = [125, 250, 500]\n"
        "\n"
        "# KF-factors\n"
        "kf_field = None\n"
        "kf_fill = False\n"
        "kf_fill_field = None\n"
        "\n"
        "# EVT Masks\n"
        "water = [7292]\n"
        "developed = [7296, 7297, 7298, 7299, 7300]\n"
        "\n"
        "\n"
        "#####\n"
        "# Assessment\n"
        "# ----------\n"
        "# Values used to implement the hazard assessment.\n"
        "#####\n"
        "\n"
        "# Network Delineation\n"
        "min_area_km2 = 0.025\n"
        "min_burned_area_km2 = 0.01\n"
        "max_length_m = 500\n"
        "\n"
        "# Filtering\n"
        "max_area_km2 = 8\n"
        "max_exterior_ratio = 0.95\n"
        "min_burn_ratio = 0.25\n"
        "min_slope = 0.12\n"
        "max_developed_area_km2 = 0.025\n"
        "max_confinement = 174\n"
        "\n"
        "# Remove specific segments\n"
        "remove_ids = []\n"
        "\n"
        "# Modeling parameters\n"
        "I15_mm_hr = [16, 20, 24, 40]\n"
        "volume_CI = [0.95]\n"
        "durations = [15, 30, 60]\n"
        "probabilities = [0.5, 0.75]\n"
        "\n"
        "\n"
        "#####\n"
        "# Export\n"
        "# ------\n"
        "# Settings for exporting saved assessment results\n"
        "#####\n"
        "\n"
        "# Output files\n"
        'format = "Shapefile"\n'
        'export_crs = "WGS 84"\n'
        'prefix = ""\n'
        'suffix = ""\n'
        "\n"
        "# Properties\n"
        'properties = "default"\n'
        r"rename = {}"
        "\n"
        "\n"
    )


@pytest.fixture
def full_config():
    return (
        f"# Configuration file for wildcat v{version()}\n"
        "\n"
        "\n"
        "#####\n"
        "# Folders\n"
        "# -------\n"
        "# These values specify the paths to the default folders that wildcat should use\n"
        "# when searching for files and saving results. Paths should either be absolute,\n"
        "# or relative to the folder containing this configuration file.\n"
        "#####\n"
        "\n"
        "# IO Folders\n"
        'inputs = r"inputs"\n'
        'preprocessed = r"preprocessed"\n'
        'assessment = r"assessment"\n'
        'exports = r"exports"\n'
        "\n"
        "\n"
        "#####\n"
        "# Preprocessing\n"
        "# -------------\n"
        "# These values determine the implementation of the preprocessor.\n"
        "#####\n"
        "\n"
        "# Datasets\n"
        'perimeter = r"perimeter"\n'
        'dem = r"dem"\n'
        'dnbr = r"dnbr"\n'
        'severity = r"severity"\n'
        'kf = r"kf"\n'
        'evt = r"evt"\n'
        "\n"
        "# Optional Datasets\n"
        'retainments = r"retainments"\n'
        'excluded = r"excluded"\n'
        'included = r"included"\n'
        'iswater = r"iswater"\n'
        'isdeveloped = r"isdeveloped"\n'
        "\n"
        "# Perimeter\n"
        "buffer_km = 3\n"
        "\n"
        "# DEM\n"
        "resolution_limits_m = [6.5, 11]\n"
        'resolution_check = "error"\n'
        "\n"
        "# dNBR\n"
        'dnbr_scaling_check = "error"\n'
        "constrain_dnbr = True\n"
        "dnbr_limits = [-2000, 2000]\n"
        "\n"
        "# Burn severity\n"
        "severity_field = None\n"
        "contain_severity = True\n"
        "estimate_severity = True\n"
        "severity_thresholds = [125, 250, 500]\n"
        "\n"
        "# KF-factors\n"
        "kf_field = None\n"
        "kf_fill = False\n"
        "kf_fill_field = None\n"
        "constrain_kf = True\n"
        "max_missing_kf_ratio = 0.05\n"
        'missing_kf_check = "warn"\n'
        "\n"
        "# EVT Masks\n"
        "water = [7292]\n"
        "developed = [7296, 7297, 7298, 7299, 7300]\n"
        "excluded_evt = []\n"
        "\n"
        "\n"
        "#####\n"
        "# Assessment\n"
        "# ----------\n"
        "# Values used to implement the hazard assessment.\n"
        "#####\n"
        "\n"
        "# Required rasters\n"
        'perimeter_p = r"perimeter"\n'
        'dem_p = r"dem"\n'
        'dnbr_p = r"dnbr"\n'
        'severity_p = r"severity"\n'
        'kf_p = r"kf"\n'
        "\n"
        "# Optional raster masks\n"
        'retainments_p = r"retainments"\n'
        'excluded_p = r"excluded"\n'
        'included_p = r"included"\n'
        'iswater_p = r"iswater"\n'
        'isdeveloped_p = r"isdeveloped"\n'
        "\n"
        "# Unit conversions\n"
        "dem_per_m = 1\n"
        "\n"
        "# Network Delineation\n"
        "min_area_km2 = 0.025\n"
        "min_burned_area_km2 = 0.01\n"
        "max_length_m = 500\n"
        "\n"
        "# Filtering\n"
        "max_area_km2 = 8\n"
        "max_exterior_ratio = 0.95\n"
        "min_burn_ratio = 0.25\n"
        "min_slope = 0.12\n"
        "max_developed_area_km2 = 0.025\n"
        "max_confinement = 174\n"
        "confinement_neighborhood = 4\n"
        "flow_continuous = True\n"
        "\n"
        "# Remove specific segments\n"
        "remove_ids = []\n"
        "\n"
        "# Modeling parameters\n"
        "I15_mm_hr = [16, 20, 24, 40]\n"
        "volume_CI = [0.95]\n"
        "durations = [15, 30, 60]\n"
        "probabilities = [0.5, 0.75]\n"
        "\n"
        "# Basins\n"
        "locate_basins = True\n"
        "parallelize_basins = False\n"
        "\n"
        "\n"
        "#####\n"
        "# Export\n"
        "# ------\n"
        "# Settings for exporting saved assessment results\n"
        "#####\n"
        "\n"
        "# Output files\n"
        'format = "Shapefile"\n'
        'export_crs = "WGS 84"\n'
        'prefix = ""\n'
        'suffix = ""\n'
        "\n"
        "# Properties\n"
        'properties = "default"\n'
        "exclude_properties = []\n"
        "include_properties = []\n"
        "\n"
        "# Property formatting\n"
        "order_properties = True\n"
        "clean_names = True\n"
        r"rename = {}"
        "\n"
        "\n"
    )
