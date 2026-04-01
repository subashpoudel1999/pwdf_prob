import os

import fiona
import numpy as np
import pytest
from pfdf.raster import Raster
from pyproj import CRS

import wildcat
from wildcat import version
from wildcat._cli import main
from wildcat._commands.preprocess import _preprocess
from wildcat._utils import _args


def _folder(parent, name):
    path = parent / name
    path.mkdir(parents=True)
    return path


@pytest.fixture
def locals(project):
    "Builds the locals dict. Uses kf-fill and iswater to test use of kwargs"

    args = _args.collect(wildcat.preprocess)
    locals = {arg: None for arg in args}
    locals["project"] = project
    locals["kf_fill"] = True
    locals["iswater"] = False
    return locals


def config(project):
    path = project / "configuration.py"
    with open(path, "w") as file:
        file.write(
            "buffer_km = 0.02\n"
            'kf_field = "KFFACT"\n'
            "kf_fill = -9\n"  # Will override using kwargs
            "iswater = 'an/example/path'\n"  # Will disable using kwargs
            "excluded_evt = [5, 7]\n"
        )
    return path


def dem(inputs):
    dem = np.arange(100).reshape(10, 10)
    dem = Raster.from_array(dem, crs=26911, bounds=(0, 0, 100, 100))
    path = inputs / "dem.tif"
    dem.save(path)
    return path


def perimeter(inputs):
    schema = {"geometry": "Polygon", "properties": {}}
    record = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[20, 20], [20, 70], [60, 70], [60, 20], [20, 20]]],
        },
        "properties": {},
    }
    path = inputs / "perimeter.shp"
    with fiona.open(path, "w", crs=CRS(26911), schema=schema) as file:
        file.write(record)
    return path


def dnbr(inputs):
    dnbr = np.empty((10, 10))
    dnbr[0:3, :] = -5000
    dnbr[3:5, :] = 150
    dnbr[5:7, :] = 275
    dnbr[7:9, :] = 700
    dnbr[9, :] = 9000
    dnbr = Raster.from_array(dnbr, crs=26911, bounds=(0, 0, 100, 100))
    dnbr.reproject(crs=4326)
    path = inputs / "dnbr.tif"
    dnbr.save(path)
    return path


def kf(inputs):
    schema = {"geometry": "Polygon", "properties": {"KFFACT": "float"}}
    record0 = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 50], [0, 100], [50, 100], [50, 50], [0, 50]]],
        },
        "properties": {"KFFACT": 1.1},
    }
    record1 = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[50, 0], [50, 50], [100, 50], [100, 0], [50, 0]]],
        },
        "properties": {"KFFACT": 2.2},
    }
    path = inputs / "kf.geojson"
    with fiona.open(path, "w", crs=CRS(26911), schema=schema) as file:
        file.write(record0)
        file.write(record1)
    return path


def evt(inputs):
    evt = np.empty((10, 10))
    evt[0:3, :] = 7292
    evt[3, :] = 7296
    evt[4, :] = 5
    evt[5, :] = 7298
    evt[6, :] = 6
    evt[7, :] = 7297
    evt[8, :] = 7
    evt[9, :] = 400
    evt = Raster.from_array(evt, crs=26911, bounds=(0, 0, 100, 100))
    path = inputs / "evt.tif"
    evt.save(path)
    return path


def excluded(inputs):
    schema = {"geometry": "Polygon", "properties": {}}
    record = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 20], [0, 50], [100, 50], [100, 20], [0, 20]]],
        },
        "properties": {},
    }
    path = inputs / "excluded.shp"
    with fiona.open(path, "w", crs=CRS(26911), schema=schema) as file:
        file.write(record)
    return path


def retainments(inputs):
    schema = {"geometry": "Point", "properties": {}}
    records = [
        {"geometry": {"type": "Point", "coordinates": [25, 35]}, "properties": {}},
        {"geometry": {"type": "Point", "coordinates": [0, 90]}, "properties": {}},
        {"geometry": {"type": "Point", "coordinates": [71, 61]}, "properties": {}},
    ]
    path = inputs / "retainments.geojson"
    with fiona.open(path, "w", crs=CRS(26911), schema=schema) as file:
        file.writerecords(records)
    return path


def make_datasets(project):
    inputs = _folder(project, "inputs")
    paths = {}
    paths["project"] = project
    paths["config"] = config(project)
    paths["inputs"] = inputs
    paths["dem"] = dem(inputs)
    paths["perimeter"] = perimeter(inputs)
    paths["dnbr"] = dnbr(inputs)
    paths["kf"] = kf(inputs)
    paths["evt"] = evt(inputs)
    paths["excluded"] = excluded(inputs)
    paths["retainments"] = retainments(inputs)
    return paths


