from pathlib import Path

import pytest
from pyproj import CRS

from wildcat import assess, export, initialize, preprocess
from wildcat._utils import _args
from wildcat._utils._validate import _core, _main


class alter:
    def __init__(self, config, field, value):
        self.config = config
        self.field = field
        self.value = value
        self.original = config[field]

    def __enter__(self):
        self.config[self.field] = self.value

    def __exit__(self, *args, **kwargs):
        self.config[self.field] = self.original


@pytest.fixture
def iconfig():
    return {
        "project": Path("test"),
        "config": "default",
        "inputs": "inputs",
    }


@pytest.fixture
def pconfig():
    config = {
        "buffer_km": 3,
        "resolution_limits_m": [6.5, 11],
        "resolution_check": "error",
        "dnbr_scaling_check": "warn",
        "constrain_dnbr": True,
        "dnbr_limits": [-2000, 2000],
        "severity_field": None,
        "estimate_severity": True,
        "severity_thresholds": [125, 250, 500],
        "contain_severity": False,
        "kf_field": "KFFACT",
        "constrain_kf": True,
        "max_missing_kf_ratio": 0.25,
        "missing_kf_check": None,
        "kf_fill": 2.2,
        "kf_fill_field": None,
        "water": 7292,
        "developed": [7296, 7297, 7298, 7299],
        "excluded_evt": [],
    }
    for name in [
        "project",
        "config",
        "inputs",
        "preprocessed",
        "perimeter",
        "dem",
        "dnbr",
        "severity",
        "kf",
        "evt",
        "retainments",
        "excluded",
    ]:
        config[name] = name
    for name in ["included", "iswater", "isdeveloped"]:
        config[name] = None

    config["kf"] = 5
    return config


@pytest.fixture
def aconfig():
    config = {
        # Units
        "dem_per_m": 1,
        # Delineation
        "min_area_km2": 0.025,
        "min_burned_area_km2": 0.01,
        "max_length_m": 500,
        # Filtering
        "max_area_km2": 8,
        "max_exterior_ratio": 0.95,
        "min_burn_ratio": 0.25,
        "min_slope": 0.12,
        "max_developed_area_km2": 0.025,
        "max_confinement": 174,
        "confinement_neighborhood": 4,
        "flow_continuous": True,
        # Remove IDs
        "remove_ids": [2, 5],
        # Hazard Modeling
        "I15_mm_hr": [16, 20, 24, 40],
        "volume_CI": [0.95],
        "durations": [15, 30, 60],
        "probabilities": [0.5, 0.75],
        # Basins
        "locate_basins": True,
        "parallelize_basins": False,
    }
    for name in ["project", "config", "preprocessed", "assessment"]:
        config[name] = name
    for name in [
        "perimeter",
        "dem",
        "dnbr",
        "severity",
        "kf",
        "retainments",
        "excluded",
        "iswater",
        "isdeveloped",
    ]:
        name = f"{name}_p"
        config[name] = name
    config["included_p"] = None
    return config


@pytest.fixture
def econfig():
    return {
        # Folders
        "project": "project",
        "config": "config",
        "assessment": "assessment",
        "exports": "exports",
        # Output files
        "format": "shapefile",
        "export_crs": "WGS 84",
        "prefix": "fire-id-",
        "suffix": "-date",
        # Properties
        "properties": ["default", "IsSteep"],
        "exclude_properties": "Segment_ID",
        "include_properties": None,
        # Property formatting
        "order_properties": True,
        "clean_names": True,
        "rename": {"H": "hazard", "volume_CI": ["90%", "95%"]},
    }


def check_all_validated(config, validate, command, errcheck):
    "Checks that all command parameters are validated"

    parameters = _args.collect(command)
    for parameter in parameters:
        value = config[parameter]
        del config[parameter]
        with pytest.raises(KeyError) as error:
            validate(config)
        errcheck(error, parameter)
        config[parameter] = value


class TestValidate:
    def test(_):
        checks = {
            "scalar": _core.scalar,
            "vector": _core.vector,
            "vectorized": _core.vector,
            "kf_fill": _core.kf_fill,
        }
        config = {"scalar": 5, "vector": (1, 2, 3), "vectorized": 6, "kf_fill": None}
        _main._validate(config, checks)

        assert config == {
            "scalar": 5,
            "vector": [1, 2, 3],
            "vectorized": [6],
            "kf_fill": False,
        }


