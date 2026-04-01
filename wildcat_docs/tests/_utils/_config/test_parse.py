from pathlib import Path

import pytest

from wildcat._utils._config import _parse
from wildcat._utils._defaults import defaults
from wildcat.errors import ConfigError

#####
# Testing fixtures
#####


@pytest.fixture
def cvals():
    return {
        "dem": "some text",
        "buffer_km": 2.2,
        "water": [1, 2, 3.3],
        "constrain_dnbr": False,
        "config": None,
    }


@pytest.fixture
def cpath(tmp_path):
    return Path(tmp_path) / "configuration.py"


@pytest.fixture
def config(cpath, cvals):
    with open(cpath, "w") as file:
        for name, value in cvals.items():
            if isinstance(value, str):
                value = f"'{value}'"
            line = f"{name} = {value}\n"
            file.write(line)
    return cpath


def check(output, expected):
    for name, value in expected.items():
        if name != "config":
            assert name in output
            assert output[name] == value


#####
# Tests
#####


class TestParse:
    def test_cli(_, config, cvals, logcheck):
        locals = cvals.copy()
        for name in locals:
            if name != "config":
                locals[name] = "override"
        locals["project"] = config.parent
        output = _parse.parse(locals, logcheck.log)
        check(output, locals)
        logcheck.check(
            [
                ("INFO", "Parsing configuration"),
                ("DEBUG", "    Locating project folder"),
                ("DEBUG", f"        {config.parent}"),
                ("DEBUG", "    Reading configuration file"),
                ("DEBUG", f"        {config}"),
            ]
        )

    def test_default_file(_, config, cvals, logcheck):
        locals = {name: None for name in cvals}
        locals["project"] = config.parent
        output = _parse.parse(locals, logcheck.log)
        check(output, cvals)
        logcheck.check(
            [
                ("INFO", "Parsing configuration"),
                ("DEBUG", "    Locating project folder"),
                ("DEBUG", f"        {config.parent}"),
                ("DEBUG", "    Reading configuration file"),
                ("DEBUG", f"        {config}"),
            ]
        )

    def test_alternate_file(_, config, cvals, logcheck):
        locals = {name: None for name in cvals}
        locals["project"] = config.parent

        alternate = config.parent / "alternate.py"
        alternate.write_text(config.read_text())
        locals["config"] = alternate

        output = _parse.parse(locals, logcheck.log)
        check(output, cvals)
        logcheck.check(
            [
                ("INFO", "Parsing configuration"),
                ("DEBUG", "    Locating project folder"),
                ("DEBUG", f"        {config.parent}"),
                ("DEBUG", "    Reading configuration file"),
                ("DEBUG", f"        {alternate}"),
            ]
        )

    def test_no_file(_, cpath, cvals, logcheck):
        locals = {name: None for name in cvals}
        locals["project"] = cpath.parent
        output = _parse.parse(locals, logcheck.log)
        expected = {name: getattr(defaults, name) for name in cvals if name != "config"}
        check(output, expected)
        logcheck.check(
            [
                ("INFO", "Parsing configuration"),
                ("DEBUG", "    Locating project folder"),
                ("DEBUG", f"        {cpath.parent}"),
                ("DEBUG", "    No configuration file detected"),
            ]
        )


class TestLocateProject:
    def test_none(_, logcheck):
        output = _parse._locate_project(None, logcheck.log)
        assert output == Path.cwd()
        logcheck.check(
            [
                ("INFO", "Parsing configuration"),
                ("DEBUG", "    Locating project folder"),
                ("DEBUG", f"        {output}"),
            ]
        )

    def test_provided(_, project, logcheck):
        output = _parse._locate_project(project, logcheck.log)
        assert output == project
        logcheck.check(
            [
                ("INFO", "Parsing configuration"),
                ("DEBUG", "    Locating project folder"),
                ("DEBUG", f"        {output}"),
            ]
        )

    def test_invalid(_, errcheck, logcheck):
        with pytest.raises(TypeError) as error:
            _parse._locate_project(5, logcheck.log)
        errcheck(error, 'Could not convert "project" to a folder path.')

    def test_missing(_, missing, errcheck, logcheck):
        with pytest.raises(FileNotFoundError) as error:
            _parse._locate_project(missing, logcheck.log)
        errcheck(error, "The project folder does not exist")

    def test_not_folder(_, project, errcheck, logcheck):
        path = project / "test.txt"
        with open(path, "w") as file:
            file.write("a file")
        with pytest.raises(ValueError) as error:
            _parse._locate_project(path, logcheck.log)
        errcheck(error, "The project path is not a folder")


class TestLocateConfig:
    def test_none(_, tmp_path):
        output = _parse._locate_config(tmp_path, None)
        assert output == tmp_path / "configuration.py"

    def test_invalid(_, tmp_path, errcheck):
        with pytest.raises(TypeError) as error:
            _parse._locate_config(tmp_path, 5)
        errcheck(error, "Could not convert the `config` input to a file path.")

    def test_absolute(_, tmp_path, config):
        path = config.resolve()
        output = _parse._locate_config(tmp_path, path)
        assert output == path

    def test_relative(_, config):
        output = _parse._locate_config(config.parent, config.name)
        assert output == config.parent / config.name

    def test_not_exist(_, cpath, errcheck):
        with pytest.raises(FileNotFoundError) as error:
            _parse._locate_config(cpath.parent, cpath.name)
        errcheck(error, "The configuration file is missing")

    def test_not_file(_, cpath, errcheck):
        with pytest.raises(ValueError) as error:
            _parse._locate_config(cpath.parents[1], cpath.parent)
        errcheck(error, "The configuration path is not a file")


class TestParseConfigFile:
    def test_exists(_, config, cvals, logcheck):
        path = config.parent / "configuration.py"
        output = _parse._parse_config_file(path, logcheck.log)
        check(output, cvals)
        logcheck.check(
            [("DEBUG", "    Reading configuration file"), ("DEBUG", f"        {path}")]
        )

    def test_missing(_, cpath, logcheck):
        path = cpath.parent / "configuration.py"
        output = _parse._parse_config_file(path, logcheck.log)
        assert output == {}
        logcheck.check([("DEBUG", "    No configuration file detected")])


class TestLoad:
    def test_valid(_, config, cvals):
        output = _parse.load(config)
        check(output, cvals)

    def test_syntax_error(_, cpath, errcheck):
        with open(cpath, "w") as file:
            file.write("a = [1, 2, }\n")
        with pytest.raises(ConfigError) as error:
            _parse.load(cpath)
        errcheck(error, "There is a syntax error in your configuration file")

    def test_exit(_, cpath, errcheck):
        with open(cpath, "w") as file:
            file.write("import sys\nsys.exit()\n")
        with pytest.raises(ConfigError) as error:
            _parse.load(cpath)
        errcheck(
            error, "The configuration file (or a module it imported) called sys.exit()"
        )

    def test_exception(_, cpath, errcheck):
        with open(cpath, "w") as file:
            file.write('raise ValueError("test")\n')
        with pytest.raises(ConfigError) as error:
            _parse.load(cpath)
        errcheck(error, "There is a programmable error in your configuration file")
