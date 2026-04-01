from wildcat._utils import _properties


def test_watershed():
    assert _properties.watershed() == [
        "Segment_ID",
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
    ]


def test_filters():
    assert _properties.filters() == [
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


def test_filtering():
    assert _properties.filtering() == [
        "Segment_ID",
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
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


def test_model_inputs():
    assert _properties.model_inputs() == [
        "Terrain_M1",
        "Fire_M1",
        "Soil_M1",
        "Bmh_km2",
        "Relief_m",
    ]


def test_results():
    assert _properties.results() == [
        "H",
        "P",
        "V",
        "Vmin",
        "Vmax",
        "I",
        "R",
    ]


def test_modeling():
    assert _properties.modeling() == [
        "H",
        "P",
        "V",
        "Vmin",
        "Vmax",
        "I",
        "R",
        "Terrain_M1",
        "Fire_M1",
        "Soil_M1",
        "Bmh_km2",
        "Relief_m",
    ]


def test_default():
    assert _properties.default() == [
        "H",
        "P",
        "V",
        "Vmin",
        "Vmax",
        "I",
        "R",
        "Terrain_M1",
        "Fire_M1",
        "Soil_M1",
        "Bmh_km2",
        "Relief_m",
        "Segment_ID",
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
    ]


def test_all():
    assert _properties.all() == [
        "H",
        "P",
        "V",
        "Vmin",
        "Vmax",
        "I",
        "R",
        "Terrain_M1",
        "Fire_M1",
        "Soil_M1",
        "Bmh_km2",
        "Relief_m",
        "Segment_ID",
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
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


def test_groups():
    assert _properties.groups() == [
        "watershed",
        "filters",
        "filtering",
        "model inputs",
        "results",
        "modeling",
        "default",
        "all",
    ]