class TestInitialize:
    def test_valid(_, iconfig):
        _main.initialize(iconfig)
        expected = {
            "project": Path("test"),
            "config": "default",
            "inputs": "inputs",
        }
        assert iconfig == expected

    def test_invalid(_, iconfig, errcheck):
        with alter(iconfig, "project", 5):
            with pytest.raises(TypeError) as error:
                _main.initialize(iconfig)
        errcheck(error, 'Could not convert the "project" setting to a file path')

        with alter(iconfig, "config", "test"):
            with pytest.raises(ValueError) as error:
                _main.initialize(iconfig)
            errcheck(
                error,
                'The "config" setting should be one of the following strings: default, full, empty, none',
            )

        with alter(iconfig, "inputs", 5):
            with pytest.raises(TypeError) as error:
                _main.initialize(iconfig)
            errcheck(error, 'The "inputs" setting must be a string, or None')

    def test_all_validated(_, iconfig, errcheck):
        check_all_validated(iconfig, _main.initialize, initialize, errcheck)


class TestPreprocess:
    def test_valid(_, pconfig):
        _main.preprocess(pconfig)
        expected = {
            # Perimeter
            "buffer_km": 3,
            # DEM
            "resolution_limits_m": [6.5, 11],
            "resolution_check": "error",
            # dNBR
            "dnbr_scaling_check": "warn",
            "constrain_dnbr": True,
            "dnbr_limits": [-2000, 2000],
            # Severity
            "severity_field": None,
            "estimate_severity": True,
            "severity_thresholds": [125, 250, 500],
            "contain_severity": False,
            # KF facotrs
            "kf_field": "KFFACT",
            "constrain_kf": True,
            "max_missing_kf_ratio": 0.25,
            "missing_kf_check": "none",
            "kf_fill": 2.2,
            "kf_fill_field": None,
            # EVT masks
            "water": [7292],
            "developed": [7296, 7297, 7298, 7299],
            "excluded_evt": [],
        }
        for name in [
            "project",
            "config",
            "inputs",
            "preprocessed",
            "perimeter",
            "dem",
            "dnbr",
            "severity",
            "kf",
            "evt",
            "retainments",
            "excluded",
        ]:
            expected[name] = Path(name)
        for name in ["included", "iswater", "isdeveloped"]:
            expected[name] = None
        expected["kf"] = 5
        assert pconfig == expected

    def test_invalid(_, pconfig, errcheck):

        for path in [
            "project",
            "inputs",
            "preprocessed",
            "perimeter",
            "dem",
            "evt",
            "retainments",
            "excluded",
            "included",
            "iswater",
            "isdeveloped",
        ]:
            with alter(pconfig, path, 5):
                with pytest.raises(TypeError) as error:
                    _main.preprocess(pconfig)
                errcheck(
                    error, f'Could not convert the "{path}" setting to a file path'
                )

        for constant in ["dnbr", "severity", "kf"]:
            with alter(pconfig, constant, [1, 2, 3]):
                with pytest.raises(TypeError) as error:
                    _main.preprocess(pconfig)
                errcheck(
                    error, f'Could not convert the "{constant}" setting to a file path'
                )

        with alter(pconfig, "buffer_km", -5):
            with pytest.raises(ValueError) as error:
                _main.preprocess(pconfig)
            errcheck(error, 'The "buffer_km" setting must be positive')

        for check in ["resolution_check", "dnbr_scaling_check", "missing_kf_check"]:
            with alter(pconfig, check, "invalid"):
                with pytest.raises(ValueError) as error:
                    _main.preprocess(pconfig)
                errcheck(
                    error,
                    f'The "{check}" setting should be one of the following strings: warn, error, none',
                )

        for boolean in [
            "constrain_dnbr",
            "estimate_severity",
            "contain_severity",
            "constrain_kf",
        ]:
            with alter(pconfig, boolean, 5):
                with pytest.raises(TypeError) as error:
                    _main.preprocess(pconfig)
                errcheck(error, f'The "{boolean}" setting must be a bool')

        for limits in ["resolution_limits_m", "dnbr_limits"]:
            with alter(pconfig, limits, [1, 2, 3]):
                with pytest.raises(ValueError) as error:
                    _main.preprocess(pconfig)
                errcheck(error, "must have exactly 2 elements")

        for string in ["severity_field", "kf_field", "kf_fill_field"]:
            with alter(pconfig, string, 5):
                with pytest.raises(TypeError) as error:
                    _main.preprocess(pconfig)
                errcheck(error, f'The "{string}" setting must be a string, or None')

        with alter(pconfig, "severity_thresholds", [1, 2, 3, 4]):
            with pytest.raises(ValueError) as error:
                _main.preprocess(pconfig)
            errcheck(error, "must have exactly 3 elements")

        with alter(pconfig, "kf_fill", {}):
            with pytest.raises(TypeError) as error:
                _main.preprocess(pconfig)
            errcheck(error, 'Could not convert the "kf_fill" setting to a file path')

        with alter(pconfig, "max_missing_kf_ratio", 2):
            with pytest.raises(ValueError) as error:
                _main.preprocess(pconfig)
            errcheck(
                error, f'The "max_missing_kf_ratio" setting must be between 0 and 1'
            )

        for vector in ["water", "developed", "excluded_evt"]:
            with alter(pconfig, vector, "invalid"):
                with pytest.raises(TypeError) as error:
                    _main.preprocess(pconfig)
                errcheck(
                    error,
                    f'The "{vector}" setting must be one of the following types: list, tuple, int, float',
                )

    def test_all_validated(_, pconfig, errcheck):
        check_all_validated(pconfig, _main.preprocess, preprocess, errcheck)


