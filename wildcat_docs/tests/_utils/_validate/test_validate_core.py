from math import inf, nan
from pathlib import Path

import pytest

from wildcat._utils._validate import _core


class TestAsList:
    @pytest.mark.parametrize(
        "input, expected",
        (
            (1, [1]),
            ([1, 2, 3], [1, 2, 3]),
            ("test", ["test"]),
            ({"a": "test"}, [{"a": "test"}]),
            ((1, 2, 3), [1, 2, 3]),
        ),
    )
    def test(_, input, expected):
        assert _core.aslist(input) == expected


class TestPath:
    @pytest.mark.parametrize("input", (False, None))
    def test_disabled(_, input, errcheck):
        with pytest.raises(TypeError) as error:
            _core.path({"test": input}, "test")
        errcheck(error, f"The test path is required, so cannot be {input}")

    def test_true(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.path({"test": True}, "test")
        errcheck(
            error,
            'The "test" setting should be a file path, so you cannot set test=True',
        )

    def test_valid(_):
        config = {"test": "a/test/path"}
        _core.path(config, "test")
        value = config["test"]
        assert isinstance(value, Path)
        assert value == Path("a") / "test" / "path"

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.path({"test": 5}, "test")
        errcheck(error, 'Could not convert the "test" setting to a file path')


class TestOptionalPath:
    @pytest.mark.parametrize("input", (False, None))
    def test_disabled(_, input):
        config = {"test": input}
        _core.optional_path(config, "test")
        assert config["test"] is None

    def test_true(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.optional_path({"test": True}, "test")
        errcheck(
            error,
            'The "test" setting should be a file path, so you cannot set test=True',
        )

    def test_valid(_):
        config = {"test": "a/test/path"}
        _core.optional_path(config, "test")
        value = config["test"]
        assert isinstance(value, Path)
        assert value == Path("a") / "test" / "path"

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.optional_path({"test": 5}, "test")
        errcheck(error, 'Could not convert the "test" setting to a file path')


class TestOptionalPathOrConstant:
    def test_invalid(_, errcheck):
        config = {"test": [1, 2, 3]}
        with pytest.raises(TypeError) as error:
            _core.optional_path_or_constant(config, "test")
        errcheck(error, 'Could not convert the "test" setting to a file path')

    @pytest.mark.parametrize(
        "value, message", ((nan, "cannot be nan"), (inf, "must be finite"))
    )
    def test_invalid_constant(_, value, message, errcheck):
        config = {"test": value}
        with pytest.raises(ValueError) as error:
            _core.optional_path_or_constant(config, "test")
        errcheck(error, f'The "test" setting {message}')

    @pytest.mark.parametrize("value", (-9, -9.1, 0, 2.2, 5))
    def test_constant(_, value):
        config = {"test": value}
        _core.optional_path_or_constant(config, "test")
        assert config["test"] == value

    @pytest.mark.parametrize("value", (None, False))
    def test_disabled(_, value):
        config = {"test": value}
        _core.optional_path_or_constant(config, "test")
        assert config["test"] is None

    def test_path(_):
        config = {"test": "a/file/path"}
        _core.optional_path_or_constant(config, "test")
        assert config["test"] == Path("a/file/path")

    def test_true(_, errcheck):
        config = {"test": True}
        with pytest.raises(TypeError) as error:
            _core.optional_path_or_constant(config, "test")
        errcheck(
            error,
            'The "test" setting should be a file path, so you cannot set test=True',
        )


class TestStrlist:
    def test_none(_):
        config = {"properties": None}
        _core.strlist(config, "properties")
        assert config["properties"] == []

    def test_invalid(_, errcheck):
        config = {"properties": 5}
        with pytest.raises(TypeError) as error:
            _core.strlist(config, "properties")
        errcheck(error, 'The "properties" setting must be a list, tuple, or string')

    def test_element_not_string(_, errcheck):
        config = {"properties": ["some", 5, "text"]}
        with pytest.raises(TypeError) as error:
            _core.strlist(config, "properties")
        errcheck(
            error,
            'Each element of the "properties" setting must be a string',
            "properties[1] is not a string",
        )

    @pytest.mark.parametrize(
        "input, expected",
        (
            (["some", "text"], ["some", "text"]),
            (("some", "text"), ["some", "text"]),
            ("example", ["example"]),
        ),
    )
    def test_valid(_, input, expected):
        config = {"properties": input}
        _core.strlist(config, "properties")
        assert config["properties"] == expected


class TestOptionalString:
    def test_none(_):
        config = {"test": None}
        _core.optional_string(config, "test")
        assert config["test"] is None

    def test_str(_):
        config = {"test": "Here is some text"}
        _core.optional_string(config, "test")
        assert config["test"] == "Here is some text"

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.optional_string({"test": 5}, "test")
        errcheck(error, 'The "test" setting must be a string, or None')


class TestOption:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core._option({"test": 5}, "test", ["some", "allowed", "options"])
        errcheck(
            error,
            'The "test" setting should be one of the following strings: some, allowed, options',
        )

    def test_invalid_str(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core._option({"test": "invalid"}, "test", ["some", "allowed", "options"])
        errcheck(
            error,
            'The "test" setting should be one of the following strings: some, allowed, options',
        )

    @pytest.mark.parametrize(
        "option", ("some", "allowed", "options", "Some", "AlLoWeD")
    )
    def test_case(_, option):
        config = {"test": option}
        _core._option(config, "test", ["some", "allowed", "options"])
        assert config["test"] == option.lower()


class TestCheck:
    def test_none(_):
        config = {"test": None}
        _core.check(config, "test")
        assert config["test"] == "none"

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.check({"test": 5}, "test")
        errcheck(
            error,
            'The "test" setting should be one of the following strings: warn, error, none',
        )

    def test_invalid_str(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.check({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting should be one of the following strings: warn, error, none',
        )

    @pytest.mark.parametrize("option", ("warn", "error", "none", "None", "ErRoR"))
    def test_valid(_, option):
        config = {"test": option}
        _core.check(config, "test")
        assert config["test"] == option.lower()


class TestConfigStyle:
    def test_none(_):
        config = {"test": None}
        _core.config_style(config, "test")
        assert config["test"] == "none"

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.config_style({"test": 5}, "test")
        errcheck(
            error,
            'The "test" setting should be one of the following strings: default, full, empty, none',
        )

    def test_invalid_str(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.config_style({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting should be one of the following strings: default, full, empty, none',
        )

    @pytest.mark.parametrize(
        "option", ("default", "full", "empty", "none", "DeFaUlt", "FULL", "Empty")
    )
    def test_valid(_, option):
        config = {"test": option}
        _core.config_style(config, "test")
        assert config["test"] == option.lower()


class TestBoolean:
    @pytest.mark.parametrize("option", (True, False))
    def test_valid(_, option):
        config = {"test": option}
        _core.boolean(config, "test")
        assert isinstance(config["test"], bool)
        assert config["test"] == option

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.boolean({"test": 5}, "test")
        errcheck(error, 'The "test" setting must be a bool')


class TestScalar:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.scalar({"test": "invalid"}, "test")
        errcheck(error, 'The "test" setting must be an int or a float')

    def test_nan(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.scalar({"test": nan}, "test")
        errcheck(error, 'The "test" setting cannot be nan')

    @pytest.mark.parametrize("value", (inf, -inf))
    def test_inf(_, value, errcheck):
        with pytest.raises(ValueError) as error:
            _core.scalar({"test": value}, "test")
        errcheck(error, 'The "test" setting must be finite')

    @pytest.mark.parametrize("value", (-999, 0, 2000, 1.1, -9.8))
    def test_valid(_, value):
        config = {"test": value}
        _core.scalar(config, "test")
        assert config["test"] == value


class TestPositive:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.positive({"test": "invalid"}, "test")
        errcheck(error, 'The "test" setting must be an int or a float')

    def test_negative(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive({"test": -2}, "test")
        errcheck(error, 'The "test" setting must be positive')

    def test_valid(_):
        config = {"test": 2}
        _core.positive(config, "test")
        assert config["test"] == 2


class TestPositiveInteger:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.positive_integer({"test": "invalid"}, "test")
        errcheck(error, 'The "test" setting must be an int or a float')

    def test_negative(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive_integer({"test": -2}, "test")
        errcheck(error, 'The "test" setting must be positive')

    def test_valid_float(_):
        config = {"test": 2.0000}
        _core.positive(config, "test")
        assert config["test"] == 2

    def test_invalid_float(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive_integer({"test": 2.2}, "test")
        errcheck(error, 'The "test" setting must be an integer')


class TestBounded:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core._bounded({"test": "invalid"}, "test", 0, 100)
        errcheck(error, 'The "test" setting must be an int or a float')

    @pytest.mark.parametrize("value", (-5, 500))
    def test_out_of_bounds(_, value, errcheck):
        with pytest.raises(ValueError) as error:
            _core._bounded({"test": value}, "test", 0, 100)
        errcheck(error, 'The "test" setting must be between 0 and 100')

    def test_valid(_):
        config = {"test": 5}
        _core._bounded(config, "test", 0, 100)
        assert config["test"] == 5


class TestRatio:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.ratio({"test": "invalid"}, "test")
        errcheck(error, 'The "test" setting must be an int or a float')

    @pytest.mark.parametrize("value", (-0.000001, 1.0000001))
    def test_out_of_bounds(_, value, errcheck):
        with pytest.raises(ValueError) as error:
            _core.ratio({"test": value}, "test")
        errcheck(error, 'The "test" setting must be between 0 and 1')

    @pytest.mark.parametrize("value", (0, 0.5, 1))
    def test_valid(_, value):
        config = {"test": value}
        _core.ratio(config, "test")
        assert config["test"] == value


class TestAngle:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.angle({"test": "invalid"}, "test")
        errcheck(error, 'The "test" setting must be an int or a float')

    @pytest.mark.parametrize("value", (-0.000001, 360.0000001))
    def test_out_of_bounds(_, value, errcheck):
        with pytest.raises(ValueError) as error:
            _core.angle({"test": value}, "test")
        errcheck(error, 'The "test" setting must be between 0 and 360')

    @pytest.mark.parametrize("value", (0, 45.5, 180, 360))
    def test_valid(_, value):
        config = {"test": value}
        _core.angle(config, "test")
        assert config["test"] == value


class TestVector:
    def test_valid_scalar(_):
        config = {"test": 5}
        _core.vector(config, "test")
        assert config["test"] == [5]

    def test_invalid_scalar(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.vector({"test": 5}, "test", 2)
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple",
        )

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.vector({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple, int, float",
        )

    @pytest.mark.parametrize("vector", ([1, 2, 3, 4], (1, 2, 3, 4)))
    def test_valid(_, vector):
        config = {"test": vector}
        _core.vector(config, "test")
        assert config["test"] == [1, 2, 3, 4]

    def test_valid_length(_):
        config = {"test": [1, 2, 3, 4]}
        _core.vector(config, "test", 4)

    def test_invalid_length(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.vector({"test": [1, 2, 3]}, "test", 4)
        errcheck(
            error,
            'The "test" setting must have exactly 4 elements',
            "but it has 3 elements instead",
        )

    def test_invalid_element(_, errcheck):
        config = {"test": [1, 2, "invalid", 4]}
        with pytest.raises(TypeError) as error:
            _core.vector(config, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be ints and/or floats',
            "but test[2] is not",
        )

    def test_nan_element(_, errcheck):
        config = {"test": [1, 2, nan, 4]}
        with pytest.raises(ValueError) as error:
            _core.vector(config, "test")
        errcheck(
            error, 'The elements of the "test" setting cannot be nan', "test[2] is nan"
        )

    def test_inf_element(_, errcheck):
        config = {"test": [1, 2, inf, 4]}
        with pytest.raises(ValueError) as error:
            _core.vector(config, "test")
        errcheck(
            error, 'The elements of the "test" setting must be finite', "test[2] is not"
        )


class TestRatios:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.ratios({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple, int, float",
        )

    def test_not_ratio(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.ratios({"test": [0, 0.2, 3, 0.4]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be between 0 and 1',
            "test[2] (value = 3) is not",
        )

    def test_valid(_):
        config = {"test": [0, 0.25, 0.5, 1]}
        _core.ratios(config, "test")
        assert config["test"] == [0, 0.25, 0.5, 1]


class TestPositives:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.positives({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple, int, float",
        )

    def test_negative(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positives({"test": [1, 2, -3, 4]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be positive',
            "test[2] (value = -3) is not",
        )

    def test_valid(_):
        config = {"test": [1, 2, 3, 4]}
        _core.positives(config, "test")
        assert config["test"] == [1, 2, 3, 4]


class TestPositiveIntegers:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.positive_integers({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple, int, float",
        )

    def test_negative(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive_integers({"test": [1, 2, -3, 4]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be positive',
            "test[2] (value = -3) is not",
        )

    def test_not_integer(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive_integers({"test": [1, 2, 3.3, 4]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be integers',
            "test[2] (value = 3.3) is not",
        )

    def test_valid(_):
        config = {"test": [1, 2, 3, 4]}
        _core.positive_integers(config, "test")
        assert config["test"] == [1, 2, 3, 4]


class TestAscending:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core._ascending({"test": "invalid"}, "test", 1)
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple",
        )

    def test_wrong_length(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core._ascending({"test": [1, 2, 3, 4]}, "test", 3)
        errcheck(
            error,
            'The "test" setting must have exactly 3 elements, but it has 4 elements instead',
        )

    def test_not_ascending(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core._ascending({"test": [1, 2, 4, 3, 5]}, "test", 5)
        errcheck(
            error,
            'The elements of the "test" setting must be in ascending order',
            "test[3] (value = 3) is less than test[2] (value = 4)",
        )

    def test_valid(_):
        config = {"test": [1, 2, 3, 4]}
        _core._ascending(config, "test", 4)
        assert config["test"] == [1, 2, 3, 4]


class TestLimits:
    def test_wrong_length(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.limits({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple",
        )

    def test_not_ascending(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.limits({"test": [4, 2]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be in ascending order',
            "test[1] (value = 2) is less than test[0] (value = 4)",
        )

    def test_valid(_):
        config = {"test": [1, 2]}
        _core.limits(config, "test")
        assert config["test"] == [1, 2]


class TestPositiveLimits:
    def test_wrong_length(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.positive_limits({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple",
        )

    def test_not_ascending(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive_limits({"test": [4, 2]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be in ascending order',
            "test[1] (value = 2) is less than test[0] (value = 4)",
        )

    def test_not_positive(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.positive_limits({"test": [-2, 4]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be positive',
            "test[0] (value = -2) is not",
        )

    def test_valid(_):
        config = {"test": [1, 2]}
        _core.limits(config, "test")
        assert config["test"] == [1, 2]


class TestSeverityThresholds:
    def test_wrong_length(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.severity_thresholds({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple",
        )

    def test_not_ascending(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.severity_thresholds({"test": [4, 2, 5]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be in ascending order',
            "test[1] (value = 2) is less than test[0] (value = 4)",
        )

    def test_valid(_):
        config = {"test": [1, 2, 3]}
        _core.severity_thresholds(config, "test")
        assert config["test"] == [1, 2, 3]


class TestKfFill:
    def test_none(_):
        config = {"test": None}
        _core.kf_fill(config, "test")
        assert config["test"] == False

    @pytest.mark.parametrize("value", (True, False, 1.1, 5))
    def test_scalar(_, value):
        config = {"test": value}
        _core.kf_fill(config, "test")
        assert config["test"] == value

    def test_path(_):
        config = {"test": "a/file/path"}
        _core.kf_fill(config, "test")
        assert isinstance(config["test"], Path)
        assert config["test"] == Path("a") / "file" / "path"

    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.kf_fill({"test": {}}, "test")
        errcheck(error, 'Could not convert the "test" setting to a file path')


class TestDurations:
    def test_invalid(_, errcheck):
        with pytest.raises(TypeError) as error:
            _core.durations({"test": "invalid"}, "test")
        errcheck(
            error,
            'The "test" setting must be one of the following types',
            "list, tuple, int, float",
        )

    def test_not_allowed(_, errcheck):
        with pytest.raises(ValueError) as error:
            _core.durations({"test": [15, 30, 45]}, "test")
        errcheck(
            error,
            'The elements of the "test" setting must be 15, 30, and/or 60',
            "test[2] (value = 45) is not",
        )

    def test_valid(_):
        config = {"test": [15, 30, 60]}
        _core.durations(config, "test")
        assert config["test"] == [15, 30, 60]
