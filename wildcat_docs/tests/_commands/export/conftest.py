import fiona
import pytest
from fiona.crs import CRS as fCRS
from pyproj import CRS


@pytest.fixture
def assessment(project):
    path = project / "assessment"
    path.mkdir()
    return path


@pytest.fixture
def exports(project):
    path = project / "exports"
    path.mkdir()
    return path


@pytest.fixture
def config_path(assessment):
    return assessment / "configuration.txt"


@pytest.fixture
def parameters():
    return {
        "I15_mm_hr": [20, 24, 40],
        "volume_CI": [0.9, 0.95],
        "durations": [15, 30, 60],
        "probabilities": [0.5, 0.75],
    }


@pytest.fixture
def config():
    return {
        # Output files
        "prefix": "",
        "suffix": "",
        "format": "GeoJSON",
        "export_crs": CRS(4326),
        # Properties
        "properties": [],
        "include_properties": [],
        "exclude_properties": [],
        # Property formatting
        "order_properties": True,
        "clean_names": True,
        "rename": {},
    }


@pytest.fixture
def outlets():
    return [
        {
            "geometry": {"coordinates": (1.0, 1.0), "type": "Point"},
            "id": "0",
            "properties": {"Segment_ID": 1, "Area_km2": 1.1, "ConfAngle": 1.11},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (2.0, 2.0), "type": "Point"},
            "id": "1",
            "properties": {"Segment_ID": 2, "Area_km2": 2.2, "ConfAngle": 2.22},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (3.0, 3.0), "type": "Point"},
            "id": "2",
            "properties": {"Segment_ID": 3, "Area_km2": 3.3, "ConfAngle": 3.33},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (4.0, 4.0), "type": "Point"},
            "id": "3",
            "properties": {"Segment_ID": 4, "Area_km2": 4.4, "ConfAngle": 4.44},
            "type": "Feature",
        },
    ]


@pytest.fixture
def segments():
    return [
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "0",
            "properties": {"Segment_ID": 1, "Area_km2": 1.1, "ConfAngle": 1.11},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "1",
            "properties": {"Segment_ID": 2, "Area_km2": 2.2, "ConfAngle": 2.22},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "2",
            "properties": {"Segment_ID": 3, "Area_km2": 3.3, "ConfAngle": 3.33},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "3",
            "properties": {"Segment_ID": 4, "Area_km2": 4.4, "ConfAngle": 4.44},
            "type": "Feature",
        },
    ]


@pytest.fixture
def basins():
    return [
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "0",
            "properties": {"Segment_ID": 1, "Area_km2": 1.1, "ConfAngle": 1.11},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "1",
            "properties": {"Segment_ID": 2, "Area_km2": 2.2, "ConfAngle": 2.22},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "2",
            "properties": {"Segment_ID": 3, "Area_km2": 3.3, "ConfAngle": 3.33},
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "3",
            "properties": {"Segment_ID": 4, "Area_km2": 4.4, "ConfAngle": 4.44},
            "type": "Feature",
        },
    ]


def save(assessment, records):
    crs = fCRS.from_epsg(4326)
    features = {
        "Point": "outlets",
        "LineString": "segments",
        "Polygon": "basins",
    }
    geometry = records[0]["geometry"]["type"]

    path = assessment / f"{features[geometry]}.geojson"
    schema = {
        "geometry": geometry,
        "properties": {"Segment_ID": "int", "Area_km2": "float", "ConfAngle": "float"},
    }
    with fiona.open(path, "w", crs=crs, schema=schema) as file:
        file.writerecords(records)
    return path


@pytest.fixture
def foutlets(assessment, outlets):
    return save(assessment, outlets)


@pytest.fixture
def fsegments(assessment, segments):
    return save(assessment, segments)


@pytest.fixture
def fbasins(assessment, basins):
    return save(assessment, basins)
