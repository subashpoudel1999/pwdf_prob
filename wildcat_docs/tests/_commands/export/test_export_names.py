import pytest

from wildcat._commands.export import _names


class TestValidate:
    def test_basic(_, config, parameters):
        rename = {"Segment_ID": "ids", "Area_km2": "area"}
        config["rename"] = rename
        _names.validate(config, parameters)
        assert config["rename"] == rename

    def test_prefix(_, config, parameters):
        rename = {"H": "hazard", "P": "likelihood", "Vmin": "volume lower bound"}
        config["rename"] = rename
        _names.validate(config, parameters)
        assert config["rename"] == rename

    def test_dynamic(_, config, parameters):
        rename = {"H_0": "H_16mmh", "P_2": "P_20mmh", "Vmin_0_1": "Vmin_16mmh_95"}
        config["rename"] = rename
        _names.validate(config, parameters)
        assert config["rename"] == rename

    def test_parameter(_, config, parameters):
        rename = {
            "probabilities": ["50", "75"],
            "I15_mm_hr": ["16mmh", "20mmh", "24mmh"],
            "volume_CI": ["90", "95"],
            "durations": ["1/4hr", "1/2hr", "1hr"],
        }
        config["rename"] = rename
        _names.validate(config, parameters)
        assert config["rename"] == rename

    def test_invalid_dynamic(_, config, parameters, errcheck):
        rename = {"H_0": "H_16mmh", "P_4": "P_60mmh", "Vmin_0_1": "Vmin_16mmh_95"}
        config["rename"] = rename
        with pytest.raises(ValueError) as error:
            _names.validate(config, parameters)
        errcheck(
            error,
            'Each key in the "rename" dict must be a property name',
            "key[1] (value = P_4) is not",
        )
        assert config["rename"] == rename

    def test_not_supported(_, config, parameters, errcheck):
        rename = {"H_0": "H_16mmh", "invalid": "test"}
        config["rename"] = rename
        with pytest.raises(ValueError) as error:
            _names.validate(config, parameters)
        errcheck(
            error,
            'Each key in the "rename" dict must be a property name',
            "key[1] (value = invalid) is not",
        )
        assert config["rename"] == rename

    def test_capitalization(_, config, parameters):
        rename = {"segment_id": "ids", "AREA_KM2": "area", "CoNfAnGlE": "confinement"}
        config["rename"] = rename
        _names.validate(config, parameters)
        assert config["rename"] == {
            "Segment_ID": "ids",
            "Area_km2": "area",
            "ConfAngle": "confinement",
        }

    def test_invalid_parameter_length(_, config, parameters, errcheck):
        rename = {
            "probabilities": ["50", "75"],
            "I15_mm_hr": ["16mmh", "20mmh", "24mmh", "40mmh"],
            "volume_CI": ["90", "95"],
            "durations": ["1/4hr", "1/2hr", "1hr"],
        }
        config["rename"] = rename
        with pytest.raises(ValueError) as error:
            _names.validate(config, parameters)
        errcheck(
            error,
            'The list for the "I15_mm_hr" key in the "rename" dict must have 3 elements, ',
            "but it has 4 elements instead.",
        )


class Test_Clean:
    def test_missing(_, parameters):
        cleaned = {"Segment_ID": "Segment_ID"}
        _names._clean(cleaned, "H", parameters["I15_mm_hr"])
        assert cleaned == {"Segment_ID": "Segment_ID"}

    def test_vector1(_, parameters):
        cleaned = {name: name for name in ["H_2", "Segment_ID", "H_0", "H_1", "V_0"]}
        _names._clean(cleaned, "H", parameters["I15_mm_hr"])
        assert cleaned == {
            "H_2": "H_40mmh",
            "Segment_ID": "Segment_ID",
            "H_0": "H_20mmh",
            "H_1": "H_24mmh",
            "V_0": "V_0",
        }

    def test_vector100_CI(_, parameters):
        "Does not lstrip"
        cleaned = {
            name: name
            for name in [
                "H_2",
                "Vmin_0_0",
                "Vmin_0_1",
                "Vmin_1_0",
                "Vmin_2_1",
                "Area_km2",
            ]
        }
        _names._clean(cleaned, "Vmin", parameters["I15_mm_hr"], parameters["volume_CI"])
        assert cleaned == {
            "H_2": "H_2",
            "Vmin_0_0": "Vmin_20_90",
            "Vmin_0_1": "Vmin_20_95",
            "Vmin_1_0": "Vmin_24_90",
            "Vmin_2_1": "Vmin_40_95",
            "Area_km2": "Area_km2",
        }

    def test_vector100_thresholds(_, parameters):
        "Implements lstrip"
        cleaned = {
            name: name
            for name in ["H_2", "R_0_0", "R_0_1", "R_1_0", "R_2_1", "Area_km2"]
        }
        _names._clean(
            cleaned,
            "R",
            parameters["durations"],
            parameters["probabilities"],
            lstrip=True,
        )
        assert cleaned == {
            "H_2": "H_2",
            "R_0_0": "R15_50",
            "R_0_1": "R15_75",
            "R_1_0": "R30_50",
            "R_2_1": "R60_75",
            "Area_km2": "Area_km2",
        }


