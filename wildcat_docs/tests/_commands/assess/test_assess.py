import os
from pathlib import Path

import fiona
import numpy as np
import pytest
from pfdf import watershed

import wildcat
from wildcat import version
from wildcat._cli import main
from wildcat._commands.assess import _assess
from wildcat._utils import _args


@pytest.fixture
def project(tmp_path):
    project = Path(tmp_path) / "project"
    project.mkdir()
    return project


@pytest.fixture
def preprocessed(project):
    folder = project / "preprocessed"
    folder.mkdir()
    return folder


@pytest.fixture
def locals(project):
    "Builds the locals dict. Uses min_area_km2 to test use of kwargs"

    args = _args.collect(wildcat.assess)
    locals = {arg: None for arg in args}
    locals["project"] = project
    locals["min_area_km2"] = 0.0
    return locals


@pytest.fixture
def config(project):
    path = project / "configuration.py"
    with open(path, "w") as file:
        file.write(
            # Delineate
            "min_burned_area_km2 = 0\n"
            "min_slope = 0\n"
            "max_confinement = 180\n"
            "confinement_neighborhood = 1\n"
            "I15_mm_hr = [16,20,24]\n"
            "volume_CI = [0.9, 0.95]\n"
        )
    return path


@pytest.fixture
def paths(preprocessed, trues, dem, dnbr, severity, kf, excluded):
    "Creates data files for the integration test"

    paths = {
        "perimeter": trues,
        "dem": dem,
        "dnbr": dnbr,
        "severity": severity,
        "kf": kf,
        "excluded": excluded,
    }
    for name, raster in paths.items():
        path = preprocessed / f"{name}.tif"
        paths[name] = path
        raster.save(path)

    project = preprocessed.parent
    paths["project"] = project
    paths["preprocessed"] = preprocessed
    paths["assessment"] = project / "assessment"
    return paths


def prop_keys(record) -> list[str]:
    return list(sorted(record["properties"].keys()))


def check_records(output, expected):

    assert len(output) == len(expected)
    for output, expected in zip(output, expected):
        assert output["geometry"] == expected["geometry"]
        assert prop_keys(output) == prop_keys(expected)
        for field in output["properties"]:
            assert np.allclose(
                output["properties"][field], expected["properties"][field]
            )


class TestAssess:
    def test_function(_, project, flow, paths, locals, config, logcheck):

        assert config.exists()
        # Monkey patch pfdf.watershed to return the flow directions from
        # the testing fixtures
        try:

            def flow_patch(*args, **kwargs):
                return flow

            original = watershed.flow
            watershed.flow = flow_patch

            # The configuration file from config tests the use of config values,
            # while min_area_km2 tests the use of kwargs. Everything else tests defaults
            logcheck.start("wildcat.assess")
            _assess.assess(locals)

        finally:
            watershed.flow = original

        # Check the files exists
        assessment = project / "assessment"
        assert assessment.exists()
        contents = os.listdir(assessment)
        assert sorted(contents) == sorted(
            [
                "configuration.txt",
                "segments.geojson",
                "basins.geojson",
                "outlets.geojson",
            ]
        )

        # Check file contents
        check_segments(assessment)
        check_basins(assessment)
        check_outlets(assessment)
        check_config(assessment, paths)
        check_log(logcheck, paths)

    def test_cli(_, project, flow, paths, config, CleanCLI, logcheck):
        assert config.exists()
        args = ["assess", "--min-area-km2", "0", f"{project}"]

        # Monkey patch pfdf.watershed to return the flow directions from
        # the testing fixtures
        try:

            def flow_patch(*args, **kwargs):
                return flow

            original = watershed.flow
            watershed.flow = flow_patch

            # The configuration file from config tests the use of config values,
            # while min_area_km2 tests the use of kwargs. Everything else tests defaults
            logcheck.start("wildcat.assess")
            with CleanCLI:
                main(args)

        finally:
            watershed.flow = original

        # Check the files exists
        assessment = project / "assessment"
        assert assessment.exists()
        contents = os.listdir(assessment)
        assert sorted(contents) == sorted(
            [
                "configuration.txt",
                "segments.geojson",
                "basins.geojson",
                "outlets.geojson",
            ]
        )

        # Check file contents
        check_segments(assessment)
        check_basins(assessment)
        check_outlets(assessment)
        check_config(assessment, paths)
        check_log(logcheck, paths)


