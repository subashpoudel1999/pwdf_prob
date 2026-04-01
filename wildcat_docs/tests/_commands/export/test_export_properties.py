import pytest

from wildcat._commands.export import _properties

#####
# Standardization
#####


class TestUngroup:
    def test(_):
        props = ["Segment_ID", "H", "results", "watershed", "Area_km2"]
        output = _properties.ungroup(props)
        assert output == [
            "Segment_ID",
            "H",
            "H",
            "P",
            "V",
            "Vmin",
            "Vmax",
            "I",
            "R",
            "Segment_ID",
            "Area_km2",
            "ExtRatio",
            "BurnRatio",
            "Slope",
            "ConfAngle",
            "DevAreaKm2",
            "Area_km2",
        ]


class Test_Collect:
    def test_missing(_):
        props = ["Segment_ID", "Area_km2"]
        output = _properties._collect(props, "H", 1, 2)
        assert output == props

    def test_1_index(_):
        props = ["Segment_ID", "Area_km2", "H", "P"]
        output = _properties._collect(props, "H", 3)
        assert output == ["Segment_ID", "Area_km2", "H_0", "H_1", "H_2", "P"]

    def test_2_index(_):
        props = ["Segment_ID", "Vmin", "H"]
        output = _properties._collect(props, "Vmin", 2, 2)
        assert output == [
            "Segment_ID",
            "Vmin_0_0",
            "Vmin_0_1",
            "Vmin_1_0",
            "Vmin_1_1",
            "H",
        ]

    @pytest.mark.parametrize("counts", ((0,), (0, 0), (3, 0), (0, 3)))
    def test_empty_parameter(_, counts):
        props = ["Segment_ID", "H", "Area_km2"]
        output = _properties._collect(props, "H", *counts)
        assert output == ["Segment_ID", "Area_km2"]


class TestCollect:
    def test(_, parameters):
        props = ["Segment_ID", "H", "P", "V", "Vmin", "Vmax", "R", "I", "Area_km2"]
        output = _properties.collect(parameters, props)
        assert output == [
            "Segment_ID",
            "H_0",
            "H_1",
            "H_2",
            "P_0",
            "P_1",
            "P_2",
            "V_0",
            "V_1",
            "V_2",
            "Vmin_0_0",
            "Vmin_0_1",
            "Vmin_1_0",
            "Vmin_1_1",
            "Vmin_2_0",
            "Vmin_2_1",
            "Vmax_0_0",
            "Vmax_0_1",
            "Vmax_1_0",
            "Vmax_1_1",
            "Vmax_2_0",
            "Vmax_2_1",
            "R_0_0",
            "R_0_1",
            "R_1_0",
            "R_1_1",
            "R_2_0",
            "R_2_1",
            "I_0_0",
            "I_0_1",
            "I_1_0",
            "I_1_1",
            "I_2_0",
            "I_2_1",
            "Area_km2",
        ]

    def test_empty(_, parameters):
        parameters["I15_mm_hr"] = []
        parameters["durations"] = []
        props = ["Segment_ID", "H", "P", "V", "Vmin", "Vmax", "R", "I", "Area_km2"]
        output = _properties.collect(parameters, props)
        assert output == ["Segment_ID", "Area_km2"]


class TestUnique:
    def test(_):
        props = ["Segment_ID", "Area_km2", "ExtRatio", "Area_km2", "Segment_ID"]
        output = _properties.unique(props)
        assert output == ["Segment_ID", "Area_km2", "ExtRatio"]


#####
# Parser steps
#####


class TestAdd:
    def test_in(_):
        name = "test"
        organized = ["Segment_ID", "Area_km2"]
        properties = ["Segment_ID", "Area_km2", "H", "test"]
        _properties._add(name, organized, properties)
        assert organized == ["Segment_ID", "Area_km2", "test"]

    def test_not_in(_):
        name = "test"
        organized = ["Segment_ID", "Area_km2"]
        properties = ["Segment_ID", "Area_km2", "H"]
        _properties._add(name, organized, properties)
        assert organized == ["Segment_ID", "Area_km2"]