class TestClean:
    def test_none(_, config, parameters, logcheck):
        config["clean_names"] = False
        props = ["H_0", "Vmin_0_1", "R_1_1"]
        output = _names.clean(config, parameters, props, logcheck.log)
        assert output == {
            "H_0": "H_0",
            "Vmin_0_1": "Vmin_0_1",
            "R_1_1": "R_1_1",
        }
        logcheck.check([])

    def test(_, config, parameters, logcheck):
        props = [
            "Segment_ID",
            "H_0",
            "P_1",
            "V_2",
            "Vmin_0_1",
            "Vmax_2_1",
            "R_0_0",
            "I_1_1",
            "Area_km2",
        ]
        output = _names.clean(config, parameters, props, logcheck.log)
        assert output == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_20mmh",
            "P_1": "P_24mmh",
            "V_2": "V_40mmh",
            "Vmin_0_1": "Vmin_20_95",
            "Vmax_2_1": "Vmax_40_95",
            "R_0_0": "R15_50",
            "I_1_1": "I30_75",
            "Area_km2": "Area_km2",
        }
        logcheck.check([("DEBUG", "    Cleaning result names")])


class TestRenamePrefixes:
    def test_cleaned(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_20",
            "P_1": "P_24",
            "Vmin_0_0": "Vmin_20_90",
            "Vmax_1_1": "Vmax_24_95",
            "R_0_1": "R15_75",
            "I_1_0": "I30_50",
            "Area_km2": "Area_km2",
        }
        rename = {
            "H": "hazard",
            "Vmin": "minvol",
            "R": "acc",
            "Segment_ID": "id",
        }
        _names._rename_prefixes(names, rename)
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "hazard_20",
            "P_1": "P_24",
            "Vmin_0_0": "minvol_20_90",
            "Vmax_1_1": "Vmax_24_95",
            "R_0_1": "acc15_75",
            "I_1_0": "I30_50",
            "Area_km2": "Area_km2",
        }

    def test_not_cleaned(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "P_1": "P_1",
            "Vmin_0_0": "Vmin_0_0",
            "Vmax_1_1": "Vmax_1_1",
            "R_0_1": "R_0_1",
            "I_1_0": "I_1_0",
            "Area_km2": "Area_km2",
        }
        rename = {
            "H": "hazard",
            "Vmin": "minvol",
            "R": "acc",
            "Segment_ID": "id",
        }
        _names._rename_prefixes(names, rename)
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "hazard_0",
            "P_1": "P_1",
            "Vmin_0_0": "minvol_0_0",
            "Vmax_1_1": "Vmax_1_1",
            "R_0_1": "acc_0_1",
            "I_1_0": "I_1_0",
            "Area_km2": "Area_km2",
        }