class TestPreprocess:
    def test_function(_, project, locals, logcheck):

        # Note: The configuration file in "make_datasets" tests the use of config
        # values, while kf_fill = True tests the use of kwargs. The remaining args
        # test the use of default values
        paths = make_datasets(project)
        preprocessed = project / "preprocessed"
        paths["preprocessed"] = preprocessed
        assert not preprocessed.exists()

        logcheck.start("wildcat.preprocess")
        _preprocess.preprocess(locals)

        assert preprocessed.exists()
        contents = os.listdir(preprocessed)
        assert sorted(contents) == sorted(
            [
                "configuration.txt",
                "perimeter.tif",
                "dem.tif",
                "dnbr.tif",
                "severity.tif",
                "kf.tif",
                "evt.tif",
                "retainments.tif",
                "excluded.tif",
                "iswater.tif",
                "isdeveloped.tif",
            ]
        )

        check_perimeter(preprocessed)
        check_dem(preprocessed)
        check_dnbr(preprocessed)
        check_severity(preprocessed)
        check_kf(preprocessed)
        check_evt(preprocessed)
        check_retainments(preprocessed)
        check_excluded(preprocessed)
        check_iswater(preprocessed)
        check_isdeveloped(preprocessed)
        check_config(preprocessed, paths)
        check_log(logcheck, paths)

    def test_constant(_, project, locals, logcheck):
        locals["kf"] = 5

        paths = make_datasets(project)
        preprocessed = project / "preprocessed"
        paths["preprocessed"] = preprocessed
        assert not preprocessed.exists()

        logcheck.start("wildcat.preprocess")
        _preprocess.preprocess(locals)

        assert preprocessed.exists()
        contents = os.listdir(preprocessed)
        assert sorted(contents) == sorted(
            [
                "configuration.txt",
                "perimeter.tif",
                "dem.tif",
                "dnbr.tif",
                "severity.tif",
                "kf.tif",
                "evt.tif",
                "retainments.tif",
                "excluded.tif",
                "iswater.tif",
                "isdeveloped.tif",
            ]
        )

        check_perimeter(preprocessed)
        check_dem(preprocessed)
        check_dnbr(preprocessed)
        check_severity(preprocessed)
        check_kf_constant(preprocessed)
        check_evt(preprocessed)
        check_retainments(preprocessed)
        check_excluded(preprocessed)
        check_iswater(preprocessed)
        check_isdeveloped(preprocessed)
        check_config_constant(preprocessed, paths)
        check_log_constant(logcheck, paths)

    def test_cli(_, project, CleanCLI, logcheck):

        # Note: The configuration file in "make_datasets" tests the use of config
        # values, while kf_fill = True tests the use of kwargs. The remaining args
        # test the use of default values
        paths = make_datasets(project)
        preprocessed = project / "preprocessed"
        paths["preprocessed"] = preprocessed
        assert not preprocessed.exists()

        logcheck.start("wildcat.preprocess")
        with CleanCLI:
            main(
                [
                    "preprocess",
                    "--kf-fill",
                    "True",
                    "--iswater",
                    "None",
                    str(project),
                ]
            )

        assert preprocessed.exists()
        contents = os.listdir(preprocessed)
        assert sorted(contents) == sorted(
            [
                "configuration.txt",
                "perimeter.tif",
                "dem.tif",
                "dnbr.tif",
                "severity.tif",
                "kf.tif",
                "evt.tif",
                "retainments.tif",
                "excluded.tif",
                "iswater.tif",
                "isdeveloped.tif",
            ]
        )

        check_perimeter(preprocessed)
        check_dem(preprocessed)
        check_dnbr(preprocessed)
        check_severity(preprocessed)
        check_kf(preprocessed)
        check_evt(preprocessed)
        check_retainments(preprocessed)
        check_excluded(preprocessed)
        check_iswater(preprocessed)
        check_isdeveloped(preprocessed)
        check_config(preprocessed, paths)
        check_log(logcheck, paths)


def _check_raster(preprocessed, name):
    raster = Raster(preprocessed / f"{name}.tif")
    assert raster.crs == 26911
    assert raster.bounds.tolist(crs=False) == [0, 0, 80, 90]
    return raster


def check_perimeter(preprocessed):
    perimeter = _check_raster(preprocessed, "perimeter")
    expected = np.zeros((9, 8))
    expected[2:-2, 2:-2] = 1
    assert np.array_equal(perimeter.values, expected)


