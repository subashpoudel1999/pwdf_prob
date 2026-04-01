import fiona
import pytest

from wildcat._commands.export import _load
from wildcat.errors import ConfigRecordError


class TestParameters:
    def test_not_exists(_, assessment, errcheck, logcheck):
        with pytest.raises(FileNotFoundError) as error:
            _load.parameters(assessment, logcheck.log)
        errcheck(
            error, "Could not locate the configuration.txt record for the assessment"
        )

    def test_folder(_, assessment, config_path, errcheck, logcheck):
        config_path.mkdir()
        with pytest.raises(ConfigRecordError) as error:
            _load.parameters(assessment, logcheck.log)
        errcheck(error, "The recorded configuration.txt is not a file")

    def test_config_error(_, assessment, config_path, errcheck, logcheck):
        with open(config_path, "w") as file:
            file.write('a = ["a", "syntax", "error"}')
        with pytest.raises(ConfigRecordError) as error:
            _load.parameters(assessment, logcheck.log)
        errcheck(error, "Could not load the recorded configuration.txt file")

    @pytest.mark.parametrize(
        "missing", ("I15_mm_hr", "volume_CI", "durations", "probabilities")
    )
    def test_missing_parameter(_, missing, assessment, config_path, errcheck, logcheck):
        with open(config_path, "w") as file:
            for parameter in ("I15_mm_hr", "volume_CI", "durations", "probabilities"):
                if parameter != missing:
                    file.write(f"{parameter} = [1, 2]\n")
        with pytest.raises(ConfigRecordError) as error:
            _load.parameters(assessment, logcheck.log)
        errcheck(
            error,
            f"The recorded configuration.txt file for the assessment is "
            f'missing the "{missing}" parameter.',
        )

    def test_invalid_parameter(_, assessment, config_path, errcheck, logcheck):
        with open(config_path, "w") as file:
            file.write(
                "I15_mm_hr = [20, 24]\n"
                "volume_CI = [0.9, 0.95]\n"
                'durations = "invalid"\n'
                "probabilities = [0.5, 0.75]\n"
            )
        with pytest.raises(ConfigRecordError) as error:
            _load.parameters(assessment, logcheck.log)
        errcheck(
            error, "The recorded configuration.txt file for the assessment is invalid"
        )

    def test_valid(_, assessment, config_path, logcheck):
        with open(config_path, "w") as file:
            file.write(
                "I15_mm_hr = [20, 24]\n"
                "volume_CI = [0.9, 0.95]\n"
                "durations = [15, 30, 60]\n"
                "probabilities = [0.5, 0.75]\n"
            )
        output = _load.parameters(assessment, logcheck.log)
        expected = {
            "I15_mm_hr": [20, 24],
            "volume_CI": [0.9, 0.95],
            "durations": [15, 30, 60],
            "probabilities": [0.5, 0.75],
        }
        for name, values in expected.items():
            assert name in output
            assert output[name] == values
        logcheck.check([("INFO", "Loading assessment parameters")])


class TestGeojson:
    def test(_, fsegments, segments):
        with fiona.open(fsegments) as file:
            output = list(file)
        output = _load._geojson(output)
        assert output == segments


class TestSegments:
    def test_not_exists(_, assessment, fsegments, errcheck, logcheck):
        fsegments.unlink()
        with pytest.raises(FileNotFoundError) as error:
            _load._segments(assessment, logcheck.log)
        errcheck(error, "Could not locate the segments.geojson file for the assessment")

    def test_folder(_, assessment, fsegments, errcheck, logcheck):
        fsegments.unlink()
        fsegments.mkdir()
        with pytest.raises(TypeError) as error:
            _load._segments(assessment, logcheck.log)
        errcheck(error, "The saved segments.geojson is not a file")

    def test_invalid(_, assessment, fsegments, errcheck, logcheck):
        fsegments.unlink()
        with open(fsegments, "w") as file:
            file.write("An invalid geojson file")
        with pytest.raises(RuntimeError) as error:
            _load._segments(assessment, logcheck.log)
        errcheck(error, "Could not load the saved segments.geojson file")

    def test_valid(_, assessment, fsegments, segments, logcheck):
        assert fsegments.exists()
        crs, schema, output = _load._segments(assessment, logcheck.log)
        assert crs == 4326
        assert schema == {
            "geometry": "LineString",
            "properties": {
                "Segment_ID": "int32",
                "Area_km2": "float",
                "ConfAngle": "float",
            },
        }
        assert output == segments
        logcheck.check(
            [
                ("DEBUG", "    Loading segments"),
            ]
        )


class TestFeatures:
    def test_not_exist(_, assessment, logcheck):
        output = _load._features(assessment, "basins", logcheck.log)
        assert output is None
        logcheck.check([])

    def test_invalid(_, assessment, fbasins, logcheck):
        fbasins.unlink()
        with open(fbasins, "w") as file:
            file.write("An invalid geojson file")
        output = _load._features(assessment, fbasins.stem, logcheck.log)
        assert output is None
        log_tuples = logcheck.caplog.record_tuples
        assert log_tuples[0] == ("test.log", 10, "    Loading basins")

        found_error = False
        for record in log_tuples:
            if "ERROR: Could not load the saved basins.geojson file" in record[2]:
                found_error = True
                break
        assert found_error

    def test_valid(_, assessment, fbasins, basins, logcheck):
        output = _load._features(assessment, fbasins.stem, logcheck.log)
        assert output == basins
        logcheck.check([("DEBUG", "    Loading basins")])


class TestResults:
    def test(
        _, assessment, fsegments, segments, fbasins, basins, foutlets, outlets, logcheck
    ):
        assert fsegments.exists()
        assert foutlets.exists()
        assert fbasins.exists()
        crs, schema, out_segments, out_basins, out_outlets = _load.results(
            assessment, logcheck.log
        )

        assert crs == 4326
        assert schema == {
            "geometry": "LineString",
            "properties": {
                "Segment_ID": "int32",
                "Area_km2": "float",
                "ConfAngle": "float",
            },
        }
        assert out_segments == segments
        assert out_basins == basins
        assert out_outlets == outlets

        logcheck.check(
            [
                ("INFO", "Loading assessment results"),
                ("DEBUG", "    Loading segments"),
                ("DEBUG", "    Loading basins"),
                ("DEBUG", "    Loading outlets"),
            ]
        )