class TestAssess:
    def test_valid(_, aconfig):
        _main.assess(aconfig)
        expected = {
            # Units
            "dem_per_m": 1,
            # Delineate
            "min_area_km2": 0.025,
            "min_burned_area_km2": 0.01,
            "max_length_m": 500,
            # Filtering
            "max_area_km2": 8,
            "max_exterior_ratio": 0.95,
            "min_burn_ratio": 0.25,
            "min_slope": 0.12,
            "max_developed_area_km2": 0.025,
            "max_confinement": 174,
            "confinement_neighborhood": 4,
            "flow_continuous": True,
            # Remove IDs
            "remove_ids": [2, 5],
            # Modling
            "I15_mm_hr": [16, 20, 24, 40],
            "volume_CI": [0.95],
            "durations": [15, 30, 60],
            "probabilities": [0.5, 0.75],
            # Basins
            "locate_basins": True,
            "parallelize_basins": False,
        }
        for name in ["project", "config", "preprocessed", "assessment"]:
            expected[name] = Path(name)
        for name in [
            "perimeter",
            "dem",
            "dnbr",
            "severity",
            "kf",
            "retainments",
            "excluded",
            "iswater",
            "isdeveloped",
        ]:
            name = f"{name}_p"
            expected[name] = Path(name)
        expected["included_p"] = None
        assert aconfig == expected

    def test_invalid(_, aconfig, errcheck):

        for path in [
            "project",
            "preprocessed",
            "assessment",
            "perimeter_p",
            "dem_p",
            "dnbr_p",
            "severity_p",
            "kf_p",
            "retainments_p",
            "excluded_p",
            "included_p",
            "iswater_p",
            "isdeveloped_p",
        ]:
            with alter(aconfig, path, 5):
                with pytest.raises(TypeError) as error:
                    _main.assess(aconfig)
                errcheck(
                    error, f'Could not convert the "{path}" setting to a file path'
                )

        for scalar in ["dem_per_m", "min_slope"]:
            with alter(aconfig, scalar, "invalid"):
                with pytest.raises(TypeError) as error:
                    _main.assess(aconfig)
                errcheck(error, f'The "{scalar}" setting must be an int or a float')

        for positive in [
            "min_area_km2",
            "min_burned_area_km2",
            "max_length_m",
            "max_area_km2",
            "max_developed_area_km2",
        ]:
            with alter(aconfig, positive, -2):
                with pytest.raises(ValueError) as error:
                    _main.assess(aconfig)
                errcheck(error, f'The "{positive}" setting must be positive')

        for ratio in ["max_exterior_ratio", "min_burn_ratio"]:
            with alter(aconfig, ratio, -2):
                with pytest.raises(ValueError) as error:
                    _main.assess(aconfig)
                errcheck(error, f'The "{ratio}" setting must be between 0 and 1')

        with alter(aconfig, "max_confinement", 361):
            with pytest.raises(ValueError) as error:
                _main.assess(aconfig)
            errcheck(error, 'The "max_confinement" setting must be between 0 and 360')

        with alter(aconfig, "confinement_neighborhood", 2.2):
            with pytest.raises(ValueError) as error:
                _main.assess(aconfig)
            errcheck(error, 'The "confinement_neighborhood" setting must be an integer')

        for boolean in ["flow_continuous", "locate_basins", "parallelize_basins"]:
            with alter(aconfig, boolean, 5):
                with pytest.raises(TypeError) as error:
                    _main.assess(aconfig)
                errcheck(error, f'The "{boolean}" setting must be a bool')

        with alter(aconfig, "remove_ids", [1, 2, 3, 4.4]):
            with pytest.raises(ValueError) as error:
                _main.assess(aconfig)
            errcheck(error, 'The elements of the "remove_ids" setting must be integers')

        with alter(aconfig, "I15_mm_hr", [1, 2, -3]):
            with pytest.raises(ValueError) as error:
                _main.assess(aconfig)
            errcheck(error, 'The elements of the "I15_mm_hr" setting must be positive')

        for ratio in ["volume_CI", "probabilities"]:
            with alter(aconfig, ratio, [0, 0.5, 5]):
                with pytest.raises(ValueError) as error:
                    _main.assess(aconfig)
                errcheck(
                    error,
                    f'The elements of the "{ratio}" setting must be between 0 and 1',
                )

        with alter(aconfig, "durations", [15, 16]):
            with pytest.raises(ValueError) as error:
                _main.assess(aconfig)
            errcheck(
                error,
                'The elements of the "durations" setting must be 15, 30, and/or 60',
            )

    def test_all_validated(_, aconfig, errcheck):
        check_all_validated(aconfig, _main.assess, assess, errcheck)


