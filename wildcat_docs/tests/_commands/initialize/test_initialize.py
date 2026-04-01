import os

import pytest

from wildcat._cli import main
from wildcat._commands.initialize import _initialize


def check_empty(path):
    assert os.listdir(path) == []


class TestInputsFolder:
    def test_none(_, project, logcheck):
        output = _initialize._inputs_folder(project, None, logcheck.log)
        assert output == "inputs"
        check_empty(project)
        logcheck.check([])

    def test(_, project, logcheck):
        path = project / "test"
        assert not path.exists()
        output = _initialize._inputs_folder(project, path.name, logcheck.log)
        assert output == path.name
        assert path.exists()
        assert path.is_dir()
        check_empty(path)
        logcheck.check([("DEBUG", f"    Initializing {path.name} subfolder")])


class TestValidateProject:
    def test_none(_, project, logcheck):
        cwd = project / "test"
        cwd.mkdir()
        os.chdir(cwd)
        output = _initialize._validate_project(None, logcheck.log)
        assert output == cwd
        check_empty(cwd)
        logcheck.check([("DEBUG", f"    Located project folder: {cwd}")])

    def test_does_not_exist(_, project, logcheck):
        path = project / "missing"
        output = _initialize._validate_project(path, logcheck.log)
        assert output == path
        assert path.exists()
        check_empty(path)
        logcheck.check([("DEBUG", f"    Creating project folder: {path}")])

    def test_file(_, project, errcheck, logcheck):
        path = project / "test.txt"
        with open(path, "w") as file:
            file.write("a file")
        with pytest.raises(ValueError) as error:
            _initialize._validate_project(path, logcheck.log)
        errcheck(error, "The project path is not a directory", f"Project path: {path}")

    def test_not_empty(_, project, errcheck, logcheck):
        path = project / "test.txt"
        with open(path, "w") as file:
            file.write("a file")
        with pytest.raises(FileExistsError) as error:
            _initialize._validate_project(project, logcheck.log)
        errcheck(
            error,
            "Cannot initialize project because the project folder is not empty",
            f"Project path: {project}",
        )

    def test_existing_empty(_, project, logcheck):
        path = project / "empty"
        path.mkdir()
        output = _initialize._validate_project(path, logcheck.log)
        assert output == path
        assert path.exists()
        check_empty(path)
        logcheck.check([("DEBUG", f"    Located project folder: {path}")])


class TestInitialize:
    def test_no_config(_, project, logcheck):
        logcheck.start("wildcat.initialize")
        _initialize.initialize(project, "none")
        assert os.listdir(project) == ["inputs"]
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Initializing inputs subfolder"),
            ]
        )

    def test_empty_config(_, project, outtext, empty_config, logcheck):
        logcheck.start("wildcat.initialize")
        _initialize.initialize(project, "empty")
        assert sorted(os.listdir(project)) == sorted(["configuration.py", "inputs"])
        assert outtext(project / "configuration.py") == empty_config
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Initializing inputs subfolder"),
                ("DEBUG", "    Writing configuration file"),
            ]
        )

    def test_default_config(_, project, outtext, default_config, logcheck):
        logcheck.start("wildcat.initialize")
        _initialize.initialize(project, "default")
        assert sorted(os.listdir(project)) == sorted(["configuration.py", "inputs"])
        assert outtext(project / "configuration.py") == default_config
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Initializing inputs subfolder"),
                ("DEBUG", "    Writing configuration file"),
            ]
        )

    def test_full_config(_, project, outtext, full_config, logcheck):
        logcheck.start("wildcat.initialize")
        _initialize.initialize(project, "full")
        assert sorted(os.listdir(project)) == sorted(["configuration.py", "inputs"])
        assert outtext(project / "configuration.py") == full_config
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Initializing inputs subfolder"),
                ("DEBUG", "    Writing configuration file"),
            ]
        )

    def test_no_inputs(_, project, outtext, empty_config, logcheck):
        logcheck.start("wildcat.initialize")
        _initialize.initialize(project, "empty", None)
        assert os.listdir(project) == ["configuration.py"]
        assert outtext(project / "configuration.py") == empty_config
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Writing configuration file"),
            ]
        )

    def test_custom_inputs(_, project, outtext, default_config, logcheck):
        logcheck.start("wildcat.initialize")
        _initialize.initialize(project, "default", "test")
        assert sorted(os.listdir(project)) == sorted(["configuration.py", "test"])
        config = default_config.replace('r"inputs"', 'r"test"')
        assert outtext(project / "configuration.py") == config
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Initializing test subfolder"),
                ("DEBUG", "    Writing configuration file"),
            ]
        )

    def test_cli(_, project, outtext, default_config, CleanCLI, logcheck):
        logcheck.start("wildcat.initialize")
        with CleanCLI:
            main(["initialize", "--config", "default", str(project)])

        assert sorted(os.listdir(project)) == sorted(["configuration.py", "inputs"])
        assert outtext(project / "configuration.py") == default_config
        logcheck.check(
            [
                ("INFO", "Initializing project"),
                ("DEBUG", f"    Located project folder: {project}"),
                ("DEBUG", "    Initializing inputs subfolder"),
                ("DEBUG", "    Writing configuration file"),
            ]
        )
