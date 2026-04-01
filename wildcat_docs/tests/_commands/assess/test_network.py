"""
Tests for the "delineate" function in the network module
"""

import numpy as np
import pytest
from pfdf.raster import Raster
from pfdf.segments import Segments

from wildcat._commands.assess import _network


class TestMask:
    def test_missing(_, logcheck):
        output = _network._mask({}, "test", logcheck.log, "test description")
        assert isinstance(output, np.bool)
        assert output == False
        logcheck.check([])

    def test_boolean(_, logcheck):
        values = np.array(
            [
                [1, 0, 0, 1],
                [1, 0, 1, 0],
                [0, 1, 1, 0],
            ],
            dtype=bool,
        )
        raster = Raster(values)

        output = _network._mask(
            {"test": raster}, "test", logcheck.log, "test description"
        )
        assert np.array_equal(output, values)
        logcheck.check([("DEBUG", "    Removing test description")])

    def test_other_dtype(_, logcheck):
        values = np.array(
            [
                [1, 0, 0, 1],
                [1, 0, 1, 0],
                [0, 1, 1, 0],
            ],
            dtype=int,
        )
        raster = Raster(values)

        output = _network._mask(
            {"test": raster}, "test", logcheck.log, "test description"
        )
        assert np.array_equal(output, values)
        assert output.dtype == bool
        logcheck.check([("DEBUG", "    Removing test description")])


class TestDelineate:
    def test_basic(_, config, rasters, stream, logcheck):

        segments = _network.delineate(config, rasters, logcheck.log)

        assert isinstance(segments, Segments)
        assert segments.size == 8
        assert segments.raster() == stream

        logcheck.check(
            [
                ("INFO", "Delineating initial network"),
                ("DEBUG", "    Building delineation mask"),
                ("DEBUG", "    Building network"),
            ]
        )

    def test_retainments(_, config, rasters, retainments, masked_stream, logcheck):
        rasters["nretainments"] = retainments
        segments = _network.delineate(config, rasters, logcheck.log)

        assert isinstance(segments, Segments)
        assert segments.size == 5
        assert segments.raster() == masked_stream

        logcheck.check(
            [
                ("INFO", "Delineating initial network"),
                ("DEBUG", "    Building delineation mask"),
                ("DEBUG", "    Removing areas below retainment features"),
                ("DEBUG", "    Building network"),
            ]
        )

    @pytest.mark.parametrize(
        "key, description",
        (
            ("iswater", "water bodies"),
            ("excluded", "excluded areas"),
        ),
    )
    def test_mask(_, config, rasters, mask, key, description, masked_stream, logcheck):
        rasters[key] = mask
        segments = _network.delineate(config, rasters, logcheck.log)

        assert isinstance(segments, Segments)
        assert segments.size == 5
        assert segments.raster() == masked_stream

        logcheck.check(
            [
                ("INFO", "Delineating initial network"),
                ("DEBUG", "    Building delineation mask"),
                ("DEBUG", f"    Removing {description}"),
                ("DEBUG", "    Building network"),
            ]
        )

    def test_max_length(_, config, rasters, split_stream, logcheck):
        config["max_length_m"] = 100
        segments = _network.delineate(config, rasters, logcheck.log)

        assert isinstance(segments, Segments)
        assert segments.size == 9
        assert segments.raster() == split_stream

        logcheck.check(
            [
                ("INFO", "Delineating initial network"),
                ("DEBUG", "    Building delineation mask"),
                ("DEBUG", "    Building network"),
            ]
        )


class TestDevelopedArea:
    def test_missing(_, segments):
        output = _network._developed_area(segments, {})
        expected = np.zeros(segments.size)
        assert np.array_equal(output, expected)

    def test(_, segments, rasters, mask):
        rasters["isdeveloped"] = mask
        output = _network._developed_area(segments, rasters)
        expected = [0, 0, 0, 0, 0, 0.0004, 0.0008, 0.0014]
        assert np.array_equal(output, expected)


class TestIncluded:
    def test_missing(_, segments):
        output = _network._included(segments, {})
        assert output.dtype == bool
        assert np.array_equal(output, np.zeros(segments.size))

    def test(_, segments, rasters, mask):
        rasters["included"] = mask
        output = _network._included(segments, rasters)
        assert output.dtype == bool
        assert np.array_equal(output, [0, 0, 0, 0, 0, 1, 1, 1])


def check_props(output, expected):
    assert list(output.keys()) == [
        # Watershed
        "Segment_ID",
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
        # Filters
        "IsIncluded",
        "IsFlood",
        "IsAtRisk",
        "IsInPerim",
        "IsXPerim",
        "IsExterior",
        "IsPhysical",
        "IsBurned",
        "IsSteep",
        "IsConfined",
        "IsUndev",
        "IsFlowSave",
    ]
    for key, values in expected.items():
        assert np.allclose(output[key], values)