def read(folder, name):
    with fiona.open(folder / f"{name}.geojson") as file:
        records = list(file)
    return [record.__geo_interface__ for record in records]


def check_segments(folder):
    output = read(folder, "segments")
    expected = [
        {
            "geometry": {
                "coordinates": [
                    (15.0, -15.0),
                    (15.0, -25.0),
                    (15.0, -35.0),
                    (15.0, -45.0),
                    (25.0, -45.0),
                    (35.0, -45.0),
                    (35.0, -55.0),
                    (45.0, -55.0),
                    (55.0, -55.0),
                ],
                "type": "LineString",
            },
            "id": "0",
            "properties": {
                "Segment_ID": 1,
                "Area_km2": 0.0016,
                "ExtRatio": 0.0,
                "BurnRatio": 0.25,
                "Slope": -0.65,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.2125,
                "Soil_M1": 0.2,
                "Bmh_km2": 0.0004,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.07582313559560436,
                "V_0": 19.362601272892466,
                "Vmin_0_0": 3.499764442411047,
                "Vmax_0_0": 107.12444629408678,
                "Vmin_0_1": 2.521820073388719,
                "Vmax_0_1": 148.6665650770349,
                "H_1": 1.0,
                "P_1": 0.09813462471646754,
                "V_1": 23.277249297112288,
                "Vmin_1_0": 4.207331869257748,
                "Vmax_1_0": 128.78240929815294,
                "Vmin_1_1": 3.031670884681819,
                "Vmax_1_1": 178.72333622281724,
                "H_2": 1.0,
                "P_2": 0.12611550685037318,
                "V_2": 27.493385142424835,
                "Vmin_2_0": 4.969392819015418,
                "Vmax_2_0": 152.10836698143527,
                "Vmin_2_1": 3.580788012953634,
                "Vmax_2_1": 211.09493883895394,
                "I_0_0": 51.420982735723776,
                "R_0_0": 12.855245683930944,
                "I_0_1": 66.98344100813613,
                "R_0_1": 16.74586025203403,
                "I_1_0": 39.480519480519476,
                "R_1_0": 19.740259740259738,
                "I_1_1": 51.495418057887726,
                "R_1_1": 25.747709028943863,
                "I_2_0": 37.10982658959537,
                "R_2_0": 37.10982658959537,
                "I_2_1": 49.81054668980474,
                "R_2_1": 49.81054668980474,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [
                    (55.0, -15.0),
                    (55.0, -25.0),
                    (55.0, -35.0),
                    (55.0, -45.0),
                    (55.0, -55.0),
                ],
                "type": "LineString",
            },
            "id": "1",
            "properties": {
                "Segment_ID": 2,
                "Area_km2": 0.0011,
                "ExtRatio": 0.0,
                "BurnRatio": 0.36363636363636365,
                "Slope": -1.2,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.39972727272727276,
                "Soil_M1": 0.2,
                "Bmh_km2": 0.0004,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.11933623283357085,
                "V_0": 19.362601272892466,
                "Vmin_0_0": 3.499764442411047,
                "Vmax_0_0": 107.12444629408678,
                "Vmin_0_1": 2.521820073388719,
                "Vmax_0_1": 148.6665650770349,
                "H_1": 1.0,
                "P_1": 0.16925539352510965,
                "V_1": 23.277249297112288,
                "Vmin_1_0": 4.207331869257748,
                "Vmax_1_0": 128.78240929815294,
                "Vmin_1_1": 3.031670884681819,
                "Vmax_1_1": 178.72333622281724,
                "H_2": 1.0,
                "P_2": 0.23449591861467728,
                "V_2": 27.493385142424835,
                "Vmin_2_0": 4.969392819015418,
                "Vmax_2_0": 152.10836698143527,
                "Vmin_2_1": 3.580788012953634,
                "Vmax_2_1": 211.09493883895394,
                "I_0_0": 35.604181016899275,
                "R_0_0": 8.901045254224819,
                "I_0_1": 46.37971567065393,
                "R_0_1": 11.594928917663482,
                "I_1_0": 28.21484778832114,
                "R_1_0": 14.10742389416057,
                "I_1_1": 36.801323827974834,
                "R_1_1": 18.400661913987417,
                "I_2_0": 25.898489071439048,
                "R_2_0": 25.898489071439048,
                "I_2_1": 34.7621645704483,
                "R_2_1": 34.7621645704483,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [
                    (55.0, -55.0),
                    (55.0, -65.0),
                    (55.0, -75.0),
                    (65.0, -75.0),
                    (65.0, -85.0),
                    (75.0, -85.0),
                    (75.0, -95.0),
                    (85.0, -95.0),
                ],
                "type": "LineString",
            },
            "id": "2",
            "properties": {
                "Segment_ID": 3,
                "Area_km2": 0.0041,
                "ExtRatio": 0.0,
                "BurnRatio": 0.4634146341463415,
                "Slope": -0.7285714285714285,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.3340487804878049,
                "Soil_M1": 0.5103448275862067,
                "Bmh_km2": 0.0019,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.2131932303915556,
                "V_0": 33.929182968391736,
                "Vmin_0_0": 6.1326547212990965,
                "Vmax_0_0": 187.71470255849397,
                "Vmin_0_1": 4.418997916522562,
                "Vmax_0_1": 260.5091648942228,
                "H_1": 1.0,
                "P_1": 0.32635232471984527,
                "V_1": 40.78884026333154,
                "Vmin_1_0": 7.372528659186037,
                "Vmax_1_0": 225.66605935869765,
                "Vmin_1_1": 5.312412040954531,
                "Vmax_1_1": 313.1777951712942,
                "H_2": 2.0,
                "P_2": 0.46414275463175014,
                "V_2": 48.176796173753225,
                "Vmin_2_0": 8.707891869582399,
                "Vmax_2_0": 266.54025157051825,
                "Vmin_2_1": 6.274632728848139,
                "Vmax_2_1": 369.9027162014371,
                "I_0_0": 24.98906890710841,
                "R_0_0": 6.247267226777103,
                "I_0_1": 32.551960968740225,
                "R_0_1": 8.137990242185056,
                "I_1_0": 18.7312830742784,
                "R_1_0": 9.3656415371392,
                "I_1_1": 24.431675807775136,
                "R_1_1": 12.215837903887568,
                "I_2_0": 17.92438741236672,
                "R_2_0": 17.92438741236672,
                "I_2_1": 24.058951984975465,
                "R_2_1": 24.058951984975465,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [
                    (105.0, -15.0),
                    (95.0, -15.0),
                    (85.0, -15.0),
                    (85.0, -25.0),
                    (85.0, -35.0),
                    (95.0, -35.0),
                    (105.0, -35.0),
                    (105.0, -45.0),
                    (105.0, -55.0),
                    (95.0, -55.0),
                    (85.0, -55.0),
                    (85.0, -65.0),
                    (85.0, -75.0),
                    (95.0, -75.0),
                    (105.0, -75.0),
                    (95.0, -85.0),
                    (85.0, -95.0),
                ],
                "type": "LineString",
            },
            "id": "3",
            "properties": {
                "Segment_ID": 4,
                "Area_km2": 0.0027,
                "ExtRatio": 0.0,
                "BurnRatio": 0.3333333333333333,
                "Slope": -0.5472271824131503,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.310962962962963,
                "Soil_M1": 0.5333333333333331,
                "Bmh_km2": 0.0009,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.2136125204247807,
                "V_0": 25.926829327716263,
                "Vmin_0_0": 4.686239937845215,
                "Vmax_0_0": 143.44132778178084,
                "Vmin_0_1": 3.3767569613435033,
                "Vmax_0_1": 199.06688182885424,
                "H_1": 1.0,
                "P_1": 0.32703911911800804,
                "V_1": 31.168604943068143,
                "Vmin_1_0": 5.6336839127097225,
                "Vmax_1_0": 172.44168276913186,
                "Vmin_1_1": 4.059455261054924,
                "Vmax_1_1": 239.31337374675104,
                "H_2": 2.0,
                "P_2": 0.4650747458361786,
                "V_2": 36.81407751895184,
                "Vmin_2_0": 6.654095576577702,
                "Vmax_2_0": 203.6755090116143,
                "Vmin_2_1": 4.794731780205301,
                "Vmax_2_1": 282.65946161296324,
                "I_0_0": 24.962242093761866,
                "R_0_0": 6.240560523440466,
                "I_0_1": 32.5170150736283,
                "R_0_1": 8.129253768407075,
                "I_1_0": 18.61101882296333,
                "R_1_0": 9.305509411481665,
                "I_1_1": 24.27481217020461,
                "R_1_1": 12.137406085102304,
                "I_2_0": 17.880425812840407,
                "R_2_0": 17.880425812840407,
                "I_2_1": 23.999944667857523,
                "R_2_1": 23.999944667857523,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(85.0, -95.0), (85.0, -105.0), (85.0, -115.0)],
                "type": "LineString",
            },
            "id": "4",
            "properties": {
                "Segment_ID": 5,
                "Area_km2": 0.0075,
                "ExtRatio": 0.0,
                "BurnRatio": 0.37333333333333335,
                "Slope": -1.2,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.3038933333333333,
                "Soil_M1": 0.48571428571428543,
                "Bmh_km2": 0.0028,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.1891464513621332,
                "V_0": 39.012070168680076,
                "Vmin_0_0": 7.051379826342692,
                "Vmax_0_0": 215.8360003754607,
                "Vmin_0_1": 5.081002302803192,
                "Vmax_0_1": 299.53570735568485,
                "H_1": 1.0,
                "P_1": 0.2865994733505535,
                "V_1": 46.89936388785373,
                "Vmin_1_0": 8.476997681928083,
                "Vmax_1_0": 259.47280105720546,
                "Vmin_1_1": 6.108257646514228,
                "Vmax_1_1": 360.0945572982708,
                "H_2": 2.0,
                "P_2": 0.40894006987314985,
                "V_2": 55.39409995765504,
                "Vmin_2_0": 10.012409934948984,
                "Vmax_2_0": 306.47030335901957,
                "Vmin_2_1": 7.214627376337415,
                "Vmax_2_1": 425.31736568721294,
                "I_0_0": 26.710397482109684,
                "R_0_0": 6.677599370527421,
                "I_0_1": 34.794246217386664,
                "R_0_1": 8.698561554346666,
                "I_1_0": 19.97921592290538,
                "R_1_0": 9.98960796145269,
                "I_1_1": 26.05938548823984,
                "R_1_1": 13.02969274411992,
                "I_2_0": 19.14865331648654,
                "R_2_0": 19.14865331648654,
                "I_2_1": 25.702219000267682,
                "R_2_1": 25.702219000267682,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [
                    (15.0, -75.0),
                    (25.0, -75.0),
                    (25.0, -85.0),
                    (25.0, -95.0),
                    (25.0, -105.0),
                ],
                "type": "LineString",
            },
            "id": "5",
            "properties": {
                "Segment_ID": 6,
                "Area_km2": 0.0005,
                "ExtRatio": 0.0,
                "BurnRatio": 1.0,
                "Slope": -0.925,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.24,
                "Soil_M1": 0.4,
                "Bmh_km2": 0.0001,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.13391242358438415,
                "V_0": 11.75498570706353,
                "Vmin_0_0": 2.124698041281589,
                "Vmax_0_0": 65.03497734196607,
                "Vmin_0_1": 1.5309905162366626,
                "Vmax_0_1": 90.25509139855959,
                "H_1": 1.0,
                "P_1": 0.19372269577057127,
                "V_1": 14.131558509670974,
                "Vmin_1_0": 2.5542604163025047,
                "Vmax_1_0": 78.18347128494322,
                "Vmin_1_1": 1.8405196396750358,
                "Vmax_1_1": 108.50248028188037,
                "H_2": 1.0,
                "P_2": 0.27186120938892905,
                "V_2": 16.691163797317515,
                "Vmin_2_0": 3.0169056696990015,
                "Vmax_2_0": 92.34460053127161,
                "Vmin_2_1": 2.173887243715704,
                "Vmax_2_1": 128.15519742997162,
                "I_0_0": 32.94010889292196,
                "R_0_0": 8.23502722323049,
                "I_0_1": 42.9093674107814,
                "R_0_1": 10.72734185269535,
                "I_1_0": 24.591280653950957,
                "R_1_0": 12.295640326975478,
                "I_1_1": 32.07501559038222,
                "R_1_1": 16.03750779519111,
                "I_2_0": 23.602941176470587,
                "R_2_0": 23.602941176470587,
                "I_2_1": 31.680972710794926,
                "R_2_1": 31.680972710794926,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [
                    (55.0, -105.0),
                    (45.0, -105.0),
                    (35.0, -105.0),
                    (25.0, -105.0),
                ],
                "type": "LineString",
            },
            "id": "6",
            "properties": {
                "Segment_ID": 7,
                "Area_km2": 0.0009,
                "ExtRatio": 0.0,
                "BurnRatio": 0.6666666666666666,
                "Slope": 0.1,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 1,
                "IsBurned": 1,
                "IsSteep": 1,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.23333333333333334,
                "Soil_M1": 0.3111111111111111,
                "Bmh_km2": 0.0003,
                "Relief_m": 3.0,
                "H_0": 1.0,
                "P_0": 0.10587792310700649,
                "V_0": 21.866253121860243,
                "Vmin_0_0": 3.9522961861422528,
                "Vmax_0_0": 120.97601067088999,
                "Vmin_0_1": 2.8479002007703094,
                "Vmax_0_1": 167.8896702419333,
                "H_1": 1.0,
                "P_1": 0.1468599328645283,
                "V_1": 26.287078783359473,
                "Vmin_1_0": 4.751354548092504,
                "Vmax_1_0": 145.43442379814903,
                "Vmin_1_1": 3.423676499470867,
                "Vmax_1_1": 201.832886684634,
                "H_2": 1.0,
                "P_2": 0.20015380877836433,
                "V_2": 31.048375692304212,
                "Vmin_2_0": 5.611952635448417,
                "Vmax_2_0": 171.7765091318238,
                "Vmin_2_1": 4.0437963868307545,
                "Vmax_2_1": 238.39025037706816,
                "I_0_0": 38.81199881199881,
                "R_0_0": 9.702999702999703,
                "I_0_1": 50.55837314881258,
                "R_0_1": 12.639593287203144,
                "I_1_0": 29.283461018476785,
                "R_1_0": 14.641730509238393,
                "I_1_1": 38.195142494829184,
                "R_1_1": 19.097571247414592,
                "I_2_0": 27.886100386100388,
                "R_2_0": 27.886100386100388,
                "I_2_1": 37.43002953476157,
                "R_2_1": 37.43002953476157,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [(25.0, -105.0), (15.0, -105.0), (5.0, -105.0)],
                "type": "LineString",
            },
            "id": "7",
            "properties": {
                "Segment_ID": 8,
                "Area_km2": 0.0016,
                "ExtRatio": 0.0,
                "BurnRatio": 0.8125,
                "Slope": 0.1,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 1,
                "IsBurned": 1,
                "IsSteep": 1,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.23125,
                "Soil_M1": 0.325,
                "Bmh_km2": 0.0004,
                "Relief_m": 5.0,
                "H_0": 1.0,
                "P_0": 0.10907252489391472,
                "V_0": 25.894543560389394,
                "Vmin_0_0": 4.680404328316619,
                "Vmax_0_0": 143.26270534880686,
                "Vmin_0_1": 3.372552004840906,
                "Vmax_0_1": 198.8189908527547,
                "H_1": 1.0,
                "P_1": 0.15215314209012643,
                "V_1": 31.129791777201415,
                "Vmin_1_0": 5.626668484571565,
                "Vmax_1_0": 172.22694721558756,
                "Vmin_1_1": 4.054400164406752,
                "Vmax_1_1": 239.0153652318904,
                "H_2": 1.0,
                "P_2": 0.20827166703804084,
                "V_2": 36.76823424493995,
                "Vmin_2_0": 6.64580946573705,
                "Vmax_2_0": 203.42187907441647,
                "Vmin_2_1": 4.788761069606879,
                "Vmax_2_1": 282.30747574168583,
                "I_0_0": 37.96698806994607,
                "R_0_0": 9.491747017486517,
                "I_0_1": 49.45762158436984,
                "R_0_1": 12.36440539609246,
                "I_1_0": 28.572841949047735,
                "R_1_0": 14.286420974523867,
                "I_1_1": 37.26826446633181,
                "R_1_1": 18.634132233165904,
                "I_2_0": 27.261146496815282,
                "R_2_0": 27.261146496815282,
                "I_2_1": 36.591187164909634,
                "R_2_1": 36.591187164909634,
            },
            "type": "Feature",
        },
    ]
    check_records(output, expected)