class TestRenameParameter:
    def test_none(_):
        names = {
            "H_0": "H_0",
            "Segment_ID": "Segment_ID",
        }
        rename = {"H": "hazard"}
        _names._rename_parameter(names, rename, "volume_CI", 1, ["Vmin", "Vmax"])
        assert names == {
            "H_0": "H_0",
            "Segment_ID": "Segment_ID",
        }

    def test_I15(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "H_1": "H_24mmh",
            "V_0": "V_0",
            "Vmin_0_0": "Vmin_0_0",
            "Vmin_1_1": "Vmin_24_95",
        }
        rename = {"I15_mm_hr": ["80", "92", "160"]}
        _names._rename_parameter(
            names, rename, "I15_mm_hr", 1, ["H", "P", "V", "Vmin", "Vmax"]
        )
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_80",
            "H_1": "H_92",
            "V_0": "V_80",
            "Vmin_0_0": "Vmin_80_0",
            "Vmin_1_1": "Vmin_92_95",
        }

    def test_CI(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "H_1": "H_24mmh",
            "V_0": "V_0",
            "Vmin_0_0": "Vmin_0_0",
            "Vmax_1_1": "Vmin_24_95",
        }
        rename = {"volume_CI": ["0.90", "0.95"]}
        _names._rename_parameter(names, rename, "volume_CI", 2, ["Vmin", "Vmax"])
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "H_1": "H_24mmh",
            "V_0": "V_0",
            "Vmin_0_0": "Vmin_0_0.90",
            "Vmax_1_1": "Vmin_24_0.95",
        }

    def test_durations(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "R_0_0": "R_0_0",
            "R_1_1": "R30_75",
            "I_0_0": "I15_50",
            "I_1_1": "I_1_1",
        }
        rename = {"durations": ["0.25", "0.5", "1"]}
        _names._rename_parameter(names, rename, "durations", 1, ["R", "I"])
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "R_0_0": "R_0.25_0",
            "R_1_1": "R0.5_75",
            "I_0_0": "I0.25_50",
            "I_1_1": "I_0.5_1",
        }

    def test_probabilities(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "R_0_0": "R_0_0",
            "R_1_1": "R30_75",
            "I_0_0": "I15_50",
            "I_1_1": "I_1_1",
        }
        rename = {"probabilities": ["0.5", "0.75"]}
        _names._rename_parameter(names, rename, "probabilities", 2, ["R", "I"])
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "R_0_0": "R_0_0.5",
            "R_1_1": "R30_0.75",
            "I_0_0": "I15_0.5",
            "I_1_1": "I_1_0.75",
        }


class TestRenameParameters:
    def test_cleaned(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_20",
            "P_1": "P_24",
            "Vmin_0_0": "Vmin_20_90",
            "Vmax_1_1": "Vmax_24_95",
            "R_0_1": "R15_75",
            "I_1_0": "I30_50",
            "Area_km2": "Area_km2",
        }
        rename = {
            "I15_mm_hr": ["80", "92", "160"],
            "volume_CI": ["0.9", "0.95"],
            "durations": ["0.25", "0.5", "1"],
            "probabilities": ["0.5", "0.75"],
            "Segment_ID": "id",
        }
        _names._rename_parameters(names, rename)
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_80",
            "P_1": "P_92",
            "Vmin_0_0": "Vmin_80_0.9",
            "Vmax_1_1": "Vmax_92_0.95",
            "R_0_1": "R0.25_0.75",
            "I_1_0": "I0.5_0.5",
            "Area_km2": "Area_km2",
        }

    def test_not_cleaned(_):
        names = {
            "Segment_ID": "Segment_ID",
            "H_0": "H_0",
            "P_1": "P_1",
            "Vmin_0_0": "Vmin_0_0",
            "Vmax_1_1": "Vmax_1_1",
            "R_0_1": "R_0_1",
            "I_1_0": "I_1_0",
            "Area_km2": "Area_km2",
        }
        rename = {
            "I15_mm_hr": ["80", "92", "160"],
            "volume_CI": ["0.9", "0.95"],
            "durations": ["0.25", "0.5", "1"],
            "probabilities": ["0.5", "0.75"],
            "Segment_ID": "id",
        }
        _names._rename_parameters(names, rename)
        assert names == {
            "Segment_ID": "Segment_ID",
            "H_0": "H_80",
            "P_1": "P_92",
            "Vmin_0_0": "Vmin_80_0.9",
            "Vmax_1_1": "Vmax_92_0.95",
            "R_0_1": "R_0.25_0.75",
            "I_1_0": "I_0.5_0.5",
            "Area_km2": "Area_km2",
        }


class TestRenameProperties:
    def test(_):
        names = {
            "I_0_0": "I15_50",
            "Segment_ID": "Segment_ID",
            "H_0": "H_20mmh",
            "R_0_0": "R_0_0",
            "Area_km2": "Area_km2",
        }
        rename = {
            "Segment_ID": "id",
            "H_0": "hazard LG",
            "R_0_0": "acc LG",
            "V": "volume",
            "volume_CI": ["0.9", "0.95"],
        }
        _names._rename_properties(names, rename)
        assert names == {
            "I_0_0": "I15_50",
            "Segment_ID": "id",
            "H_0": "hazard LG",
            "R_0_0": "acc LG",
            "Area_km2": "Area_km2",
        }


