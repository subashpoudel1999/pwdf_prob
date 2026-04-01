import fiona
import pytest
from fiona.crs import CRS

import wildcat
from wildcat._cli import main
from wildcat._commands.export import _export
from wildcat._utils import _args


def crs():
    return CRS.from_epsg(4326)


def load(path):
    with fiona.open(path) as file:
        crs = file.crs
        schema = file.schema
        records = list(file)
    records = [record.__geo_interface__ for record in records]
    return crs, schema, records


@pytest.fixture
def properties():
    return {
        # Watershed
        "Segment_ID": [1, 2, 3, 4],
        "Area_km2": [0.1, 0.2, 0.3, 0.4],
        "ExtRatio": [0.2, 0.4, 0.6, 0.8],
        "BurnRatio": [0.2, 0.4, 0.6, 0.8],
        "Slope": [0.1, 0.2, 0.3, 0.4],
        "ConfAngle": [110, 120, 130, 140],
        "DevAreaKm2": [0.01, 0.02, 0.03, 0.04],
        # Filters
        "IsIncluded": [False, False, False, False],
        "IsFlood": [False, False, False, False],
        "IsAtRisk": [True, True, True, True],
        "IsInPerim": [True, True, True, True],
        "IsXPerim": [True, True, True, True],
        "IsExterior": [False, False, False, False],
        "IsPhysical": [True, True, True, True],
        "IsBurned": [True, True, True, True],
        "IsSteep": [True, True, True, True],
        "IsConfined": [True, True, True, True],
        "IsUndev": [True, True, True, True],
        "IsFlowSave": [False, False, False, False],
        # Model Inputs
        "Terrain_M1": [10, 11, 12, 13],
        "Fire_M1": [0.1, 0.2, 0.3, 0.4],
        "Soil_M1": [0.1, 0.2, 0.3, 0.4],
        "Bmh_km2": [10.1, 20.2, 30.3, 40.4],
        "Relief_m": [100, 101, 102, 103],
        # Results
        "H_0": [1, 2, 3, 3],
        "H_1": [2, 2, 3, 3],
        "H_2": [3, 3, 3, 3],
        "P_0": [0.2, 0.3, 0.4, 0.5],
        "P_1": [0.4, 0.5, 0.6, 0.7],
        "P_2": [0.6, 0.7, 0.8, 0.9],
        "V_0": [100, 110, 120, 130],
        "V_1": [1000, 1100, 1200, 1300],
        "V_2": [10000, 11000, 12000, 13000],
        "Vmin_0_0": [100, 110, 120, 130],
        "Vmin_0_1": [100, 110, 120, 130],
        "Vmin_1_0": [1000, 1100, 1200, 1300],
        "Vmin_1_1": [1000, 1100, 1200, 1300],
        "Vmin_2_0": [10000, 11000, 12000, 13000],
        "Vmin_2_1": [10000, 11000, 12000, 13000],
        "Vmax_0_0": [100, 110, 120, 130],
        "Vmax_0_1": [100, 110, 120, 130],
        "Vmax_1_0": [1000, 1100, 1200, 1300],
        "Vmax_1_1": [1000, 1100, 1200, 1300],
        "Vmax_2_0": [10000, 11000, 12000, 13000],
        "Vmax_2_1": [10000, 11000, 12000, 13000],
        "I_0_0": [6, 7, 8, 9],
        "I_0_1": [6, 7, 8, 9],
        "I_1_0": [6, 7, 8, 9],
        "I_1_1": [6, 7, 8, 9],
        "I_2_0": [6, 7, 8, 9],
        "I_2_1": [6, 7, 8, 9],
        "R_0_0": [6, 7, 8, 9],
        "R_0_1": [6, 7, 8, 9],
        "R_1_0": [6, 7, 8, 9],
        "R_1_1": [6, 7, 8, 9],
        "R_2_0": [6, 7, 8, 9],
        "R_2_1": [6, 7, 8, 9],
    }


