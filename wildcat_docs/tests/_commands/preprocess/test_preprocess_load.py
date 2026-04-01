import warnings
from math import nan
from pathlib import Path

import fiona
import numpy as np
import pytest
from pfdf.errors import NoOverlapError, NoOverlappingFeaturesError
from pfdf.projection import CRS, BoundingBox
from pfdf.raster import Raster
from rasterio.errors import NotGeoreferencedWarning

from wildcat._commands.preprocess import _load
from wildcat.errors import GeoreferencingError

#####
# Testing fixtures
#####


@pytest.fixture
def dem_no_georef():
    dem = np.ones((10, 10))
    return Raster.from_array(dem, nodata=-999)


@pytest.fixture
def dem(dem_no_georef):
    "DEM raster"
    dem = dem_no_georef
    dem.crs = 26911
    dem.bounds = (0, 0, 100, 100)
    return dem


@pytest.fixture
def pdem(tmp_path, dem):
    "Path to a DEM file"
    path = Path(tmp_path) / "dem.tif"
    dem.save(path)
    return path


@pytest.fixture
def perimeter():
    "Perimeter raster"
    perimeter = np.ones((5, 3), bool)
    perimeter = Raster.from_array(perimeter, isbool=True)
    perimeter.crs = 26911
    perimeter.bounds = (20, 30, 50, 80)
    return perimeter


@pytest.fixture
def rperimeter(tmp_path, perimeter):
    "Path to a perimeter raster file"
    path = Path(tmp_path) / "perimeter.tif"
    perimeter.save(path)
    return path


@pytest.fixture
def fperimeter(tmp_path):
    "Path to a perimeter feature file"

    schema = {"geometry": "Polygon", "properties": {}}
    geometry = {
        "type": "Polygon",
        "coordinates": [[[20, 30], [20, 80], [50, 80], [50, 30], [20, 30]]],
    }
    record = {"geometry": geometry, "properties": {}}
    path = Path(tmp_path) / "perimeter.geojson"
    with fiona.open(path, "w", crs=CRS(26911), schema=schema) as file:
        file.write(record)
    return path


@pytest.fixture
def config():
    return {"buffer_km": 0.01, "kf_field": "KFFACT", "severity_field": None}


@pytest.fixture
def points(tmp_path, perimeter):
    crs = CRS(26911)
    schema = {"geometry": "Point", "properties": {}}
    records = [
        {"geometry": {"type": "Point", "coordinates": [0, 100]}, "properties": {}},
        {"geometry": {"type": "Point", "coordinates": [20, 80]}, "properties": {}},
        {"geometry": {"type": "Point", "coordinates": [33, 52]}, "properties": {}},
    ]

    path = Path(tmp_path) / "points.geojson"
    with fiona.open(path, "w", schema=schema, crs=crs) as file:
        file.writerecords(records)

    expected = np.array(
        [
            [1, 0, 0],
            [0, 0, 0],
            [0, 1, 0],
            [0, 0, 0],
            [0, 0, 0],
        ],
        dtype=bool,
    )
    expected = Raster.from_array(expected, crs=crs, bounds=perimeter)

    return {"path": path, "expected": expected}


@pytest.fixture
def polygons(tmp_path, perimeter):
    crs = CRS(26911)
    schema = {"geometry": "Polygon", "properties": {"KFFACT": "float"}}
    record0 = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[10, 100], [39, 100], [39, 61], [10, 61], [10, 100]]],
        },
        "properties": {"KFFACT": 2.2},
    }
    record1 = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[31, 59], [70, 59], [70, 10], [31, 10], [31, 59]],
                [[41, 49], [60, 49], [60, 20], [41, 20], [41, 49]],
            ],
        },
        "properties": {"KFFACT": 3.3},
    }
    records = [record0, record1]

    path = Path(tmp_path) / "polygons.shp"
    with fiona.open(path, "w", schema=schema, crs=crs) as file:
        file.writerecords(records)

    mask = np.array(
        [
            [1, 1, 0],
            [1, 1, 0],
            [0, 1, 1],
            [0, 1, 0],
            [0, 1, 0],
        ],
        dtype=bool,
    )
    mask = Raster.from_array(mask, crs=crs, bounds=perimeter)

    field = np.array(
        [
            [2.2, 2.2, nan],
            [2.2, 2.2, nan],
            [nan, 3.3, 3.3],
            [nan, 3.3, nan],
            [nan, 3.3, nan],
        ]
    )
    field = Raster.from_array(field, crs=crs, bounds=perimeter)
    return {"path": path, "mask": mask, "field": field}