class TestRename:
    def test_cleaned(_, config, logcheck):
        config["rename"] = {
            "Segment_ID": "id",
            "H": "hazard",
            "I15_mm_hr": ["80", "92", "160"],
            "durations": ["0.25", "0.5", "1"],
        }
        names = {
            "Segment_ID": "Segment_ID",
            "Area_km2": "Area_km2",
            "H_0": "H_20mmh",
            "P_1": "P_24mmh",
            "Vmin_0_0": "Vmin_20_90",
            "Vmax_1_1": "Vmax_24_95",
            "R_0_0": "R15_50",
            "I_1_1": "I30_75",
        }
        _names.rename(config, names, logcheck.log)
        assert names == {
            "Segment_ID": "id",
            "Area_km2": "Area_km2",
            "H_0": "hazard_80",
            "P_1": "P_92",
            "Vmin_0_0": "Vmin_80_90",
            "Vmax_1_1": "Vmax_92_95",
            "R_0_0": "R0.25_50",
            "I_1_1": "I0.5_75",
        }
        logcheck.check([("DEBUG", "    Applying user-provided names")])

    def test_not_cleaned(_, config, logcheck):
        config["rename"] = {
            "Segment_ID": "id",
            "H": "hazard",
            "I15_mm_hr": ["80", "92", "160"],
            "durations": ["0.25", "0.5", "1"],
        }
        names = {
            "Segment_ID": "Segment_ID",
            "Area_km2": "Area_km2",
            "H_0": "H_0",
            "P_1": "P_1",
            "Vmin_0_0": "Vmin_0_0",
            "Vmax_1_1": "Vmax_1_1",
            "R_0_0": "R_0_0",
            "I_1_1": "I_1_1",
        }
        _names.rename(config, names, logcheck.log)
        assert names == {
            "Segment_ID": "id",
            "Area_km2": "Area_km2",
            "H_0": "hazard_80",
            "P_1": "P_92",
            "Vmin_0_0": "Vmin_80_0",
            "Vmax_1_1": "Vmax_92_1",
            "R_0_0": "R_0.25_0",
            "I_1_1": "I_0.5_1",
        }
        logcheck.check([("DEBUG", "    Applying user-provided names")])


class TestParse:
    def test_clean(_, config, parameters, logcheck):
        props = [
            "Segment_ID",
            "Area_km2",
            "H_0",
            "P_1",
            "Vmin_0_0",
            "Vmax_1_1",
            "R_0_0",
            "I_1_1",
        ]
        config["rename"] = {
            "Segment_ID": "id",
            "H": "hazard",
            "I15_mm_hr": ["80", "92", "160"],
            "durations": ["0.25", "0.5", "1"],
        }
        output = _names.parse(config, parameters, props, logcheck.log)
        assert output == {
            "Segment_ID": "id",
            "Area_km2": "Area_km2",
            "H_0": "hazard_80",
            "P_1": "P_92",
            "Vmin_0_0": "Vmin_80_90",
            "Vmax_1_1": "Vmax_92_95",
            "R_0_0": "R0.25_50",
            "I_1_1": "I0.5_75",
        }
        logcheck.check(
            [
                ("INFO", "Parsing property names"),
                ("DEBUG", "    Cleaning result names"),
                ("DEBUG", "    Applying user-provided names"),
            ]
        )

    def test_no_clean(_, config, parameters, logcheck):
        props = [
            "Segment_ID",
            "Area_km2",
            "H_0",
            "P_1",
            "Vmin_0_0",
            "Vmax_1_1",
            "R_0_0",
            "I_1_1",
        ]
        config["rename"] = {
            "Segment_ID": "id",
            "H": "hazard",
            "I15_mm_hr": ["80", "92", "160"],
            "durations": ["0.25", "0.5", "1"],
        }
        config["clean_names"] = False
        output = _names.parse(config, parameters, props, logcheck.log)
        assert output == {
            "Segment_ID": "id",
            "Area_km2": "Area_km2",
            "H_0": "hazard_80",
            "P_1": "P_92",
            "Vmin_0_0": "Vmin_80_0",
            "Vmax_1_1": "Vmax_92_1",
            "R_0_0": "R_0.25_0",
            "I_1_1": "I_0.5_1",
        }
        logcheck.check(
            [
                ("INFO", "Parsing property names"),
                ("DEBUG", "    Applying user-provided names"),
            ]
        )