def check_filter_log(logcheck):
    logcheck.check(
        [
            ("INFO", "Filtering network"),
            ("DEBUG", "    Characterizing segments"),
            ("DEBUG", "    Removing filtered segments"),
        ]
    )


def check_removed(segments, stream, id):
    expected = stream.values.copy()
    expected[expected == id] = 0
    assert np.array_equal(segments.raster().values, expected)


class TestFilter:
    def test_floodlike(_, config, segments, rasters, stream, trues, logcheck):

        rasters["perimeter"] = trues
        config["max_area_km2"] = 0.007

        output = _network.filter(config, segments, rasters, logcheck.log)
        check_removed(segments, stream, 5)
        check_props(
            output,
            {
                # Watershed
                "Segment_ID": [1, 2, 3, 4, 6, 7, 8],
                "Area_km2": [0.0016, 0.0011, 0.0041, 0.0027, 0.0005, 0.0009, 0.0016],
                "ExtRatio": [0, 0, 0, 0, 0, 0, 0],
                "BurnRatio": [1, 1, 1, 1, 1, 1, 1],
                "Slope": [1, 1, 1, 1, 1, 1, 1],
                "ConfAngle": [180, 180, 180, 180, 180, 180, 180],
                "DevAreaKm2": [0, 0, 0, 0, 0, 0, 0],
                # Filters
                "IsIncluded": [0, 0, 0, 0, 0, 0, 0],
                "IsFlood": [0, 0, 0, 0, 0, 0, 0],
                "IsAtRisk": [1, 1, 1, 1, 1, 1, 1],
                "IsInPerim": [1, 1, 1, 1, 1, 1, 1],
                "IsXPerim": [1, 1, 1, 1, 1, 1, 1],
                "IsExterior": [0, 0, 0, 0, 0, 0, 0],
                "IsPhysical": [1, 1, 1, 1, 1, 1, 1],
                "IsBurned": [1, 1, 1, 1, 1, 1, 1],
                "IsSteep": [1, 1, 1, 1, 1, 1, 1],
                "IsConfined": [1, 1, 1, 1, 1, 1, 1],
                "IsUndev": [1, 1, 1, 1, 1, 1, 1],
                "IsFlowSave": [0, 0, 0, 0, 0, 0, 0],
            },
        )
        check_filter_log(logcheck)

    def test_in_perim(_, config, segments, rasters, stream, trues, logcheck):
        "Test that a segment in the perimeter is retained even when not physical"

        # Create an area of low slopes within the perimeter
        slopes = np.ones(stream.shape)
        slopes[stream.values == 2] = 0
        slopes[stream.values == 1] = 0
        rasters["slopes"] = Raster.from_array(slopes, spatial=stream)
        rasters["perimeter"] = trues
        config["min_slope"] = 0.5

        output = _network.filter(config, segments, rasters, logcheck.log)
        assert segments.raster() == stream
        check_props(
            output,
            {
                # Watershed
                "Segment_ID": [1, 2, 3, 4, 5, 6, 7, 8],
                "Area_km2": [
                    0.0016,
                    0.0011,
                    0.0041,
                    0.0027,
                    0.0075,
                    0.0005,
                    0.0009,
                    0.0016,
                ],
                "ExtRatio": [0, 0, 0, 0, 0, 0, 0, 0],
                "BurnRatio": [1, 1, 1, 1, 1, 1, 1, 1],
                "Slope": [0, 0, 1, 1, 1, 1, 1, 1],
                "ConfAngle": [180, 180, 180, 180, 180, 180, 180, 180],
                "DevAreaKm2": [0, 0, 0, 0, 0, 0, 0, 0],
                # Filters
                "IsIncluded": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsFlood": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsAtRisk": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsInPerim": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsXPerim": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsExterior": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsPhysical": [0, 0, 1, 1, 1, 1, 1, 1],
                "IsBurned": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsSteep": [0, 0, 1, 1, 1, 1, 1, 1],
                "IsConfined": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsUndev": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsFlowSave": [0, 0, 0, 0, 0, 0, 0, 0],
            },
        )
        check_filter_log(logcheck)

    def test_not_physical_outside_perim(_, config, segments, rasters, stream, logcheck):
        "Check that an unphysical segment outside the perimeter is removed"

        perimeter = np.ones(stream.shape, bool)
        perimeter[:, 8:] = False
        slopes = np.ones(stream.shape)
        slopes[stream.values == 4] = 0
        rasters["perimeter"] = Raster.from_array(perimeter, spatial=stream)
        rasters["slopes"] = Raster.from_array(slopes, spatial=stream)
        config["min_slope"] = 0.5

        output = _network.filter(config, segments, rasters, logcheck.log)
        check_removed(segments, stream, 4)
        check_props(
            output,
            {
                # Watershed
                "Segment_ID": [1, 2, 3, 5, 6, 7, 8],
                "Area_km2": [0.0016, 0.0011, 0.0041, 0.0075, 0.0005, 0.0009, 0.0016],
                "ExtRatio": [0, 0, 0, 0.34666666666, 0, 0, 0],
                "BurnRatio": [1, 1, 1, 1, 1, 1, 1],
                "Slope": [1, 1, 1, 1, 1, 1, 1],
                "ConfAngle": [180, 180, 180, 180, 180, 180, 180],
                "DevAreaKm2": [0, 0, 0, 0, 0, 0, 0],
                # Filters
                "IsIncluded": [0, 0, 0, 0, 0, 0, 0],
                "IsFlood": [0, 0, 0, 0, 0, 0, 0],
                "IsAtRisk": [1, 1, 1, 1, 1, 1, 1],
                "IsInPerim": [1, 1, 1, 0, 1, 1, 1],
                "IsXPerim": [1, 1, 1, 0, 1, 1, 1],
                "IsExterior": [0, 0, 0, 0, 0, 0, 0],
                "IsPhysical": [1, 1, 1, 1, 1, 1, 1],
                "IsBurned": [1, 1, 1, 1, 1, 1, 1],
                "IsSteep": [1, 1, 1, 1, 1, 1, 1],
                "IsConfined": [1, 1, 1, 1, 1, 1, 1],
                "IsUndev": [1, 1, 1, 1, 1, 1, 1],
                "IsFlowSave": [0, 0, 0, 0, 0, 0, 0],
            },
        )
        check_filter_log(logcheck)

    def test_included(_, config, segments, rasters, stream, trues, logcheck):
        "Test that a segment in an include mask is retained even when floodlike"

        include = np.zeros(stream.shape, bool)
        include[stream.values == 5] = True
        rasters["included"] = Raster.from_array(include, spatial=stream)
        rasters["perimeter"] = trues
        config["max_area_km2"] = 0.007
        config["flow_continuous"] = False

        output = _network.filter(config, segments, rasters, logcheck.log)
        assert segments.raster() == stream
        check_props(
            output,
            {
                # Watershed
                "Segment_ID": [1, 2, 3, 4, 5, 6, 7, 8],
                "Area_km2": [
                    0.0016,
                    0.0011,
                    0.0041,
                    0.0027,
                    0.0075,
                    0.0005,
                    0.0009,
                    0.0016,
                ],
                "ExtRatio": [0, 0, 0, 0, 0, 0, 0, 0],
                "BurnRatio": [1, 1, 1, 1, 1, 1, 1, 1],
                "Slope": [1, 1, 1, 1, 1, 1, 1, 1],
                "ConfAngle": [180, 180, 180, 180, 180, 180, 180, 180],
                "DevAreaKm2": [0, 0, 0, 0, 0, 0, 0, 0],
                # Filters
                "IsIncluded": [0, 0, 0, 0, 1, 0, 0, 0],
                "IsFlood": [0, 0, 0, 0, 1, 0, 0, 0],
                "IsAtRisk": [1, 1, 1, 1, 0, 1, 1, 1],
                "IsInPerim": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsXPerim": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsExterior": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsPhysical": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsBurned": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsSteep": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsConfined": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsUndev": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsFlowSave": [0, 0, 0, 0, 0, 0, 0, 0],
            },
        )
        check_filter_log(logcheck)

    def test_continuous(_, config, segments, rasters, stream, falses, logcheck):
        "Check that an unphysical segment is retained for flow continuity"

        slopes = np.ones(stream.shape)
        slopes[stream.values == 3] = 0
        rasters["slopes"] = Raster.from_array(slopes, spatial=stream)
        rasters["perimeter"] = falses
        config["min_slope"] = 0.5

        output = _network.filter(config, segments, rasters, logcheck.log)
        assert segments.raster() == stream
        check_props(
            output,
            {
                # Watershed
                "Segment_ID": [1, 2, 3, 4, 5, 6, 7, 8],
                "Area_km2": [
                    0.0016,
                    0.0011,
                    0.0041,
                    0.0027,
                    0.0075,
                    0.0005,
                    0.0009,
                    0.0016,
                ],
                "ExtRatio": [1, 1, 1, 1, 1, 1, 1, 1],
                "BurnRatio": [1, 1, 1, 1, 1, 1, 1, 1],
                "Slope": [1, 1, 0, 1, 1, 1, 1, 1],
                "ConfAngle": [180, 180, 180, 180, 180, 180, 180, 180],
                "DevAreaKm2": [0, 0, 0, 0, 0, 0, 0, 0],
                # Filters
                "IsIncluded": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsFlood": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsAtRisk": [1, 1, 0, 1, 1, 1, 1, 1],
                "IsInPerim": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsXPerim": [0, 0, 0, 0, 0, 0, 0, 0],
                "IsExterior": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsPhysical": [1, 1, 0, 1, 1, 1, 1, 1],
                "IsBurned": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsSteep": [1, 1, 0, 1, 1, 1, 1, 1],
                "IsConfined": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsUndev": [1, 1, 1, 1, 1, 1, 1, 1],
                "IsFlowSave": [0, 0, 1, 0, 0, 0, 0, 0],
            },
        )
        check_filter_log(logcheck)

    def test_not_continuous(_, config, segments, rasters, stream, falses, logcheck):
        "Check that an unphysical segment is removed after disabling flow continuity"

        slopes = np.ones(stream.shape)
        slopes[stream.values == 3] = 0
        rasters["slopes"] = Raster.from_array(slopes, spatial=stream)
        rasters["perimeter"] = falses
        config["min_slope"] = 0.5
        config["flow_continuous"] = False

        output = _network.filter(config, segments, rasters, logcheck.log)
        stream = stream.values.copy()
        stream[stream == 3] = 0
        assert np.array_equal(segments.raster().values, stream)
        check_props(
            output,
            {
                # Watershed
                "Segment_ID": [1, 2, 4, 5, 6, 7, 8],
                "Area_km2": [
                    0.0016,
                    0.0011,
                    0.0027,
                    0.0075,
                    0.0005,
                    0.0009,
                    0.0016,
                ],
                "ExtRatio": [1, 1, 1, 1, 1, 1, 1],
                "BurnRatio": [1, 1, 1, 1, 1, 1, 1],
                "Slope": [1, 1, 1, 1, 1, 1, 1],
                "ConfAngle": [180, 180, 180, 180, 180, 180, 180],
                "DevAreaKm2": [0, 0, 0, 0, 0, 0, 0],
                # Filters
                "IsIncluded": [0, 0, 0, 0, 0, 0, 0],
                "IsFlood": [0, 0, 0, 0, 0, 0, 0],
                "IsAtRisk": [1, 1, 1, 1, 1, 1, 1],
                "IsInPerim": [0, 0, 0, 0, 0, 0, 0],
                "IsXPerim": [0, 0, 0, 0, 0, 0, 0],
                "IsExterior": [1, 1, 1, 1, 1, 1, 1],
                "IsPhysical": [1, 1, 1, 1, 1, 1, 1],
                "IsBurned": [1, 1, 1, 1, 1, 1, 1],
                "IsSteep": [1, 1, 1, 1, 1, 1, 1],
                "IsConfined": [1, 1, 1, 1, 1, 1, 1],
                "IsUndev": [1, 1, 1, 1, 1, 1, 1],
                "IsFlowSave": [0, 0, 0, 0, 0, 0, 0],
            },
        )
        check_filter_log(logcheck)