class TestOrder:
    def test_none(_, config, parameters, logcheck):
        config["order_properties"] = False
        props = ["H_1", "H_2", "Segment_ID", "V_1", "V_2"]
        output = _properties.order(config, parameters, props, logcheck.log)
        assert output == props
        logcheck.check([])

    def test(_, config, parameters, logcheck):
        props = [
            "H_0",
            "H_1",
            "H_2",
            "V_1",
            "V_2",
            "Vmin_0_0",
            "Vmin_0_1",
            "Vmin_1_0",
            "Vmin_1_1",
            "Vmin_2_0",
            "Vmin_2_1",
            "Vmax_0_0",
            "Vmin_0_1",
            "Vmin_1_0",
            "Vmin_1_1",
            "Vmin_2_0",
            "Vmin_2_1",
            "Vmin_0_0",
            "Vmin_0_1",
            "Vmin_1_0",
            "Vmin_1_1",
            "Vmin_2_0",
            "Vmin_2_1",
            "Vmax_0_0",
            "Vmax_0_1",
            "Vmax_1_0",
            "Vmax_1_1",
            "Vmax_2_0",
            "Vmax_2_1",
            "R_0_0",
            "R_0_1",
            "R_1_0",
            "R_1_1",
            "R_2_0",
            "R_2_1",
            "I_0_0",
            "I_0_1",
            "I_1_0",
            "I_1_1",
            "I_2_0",
            "I_2_1",
            "Segment_ID",
            "Area_km2",
            "ExtRatio",
            "Terrain_M1",
            "Soil_M1",
            "IsSteep",
            "IsPhysical",
            "Bmh_km2",
            "Relief_m",
        ]
        output = _properties.order(config, parameters, props, logcheck.log)
        assert output == [
            "Segment_ID",
            "H_0",
            "Vmin_0_0",
            "Vmax_0_0",
            "Vmin_0_1",
            "Vmax_0_1",
            "H_1",
            "V_1",
            "Vmin_1_0",
            "Vmax_1_0",
            "Vmin_1_1",
            "Vmax_1_1",
            "H_2",
            "V_2",
            "Vmin_2_0",
            "Vmax_2_0",
            "Vmin_2_1",
            "Vmax_2_1",
            "I_0_0",
            "R_0_0",
            "I_0_1",
            "R_0_1",
            "I_1_0",
            "R_1_0",
            "I_1_1",
            "R_1_1",
            "I_2_0",
            "R_2_0",
            "I_2_1",
            "R_2_1",
            "Terrain_M1",
            "Soil_M1",
            "Bmh_km2",
            "Relief_m",
            "Area_km2",
            "ExtRatio",
            "IsPhysical",
            "IsSteep",
        ]
        logcheck.check([("DEBUG", "    Reordering properties")])


class TestStandardize:
    def test_with_log(_, parameters, logcheck):
        props = ["Segment_ID", "H", "watershed", "Segment_ID"]
        output = _properties.standardize(parameters, props, logcheck.log)
        assert output == [
            "Segment_ID",
            "H_0",
            "H_1",
            "H_2",
            "Area_km2",
            "ExtRatio",
            "BurnRatio",
            "Slope",
            "ConfAngle",
            "DevAreaKm2",
        ]
        logcheck.check(
            [
                ("DEBUG", "    Unpacking property groups"),
                ("DEBUG", "    Parsing result vectors"),
                ("DEBUG", "    Removing duplicate properties"),
            ]
        )

    def test_no_log(_, parameters, logcheck):
        props = ["Segment_ID", "H", "watershed", "Segment_ID"]
        output = _properties.standardize(parameters, props)
        assert output == [
            "Segment_ID",
            "H_0",
            "H_1",
            "H_2",
            "Area_km2",
            "ExtRatio",
            "BurnRatio",
            "Slope",
            "ConfAngle",
            "DevAreaKm2",
        ]
        logcheck.check([])


class TestFinalize:
    def test(_, logcheck):
        props = [
            "Segment_ID",
            "Area_km2",
            "ExtRatio",
            "BurnRatio",
            "Slope",
            "ConfAngle",
            "DevAreaKm2",
        ]
        exclude = ["Segment_ID", "ExtRatio"]
        include = ["ExtRatio", "IsSteep"]
        _properties.finalize(props, exclude, include, logcheck.log)
        assert props == [
            "Area_km2",
            "BurnRatio",
            "Slope",
            "ConfAngle",
            "DevAreaKm2",
            "ExtRatio",
            "IsSteep",
        ]
        logcheck.check(
            [
                ("DEBUG", "    Removing excluded properties"),
                ("DEBUG", "    Adding included properties"),
            ]
        )


#####
# Main functions
#####


