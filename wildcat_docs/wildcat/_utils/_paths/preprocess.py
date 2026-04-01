"""
Functions that return lists of datasets that meet a preprocessing criterion
----------
Core:
    all         - All preprocessing parameters that can be datasets (includes kf_fill)
    standard    - Preprocessing parameters that can only be datasets
    required    - Datasets that are required to run the preprocessor
    raster_only - Datasets that can only be rasters
    constant    - Datasets that may be a constant value

Features:
    features    - Datasets that can be vector feature files
    points      - Datasets that support Point features
    polygons    - Datasets that support Polygon features
    field       - Datasets that, when vector features, require a data field
"""

#####
# Core
#####


def all() -> list[str]:
    "Preprocessor inputs that can be files"
    return [
        "perimeter",
        "dem",
        "dnbr",
        "severity",
        "kf",
        "kf_fill",
        "evt",
        "retainments",
        "excluded",
        "included",
        "iswater",
        "isdeveloped",
    ]


def standard() -> list[str]:
    "Preprocessor inputs that can only be file-based datasets"
    datasets = all()
    datasets.remove("kf_fill")
    return datasets


def required() -> list[str]:
    "Required preprocessor inputs"
    return ["perimeter", "dem"]


def raster_only() -> list[str]:
    "Datasets that can only be rasters"
    return ["dem", "dnbr", "evt"]


def constant() -> list[str]:
    "Datasets that may be a constant value"
    return ["dnbr", "severity", "kf"]


#####
# Features
#####


def features() -> list[str]:
    "Preprocessor inputs that support vector feature files"
    return [dataset for dataset in all() if dataset not in raster_only()]


def points() -> list[str]:
    "Preprocessor inputs that support Point vector features"
    return ["retainments"]


def polygons() -> list[str]:
    "Preprocessor inputs that support Polygon vector features"
    return [dataset for dataset in features() if dataset not in points()]


def field() -> list[str]:
    "Preprocessor inputs that must be read from a data field when vector features"
    return ["severity", "kf", "kf_fill"]
