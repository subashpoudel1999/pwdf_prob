import numpy as np
import pytest
from pfdf.raster import Raster

from wildcat._commands.preprocess import _numeric


@pytest.fixture
def dconfig():
    return {"constrain_dnbr": True, "dnbr_limits": [-2000, 2000]}


@pytest.fixture
def drasters():
    nodata = -9999
    dnbr = np.full((20, 5), nodata)
    dnbr[0, 0] = -10000
    dnbr[0, 1] = 10000
    dnbr = Raster.from_array(dnbr, nodata=nodata)
    return {"dnbr": dnbr}


class TestConstrainDnbr:
    def test_disabled(_, dconfig, drasters, logcheck):
        dconfig["constrain_dnbr"] = False
        _numeric.constrain_dnbr(dconfig, drasters, logcheck.log)
        assert np.min(drasters["dnbr"].values) == -10000
        assert np.max(drasters["dnbr"].values) == 10000
        logcheck.check([])

    def test_no_dnbr(_, dconfig, drasters, logcheck):
        del drasters["dnbr"]
        _numeric.constrain_dnbr(dconfig, drasters, logcheck.log)
        logcheck.check([])

    def test_constrain(_, dconfig, drasters, logcheck):
        _numeric.constrain_dnbr(dconfig, drasters, logcheck.log)
        dnbr = drasters["dnbr"]
        assert np.min(dnbr.values) == -9999
        data = dnbr.values[dnbr.data_mask]
        assert np.min(data) == -2000
        assert np.max(data) == 2000


@pytest.fixture
def kconfig():
    return {"constrain_kf": True, "kf_fill": True}


@pytest.fixture
def krasters():
    nodata = -9999
    kf = np.full((20, 5), -9999.0)
    kf[0, 0] = -5
    kf[0, 1] = 0
    kf[0, 2] = 5
    kf[0, 3] = 6
    kf = Raster.from_array(kf, nodata=nodata)

    kf_fill = np.full((20, 5), 2.4)
    kf_fill = Raster.from_array(kf_fill)
    return {"kf": kf, "kf_fill": kf_fill}


class TestConstrainKf:
    def test_disabled(_, kconfig, krasters, logcheck):
        kconfig["constrain_kf"] = False
        _numeric.constrain_kf(kconfig, krasters, logcheck.log)
        kf = krasters["kf"]
        assert kf.values[0, 0] == -5
        logcheck.check([])

    def test_no_kf(_, kconfig, krasters, logcheck):
        del krasters["kf"]
        _numeric.constrain_kf(kconfig, krasters, logcheck.log)
        logcheck.check([])

    def test_constrain(_, kconfig, krasters, logcheck):
        _numeric.constrain_kf(kconfig, krasters, logcheck.log)
        kf = krasters["kf"]
        assert np.min(kf.values) == -9999
        data = kf.values[kf.data_mask]
        assert np.min(data) == 5


class TestFillMissingKf:
    def test_disabled(_, kconfig, krasters, logcheck):
        kconfig["kf_fill"] = False
        _numeric.fill_missing_kf(kconfig, krasters, logcheck.log)
        assert np.min(krasters["kf"].values) == -9999
        logcheck.check([])

    def test_no_kf(_, kconfig, krasters, logcheck):
        del krasters["kf"]
        _numeric.fill_missing_kf(kconfig, krasters, logcheck.log)
        logcheck.check([])

    def test_median(_, kconfig, krasters, logcheck):
        _numeric.fill_missing_kf(kconfig, krasters, logcheck.log)
        assert krasters["kf"].values[0, 4] == 2.5
        assert krasters["kf"].values[1, 0] == 2.5
        logcheck.check(
            [
                ("INFO", "Filling missing KF-factors"),
                ("DEBUG", "    Filling with median KF: 2.5"),
            ]
        )

    def test_value(_, kconfig, krasters, logcheck):
        kconfig["kf_fill"] = 2.2
        _numeric.fill_missing_kf(kconfig, krasters, logcheck.log)
        assert krasters["kf"].values[0, 4] == 2.2
        assert krasters["kf"].values[1, 0] == 2.2
        logcheck.check(
            [("INFO", "Filling missing KF-factors"), ("DEBUG", "    Filling with 2.2")]
        )

    def test_file(_, kconfig, krasters, logcheck):
        kconfig["kf_fill"] = "a/file/path"
        _numeric.fill_missing_kf(kconfig, krasters, logcheck.log)
        assert krasters["kf"].values[0, 4] == 2.4
        assert krasters["kf"].values[1, 0] == 2.4
        logcheck.check(
            [
                ("INFO", "Filling missing KF-factors"),
                ("DEBUG", "    Filling using kf_fill file"),
            ]
        )


@pytest.fixture
def sconfig():
    return {
        "estimate_severity": True,
        "severity_thresholds": [100, 200, 300],
        "contain_severity": True,
    }