class TestExport:
    def test_valid(_, econfig):
        _main.export(econfig)
        assert econfig == {
            # Folders
            "project": Path("project"),
            "config": Path("config"),
            "assessment": Path("assessment"),
            "exports": Path("exports"),
            # Output files
            "format": "Shapefile",
            "export_crs": CRS("WGS 84"),
            "prefix": "fire-id-",
            "suffix": "-date",
            # Properties
            "properties": ["default", "IsSteep"],
            "exclude_properties": ["Segment_ID"],
            "include_properties": [],
            # Property formatting
            "order_properties": True,
            "clean_names": True,
            "rename": {"H": "hazard", "volume_CI": ["90%", "95%"]},
        }

    def test_invalid(_, econfig, errcheck):
        for path in ["project", "assessment", "exports"]:
            with alter(econfig, path, 5):
                with pytest.raises(TypeError) as error:
                    _main.export(econfig)
                errcheck(
                    error, f'Could not convert the "{path}" setting to a file path'
                )

        for filename in ["prefix", "suffix"]:
            with alter(econfig, filename, "test,invalid"):
                with pytest.raises(ValueError) as error:
                    _main.export(econfig)
                errcheck(error, f'The "{filename}" setting must be a string of ASCII')

        with alter(econfig, "format", "invalid"):
            with pytest.raises(ValueError) as error:
                _main.export(econfig)
            errcheck(
                error, 'The "format" setting must be a recognized vector file format'
            )

        with alter(econfig, "export_crs", "invalid"):
            with pytest.raises(TypeError) as error:
                _main.export(econfig)
            errcheck(error, "Could not convert export_crs to a CRS")

        for strlist in ["properties", "exclude_properties", "include_properties"]:
            with alter(econfig, strlist, 5):
                with pytest.raises(TypeError) as error:
                    _main.export(econfig)
                errcheck(
                    error, f'The "{strlist}" setting must be a list, tuple, or string'
                )

        for boolean in ["order_properties", "clean_names"]:
            with alter(econfig, boolean, 5):
                with pytest.raises(TypeError) as error:
                    _main.export(econfig)
                errcheck(error, f'The "{boolean}" setting must be a bool')

        with alter(econfig, "rename", 5):
            with pytest.raises(TypeError) as error:
                _main.export(econfig)
            errcheck(error, 'The "rename" setting must be a dict')

    def test_all_validated(_, econfig, errcheck):
        check_all_validated(econfig, _main.export, export, errcheck)