@pytest.fixture
def pschema(properties):
    return {name: type(values[0]).__name__ for name, values in properties.items()}


@pytest.fixture
def segments(assessment, properties, pschema):
    schema = {"geometry": "LineString", "properties": pschema}
    records = []
    for k in range(4):
        props = {name: values[k] for name, values in properties.items()}
        record = {
            "geometry": {
                "type": "LineString",
                "coordinates": [[k, k], [k + 1, k + 1], [k + 2, k + 2]],
            },
            "properties": props,
        }
        records.append(record)

    path = assessment / "segments.geojson"
    with fiona.open(path, "w", crs=crs(), schema=schema) as file:
        file.writerecords(records)
    return path


@pytest.fixture
def basins(assessment, properties, pschema):
    schema = {"geometry": "Polygon", "properties": pschema}
    records = []
    for k in range(4):
        props = {name: values[k] for name, values in properties.items()}
        record = {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[k, k], [k + 1, k], [k + 1, k + 1], [k, k]]],
            },
            "properties": props,
        }
        records.append(record)

    path = assessment / "basins.geojson"
    with fiona.open(path, "w", crs=crs(), schema=schema) as file:
        file.writerecords(records)
    return path


@pytest.fixture
def outlets(assessment):
    schema = {"geometry": "Point", "properties": {}}
    records = []
    for k in range(4):
        record = {
            "geometry": {"type": "Point", "coordinates": [k, k]},
            "properties": {},
        }
        records.append(record)

    path = assessment / "outlets.geojson"
    with fiona.open(path, "w", crs=crs(), schema=schema) as file:
        file.writerecords(records)
    return path


@pytest.fixture
def config(project):
    path = project / "configuration.py"
    with open(path, "w") as file:
        file.write(
            # Output files
            'prefix = "fire-id-"\n'
            'suffix = "-date"\n'
            'format = "geojson"\n'
            # Properties
            'properties = ["default", "isflowsave"]\n'
            'exclude_properties = "DevAreaKm2"\n'
            # Property formatting
            r'rename = {"Segment_ID": "id", "H": "hazard", "durations": ["15min","30min","60min"]}'
            "\n"
        )
    return path


@pytest.fixture
def parameters(assessment):
    path = assessment / "configuration.txt"
    with open(path, "w") as file:
        file.write(
            "I15_mm_hr = [20, 24, 40]\n"
            "volume_CI = [0.9, 0.95]\n"
            "durations = [15, 30, 60]\n"
            "probabilities = [0.5, 0.75]\n"
        )
    return path


@pytest.fixture
def locals(project):
    "Builds the locals dict. Uses include_properties to test use of kwargs"

    args = _args.collect(wildcat.export)
    locals = {arg: None for arg in args}
    locals["project"] = project
    locals["include_properties"] = "IsSteep"
    return locals


class TestExport:
    def test_function(
        _, project, locals, segments, basins, outlets, config, parameters, logcheck
    ):
        assert segments.exists()
        assert basins.exists()
        assert outlets.exists()
        assert config.exists()
        assert parameters.exists()

        logcheck.start("wildcat.export")
        _export.export(locals)

        check_segments(project)
        check_basins(project)
        check_outlets(project)
        check_log(project, logcheck)

    def test_cli(
        _, project, segments, basins, outlets, config, parameters, CleanCLI, logcheck
    ):
        assert segments.exists()
        assert basins.exists()
        assert outlets.exists()
        assert config.exists()
        assert parameters.exists()

        logcheck.start("wildcat.export")
        args = [
            "export",
            f"{project}",
            "--include-properties",
            "IsSteep",
            "--rename",
            "H",
            "hazard",
            "--rename",
            "Segment_ID",
            "id",
            "--rename-parameter",
            "durations",
            "15min",
            "30min",
            "60min",
        ]
        with CleanCLI:
            main(args)

        check_segments(project)
        check_basins(project)
        check_outlets(project)
        check_log(project, logcheck)