class TestValidate:
    def test_basic(_, config, parameters):
        props = ["Segment_ID", "Area_km2", "ConfAngle"]
        config["properties"] = props
        _properties.validate(config, parameters)
        assert config["properties"] == props

    def test_prefix(_, config, parameters):
        props = ["H", "P", "V", "Vmin", "Vmax"]
        config["properties"] = props
        _properties.validate(config, parameters)
        assert config["properties"] == props

    def test_dynamic(_, config, parameters):
        props = ["H_1", "Vmin_2_0", "R_1_1", "I_0_1"]
        config["properties"] = props
        _properties.validate(config, parameters)
        assert config["properties"] == props

    def test_invalid_dynamic(_, config, parameters, errcheck):
        props = ["H_1", "Vmin_4_4"]
        config["properties"] = props
        with pytest.raises(ValueError) as error:
            _properties.validate(config, parameters)
        errcheck(
            error,
            'Each element of the "properties" setting must be a supported property name or group.',
            "properties[1] (value = Vmin_4_4) is not",
        )

    def test_group(_, config, parameters):
        props = [
            "filters",
            "watershed",
            "filtering",
            "model inputs",
            "results",
            "modeling",
        ]
        config["properties"] = props
        _properties.validate(config, parameters)
        assert config["properties"] == props

    def test_duplicates(_, config, parameters):
        props = ["H", "results", "modeling", "H_1"]
        config["properties"] = props
        _properties.validate(config, parameters)
        assert config["properties"] == props

    def test_not_recognized(_, config, parameters, errcheck):
        props = ["H_1", "invalid"]
        config["properties"] = props
        with pytest.raises(ValueError) as error:
            _properties.validate(config, parameters)
        errcheck(
            error,
            'Each element of the "properties" setting must be a supported property name or group.',
            "properties[1] (value = invalid) is not",
        )

    def test_capitalization(_, config, parameters):
        props = ["segment_id", "AREA_KM2", "CoNfAnGlE"]
        config["properties"] = props
        _properties.validate(config, parameters)
        assert config["properties"] == ["Segment_ID", "Area_km2", "ConfAngle"]


class TestParse:
    def test_organized(_, config, parameters, logcheck):
        config["properties"] = ["IsSteep", "IsPhysical", "default"]
        output = _properties.parse(config, parameters, logcheck.log)
        assert output == [
            "Segment_ID",
            "H_0",
            "P_0",
            "V_0",
            "Vmin_0_0",
            "Vmax_0_0",
            "Vmin_0_1",
            "Vmax_0_1",
            "H_1",
            "P_1",
            "V_1",
            "Vmin_1_0",
            "Vmax_1_0",
            "Vmin_1_1",
            "Vmax_1_1",
            "H_2",
            "P_2",
            "V_2",
            "Vmin_2_0",
            "Vmax_2_0",
            "Vmin_2_1",
            "Vmax_2_1",
            "I_0_0",
            "R_0_0",
            "I_0_1",
            "R_0_1",
            "I_1_0",
            "R_1_0",
            "I_1_1",
            "R_1_1",
            "I_2_0",
            "R_2_0",
            "I_2_1",
            "R_2_1",
            "Terrain_M1",
            "Fire_M1",
            "Soil_M1",
            "Bmh_km2",
            "Relief_m",
            "Area_km2",
            "ExtRatio",
            "BurnRatio",
            "Slope",
            "ConfAngle",
            "DevAreaKm2",
            "IsPhysical",
            "IsSteep",
        ]
        logcheck.check(
            [
                ("INFO", "Parsing exported properties"),
                ("DEBUG", "    Unpacking property groups"),
                ("DEBUG", "    Parsing result vectors"),
                ("DEBUG", "    Removing duplicate properties"),
                ("DEBUG", "    Removing excluded properties"),
                ("DEBUG", "    Adding included properties"),
                ("DEBUG", "    Reordering properties"),
            ]
        )

    def test_unorganized(_, config, parameters, logcheck):
        config["properties"] = ["IsSteep", "IsPhysical", "default"]
        config["order_properties"] = False
        output = _properties.parse(config, parameters, logcheck.log)
        print(output)
        assert output == [
            "IsSteep",
            "IsPhysical",
            "H_0",
            "H_1",
            "H_2",
            "P_0",
            "P_1",
            "P_2",
            "V_0",
            "V_1",
            "V_2",
            "Vmin_0_0",
            "Vmin_0_1",
            "Vmin_1_0",
            "Vmin_1_1",
            "Vmin_2_0",
            "Vmin_2_1",
            "Vmax_0_0",
            "Vmax_0_1",
            "Vmax_1_0",
            "Vmax_1_1",
            "Vmax_2_0",
            "Vmax_2_1",
            "I_0_0",
            "I_0_1",
            "I_1_0",
            "I_1_1",
            "I_2_0",
            "I_2_1",
            "R_0_0",
            "R_0_1",
            "R_1_0",
            "R_1_1",
            "R_2_0",
            "R_2_1",
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
        logcheck.check(
            [
                ("INFO", "Parsing exported properties"),
                ("DEBUG", "    Unpacking property groups"),
                ("DEBUG", "    Parsing result vectors"),
                ("DEBUG", "    Removing duplicate properties"),
                ("DEBUG", "    Removing excluded properties"),
                ("DEBUG", "    Adding included properties"),
            ]
        )