def check_dem(preprocessed):
    dem = _check_raster(preprocessed, "dem")
    expected = np.arange(100).reshape(10, 10)
    expected = expected[1:, :-2]
    assert np.array_equal(dem.values, expected)


def check_dnbr(preprocessed):
    dnbr = _check_raster(preprocessed, "dnbr")
    expected = np.empty((9, 8))
    expected[0:2, :] = -2000
    expected[2:4, :] = 150
    expected[4:6, :] = 275
    expected[6:8, :] = 700
    expected[8, :] = 2000
    assert np.array_equal(dnbr.values, expected)


def check_severity(preprocessed):
    severity = _check_raster(preprocessed, "severity")
    expected = np.empty((9, 8))
    expected[0:2, :] = 1
    expected[2:4, :] = 2
    expected[4:6, :] = 3
    expected[6:, :] = 4

    expected[0:2, :] = severity.nodata
    expected[-2:, :] = severity.nodata
    expected[:, 0:2] = severity.nodata
    expected[:, -2:] = severity.nodata

    assert np.array_equal(severity.values, expected)


def check_kf(preprocessed):
    kf = _check_raster(preprocessed, "kf")
    expected = np.full((9, 8), 1.1)
    expected[4:, 5:] = 2.2
    assert np.array_equal(kf.values, expected)


def check_kf_constant(preprocessed):
    kf = _check_raster(preprocessed, "kf")
    expected = np.full((9, 8), 5)
    assert np.array_equal(kf.values, expected)


def check_evt(preprocessed):
    evt = _check_raster(preprocessed, "evt")
    expected = np.empty((9, 8))
    expected[0:2, :] = 7292
    expected[2, :] = 7296
    expected[3, :] = 5
    expected[4, :] = 7298
    expected[5, :] = 6
    expected[6, :] = 7297
    expected[7, :] = 7
    expected[8, :] = 400
    assert np.array_equal(evt.values, expected)


def check_retainments(preprocessed):
    retainments = _check_raster(preprocessed, "retainments")
    expected = np.zeros((9, 8))
    expected[0, 0] = 1
    expected[5, 2] = 1
    expected[2, 7] = 1
    assert np.array_equal(retainments.values, expected)


def check_excluded(preprocessed):
    mask = _check_raster(preprocessed, "excluded")
    expected = np.zeros((9, 8), bool)
    expected[3:8, :] = True
    assert np.array_equal(mask.values, expected)


def check_iswater(preprocessed):
    mask = _check_raster(preprocessed, "iswater")
    expected = np.zeros((9, 8), bool)
    expected[0:2, :] = True
    assert np.array_equal(mask.values, expected)


def check_isdeveloped(preprocessed):
    mask = _check_raster(preprocessed, "isdeveloped")
    expected = np.zeros((9, 8), bool)
    for row in [3, 5, 7]:
        expected[row - 1, :] = True
    assert np.array_equal(mask.values, expected)


def check_config(preprocessed, paths):
    path = preprocessed / "configuration.txt"
    with open(path) as file:
        text = file.read()

    perimeter = paths["perimeter"]
    dem = paths["dem"]
    dnbr = paths["dnbr"]
    kf = paths["kf"]
    evt = paths["evt"]
    retainments = paths["retainments"]
    excluded = paths["excluded"]

    assert text == (
        f"# Preprocessor configuration for wildcat v{version()}\n"
        "\n"
        "# Input datasets\n"
        f'perimeter = r"{perimeter}"\n'
        f'dem = r"{dem}"\n'
        f'dnbr = r"{dnbr}"\n'
        f"severity = None\n"
        f'kf = r"{kf}"\n'
        f'evt = r"{evt}"\n'
        f'retainments = r"{retainments}"\n'
        f'excluded = r"{excluded}"\n'
        f"included = None\n"
        f"iswater = None\n"
        f"isdeveloped = None\n"
        "\n"
        "# Perimeter\n"
        "buffer_km = 0.02\n"
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
        'kf_field = "KFFACT"\n'
        "constrain_kf = True\n"
        "max_missing_kf_ratio = 0.05\n"
        'missing_kf_check = "warn"\n'
        "kf_fill = True\n"
        "kf_fill_field = None\n"
        "\n"
        "# EVT masks\n"
        "water = [7292]\n"
        "developed = [7296, 7297, 7298, 7299, 7300]\n"
        "excluded_evt = [5, 7]\n\n"
    )


