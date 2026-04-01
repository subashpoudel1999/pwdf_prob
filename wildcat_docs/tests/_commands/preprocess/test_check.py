import numpy as np
import pytest
from pfdf.raster import Raster

from wildcat._commands.preprocess import _check


@pytest.fixture
def resconfig():
    return {
        "resolution_check": "error",
        "resolution_limits_m": [6.5, 11],
    }


@pytest.fixture
def resdem():
    dem = Raster(np.arange(100).reshape(20, 5))
    dem.crs = 26911
    dem.transform = (3.33, 11.11, 0, 0)
    return dem


@pytest.fixture
def drasters():
    nodata = -90000
    dnbr = np.zeros(100).reshape(20, 5)
    dnbr[0, 0] = nodata
    dnbr = Raster.from_array(dnbr, nodata=nodata)
    return {"dnbr": dnbr}


@pytest.fixture
def dconfig():
    return {"dnbr_scaling_check": "error"}


@pytest.fixture
def krasters():
    kf = np.arange(100).reshape(10, 10)
    kf[0, :] = -1
    kf = Raster.from_array(kf, nodata=-1)
    return {"kf": kf}


@pytest.fixture
def kconfig():
    return {
        "max_missing_kf_ratio": 0.05,
        "missing_kf_check": "error",
        "kf_fill": False,
    }


class TestCheck:
    def test_pass(_, logcheck):
        _check._check("error", False, "A test message", logcheck.log)
        logcheck.check([])

    def test_warn(_, logcheck):
        _check._check("warn", True, "test message", logcheck.log)
        logcheck.check([("WARNING", "\ntest message\n")])

    def test_error(_, errcheck, logcheck):
        with pytest.raises(ValueError) as error:
            _check._check("error", True, "test message", logcheck.log)
        errcheck(error, "test message")


class TestIsUnexpected:
    @pytest.mark.parametrize(
        "value, limits, expected",
        (
            (5, [6.5, 11], True),
            (5, [1, 6], False),
            (10, [6.5, 11], False),
            (12, [6.5, 11], True),
        ),
    )
    def test(_, value, limits, expected):
        assert _check._isunexpected(value, limits) == expected


class TestResolution:
    def test_valid(_, resconfig, resdem, logcheck):
        resdem.override(transform=(10.3333, 10.7777, 0, 0))
        _check.resolution(resconfig, resdem, logcheck.log)
        logcheck.check([("DEBUG", "    Resolution: 10.33 x 10.78 meters")])

    def test_none(_, resconfig, resdem, logcheck):
        resconfig["resolution_check"] = "none"
        _check.resolution(resconfig, resdem, logcheck.log)
        logcheck.check([("DEBUG", "    Resolution: 3.33 x 11.11 meters")])

    def test_warn(_, resconfig, resdem, logcheck):
        resconfig["resolution_check"] = "warn"
        _check.resolution(resconfig, resdem, logcheck.log)
        logcheck.check(
            [
                ("DEBUG", "    Resolution: 3.33 x 11.11 meters"),
                (
                    "WARNING",
                    (
                        "\n"
                        "WARNING: The DEM does not have an allowed resolution.\n"
                        "    Allowed resolutions: from 6.5 to 11 meters\n"
                        "    DEM resolution: 3.33 x 11.11 meters\n"
                        "\n"
                        "    The hazard assessment models in wildcat were calibrated using\n"
                        "    a 10 meter DEM, so this resolution is recommended for most\n"
                        "    applications. See also Smith et al., (2019) for a discussion\n"
                        "    of the effects of DEM resolution on topographic analysis:\n"
                        "    https://doi.org/10.5194/esurf-7-475-2019\n"
                        "\n"
                        "    To continue with the current DEM, add either of the following lines to\n"
                        "    configuration.py:\n"
                        "\n"
                        '     resolution_check = "warn"\n'
                        "     OR\n"
                        '     resolution_check = "none"\n'
                    ),
                ),
            ]
        )

    def test_error(_, resconfig, resdem, errcheck, logcheck):
        with pytest.raises(ValueError) as error:
            _check.resolution(resconfig, resdem, logcheck.log)
        errcheck(error, "The DEM does not have an allowed resolution")