@pytest.fixture
def srasters():
    dnbr = np.array(
        [
            [50, 50, 50, 50],
            [150, 150, 150, 150],
            [250, 250, 250, 250],
            [400, 400, 400, 400],
        ]
    )
    dnbr = Raster.from_array(dnbr, nodata=-9999)
    estimated = np.array(
        [
            [1, 1, 1, 1],
            [2, 2, 2, 2],
            [3, 3, 3, 3],
            [4, 4, 4, 4],
        ]
    )
    estimated = Raster.from_array(estimated, nodata=0)

    severity = np.array(
        [
            [1, 2, 3, 4],
            [1, 2, 3, 4],
            [1, 2, 3, 4],
            [1, 2, 3, 4],
        ]
    )
    severity = Raster.from_array(severity, nodata=0)
    perimeter = np.array(
        [
            [0, 0, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 1],
            [0, 0, 1, 1],
        ]
    )
    perimeter = Raster(perimeter, isbool=True)
    contained = np.array(
        [
            [0, 0, 0, 0],
            [0, 2, 3, 0],
            [0, 0, 3, 4],
            [0, 0, 3, 4],
        ]
    )
    contained = Raster.from_array(contained, nodata=0)

    return {
        "dnbr": dnbr,
        "estimated": estimated,
        "severity": severity,
        "perimeter": perimeter,
        "contained": contained,
    }


class TestEstimateSeverity:
    def test_disabled(_, sconfig, srasters, logcheck):
        sconfig["estimate_severity"] = False
        del srasters["severity"]
        _numeric.estimate_severity(sconfig, srasters, logcheck.log)
        assert "severity" not in srasters
        logcheck.check([])

    def test_have_severity(_, sconfig, srasters, logcheck):
        _numeric.estimate_severity(sconfig, srasters, logcheck.log)
        severity = srasters["severity"].values
        estimated = srasters["estimated"].values
        assert not np.array_equal(severity, estimated)
        logcheck.check([])

    def test_no_dnbr(_, sconfig, srasters, logcheck):
        del srasters["severity"]
        del srasters["dnbr"]
        _numeric.estimate_severity(sconfig, srasters, logcheck.log)
        assert "severity" not in srasters
        logcheck.check([])

    def test_estimate(_, sconfig, srasters, logcheck):
        del srasters["severity"]
        _numeric.estimate_severity(sconfig, srasters, logcheck.log)
        severity = srasters["severity"].values
        estimated = srasters["estimated"].values
        assert np.array_equal(severity, estimated)


class TestContainSeverity:
    def test_disabled(_, sconfig, srasters, logcheck):
        sconfig["contain_severity"] = False
        _numeric.contain_severity(sconfig, srasters, logcheck.log)
        severity = srasters["severity"].values
        contained = srasters["contained"].values
        assert not np.array_equal(severity, contained)
        logcheck.check([])

    def test_no_severity(_, sconfig, srasters, logcheck):
        del srasters["severity"]
        _numeric.contain_severity(sconfig, srasters, logcheck.log)
        assert "severity" not in srasters
        logcheck.check([])

    def test_contain(_, sconfig, srasters, logcheck):
        _numeric.contain_severity(sconfig, srasters, logcheck.log)
        severity = srasters["severity"].values
        contained = srasters["contained"].values
        assert np.array_equal(severity, contained)


@pytest.fixture
def econfig():
    return {"water": [7292], "developed": [7296, 7297, 7298, 7299], "excluded_evt": []}


@pytest.fixture
def erasters():
    evt = np.array(
        [
            [7292, 7292, 1000, 1000],
            [7292, 7292, 1000, 1000],
            [1000, 1000, 1000, 7296],
            [7296, 7298, 7299, 7298],
        ]
    )
    evt = Raster(evt)

    expected_water = np.array(
        [
            [1, 1, 0, 0],
            [1, 1, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ]
    )
    expected_water = Raster(expected_water, isbool=True)

    developed = np.array(
        [
            [0, 0, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 1],
            [0, 0, 1, 1],
        ]
    )
    developed = Raster(developed, isbool=True)

    merged = np.array(
        [
            [0, 0, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 1],
            [1, 1, 1, 1],
        ]
    )
    merged = Raster(merged, isbool=True)
    return {
        "evt": evt,
        "isdeveloped": developed,
        "merged": merged,
        "expected_water": expected_water,
    }


class TestBuildEVTMasks:
    def test_none(_, econfig, erasters, logcheck):
        econfig["water"] = []
        econfig["developed"] = []
        del erasters["isdeveloped"]
        _numeric.build_evt_masks(econfig, erasters, logcheck.log)
        assert "iswater" not in erasters
        assert "isdeveloped" not in erasters
        assert "excluded" not in erasters
        logcheck.check([])

    def test_no_evt(_, econfig, erasters, logcheck):
        del erasters["evt"]
        del erasters["isdeveloped"]
        _numeric.build_evt_masks(econfig, erasters, logcheck.log)
        assert "iswater" not in erasters
        assert "isdeveloped" not in erasters
        assert "excluded" not in erasters
        logcheck.check([])

    def test_masks(_, econfig, erasters, logcheck):
        # water tests just an EVT
        # developed tests merging and EVT
        # excluded tests no EVT codes
        _numeric.build_evt_masks(econfig, erasters, logcheck.log)
        iswater = erasters["iswater"].values
        expected = erasters["expected_water"].values
        assert np.array_equal(iswater, expected)

        developed = erasters["isdeveloped"].values
        expected = erasters["merged"].values

        assert np.array_equal(developed, expected)

        assert "excluded" not in erasters
        logcheck.check(
            [
                ("INFO", "Building EVT masks"),
                ("DEBUG", "    Locating water pixels"),
                ("DEBUG", "    Locating developed pixels"),
                ("DEBUG", '    Merging developed mask with "isdeveloped" file'),
            ]
        )