def check_config_constant(preprocessed, paths):
    path = preprocessed / "configuration.txt"
    with open(path) as file:
        text = file.read()

    perimeter = paths["perimeter"]
    dem = paths["dem"]
    dnbr = paths["dnbr"]
    evt = paths["evt"]
    retainments = paths["retainments"]
    excluded = paths["excluded"]

    assert text == (
        f"# Preprocessor configuration for wildcat v{version()}\n"
        "\n"
        "# Input datasets\n"
        f'perimeter = r"{perimeter}"\n'
        f'dem = r"{dem}"\n'
        f'dnbr = r"{dnbr}"\n'
        f"severity = None\n"
        f"kf = 5\n"
        f'evt = r"{evt}"\n'
        f'retainments = r"{retainments}"\n'
        f'excluded = r"{excluded}"\n'
        f"included = None\n"
        f"iswater = None\n"
        f"isdeveloped = None\n"
        "\n"
        "# Perimeter\n"
        "buffer_km = 0.02\n"
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
        'kf_field = "KFFACT"\n'
        "constrain_kf = True\n"
        "max_missing_kf_ratio = 0.05\n"
        'missing_kf_check = "warn"\n'
        "kf_fill = True\n"
        "kf_fill_field = None\n"
        "\n"
        "# EVT masks\n"
        "water = [7292]\n"
        "developed = [7296, 7297, 7298, 7299, 7300]\n"
        "excluded_evt = [5, 7]\n\n"
    )


def check_log(logcheck, paths):
    config_path = paths["project"] / "configuration.py"
    logcheck.check(
        [
            ("INFO", "----- Preprocessing -----"),
            ("INFO", "Parsing configuration"),
            ("DEBUG", "    Locating project folder"),
            ("DEBUG", f"        {paths['project']}"),
            ("DEBUG", "    Reading configuration file"),
            ("DEBUG", f"        {config_path}"),
            ("INFO", "Locating IO folders"),
            ("DEBUG", f"    inputs: {paths['inputs']}"),
            ("DEBUG", f"    preprocessed: {paths['preprocessed']}"),
            ("INFO", "Locating input datasets"),
            ("DEBUG", f"    perimeter:    {paths['perimeter']}"),
            ("DEBUG", f"    dem:          {paths['dem']}"),
            ("DEBUG", f"    dnbr:         {paths['dnbr']}"),
            ("DEBUG", f"    severity:     None"),
            ("DEBUG", f"    kf:           {paths['kf']}"),
            ("DEBUG", f"    evt:          {paths['evt']}"),
            ("DEBUG", f"    retainments:  {paths['retainments']}"),
            ("DEBUG", f"    excluded:     {paths['excluded']}"),
            ("DEBUG", f"    included:     None"),
            ("DEBUG", f"    isdeveloped:  None"),
            ("INFO", "Building buffered burn perimeter"),
            ("DEBUG", "    Loading perimeter mask"),
            ("DEBUG", "    Buffering perimeter"),
            ("INFO", "Loading DEM"),
            ("DEBUG", "    Resolution: 10.00 x 10.00 meters"),
            ("INFO", "Loading file-based datasets"),
            ("DEBUG", "    Loading dnbr"),
            ("DEBUG", "    Loading kf"),
            ("DEBUG", "    Loading evt"),
            ("DEBUG", "    Loading retainments"),
            ("DEBUG", "    Loading excluded"),
            ("INFO", "Reprojecting rasters to match the DEM"),
            ("DEBUG", "    Reprojecting perimeter"),
            ("DEBUG", "    Reprojecting dnbr"),
            ("DEBUG", "    Reprojecting kf"),
            ("DEBUG", "    Reprojecting evt"),
            ("DEBUG", "    Reprojecting retainments"),
            ("DEBUG", "    Reprojecting excluded"),
            ("INFO", "Clipping rasters to the buffered perimeter"),
            ("DEBUG", "    Clipping dem"),
            ("DEBUG", "    Clipping dnbr"),
            ("DEBUG", "    Clipping kf"),
            ("DEBUG", "    Clipping evt"),
            ("DEBUG", "    Clipping retainments"),
            ("DEBUG", "    Clipping excluded"),
            ("INFO", "Checking dNBR scaling"),
            ("INFO", "Constraining dNBR data range"),
            ("INFO", "Estimating severity from dNBR"),
            ("INFO", "Containing severity data to the perimeter"),
            ("INFO", "Constraining KF-factors to positive values"),
            ("INFO", "Filling missing KF-factors"),
            ("DEBUG", "    Filling with median KF: 1.1"),
            ("INFO", "Building EVT masks"),
            ("DEBUG", "    Locating water pixels"),
            ("DEBUG", "    Locating developed pixels"),
            ("DEBUG", "    Locating excluded_evt pixels"),
            ("DEBUG", '    Merging excluded_evt mask with "excluded" file'),
            ("INFO", "Saving preprocessed rasters"),
            ("DEBUG", "    Saving perimeter"),
            ("DEBUG", "    Saving dem"),
            ("DEBUG", "    Saving dnbr"),
            ("DEBUG", "    Saving kf"),
            ("DEBUG", "    Saving evt"),
            ("DEBUG", "    Saving retainments"),
            ("DEBUG", "    Saving excluded"),
            ("DEBUG", "    Saving severity"),
            ("DEBUG", "    Saving iswater"),
            ("DEBUG", "    Saving isdeveloped"),
            ("DEBUG", "    Saving configuration.txt"),
        ]
    )