def check_segments(project):

    path = project / "exports" / "fire-id-segments-date.json"
    assert path.exists()
    output = load(path)
    assert output[0] == crs()

    assert output[1]["properties"] == {
        "id": "int32",
        "hazard_20mmh": "int32",
        "P_20mmh": "float",
        "V_20mmh": "int32",
        "Vmin_20_90": "int32",
        "Vmax_20_90": "int32",
        "Vmin_20_95": "int32",
        "Vmax_20_95": "int32",
        "hazard_24mmh": "int32",
        "P_24mmh": "float",
        "V_24mmh": "int32",
        "Vmin_24_90": "int32",
        "Vmax_24_90": "int32",
        "Vmin_24_95": "int32",
        "Vmax_24_95": "int32",
        "hazard_40mmh": "int32",
        "P_40mmh": "float",
        "V_40mmh": "int32",
        "Vmin_40_90": "int32",
        "Vmax_40_90": "int32",
        "Vmin_40_95": "int32",
        "Vmax_40_95": "int32",
        "I15min_50": "int32",
        "R15min_50": "int32",
        "I15min_75": "int32",
        "R15min_75": "int32",
        "I30min_50": "int32",
        "R30min_50": "int32",
        "I30min_75": "int32",
        "R30min_75": "int32",
        "I60min_50": "int32",
        "R60min_50": "int32",
        "I60min_75": "int32",
        "R60min_75": "int32",
        "Terrain_M1": "int32",
        "Fire_M1": "float",
        "Soil_M1": "float",
        "Bmh_km2": "float",
        "Relief_m": "int32",
        "Area_km2": "float",
        "ExtRatio": "float",
        "BurnRatio": "float",
        "Slope": "float",
        "ConfAngle": "int32",
        "IsSteep": "bool",
        "IsFlowSave": "bool",
    }
    assert output[1]["geometry"] == "LineString"

    assert output[2] == [
        {
            "geometry": {
                "coordinates": [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
                "type": "LineString",
            },
            "id": "1",
            "properties": {
                "id": 1,
                "hazard_20mmh": 1,
                "P_20mmh": 0.2,
                "V_20mmh": 100,
                "Vmin_20_90": 100,
                "Vmax_20_90": 100,
                "Vmin_20_95": 100,
                "Vmax_20_95": 100,
                "hazard_24mmh": 2,
                "P_24mmh": 0.4,
                "V_24mmh": 1000,
                "Vmin_24_90": 1000,
                "Vmax_24_90": 1000,
                "Vmin_24_95": 1000,
                "Vmax_24_95": 1000,
                "hazard_40mmh": 3,
                "P_40mmh": 0.6,
                "V_40mmh": 10000,
                "Vmin_40_90": 10000,
                "Vmax_40_90": 10000,
                "Vmin_40_95": 10000,
                "Vmax_40_95": 10000,
                "I15min_50": 6,
                "R15min_50": 6,
                "I15min_75": 6,
                "R15min_75": 6,
                "I30min_50": 6,
                "R30min_50": 6,
                "I30min_75": 6,
                "R30min_75": 6,
                "I60min_50": 6,
                "R60min_50": 6,
                "I60min_75": 6,
                "R60min_75": 6,
                "Terrain_M1": 10,
                "Fire_M1": 0.1,
                "Soil_M1": 0.1,
                "Bmh_km2": 10.1,
                "Relief_m": 100,
                "Area_km2": 0.1,
                "ExtRatio": 0.2,
                "BurnRatio": 0.2,
                "Slope": 0.1,
                "ConfAngle": 110,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)],
                "type": "LineString",
            },
            "id": "2",
            "properties": {
                "id": 2,
                "hazard_20mmh": 2,
                "P_20mmh": 0.3,
                "V_20mmh": 110,
                "Vmin_20_90": 110,
                "Vmax_20_90": 110,
                "Vmin_20_95": 110,
                "Vmax_20_95": 110,
                "hazard_24mmh": 2,
                "P_24mmh": 0.5,
                "V_24mmh": 1100,
                "Vmin_24_90": 1100,
                "Vmax_24_90": 1100,
                "Vmin_24_95": 1100,
                "Vmax_24_95": 1100,
                "hazard_40mmh": 3,
                "P_40mmh": 0.7,
                "V_40mmh": 11000,
                "Vmin_40_90": 11000,
                "Vmax_40_90": 11000,
                "Vmin_40_95": 11000,
                "Vmax_40_95": 11000,
                "I15min_50": 7,
                "R15min_50": 7,
                "I15min_75": 7,
                "R15min_75": 7,
                "I30min_50": 7,
                "R30min_50": 7,
                "I30min_75": 7,
                "R30min_75": 7,
                "I60min_50": 7,
                "R60min_50": 7,
                "I60min_75": 7,
                "R60min_75": 7,
                "Terrain_M1": 11,
                "Fire_M1": 0.2,
                "Soil_M1": 0.2,
                "Bmh_km2": 20.2,
                "Relief_m": 101,
                "Area_km2": 0.2,
                "ExtRatio": 0.4,
                "BurnRatio": 0.4,
                "Slope": 0.2,
                "ConfAngle": 120,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(2.0, 2.0), (3.0, 3.0), (4.0, 4.0)],
                "type": "LineString",
            },
            "id": "3",
            "properties": {
                "id": 3,
                "hazard_20mmh": 3,
                "P_20mmh": 0.4,
                "V_20mmh": 120,
                "Vmin_20_90": 120,
                "Vmax_20_90": 120,
                "Vmin_20_95": 120,
                "Vmax_20_95": 120,
                "hazard_24mmh": 3,
                "P_24mmh": 0.6,
                "V_24mmh": 1200,
                "Vmin_24_90": 1200,
                "Vmax_24_90": 1200,
                "Vmin_24_95": 1200,
                "Vmax_24_95": 1200,
                "hazard_40mmh": 3,
                "P_40mmh": 0.8,
                "V_40mmh": 12000,
                "Vmin_40_90": 12000,
                "Vmax_40_90": 12000,
                "Vmin_40_95": 12000,
                "Vmax_40_95": 12000,
                "I15min_50": 8,
                "R15min_50": 8,
                "I15min_75": 8,
                "R15min_75": 8,
                "I30min_50": 8,
                "R30min_50": 8,
                "I30min_75": 8,
                "R30min_75": 8,
                "I60min_50": 8,
                "R60min_50": 8,
                "I60min_75": 8,
                "R60min_75": 8,
                "Terrain_M1": 12,
                "Fire_M1": 0.3,
                "Soil_M1": 0.3,
                "Bmh_km2": 30.3,
                "Relief_m": 102,
                "Area_km2": 0.3,
                "ExtRatio": 0.6,
                "BurnRatio": 0.6,
                "Slope": 0.3,
                "ConfAngle": 130,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(3.0, 3.0), (4.0, 4.0), (5.0, 5.0)],
                "type": "LineString",
            },
            "id": "4",
            "properties": {
                "id": 4,
                "hazard_20mmh": 3,
                "P_20mmh": 0.5,
                "V_20mmh": 130,
                "Vmin_20_90": 130,
                "Vmax_20_90": 130,
                "Vmin_20_95": 130,
                "Vmax_20_95": 130,
                "hazard_24mmh": 3,
                "P_24mmh": 0.7,
                "V_24mmh": 1300,
                "Vmin_24_90": 1300,
                "Vmax_24_90": 1300,
                "Vmin_24_95": 1300,
                "Vmax_24_95": 1300,
                "hazard_40mmh": 3,
                "P_40mmh": 0.9,
                "V_40mmh": 13000,
                "Vmin_40_90": 13000,
                "Vmax_40_90": 13000,
                "Vmin_40_95": 13000,
                "Vmax_40_95": 13000,
                "I15min_50": 9,
                "R15min_50": 9,
                "I15min_75": 9,
                "R15min_75": 9,
                "I30min_50": 9,
                "R30min_50": 9,
                "I30min_75": 9,
                "R30min_75": 9,
                "I60min_50": 9,
                "R60min_50": 9,
                "I60min_75": 9,
                "R60min_75": 9,
                "Terrain_M1": 13,
                "Fire_M1": 0.4,
                "Soil_M1": 0.4,
                "Bmh_km2": 40.4,
                "Relief_m": 103,
                "Area_km2": 0.4,
                "ExtRatio": 0.8,
                "BurnRatio": 0.8,
                "Slope": 0.4,
                "ConfAngle": 140,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
    ]