@pytest.fixture
def paths(fperimeter, pdem, points, polygons):
    return {
        "perimeter": fperimeter,
        "dem": pdem,
        "retainments": points["path"],
        "kf": polygons["path"],
        "excluded": polygons["path"],
        "dnbr": pdem,
    }


#####
# Special Datasets
#####


class TestBufferedPerimeter:
    def test_raster(_, config, rperimeter, logcheck):
        paths = {"perimeter": rperimeter}
        perimeter = _load.buffered_perimeter(config, paths, logcheck.log)
        assert isinstance(perimeter, Raster)
        assert perimeter.dtype == bool
        assert perimeter.bounds == BoundingBox(10, 20, 60, 90, 26911)
        logcheck.check(
            [
                ("INFO", "Building buffered burn perimeter"),
                ("DEBUG", "    Loading perimeter mask"),
                ("DEBUG", "    Buffering perimeter"),
            ]
        )

    def test_polygons(_, config, fperimeter, logcheck):
        paths = {"perimeter": fperimeter}
        perimeter = _load.buffered_perimeter(config, paths, logcheck.log)
        assert isinstance(perimeter, Raster)
        assert perimeter.dtype == bool
        assert perimeter.bounds == BoundingBox(10, 20, 60, 90, 26911)
        assert perimeter.resolution(units="meters") == (10, 10)
        logcheck.check(
            [
                ("INFO", "Building buffered burn perimeter"),
                ("DEBUG", "    Loading perimeter mask"),
                ("DEBUG", "    Buffering perimeter"),
            ]
        )


class TestDEM:
    def test_valid(_, pdem, perimeter, logcheck):
        paths = {"dem": pdem}
        dem = _load.dem(paths, perimeter, logcheck.log)
        assert isinstance(dem, Raster)
        assert dem.bounds == perimeter.bounds
        assert dem.crs is not None
        assert dem.transform is not None
        logcheck.check([("INFO", "Loading DEM")])

    def test_no_transform(_, tmp_path, dem_no_georef, perimeter, errcheck, logcheck):
        dem = dem_no_georef
        dem.crs = 26911
        path = Path(tmp_path) / "dem.tif"
        with warnings.catch_warnings(action="ignore", category=NotGeoreferencedWarning):
            dem.save(path)

        paths = {"dem": path}
        with pytest.raises(GeoreferencingError) as error:
            _load.dem(paths, perimeter, logcheck.log)
        errcheck(
            error,
            "The input DEM does not have an affine transform.",
            "Please provide a properly georeferenced DEM",
        )


class TestConstants:
    def test_none(_, config, logcheck):
        for name in ["kf", "dnbr", "severity"]:
            config[name] = Path("test")
        rasters = {}
        _load.constants(config, rasters, logcheck.log)
        assert rasters == {}
        logcheck.check([])

    def test_standard(_, config, dem, logcheck):
        config["kf"] = 5
        config["dnbr"] = Path("test")
        config["severity"] = 2.2
        rasters = {"dem": dem}
        _load.constants(config, rasters, logcheck.log)

        kf = np.full((10, 10), 5)
        nodata = np.iinfo(kf.dtype).min
        expected_kf = Raster.from_array(kf, nodata=nodata, spatial=dem)

        severity = np.full((10, 10), 2.2)
        expected_severity = Raster.from_array(severity, nodata=nan, spatial=dem)

        assert rasters == {
            "dem": dem,
            "severity": expected_severity,
            "kf": expected_kf,
        }
        logcheck.check(
            [
                ("INFO", "Building constant-valued rasters"),
                ("DEBUG", "    Building severity"),
                ("DEBUG", "    Building kf"),
            ]
        )

    def test_0_nodata(_, config, dem, logcheck):
        for name in ["kf", "dnbr", "severity"]:
            config[name] = Path("test")

        dtype = np.array(0).dtype
        kf = np.iinfo(dtype).min
        config["kf"] = kf

        rasters = {"dem": dem}
        _load.constants(config, rasters, logcheck.log)

        kf = np.full((10, 10), kf)
        expected_kf = Raster.from_array(kf, nodata=0, spatial=dem)

        assert rasters == {
            "dem": dem,
            "kf": expected_kf,
        }
        logcheck.check(
            [("INFO", "Building constant-valued rasters"), ("DEBUG", "    Building kf")]
        )