def check_log_constant(logcheck, paths):
    config_path = paths["project"] / "configuration.py"
    logcheck.check(
        [
            ("INFO", "----- Preprocessing -----"),
            ("INFO", "Parsing configuration"),
            ("DEBUG", "    Locating project folder"),
            ("DEBUG", f"        {paths['project']}"),
            ("DEBUG", "    Reading configuration file"),
            ("DEBUG", f"        {config_path}"),
            ("INFO", "Locating IO folders"),
            ("DEBUG", f"    inputs: {paths['inputs']}"),
            ("DEBUG", f"    preprocessed: {paths['preprocessed']}"),
            ("INFO", "Locating input datasets"),
            ("DEBUG", f"    perimeter:    {paths['perimeter']}"),
            ("DEBUG", f"    dem:          {paths['dem']}"),
            ("DEBUG", f"    dnbr:         {paths['dnbr']}"),
            ("DEBUG", f"    severity:     None"),
            ("DEBUG", f"    evt:          {paths['evt']}"),
            ("DEBUG", f"    retainments:  {paths['retainments']}"),
            ("DEBUG", f"    excluded:     {paths['excluded']}"),
            ("DEBUG", f"    included:     None"),
            ("DEBUG", f"    isdeveloped:  None"),
            ("INFO", "Building buffered burn perimeter"),
            ("DEBUG", "    Loading perimeter mask"),
            ("DEBUG", "    Buffering perimeter"),
            ("INFO", "Loading DEM"),
            ("DEBUG", "    Resolution: 10.00 x 10.00 meters"),
            ("INFO", "Loading file-based datasets"),
            ("DEBUG", "    Loading dnbr"),
            ("DEBUG", "    Loading evt"),
            ("DEBUG", "    Loading retainments"),
            ("DEBUG", "    Loading excluded"),
            ("INFO", "Reprojecting rasters to match the DEM"),
            ("DEBUG", "    Reprojecting perimeter"),
            ("DEBUG", "    Reprojecting dnbr"),
            ("DEBUG", "    Reprojecting evt"),
            ("DEBUG", "    Reprojecting retainments"),
            ("DEBUG", "    Reprojecting excluded"),
            ("INFO", "Clipping rasters to the buffered perimeter"),
            ("DEBUG", "    Clipping dem"),
            ("DEBUG", "    Clipping dnbr"),
            ("DEBUG", "    Clipping evt"),
            ("DEBUG", "    Clipping retainments"),
            ("DEBUG", "    Clipping excluded"),
            ("INFO", "Building constant-valued rasters"),
            ("DEBUG", "    Building kf"),
            ("INFO", "Checking dNBR scaling"),
            ("INFO", "Constraining dNBR data range"),
            ("INFO", "Estimating severity from dNBR"),
            ("INFO", "Containing severity data to the perimeter"),
            ("INFO", "Constraining KF-factors to positive values"),
            ("INFO", "Building EVT masks"),
            ("DEBUG", "    Locating water pixels"),
            ("DEBUG", "    Locating developed pixels"),
            ("DEBUG", "    Locating excluded_evt pixels"),
            ("DEBUG", '    Merging excluded_evt mask with "excluded" file'),
            ("INFO", "Saving preprocessed rasters"),
            ("DEBUG", "    Saving perimeter"),
            ("DEBUG", "    Saving dem"),
            ("DEBUG", "    Saving dnbr"),
            ("DEBUG", "    Saving evt"),
            ("DEBUG", "    Saving retainments"),
            ("DEBUG", "    Saving excluded"),
            ("DEBUG", "    Saving kf"),
            ("DEBUG", "    Saving severity"),
            ("DEBUG", "    Saving iswater"),
            ("DEBUG", "    Saving isdeveloped"),
            ("DEBUG", "    Saving configuration.txt"),
        ]
    )
