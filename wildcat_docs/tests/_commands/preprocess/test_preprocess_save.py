from pathlib import Path

import numpy as np
import pytest
from pfdf.raster import Raster

import wildcat._utils._paths.preprocess as _paths
from wildcat import version
from wildcat._commands.preprocess import _save


@pytest.fixture
def raster():
    raster = np.arange(100).reshape(20, 5)
    return Raster.from_array(raster, crs=26911, transform=(10, 10, 0, 0))


@pytest.fixture
def paths(inputs):
    return {
        "perimeter": inputs / "perimeter.tif",
        "dem": inputs / "dem.tif",
    }


@pytest.fixture
def config():
    datasets = {name: None for name in _paths.standard()}
    datasets["perimeter"] = Path("perimeter")
    datasets["dem"] = Path("dem")
    datasets["kf"] = 5

    config = {
        # Perimeter
        "buffer_km": 3,
        # DEM
        "resolution_limits_m": [6.5, 11],
        "resolution_check": "error",
        # dNBR
        "dnbr_scaling_check": "error",
        "constrain_dnbr": True,
        "dnbr_limits": [-2000, 2000],
        # Severity
        "severity_field": None,
        "estimate_severity": True,
        "severity_thresholds": [125, 250, 500],
        "contain_severity": True,
        # KF
        "kf_field": None,
        "constrain_kf": True,
        "max_missing_kf_ratio": 0.05,
        "missing_kf_check": "warn",
        "kf_fill": 2.2,
        "kf_fill_field": None,
        # EVT
        "water": 7292,
        "developed": [7296, 7297, 7298, 7299],
        "excluded_evt": [],
    }
    return datasets | config


class TestRasters:
    def test(_, outputs, raster, logcheck):
        perimeter = outputs / "perimeter.tif"
        dem = outputs / "dem.tif"
        rasters = {"perimeter": raster, "dem": raster}

        assert not perimeter.exists()
        assert not dem.exists()
        _save.rasters(outputs, rasters, logcheck.log)
        assert perimeter.exists()
        assert dem.exists()

        logcheck.check(
            [
                ("INFO", "Saving preprocessed rasters"),
                ("DEBUG", "    Saving perimeter"),
                ("DEBUG", "    Saving dem"),
            ]
        )

    def test_overwrite(_, outputs, raster, logcheck):
        with open(outputs / "perimeter.tif", "w") as file:
            file.write("a text file")
        with open(outputs / "dem.tif", "w") as file:
            file.write("a text file")

        perimeter = outputs / "perimeter.tif"
        dem = outputs / "dem.tif"
        rasters = {"perimeter": raster, "dem": raster}

        _save.rasters(outputs, rasters, logcheck.log)
        assert perimeter.exists()
        assert dem.exists()
        Raster(perimeter)
        Raster(dem)

        logcheck.check(
            [
                ("INFO", "Saving preprocessed rasters"),
                ("DEBUG", "    Saving perimeter"),
                ("DEBUG", "    Saving dem"),
            ]
        )


class TestConfig:
    def test(_, outputs, config, paths, outtext, logcheck):
        path = outputs / "configuration.txt"
        assert not path.exists()
        _save.config(outputs, config, paths, logcheck.log)
        assert path.exists()
        logcheck.check([("DEBUG", "    Saving configuration.txt")])

        perimeter = paths["perimeter"]
        dem = paths["dem"]
        assert outtext(path) == (
            f"# Preprocessor configuration for wildcat v{version()}\n"
            "\n"
            "# Input datasets\n"
            f'perimeter = r"{perimeter}"\n'
            f'dem = r"{dem}"\n'
            "dnbr = None\n"
            "severity = None\n"
            "kf = 5\n"
            "evt = None\n"
            "retainments = None\n"
            "excluded = None\n"
            "included = None\n"
            "iswater = None\n"
            "isdeveloped = None\n"
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
            "# Burn Severity\n"
            "severity_field = None\n"
            "estimate_severity = True\n"
            "severity_thresholds = [125, 250, 500]\n"
            "contain_severity = True\n"
            "\n"
            "# KF-factors\n"
            "kf_field = None\n"
            "constrain_kf = True\n"
            "max_missing_kf_ratio = 0.05\n"
            'missing_kf_check = "warn"\n'
            "kf_fill = 2.2\n"
            "kf_fill_field = None\n"
            "\n"
            "# EVT masks\n"
            "water = 7292\n"
            "developed = [7296, 7297, 7298, 7299]\n"
            "excluded_evt = []\n\n"
        )

    def test_kf_fill_file(_, outputs, config, paths, outtext, logcheck):
        filename = "kf_fill.shp"
        kf_fill = paths["perimeter"].parent / filename

        paths["kf_fill"] = kf_fill
        config["kf_fill"] = Path(filename)
        config["kf_fill_field"] = "KFFACT"

        path = outputs / "configuration.txt"
        assert not path.exists()
        _save.config(outputs, config, paths, logcheck.log)
        assert path.exists()
        logcheck.check([("DEBUG", "    Saving configuration.txt")])

        perimeter = paths["perimeter"]
        dem = paths["dem"]
        print(outtext(path))
        assert outtext(path) == (
            f"# Preprocessor configuration for wildcat v{version()}\n"
            "\n"
            "# Input datasets\n"
            f'perimeter = r"{perimeter}"\n'
            f'dem = r"{dem}"\n'
            "dnbr = None\n"
            "severity = None\n"
            "kf = 5\n"
            "evt = None\n"
            "retainments = None\n"
            "excluded = None\n"
            "included = None\n"
            "iswater = None\n"
            "isdeveloped = None\n"
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
            "# Burn Severity\n"
            "severity_field = None\n"
            "estimate_severity = True\n"
            "severity_thresholds = [125, 250, 500]\n"
            "contain_severity = True\n"
            "\n"
            "# KF-factors\n"
            "kf_field = None\n"
            "constrain_kf = True\n"
            "max_missing_kf_ratio = 0.05\n"
            'missing_kf_check = "warn"\n'
            f'kf_fill = r"{kf_fill}"\n'
            'kf_fill_field = "KFFACT"\n'
            "\n"
            "# EVT masks\n"
            "water = 7292\n"
            "developed = [7296, 7297, 7298, 7299]\n"
            "excluded_evt = []\n\n"
        )