class TestRemoveIDs:
    def test_no_ids(_, segments, logcheck):
        config = {"remove_ids": []}
        _network.remove_ids(config, segments, {}, logcheck.log)
        logcheck.check([])

    def test_not_in_network(_, segments, errcheck, logcheck):
        config = {"remove_ids": [2, 9]}
        with pytest.raises(ValueError) as error:
            _network.remove_ids(config, segments, {}, logcheck.log)
        errcheck(
            error,
            "Cannot remove ID 9 from the network",
            "the network does not contain a segment with this ID",
        )

    def test_remove(_, segments, logcheck):
        config = {"remove_ids": [3, 7]}
        properties = {"SegmentID": segments.ids, "Area": segments.area()}
        _network.remove_ids(config, segments, properties, logcheck.log)

        assert np.array_equal(properties["SegmentID"], [1, 2, 4, 5, 6, 8])
        assert np.allclose(
            properties["Area"], [0.0016, 0.0011, 0.0027, 0.0075, 0.0005, 0.0016]
        )
        logcheck.check([("INFO", "Removing listed segments")])


class TestLocateBasins:
    def test(_, config, segments, logcheck):
        assert segments._basins is None
        _network.locate_basins(config, segments, logcheck.log)
        assert segments._basins is not None
        logcheck.check([("INFO", "Locating outlet basins")])

    def test_disabled(_, config, segments, logcheck):
        config["locate_basins"] = False
        assert segments._basins is None
        _network.locate_basins(config, segments, logcheck.log)
        assert segments._basins is None
        logcheck.check([])
