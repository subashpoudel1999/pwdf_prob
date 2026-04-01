import pytest
from pyproj import CRS

from wildcat._utils._validate import _export


class TestFilename:
    def test_none(_):
        config = {"prefix": None}
        _export.filename(config, "prefix")
        assert config["prefix"] == ""

    def test_unsupported(_, errcheck):
        config = {"prefix": "test,invalid"}
        with pytest.raises(ValueError) as error:
            _export.filename(config, "prefix")
        errcheck(
            error,
            'The "prefix" setting must be a string of ASCII letters, numbers, '
            "underscores, and/or hyphens",
            'However, prefix[4] (value = ",") is not an allowed character',
        )

    def test_valid(_):
        config = {"prefix": "valid"}
        _export.filename(config, "prefix")
        assert config["prefix"] == "valid"


class TestFileFormat:
    def test_not_string(_, errcheck):
        config = {"format": None}
        with pytest.raises(TypeError) as error:
            _export.file_format(config, "format")
        errcheck(error, 'The "format" setting must be a string')

    def test_supported(_):
        config = {"format": "GeoJSON"}
        _export.file_format(config, "format")
        assert config["format"] == "GeoJSON"

    def test_capitalization(_):
        config = {"format": "geojson"}
        _export.file_format(config, "format")
        assert config["format"] == "GeoJSON"

    def test_not_supported(_, errcheck):
        config = {"format": "invalid"}
        with pytest.raises(ValueError) as error:
            _export.file_format(config, "format")
        errcheck(error, 'The "format" setting must be a recognized vector file format')


class TestStrList:
    def test_none(_):
        output = _export._strlist("", "", None)
        assert output == []

    @pytest.mark.parametrize(
        "input, expected",
        (
            (["some", "text"], ["some", "text"]),
            (("some", "text"), ["some", "text"]),
            ("example", ["example"]),
        ),
    )
    def test_valid(_, input, expected):
        output = _export._strlist("rename", "test", input)
        assert output == expected

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _export._strlist("rename", "volume", 5)
        errcheck(
            error,
            'The value of the "volume" key in the "rename" setting',
            "must be a list, tuple, or string",
        )

    def test_not_all_string(_, errcheck):
        with pytest.raises(TypeError) as error:
            _export._strlist("rename", "volume", ["some", "text", 5])
        errcheck(
            error,
            'Each element of the "volume" key in the "rename" setting',
            'must be a string, but rename["volume"][2] is not',
        )


class TestRename:
    def test_none(_):
        config = {"rename": None}
        _export.rename(config, "rename")
        assert config["rename"] == {}

    def test_not_dict(_, errcheck):
        config = {"rename": 5}
        with pytest.raises(TypeError) as error:
            _export.rename(config, "rename")
        errcheck(error, 'The "rename" setting must be a dict')

    def test_bad_key(_, errcheck):
        config = {"rename": {"H": "hazard", 5: "invalid"}}
        with pytest.raises(TypeError) as error:
            _export.rename(config, "rename")
        errcheck(
            error, 'Each key of the "rename" dict must be a string, but key[1] is not'
        )

    def test_invalid_parameter(_, errcheck):
        config = {"rename": {"H": "hazard", "volume_CI": ["some", 5, "text"]}}
        with pytest.raises(TypeError) as error:
            _export.rename(config, "rename")
        errcheck(
            error,
            'Each element of the "volume_CI" key in the "rename" setting must be a string',
            'rename["volume_CI"][1] is not',
        )

    def test_invalid_nonparameter(_, errcheck):
        config = {"rename": {"H": 5}}
        with pytest.raises(TypeError) as error:
            _export.rename(config, "rename")
        errcheck(
            error, 'The value of the "H" key in the "rename" setting must be a string'
        )

    def test_valid(_):
        config = {"rename": {"H": "hazard", "volume_CI": ["90%", "95%"]}}
        _export.rename(config, "rename")
        assert config["rename"] == {"H": "hazard", "volume_CI": ["90%", "95%"]}


class TestCrs:
    @pytest.mark.parametrize("crs", ("WGS84", 26911, "26911"))
    def test_valid(_, crs):
        config = {"export_crs": crs}
        _export.crs(config, "export_crs")
        assert isinstance(config["export_crs"], CRS)
        assert config["export_crs"] == CRS(crs)

    def test_invalid(_, errcheck):
        config = {"export_crs": "invalid"}
        with pytest.raises(TypeError) as error:
            _export.crs(config, "export_crs")
        errcheck(error, "Could not convert export_crs to a CRS")

    def test_none(_):
        config = {"export_crs": None}
        _export.crs(config, "export_crs")
        assert config["export_crs"] is None
