from fiona.crs import CRS as fCRS
from pyproj import CRS

from wildcat._commands.export import _reproject


class TestFeatures:
    def test_segments(_, outlets, logcheck):
        iCRS = CRS(26911)
        fCRS = CRS(4326)
        _reproject._features(outlets, "outlets", iCRS, fCRS, logcheck.log)

        # Round to 8 digits for machine precision
        for outlet in outlets:
            geometry = outlet["geometry"].__geo_interface__
            coords = tuple(round(coord, ndigits=8) for coord in geometry["coordinates"])
            geometry["coordinates"] = coords
            outlet["geometry"] = geometry

        assert outlets == [
            {
                "geometry": {"coordinates": (-121.48873493, 9.02e-06), "type": "Point"},
                "id": "0",
                "properties": {"Segment_ID": 1, "Area_km2": 1.1, "ConfAngle": 1.11},
                "type": "Feature",
            },
            {
                "geometry": {
                    "coordinates": (-121.48872597, 1.804e-05),
                    "type": "Point",
                },
                "id": "1",
                "properties": {"Segment_ID": 2, "Area_km2": 2.2, "ConfAngle": 2.22},
                "type": "Feature",
            },
            {
                "geometry": {
                    "coordinates": (-121.48871701, 2.706e-05),
                    "type": "Point",
                },
                "id": "2",
                "properties": {"Segment_ID": 3, "Area_km2": 3.3, "ConfAngle": 3.33},
                "type": "Feature",
            },
            {
                "geometry": {
                    "coordinates": (-121.48870805, 3.608e-05),
                    "type": "Point",
                },
                "id": "3",
                "properties": {"Segment_ID": 4, "Area_km2": 4.4, "ConfAngle": 4.44},
                "type": "Feature",
            },
        ]

        logcheck.check([("DEBUG", "    Reprojecting outlets")])

    def test_empty(_, logcheck):
        outlets = None
        iCRS = CRS(26911)
        fCRS = CRS(4326)
        _reproject._features(outlets, "outlets", iCRS, fCRS, logcheck.log)
        assert outlets is None
        logcheck.check([])


class TestResults:
    def test_no_crs(_, config, logcheck):
        results = 1, 2, 3, 4, 5
        config["export_crs"] = None
        output = _reproject.results(results, config, logcheck.log)
        assert output == (1, 2, 3, 4, 5)
        logcheck.check([])

    def test_same_crs(_, config, logcheck):
        iCRS = fCRS.from_epsg(4326)
        schema = {"properties": {"test": "float"}}
        results = iCRS, schema, 1, 2, 3
        config["export_crs"] = CRS(4326)
        output = _reproject.results(results, config, logcheck.log)
        assert output == (iCRS, schema, 1, 2, 3)
        logcheck.check([])

    def test_reproject_all(_, config, segments, basins, outlets, logcheck):
        iCRS = fCRS.from_epsg(26911)
        config["export_crs"] = CRS(4326)
        schema = {"properties": {"test": "float"}}
        results = iCRS, schema, segments, basins, outlets
        fcrs, out_schema, segments, basins, outlets = _reproject.results(
            results, config, logcheck.log
        )
        assert fcrs == CRS(4326)
        assert out_schema == schema
        assert segments != basins
        assert segments != outlets
        assert basins != outlets

        outsegs = tuple(
            round(coord, 8) for coord in segments[0]["geometry"]["coordinates"][0]
        )
        outbasin = tuple(
            round(coord, 8) for coord in basins[0]["geometry"]["coordinates"][0][0]
        )
        outpoint = tuple(
            round(coord, 8) for coord in outlets[0]["geometry"]["coordinates"]
        )
        expected = (-121.48873493, 9.02e-06)
        for output in [outsegs, outbasin, outpoint]:
            assert output == expected

        logcheck.check(
            [
                ("INFO", "Reprojecting from NAD83 / UTM zone 11N to WGS 84"),
                ("DEBUG", "    Reprojecting segments"),
                ("DEBUG", "    Reprojecting basins"),
                ("DEBUG", "    Reprojecting outlets"),
            ]
        )

    def test_no_basins(_, config, segments, outlets, logcheck):
        iCRS = fCRS.from_epsg(26911)
        config["export_crs"] = CRS(4326)
        schema = {"properties": {"test": "float"}}
        results = iCRS, schema, segments, None, outlets
        fcrs, out_schema, segments, basins, outlets = _reproject.results(
            results, config, logcheck.log
        )
        assert fcrs == CRS(4326)
        assert out_schema == schema
        assert segments != basins
        assert segments != outlets
        assert basins is None

        outsegs = tuple(
            round(coord, 8) for coord in segments[0]["geometry"]["coordinates"][0]
        )
        outpoint = tuple(
            round(coord, 8) for coord in outlets[0]["geometry"]["coordinates"]
        )
        expected = (-121.48873493, 9.02e-06)
        for output in [outsegs, outpoint]:
            assert output == expected

        logcheck.check(
            [
                ("INFO", "Reprojecting from NAD83 / UTM zone 11N to WGS 84"),
                ("DEBUG", "    Reprojecting segments"),
                ("DEBUG", "    Reprojecting outlets"),
            ]
        )