def check_basins(project):

    path = project / "exports" / "fire-id-basins-date.json"
    assert path.exists()
    output = load(path)
    assert output[0] == crs()

    assert output[1] == {
        "properties": {
            "id": "int32",
            "hazard_20mmh": "int32",
            "P_20mmh": "float",
            "V_20mmh": "int32",
            "Vmin_20_90": "int32",
            "Vmax_20_90": "int32",
            "Vmin_20_95": "int32",
            "Vmax_20_95": "int32",
            "hazard_24mmh": "int32",
            "P_24mmh": "float",
            "V_24mmh": "int32",
            "Vmin_24_90": "int32",
            "Vmax_24_90": "int32",
            "Vmin_24_95": "int32",
            "Vmax_24_95": "int32",
            "hazard_40mmh": "int32",
            "P_40mmh": "float",
            "V_40mmh": "int32",
            "Vmin_40_90": "int32",
            "Vmax_40_90": "int32",
            "Vmin_40_95": "int32",
            "Vmax_40_95": "int32",
            "I15min_50": "int32",
            "R15min_50": "int32",
            "I15min_75": "int32",
            "R15min_75": "int32",
            "I30min_50": "int32",
            "R30min_50": "int32",
            "I30min_75": "int32",
            "R30min_75": "int32",
            "I60min_50": "int32",
            "R60min_50": "int32",
            "I60min_75": "int32",
            "R60min_75": "int32",
            "Terrain_M1": "int32",
            "Fire_M1": "float",
            "Soil_M1": "float",
            "Bmh_km2": "float",
            "Relief_m": "int32",
            "Area_km2": "float",
            "ExtRatio": "float",
            "BurnRatio": "float",
            "Slope": "float",
            "ConfAngle": "int32",
            "IsSteep": "bool",
            "IsFlowSave": "bool",
        },
        "geometry": "Polygon",
    }

    assert output[2] == [
        {
            "geometry": {
                "coordinates": [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]],
                "type": "Polygon",
            },
            "id": "1",
            "properties": {
                "id": 1,
                "hazard_20mmh": 1,
                "P_20mmh": 0.2,
                "V_20mmh": 100,
                "Vmin_20_90": 100,
                "Vmax_20_90": 100,
                "Vmin_20_95": 100,
                "Vmax_20_95": 100,
                "hazard_24mmh": 2,
                "P_24mmh": 0.4,
                "V_24mmh": 1000,
                "Vmin_24_90": 1000,
                "Vmax_24_90": 1000,
                "Vmin_24_95": 1000,
                "Vmax_24_95": 1000,
                "hazard_40mmh": 3,
                "P_40mmh": 0.6,
                "V_40mmh": 10000,
                "Vmin_40_90": 10000,
                "Vmax_40_90": 10000,
                "Vmin_40_95": 10000,
                "Vmax_40_95": 10000,
                "I15min_50": 6,
                "R15min_50": 6,
                "I15min_75": 6,
                "R15min_75": 6,
                "I30min_50": 6,
                "R30min_50": 6,
                "I30min_75": 6,
                "R30min_75": 6,
                "I60min_50": 6,
                "R60min_50": 6,
                "I60min_75": 6,
                "R60min_75": 6,
                "Terrain_M1": 10,
                "Fire_M1": 0.1,
                "Soil_M1": 0.1,
                "Bmh_km2": 10.1,
                "Relief_m": 100,
                "Area_km2": 0.1,
                "ExtRatio": 0.2,
                "BurnRatio": 0.2,
                "Slope": 0.1,
                "ConfAngle": 110,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 1.0)]],
                "type": "Polygon",
            },
            "id": "2",
            "properties": {
                "id": 2,
                "hazard_20mmh": 2,
                "P_20mmh": 0.3,
                "V_20mmh": 110,
                "Vmin_20_90": 110,
                "Vmax_20_90": 110,
                "Vmin_20_95": 110,
                "Vmax_20_95": 110,
                "hazard_24mmh": 2,
                "P_24mmh": 0.5,
                "V_24mmh": 1100,
                "Vmin_24_90": 1100,
                "Vmax_24_90": 1100,
                "Vmin_24_95": 1100,
                "Vmax_24_95": 1100,
                "hazard_40mmh": 3,
                "P_40mmh": 0.7,
                "V_40mmh": 11000,
                "Vmin_40_90": 11000,
                "Vmax_40_90": 11000,
                "Vmin_40_95": 11000,
                "Vmax_40_95": 11000,
                "I15min_50": 7,
                "R15min_50": 7,
                "I15min_75": 7,
                "R15min_75": 7,
                "I30min_50": 7,
                "R30min_50": 7,
                "I30min_75": 7,
                "R30min_75": 7,
                "I60min_50": 7,
                "R60min_50": 7,
                "I60min_75": 7,
                "R60min_75": 7,
                "Terrain_M1": 11,
                "Fire_M1": 0.2,
                "Soil_M1": 0.2,
                "Bmh_km2": 20.2,
                "Relief_m": 101,
                "Area_km2": 0.2,
                "ExtRatio": 0.4,
                "BurnRatio": 0.4,
                "Slope": 0.2,
                "ConfAngle": 120,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 2.0)]],
                "type": "Polygon",
            },
            "id": "3",
            "properties": {
                "id": 3,
                "hazard_20mmh": 3,
                "P_20mmh": 0.4,
                "V_20mmh": 120,
                "Vmin_20_90": 120,
                "Vmax_20_90": 120,
                "Vmin_20_95": 120,
                "Vmax_20_95": 120,
                "hazard_24mmh": 3,
                "P_24mmh": 0.6,
                "V_24mmh": 1200,
                "Vmin_24_90": 1200,
                "Vmax_24_90": 1200,
                "Vmin_24_95": 1200,
                "Vmax_24_95": 1200,
                "hazard_40mmh": 3,
                "P_40mmh": 0.8,
                "V_40mmh": 12000,
                "Vmin_40_90": 12000,
                "Vmax_40_90": 12000,
                "Vmin_40_95": 12000,
                "Vmax_40_95": 12000,
                "I15min_50": 8,
                "R15min_50": 8,
                "I15min_75": 8,
                "R15min_75": 8,
                "I30min_50": 8,
                "R30min_50": 8,
                "I30min_75": 8,
                "R30min_75": 8,
                "I60min_50": 8,
                "R60min_50": 8,
                "I60min_75": 8,
                "R60min_75": 8,
                "Terrain_M1": 12,
                "Fire_M1": 0.3,
                "Soil_M1": 0.3,
                "Bmh_km2": 30.3,
                "Relief_m": 102,
                "Area_km2": 0.3,
                "ExtRatio": 0.6,
                "BurnRatio": 0.6,
                "Slope": 0.3,
                "ConfAngle": 130,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [[(3.0, 3.0), (4.0, 3.0), (4.0, 4.0), (3.0, 3.0)]],
                "type": "Polygon",
            },
            "id": "4",
            "properties": {
                "id": 4,
                "hazard_20mmh": 3,
                "P_20mmh": 0.5,
                "V_20mmh": 130,
                "Vmin_20_90": 130,
                "Vmax_20_90": 130,
                "Vmin_20_95": 130,
                "Vmax_20_95": 130,
                "hazard_24mmh": 3,
                "P_24mmh": 0.7,
                "V_24mmh": 1300,
                "Vmin_24_90": 1300,
                "Vmax_24_90": 1300,
                "Vmin_24_95": 1300,
                "Vmax_24_95": 1300,
                "hazard_40mmh": 3,
                "P_40mmh": 0.9,
                "V_40mmh": 13000,
                "Vmin_40_90": 13000,
                "Vmax_40_90": 13000,
                "Vmin_40_95": 13000,
                "Vmax_40_95": 13000,
                "I15min_50": 9,
                "R15min_50": 9,
                "I15min_75": 9,
                "R15min_75": 9,
                "I30min_50": 9,
                "R30min_50": 9,
                "I30min_75": 9,
                "R30min_75": 9,
                "I60min_50": 9,
                "R60min_50": 9,
                "I60min_75": 9,
                "R60min_75": 9,
                "Terrain_M1": 13,
                "Fire_M1": 0.4,
                "Soil_M1": 0.4,
                "Bmh_km2": 40.4,
                "Relief_m": 103,
                "Area_km2": 0.4,
                "ExtRatio": 0.8,
                "BurnRatio": 0.8,
                "Slope": 0.4,
                "ConfAngle": 140,
                "IsSteep": 1,
                "IsFlowSave": 0,
            },
            "type": "Feature",
        },
    ]


