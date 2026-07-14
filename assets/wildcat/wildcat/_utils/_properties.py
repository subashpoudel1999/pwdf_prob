"""
Functions that return the names/prefixes of properties in supported groups
----------
When exporting assessment results, users can specify the properties to be
exported. Although users can specify explicit properties, it is often more
useful to export groups of related properties. As such, wildcat supports several
property groups, and the functions in this module define the properties in each
group.
----------
Filtering:
    watershed       - Properties that characterize a watershed
    filters         - Boolean properties used to implement filter checks
    filtering       - Properties in the "filters" or "watershed" groups

Modeling:
    model_inputs    - Properties used as input to hazard assessment models
    results         - Prefixes of properties output by a hazard assessment model
    modeling        - Properties/prefixes in the "model_inputs" or "results" groups

Misc:
    default         - Properties/prefixes in the default export group
    all             - All available property names/prefixes
    groups          - Returns a list of supported property groups
"""


def watershed() -> list[str]:
    "Returns the names of properties that characterize segment watersheds"

    return [
        "Segment_ID",
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
    ]


def filters() -> list[str]:
    "Returns the names of properties that are filter checks"

    return [
        "IsIncluded",
        "IsFlood",
        "IsAtRisk",
        "IsInPerim",
        "IsXPerim",
        "IsExterior",
        "IsPhysical",
        "IsBurned",
        "IsSteep",
        "IsConfined",
        "IsUndev",
        "IsFlowSave",
    ]


def filtering() -> list[str]:
    "Returns the names of properties used for filtering"
    return watershed() + filters()


def model_inputs() -> list[str]:
    "Returns the names of properties used as model inputs"

    return [
        "Terrain_M1",
        "Fire_M1",
        "Soil_M1",
        "Bmh_km2",
        "Relief_m",
    ]


def results() -> list[str]:
    "Returns the prefixes of properties that are hazard assessment results"

    return [
        "H",
        "P",
        "V",
        "Vmin",
        "Vmax",
        "I",
        "R",
    ]


def modeling() -> list[str]:
    "Returns names of model inputs and result prefixes"
    return results() + model_inputs()


def default() -> list[str]:
    "Returns the names of properties exported by default in the order of export"
    return modeling() + watershed()


def all() -> list[str]:
    "Returns the names/prefixes of all properties"
    return default() + filters()


def groups() -> list[str]:
    "Returns names that represent groups of properties"

    return [
        "watershed",
        "filters",
        "filtering",
        "model inputs",
        "results",
        "modeling",
        "default",
        "all",
    ]