def check_basins(folder):
    output = read(folder, "basins")
    expected = [
        {
            "geometry": {
                "coordinates": [
                    [
                        (10.0, -10.0),
                        (10.0, -50.0),
                        (20.0, -50.0),
                        (20.0, -60.0),
                        (30.0, -60.0),
                        (30.0, -70.0),
                        (40.0, -70.0),
                        (40.0, -80.0),
                        (50.0, -80.0),
                        (50.0, -90.0),
                        (60.0, -90.0),
                        (60.0, -100.0),
                        (70.0, -100.0),
                        (70.0, -110.0),
                        (110.0, -110.0),
                        (110.0, -70.0),
                        (90.0, -70.0),
                        (90.0, -60.0),
                        (110.0, -60.0),
                        (110.0, -30.0),
                        (90.0, -30.0),
                        (90.0, -20.0),
                        (110.0, -20.0),
                        (110.0, -10.0),
                        (10.0, -10.0),
                    ]
                ],
                "type": "Polygon",
            },
            "id": "0",
            "properties": {
                "Segment_ID": 5,
                "Area_km2": 0.0075,
                "ExtRatio": 0.0,
                "BurnRatio": 0.37333333333333335,
                "Slope": -1.2,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 0,
                "IsBurned": 1,
                "IsSteep": 0,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.3038933333333333,
                "Soil_M1": 0.48571428571428543,
                "Bmh_km2": 0.0028,
                "Relief_m": 0.0,
                "H_0": 1.0,
                "P_0": 0.1891464513621332,
                "V_0": 39.012070168680076,
                "Vmin_0_0": 7.051379826342692,
                "Vmax_0_0": 215.8360003754607,
                "Vmin_0_1": 5.081002302803192,
                "Vmax_0_1": 299.53570735568485,
                "H_1": 1.0,
                "P_1": 0.2865994733505535,
                "V_1": 46.89936388785373,
                "Vmin_1_0": 8.476997681928083,
                "Vmax_1_0": 259.47280105720546,
                "Vmin_1_1": 6.108257646514228,
                "Vmax_1_1": 360.0945572982708,
                "H_2": 2.0,
                "P_2": 0.40894006987314985,
                "V_2": 55.39409995765504,
                "Vmin_2_0": 10.012409934948984,
                "Vmax_2_0": 306.47030335901957,
                "Vmin_2_1": 7.214627376337415,
                "Vmax_2_1": 425.31736568721294,
                "I_0_0": 26.710397482109684,
                "R_0_0": 6.677599370527421,
                "I_0_1": 34.794246217386664,
                "R_0_1": 8.698561554346666,
                "I_1_0": 19.97921592290538,
                "R_1_0": 9.98960796145269,
                "I_1_1": 26.05938548823984,
                "R_1_1": 13.02969274411992,
                "I_2_0": 19.14865331648654,
                "R_2_0": 19.14865331648654,
                "I_2_1": 25.702219000267682,
                "R_2_1": 25.702219000267682,
            },
            "type": "Feature",
        },
        {
            "geometry": {
                "coordinates": [
                    [
                        (20.0, -60.0),
                        (20.0, -70.0),
                        (10.0, -70.0),
                        (10.0, -80.0),
                        (20.0, -80.0),
                        (20.0, -100.0),
                        (10.0, -100.0),
                        (10.0, -110.0),
                        (60.0, -110.0),
                        (60.0, -90.0),
                        (50.0, -90.0),
                        (50.0, -80.0),
                        (40.0, -80.0),
                        (40.0, -70.0),
                        (30.0, -70.0),
                        (30.0, -60.0),
                        (20.0, -60.0),
                    ]
                ],
                "type": "Polygon",
            },
            "id": "1",
            "properties": {
                "Segment_ID": 8,
                "Area_km2": 0.0016,
                "ExtRatio": 0.0,
                "BurnRatio": 0.8125,
                "Slope": 0.1,
                "ConfAngle": 180.0,
                "DevAreaKm2": 0.0,
                "IsIncluded": 0,
                "IsFlood": 0,
                "IsAtRisk": 1,
                "IsInPerim": 1,
                "IsXPerim": 1,
                "IsExterior": 0,
                "IsPhysical": 1,
                "IsBurned": 1,
                "IsSteep": 1,
                "IsConfined": 1,
                "IsUndev": 1,
                "IsFlowSave": 0,
                "Terrain_M1": 0.0,
                "Fire_M1": 0.23125,
                "Soil_M1": 0.325,
                "Bmh_km2": 0.0004,
                "Relief_m": 5.0,
                "H_0": 1.0,
                "P_0": 0.10907252489391472,
                "V_0": 25.894543560389394,
                "Vmin_0_0": 4.680404328316619,
                "Vmax_0_0": 143.26270534880686,
                "Vmin_0_1": 3.372552004840906,
                "Vmax_0_1": 198.8189908527547,
                "H_1": 1.0,
                "P_1": 0.15215314209012643,
                "V_1": 31.129791777201415,
                "Vmin_1_0": 5.626668484571565,
                "Vmax_1_0": 172.22694721558756,
                "Vmin_1_1": 4.054400164406752,
                "Vmax_1_1": 239.0153652318904,
                "H_2": 1.0,
                "P_2": 0.20827166703804084,
                "V_2": 36.76823424493995,
                "Vmin_2_0": 6.64580946573705,
                "Vmax_2_0": 203.42187907441647,
                "Vmin_2_1": 4.788761069606879,
                "Vmax_2_1": 282.30747574168583,
                "I_0_0": 37.96698806994607,
                "R_0_0": 9.491747017486517,
                "I_0_1": 49.45762158436984,
                "R_0_1": 12.36440539609246,
                "I_1_0": 28.572841949047735,
                "R_1_0": 14.286420974523867,
                "I_1_1": 37.26826446633181,
                "R_1_1": 18.634132233165904,
                "I_2_0": 27.261146496815282,
                "R_2_0": 27.261146496815282,
                "I_2_1": 36.591187164909634,
                "R_2_1": 36.591187164909634,
            },
            "type": "Feature",
        },
    ]
    check_records(output, expected)