#####
# General Loading
#####


class TestDatasets:
    def test(_, config, paths, points, polygons, perimeter, dem, logcheck):
        output = _load.datasets(config, paths, perimeter, dem, logcheck.log)
        assert isinstance(output, dict)
        assert list(output.keys()) == [
            "perimeter",
            "dem",
            "retainments",
            "kf",
            "excluded",
            "dnbr",
        ]

        dnbr = dem.copy()
        dnbr.clip(bounds=perimeter)

        assert output["perimeter"] == perimeter
        assert output["dem"] == dem
        assert output["retainments"] == points["expected"]
        assert output["kf"] == polygons["field"]
        assert output["excluded"] == polygons["mask"]
        assert output["dnbr"] == dnbr

        logcheck.check(
            [
                ("INFO", "Loading file-based datasets"),
                ("DEBUG", "    Loading retainments"),
                ("DEBUG", "    Loading kf"),
                ("DEBUG", "    Loading excluded"),
                ("DEBUG", "    Loading dnbr"),
            ]
        )

    def test_missing_field(
        _, config, paths, polygons, perimeter, dem, errcheck, logcheck
    ):
        paths["severity"] = polygons["path"]
        with pytest.raises(ValueError) as error:
            _load.datasets(config, paths, perimeter, dem, logcheck.log)
        errcheck(
            error, "severity is a vector feature file, so severity_field cannot be None"
        )

    def test_no_datasets(_, config, paths, perimeter, dem, logcheck):
        paths = {paths[name] for name in ["perimeter", "dem"]}
        output = _load.datasets(config, paths, perimeter, dem, logcheck.log)
        assert output == {"perimeter": perimeter, "dem": dem}
        logcheck.check([])


class TestLoadFeatures:
    def test_retainments(_, paths, perimeter, dem, config, points):
        output = _load._load_features(
            "retainments", paths["retainments"], perimeter, dem, config
        )
        assert output == points["expected"]
        assert output.name == "retainments"

    def test_kf(_, paths, perimeter, dem, config, polygons):
        output = _load._load_features("kf", paths["kf"], perimeter, dem, config)
        assert output == polygons["field"]
        assert output.name == "kf"

    def test_kf_missing_field(_, paths, perimeter, dem, config, polygons, errcheck):
        paths["severity"] = polygons["path"]
        with pytest.raises(ValueError) as error:
            _load._load_features("severity", paths["severity"], perimeter, dem, config)
        errcheck(
            error, "severity is a vector feature file, so severity_field cannot be None"
        )

    def test_mask(_, paths, perimeter, dem, config, polygons):
        output = _load._load_features(
            "excluded", paths["excluded"], perimeter, dem, config
        )
        assert output == polygons["mask"]
        assert output.name == "excluded"


class TestRasterize:
    def test_valid(_, paths, perimeter, dem, config, polygons):
        kwargs = {
            "path": paths["kf"],
            "bounds": perimeter,
            "resolution": dem,
            "field": config["kf_field"],
        }
        output = _load._rasterize("", Raster.from_polygons, kwargs)
        assert output == polygons["field"]

    def test_no_overlap(_, paths, perimeter, dem, errcheck):
        perimeter = BoundingBox(120, 55, 121, 56, 4326)
        kwargs = {"path": paths["retainments"], "bounds": perimeter, "resolution": dem}
        with pytest.raises(NoOverlappingFeaturesError) as error:
            _load._rasterize("test", Raster.from_points, kwargs)
        errcheck(error, "The test dataset does not overlap the buffered fire perimeter")


class TestLoadRaster:
    def test_valid(_, paths, perimeter, dem):
        output = _load._load_raster("dnbr", paths["dnbr"], perimeter)
        expected = dem.copy()
        expected.clip(bounds=perimeter)
        assert output == expected

    def test_no_overlap(_, paths, errcheck):
        perimeter = BoundingBox(120, 55, 121, 56, 4326)
        with pytest.raises(NoOverlapError) as error:
            _load._load_raster("test", paths["dnbr"], perimeter)
        errcheck(error, "The test dataset does not overlap the buffered fire perimeter")