class TestDnbrScaling:
    @pytest.mark.parametrize("value", (-11, 11))
    def test_valid(_, dconfig, value, drasters, logcheck):
        dnbr = np.zeros((20, 5))
        dnbr[0, 0] = value
        drasters = {"dnbr": Raster(dnbr)}
        _check.dnbr_scaling(dconfig, drasters, logcheck.log)
        logcheck.check([("INFO", "Checking dNBR scaling")])

    def test_missing_dnbr(_, dconfig, drasters, logcheck):
        del drasters["dnbr"]
        _check.dnbr_scaling(dconfig, drasters, logcheck.log)
        logcheck.check([])

    def test_none(_, dconfig, drasters, logcheck):
        dconfig["dnbr_scaling_check"] = "none"
        _check.dnbr_scaling(dconfig, drasters, logcheck.log)
        logcheck.check([])

    def test_warn(_, dconfig, drasters, logcheck):
        dconfig["dnbr_scaling_check"] = "warn"
        _check.dnbr_scaling(dconfig, drasters, logcheck.log)
        logcheck.check(
            [
                ("INFO", "Checking dNBR scaling"),
                (
                    "WARNING",
                    (
                        "\n"
                        "WARNING: The dNBR may not be scaled properly. Wildcat expects dNBR\n"
                        "    inputs to be (raw dNBR * 1000). Typical values of scaled datasets\n"
                        "    range roughly between -1000 and 1000, but the values in the input\n"
                        "    raster are between -10 and 10. You may need to multiply your dNBR\n"
                        "    values by 1000 to scale them correctly.\n"
                        "\n"
                        "    To continue with the current dNBR, edit configuration.py to include\n"
                        "    one of the following lines:\n"
                        "\n"
                        '    dnbr_check = "warn"\n'
                        "    OR\n"
                        '    dnbr_check = "none"\n'
                    ),
                ),
            ]
        )

    def test_error(_, dconfig, drasters, errcheck, logcheck):
        with pytest.raises(ValueError) as error:
            _check.dnbr_scaling(dconfig, drasters, logcheck.log)
        errcheck(error, "The dNBR may not be scaled properly")


class TestMissingKF:
    def test_valid(_, kconfig, logcheck):
        kf = np.ones((20, 5))
        kf = Raster.from_array(kf, nodata=-1)
        krasters = {"kf": kf}
        _check.missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check(
            [
                ("INFO", "Checking for missing KF-factor data"),
                ("DEBUG", "    Proportion of missing data: 0.0"),
            ]
        )

    @pytest.mark.parametrize("fill", (True, 2.2, "a/file/path"))
    def test_filling(_, fill, kconfig, krasters, logcheck):
        kconfig["kf_fill"] = fill
        _check.missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check([])

    def test_missing_kf(_, kconfig, krasters, logcheck):
        del krasters["kf"]
        _check.missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check([])

    def test_none(_, kconfig, krasters, logcheck):
        kconfig["missing_kf_check"] = "none"
        _check.missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check([])

    def test_under_threshold(_, kconfig, krasters, logcheck):
        kconfig["max_missing_kf_ratio"] = 0.25
        _check.missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check(
            [
                ("INFO", "Checking for missing KF-factor data"),
                ("DEBUG", "    Proportion of missing data: 0.1"),
            ]
        )

    def test_warn(_, kconfig, krasters, logcheck):
        kconfig["missing_kf_check"] = "warn"
        _check.missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check(
            [
                ("INFO", "Checking for missing KF-factor data"),
                ("DEBUG", "    Proportion of missing data: 0.1"),
                (
                    "WARNING",
                    "\n"
                    "WARNING: The KF-factor raster has missing data. This may indicate that\n"
                    "    the KF-factor dataset is incomplete, but can also occur for normal\n"
                    "    reasons (such as the analysis domain intersecting a water feature).\n"
                    "    We recommend examining the KF-factor dataset for missing data before\n"
                    "    continuing.\n"
                    "    \n"
                    "    If the dataset appears satisfactory, you can disable this message\n"
                    "    by adding the following line to configuration.py:\n"
                    '    missing_kf_check = "none"\n'
                    "    \n"
                    '    Alternatively, see the "kf_fill" config value for options to fill missing\n'
                    "    KF-factor data pixels.\n",
                ),
            ]
        )

    def test_error(_, kconfig, krasters, errcheck, logcheck):
        with pytest.raises(ValueError) as error:
            _check.missing_kf(kconfig, krasters, logcheck.log)
        errcheck(error, "The KF-factor raster has missing data")
