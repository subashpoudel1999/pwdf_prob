import fiona
import pytest
from fiona.crs import CRS

from wildcat import version
from wildcat._commands.export import _save


@pytest.fixture
def expected_segments():
    return [
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "1",
            "properties": {"id": 1, "area": 1.1},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "2",
            "properties": {"id": 2, "area": 2.2},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "3",
            "properties": {"id": 3, "area": 3.3},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "4",
            "properties": {"id": 4, "area": 4.4},
            "type": "Feature",
        },
    ]


@pytest.fixture
def expected_basins():
    return [
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "1",
            "properties": {"id": 1, "area": 1.1},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "2",
            "properties": {"id": 2, "area": 2.2},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "3",
            "properties": {"id": 3, "area": 3.3},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "4",
            "properties": {"id": 4, "area": 4.4},
            "type": "Feature",
        },
    ]


@pytest.fixture
def expected_outlets():
    return [
        {
            "geometry": {"coordinates": (1.0, 1.0), "type": "Point"},
            "id": "0",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (2.0, 2.0), "type": "Point"},
            "id": "1",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (3.0, 3.0), "type": "Point"},
            "id": "2",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (4.0, 4.0), "type": "Point"},
            "id": "3",
            "properties": {},
            "type": "Feature",
        },
    ]


def crs():
    return CRS.from_epsg(4326)


def load(path):
    with fiona.open(path) as file:
        crs = file.crs
        schema = file.schema
        records = list(file)
    records = [record.__geo_interface__ for record in records]
    return crs, schema, records


class TestPropertySchema:
    def test(_):
        schema = {
            "properties": {
                "some": "float",
                "exported": "int",
                "fields": "int",
                "and": "int",
                "others": "float",
                "not": "int",
            }
        }
        names = {
            "some": "hazard",
            "exported": "likelihood",
            "fields": "volume",
        }
        output = _save._property_schema(names, schema)
        assert output == {
            "hazard": "float",
            "likelihood": "int",
            "volume": "int",
        }


class TestFeatures:
    def test_none(_, exports, config, logcheck):
        _save._features(None, exports, config, crs(), logcheck.log)
        logcheck.check([])

    def test_segments(_, segments, expected_segments, exports, config, logcheck):
        names = {"Segment_ID": "id", "Area_km2": "area"}
        pschema = {"id": "int", "area": "float"}
        _save._features(segments, exports, config, crs(), logcheck.log, names, pschema)

        path = exports / "segments.json"
        assert path.exists()

        output = load(path)
        assert output[0] == crs()
        assert output[1] == {
            "geometry": "LineString",
            "properties": {"area": "float", "id": "int32"},
        }
        assert output[2] == expected_segments

    def test_basins(_, basins, expected_basins, exports, config, logcheck):
        names = {"Segment_ID": "id", "Area_km2": "area"}
        pschema = {"id": "int", "area": "float"}
        _save._features(basins, exports, config, crs(), logcheck.log, names, pschema)

        path = exports / "basins.json"
        assert path.exists()

        output = load(path)
        assert output[0] == crs()
        assert output[1] == {
            "geometry": "Polygon",
            "properties": {"area": "float", "id": "int32"},
        }
        assert output[2] == expected_basins

    def test_outlets(_, outlets, expected_outlets, exports, config, logcheck):
        _save._features(outlets, exports, config, crs(), logcheck.log)

        path = exports / "outlets.json"
        assert path.exists()

        output = load(path)
        assert output[0] == crs()
        assert output[1] == {"geometry": "Point", "properties": {}}
        assert output[2] == expected_outlets

    def test_filename(_, segments, exports, config, logcheck):
        config["prefix"] = "fire-id-"
        config["suffix"] = "-date"
        _save._features(segments, exports, config, crs(), logcheck.log)

        path = exports / "fire-id-segments-date.json"
        assert path.exists()


class TestResults:
    def test(
        _,
        segments,
        basins,
        outlets,
        expected_segments,
        expected_basins,
        expected_outlets,
        exports,
        config,
        logcheck,
    ):
        schema = {
            "geometry": "LineString",
            "properties": {
                "Segment_ID": "int",
                "Area_km2": "float",
                "ConfAngle": "float",
            },
        }
        results = (crs(), schema, segments, basins, outlets)
        names = {"Segment_ID": "id", "Area_km2": "area"}
        _save.results(exports, config, results, names, logcheck.log)

        path = exports / "segments.json"
        assert path.exists()
        output = load(path)
        assert output[0] == crs()
        assert output[1] == {
            "geometry": "LineString",
            "properties": {"area": "float", "id": "int32"},
        }
        assert output[2] == expected_segments

        path = exports / "basins.json"
        assert path.exists()
        output = load(path)
        assert output[0] == crs()
        assert output[1] == {
            "geometry": "Polygon",
            "properties": {"area": "float", "id": "int32"},
        }
        assert output[2] == expected_basins

        path = exports / "outlets.json"
        assert path.exists()
        output = load(path)
        assert output[0] == crs()
        assert output[1] == {"geometry": "Point", "properties": {}}
        assert output[2] == expected_outlets

        logcheck.check(
            [
                ("INFO", "Exporting results to GeoJSON"),
                ("DEBUG", "    Exporting segments"),
                ("DEBUG", "    Exporting basins"),
                ("DEBUG", "    Exporting outlets"),
            ]
        )


class TestConfig:
    def test(_, exports, config, logcheck):
        config["prefix"] = "fire-id-"
        config["suffix"] = "-date"
        config["rename"] = {"Segment_ID": "id", "Area_km2": "area"}
        config["properties"] = ["default"]
        _save.config(exports, config, logcheck.log)

        path = exports / "configuration.txt"
        assert path.exists()
        with open(path) as file:
            output = file.read()
        assert output == (
            f"# Export configuration for wildcat v{version()}\n"
            "\n"
            "# Output files\n"
            'format = "GeoJSON"\n'
            'export_crs = "WGS 84"\n'
            'prefix = "fire-id-"\n'
            'suffix = "-date"\n'
            "\n"
            "# Properties\n"
            "properties = ['default']\n"
            "order_properties = True\n"
            "\n"
            "# Property names\n"
            "clean_names = True\n"
            r"rename = {'Segment_ID': 'id', 'Area_km2': 'area'}"
            "\n"
            "\n"
        )