def check_outlets(folder):
    output = read(folder, "outlets")
    expected = [
        {
            "geometry": {"coordinates": (85.0, -115.0), "type": "Point"},
            "id": "0",
            "properties": {},
            "type": "Feature",
        },
        {
            "geometry": {"coordinates": (5.0, -105.0), "type": "Point"},
            "id": "1",
            "properties": {},
            "type": "Feature",
        },
    ]
    check_records(output, expected)


def check_config(folder, paths):
    with open(folder / "configuration.txt") as file:
        output = file.read()

    perimeter = paths["perimeter"]
    dem = paths["dem"]
    dnbr = paths["dnbr"]
    severity = paths["severity"]
    kf = paths["kf"]
    excluded = paths["excluded"]

    assert output == (
        f"# Assessment configuration for wildcat v{version()}\n"
        "\n"
        "# Preprocessed rasters\n"
        f'perimeter_p = r"{perimeter}"\n'
        f'dem_p = r"{dem}"\n'
        f'dnbr_p = r"{dnbr}"\n'
        f'severity_p = r"{severity}"\n'
        f'kf_p = r"{kf}"\n'
        f"retainments_p = None\n"
        f'excluded_p = r"{excluded}"\n'
        f"included_p = None\n"
        f"iswater_p = None\n"
        f"isdeveloped_p = None\n"
        "\n"
        "# Unit conversions\n"
        "dem_per_m = 1\n"
        "\n"
        "# Network delineation\n"
        "min_area_km2 = 0.0\n"
        "min_burned_area_km2 = 0\n"
        "max_length_m = 500\n"
        "\n"
        "# Filtering\n"
        "max_area_km2 = 8\n"
        "max_exterior_ratio = 0.95\n"
        "min_burn_ratio = 0.25\n"
        "min_slope = 0\n"
        "max_developed_area_km2 = 0.025\n"
        "max_confinement = 180\n"
        "confinement_neighborhood = 1\n"
        "flow_continuous = True\n"
        "\n"
        "# Removed segments\n"
        "remove_ids = []\n"
        "\n"
        "# Hazard Modeling\n"
        "I15_mm_hr = [16, 20, 24]\n"
        "volume_CI = [0.9, 0.95]\n"
        "durations = [15, 30, 60]\n"
        "probabilities = [0.5, 0.75]\n"
        "\n"
        "# Basins\n"
        "locate_basins = True\n"
        "parallelize_basins = False\n"
        "\n"
    )


