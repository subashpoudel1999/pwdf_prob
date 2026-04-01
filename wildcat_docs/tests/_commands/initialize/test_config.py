from pathlib import Path

import pytest

from wildcat._commands.initialize import _config
from wildcat._utils import _paths


@pytest.fixture
def path(project):
    return project / "configuration.py"


@pytest.fixture
def defaults():
    paths = _paths.folders() + _paths.preprocess.standard() + _paths.assess.all()
    defaults = {name: Path(name) for name in paths}
    defaults["inputs"] = Path("test")

    return defaults | {
        # Perimeter
        "buffer_km": 3,
        # DEM
        "resolution_limits_m": [6.5, 11],
        "resolution_check": "error",
        # dNBR
        "dnbr_scaling_check": "error",
        "constrain_dnbr": True,
        "dnbr_limits": [-2000, 2000],
        # Burn Severity
        "severity_field": None,
        "contain_severity": True,
        "estimate_severity": True,
        "severity_thresholds": [125, 250, 500],
        # KF-factors
        "kf_field": None,
        "constrain_kf": True,
        "max_missing_kf_ratio": 0.05,
        "missing_kf_check": "warn",
        "kf_fill": False,
        "kf_fill_field": None,
        # EVT masks
        "water": [7292],
        "developed": [7296, 7297, 7298, 7299, 7300],
        "excluded_evt": [],
        # Unit conversions
        "dem_per_m": 1,
        # Network delineation
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
        # Remove specific segments
        "remove_ids": [],
        # Hazard modeling
        "I15_mm_hr": [16, 20, 24, 40],
        "volume_CI": [0.95],
        "durations": [15, 30, 60],
        "probabilities": [0.5, 0.75],
        # Basins
        "locate_basins": True,
        "parallelize_basins": False,
        # Output files
        "format": "Shapefile",
        "export_crs": "WGS 84",
        "prefix": "",
        "suffix": "",
        # Properties
        "properties": "default",
        "exclude_properties": [],
        "include_properties": [],
        # Property formatting
        "order_properties": True,
        "clean_names": True,
        "rename": {},
    }


class TestHowToFull:
    def test(_, path, outtext):
        with open(path, "w") as file:
            _config._how_to_full(file)
        assert outtext(path) == (
            "# Note that this file only lists the most common configuration values.\n"
            "# For the complete list of configuration values, run:\n"
            "#\n"
            "#     wildcat initialize --config full\n"
        )


class TestHeading:
    def test(_, path, outtext):
        with open(path, "w") as file:
            _config._heading(
                file,
                "Test Heading",
                ["Here is some text", "that describes", "what the section is for."],
            )
        assert outtext(path) == (
            "\n"
            "#####\n"
            "# Test Heading\n"
            "# ------------\n"
            "# Here is some text\n"
            "# that describes\n"
            "# what the section is for.\n"
            "#####\n"
            "\n"
        )


class TestFolders:
    def test(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._folders(file, defaults)
        assert outtext(path) == (
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
            'inputs = r"test"\n'
            'preprocessed = r"preprocessed"\n'
            'assessment = r"assessment"\n'
            'exports = r"exports"\n'
            "\n"
        )


class TestPreprocess:
    def test_default(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._preprocess(file, defaults, False)
        assert outtext(path) == (
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
        )

    def test_full(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._preprocess(file, defaults, True)
        assert outtext(path) == (
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
        )


class TestAssess:
    def test_default(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._assess(file, defaults, False)
        assert outtext(path) == (
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
        )

    def test_full(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._assess(file, defaults, True)
        assert outtext(path) == (
            "\n"
            "#####\n"
            "# Assessment\n"
            "# ----------\n"
            "# Values used to implement the hazard assessment.\n"
            "#####\n"
            "\n"
            "# Required rasters\n"
            'perimeter_p = r"perimeter_p"\n'
            'dem_p = r"dem_p"\n'
            'dnbr_p = r"dnbr_p"\n'
            'severity_p = r"severity_p"\n'
            'kf_p = r"kf_p"\n'
            "\n"
            "# Optional raster masks\n"
            'retainments_p = r"retainments_p"\n'
            'excluded_p = r"excluded_p"\n'
            'included_p = r"included_p"\n'
            'iswater_p = r"iswater_p"\n'
            'isdeveloped_p = r"isdeveloped_p"\n'
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
        )


class TestExport:
    def test_default(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._export(file, defaults, False)
        assert outtext(path) == (
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

    def test_full(_, path, defaults, outtext):
        with open(path, "w") as file:
            _config._export(file, defaults, True)
        assert outtext(path) == (
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


class TestWrite:
    def test_none(_, project, path, logcheck):
        assert not path.exists()
        _config.write(project, "test", "none", logcheck.log)
        assert not path.exists()
        logcheck.check([])

    def test_empty(_, project, path, outtext, empty_config, logcheck):
        assert not path.exists()
        _config.write(project, "test", "empty", logcheck.log)
        assert path.exists()
        assert outtext(path) == empty_config
        logcheck.check([("DEBUG", "    Writing configuration file")])

    def test_default(_, project, path, outtext, default_config, logcheck):
        assert not path.exists()
        _config.write(project, "test", "default", logcheck.log)
        assert path.exists()
        config = default_config.replace('r"inputs"', 'r"test"')
        assert outtext(path) == config
        logcheck.check([("DEBUG", "    Writing configuration file")])

    def test_full(_, project, path, outtext, full_config, logcheck):
        assert not path.exists()
        _config.write(project, "test", "full", logcheck.log)
        assert path.exists()
        config = full_config.replace('r"inputs"', 'r"test"')
        assert outtext(path) == config
        logcheck.check([("DEBUG", "    Writing configuration file")])