def check_outlets(project):

    path = project / "exports" / "fire-id-outlets-date.json"
    assert path.exists()
    output = load(path)
    assert output[0] == crs()
    assert output[1] == {"properties": {}, "geometry": "Point"}
    assert output[2] == [
        {
            "geometry": {"coordinates": (0.0, 0.0), "type": "Point"},
            "id": "0",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (1.0, 1.0), "type": "Point"},
            "id": "1",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (2.0, 2.0), "type": "Point"},
            "id": "2",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (3.0, 3.0), "type": "Point"},
            "id": "3",
            "properties": {},
            "type": "Feature",
        },
    ]


def check_log(project, logcheck):
    assessment = project / "assessment"
    exports = project / "exports"
    config_path = project / "configuration.py"
    logcheck.check(
        [
            ("INFO", "----- Exporting Results -----"),
            ("INFO", "Parsing configuration"),
            ("DEBUG", "    Locating project folder"),
            ("DEBUG", f"        {project}"),
            ("DEBUG", "    Reading configuration file"),
            ("DEBUG", f"        {config_path}"),
            ("INFO", "Locating IO folders"),
            ("DEBUG", f"    assessment: {assessment}"),
            ("DEBUG", f"    exports: {exports}"),
            ("INFO", "Loading assessment parameters"),
            ("INFO", "Parsing exported properties"),
            ("DEBUG", "    Unpacking property groups"),
            ("DEBUG", "    Parsing result vectors"),
            ("DEBUG", "    Removing duplicate properties"),
            ("DEBUG", "    Removing excluded properties"),
            ("DEBUG", "    Adding included properties"),
            ("DEBUG", "    Reordering properties"),
            ("INFO", "Parsing property names"),
            ("DEBUG", "    Cleaning result names"),
            ("DEBUG", "    Applying user-provided names"),
            ("INFO", "Loading assessment results"),
            ("DEBUG", "    Loading segments"),
            ("DEBUG", "    Loading basins"),
            ("DEBUG", "    Loading outlets"),
            ("INFO", "Exporting results to GeoJSON"),
            ("DEBUG", "    Exporting segments"),
            ("DEBUG", "    Exporting basins"),
            ("DEBUG", "    Exporting outlets"),
            ("DEBUG", "    Saving configuration.txt"),
        ]
    )