def check_log(logcheck, paths):
    config_path = paths["project"] / "configuration.py"
    logcheck.check(
        [
            ("INFO", "----- Assessment -----"),
            ("INFO", "Parsing configuration"),
            ("DEBUG", "    Locating project folder"),
            ("DEBUG", f"        {paths['project']}"),
            ("DEBUG", "    Reading configuration file"),
            ("DEBUG", f"        {config_path}"),
            ("INFO", "Locating IO folders"),
            ("DEBUG", f"    preprocessed: {paths['preprocessed']}"),
            ("DEBUG", f"    assessment: {paths['assessment']}"),
            ("INFO", "Locating preprocessed rasters"),
            ("DEBUG", f"    perimeter_p:    {paths['perimeter']}"),
            ("DEBUG", f"    dem_p:          {paths['dem']}"),
            ("DEBUG", f"    dnbr_p:         {paths['dnbr']}"),
            ("DEBUG", f"    severity_p:     {paths['severity']}"),
            ("DEBUG", f"    kf_p:           {paths['kf']}"),
            ("DEBUG", f"    retainments_p:  None"),
            ("DEBUG", f"    excluded_p:     {paths['excluded']}"),
            ("DEBUG", f"    included_p:     None"),
            ("DEBUG", f"    iswater_p:      None"),
            ("DEBUG", f"    isdeveloped_p:  None"),
            ("INFO", "Loading preprocessed rasters"),
            ("DEBUG", "    Loading perimeter"),
            ("DEBUG", "    Loading dem"),
            ("DEBUG", "    Loading dnbr"),
            ("DEBUG", "    Loading severity"),
            ("DEBUG", "    Loading kf"),
            ("DEBUG", "    Loading excluded"),
            ("INFO", "Building burn severity masks"),
            ("DEBUG", "    Locating burned areas"),
            ("DEBUG", "    Locating moderate-high burn severity"),
            ("INFO", "Characterizing watershed"),
            ("DEBUG", "    Conditioning the DEM"),
            ("DEBUG", "    Determining flow directions"),
            ("DEBUG", "    Computing flow slopes"),
            ("DEBUG", "    Computing vertical relief"),
            ("INFO", "Computing flow accumulations"),
            ("DEBUG", "    Total catchment area"),
            ("DEBUG", "    Burned catchment area"),
            ("INFO", "Delineating initial network"),
            ("DEBUG", "    Building delineation mask"),
            ("DEBUG", "    Removing excluded areas"),
            ("DEBUG", "    Building network"),
            ("INFO", "Filtering network"),
            ("DEBUG", "    Characterizing segments"),
            ("DEBUG", "    Removing filtered segments"),
            ("INFO", "Locating outlet basins"),
            ("INFO", "Estimating debris-flow likelihood"),
            ("DEBUG", "    Computing M1 variables"),
            ("DEBUG", "    Running model"),
            ("INFO", "Estimating potential sediment volume"),
            (
                "DEBUG",
                "    Computing catchment area burned at moderate-or-high severity",
            ),
            ("DEBUG", "    Computing vertical relief"),
            ("DEBUG", "    Running model"),
            ("INFO", "Classifying combined hazard"),
            ("INFO", "Estimating rainfall thresholds"),
            ("DEBUG", "    Running model"),
            ("INFO", "Saving results"),
            ("DEBUG", "    Finalizing properties"),
            ("DEBUG", "    Saving segments"),
            ("DEBUG", "    Saving basins"),
            ("DEBUG", "    Removing nested drainages"),
            ("DEBUG", "    Saving outlets"),
            ("DEBUG", "    Saving configuration.txt"),
        ]
    )
