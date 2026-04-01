import logging
import sys
from pathlib import Path

import pytest

#####
# Logs, Errors, Config
#####


class _CleanCLI:
    "Resets logging and traceback limits after running a CLI command"

    def __init__(self) -> None:
        return

    def __enter__(self) -> None:
        return

    def __exit__(self, exc_type, exc_value, exc_tb):
        sys.tracebacklimit = 1000
        logger = logging.getLogger("wildcat.initialize")
        for handler in logger.handlers:
            logger.removeHandler(handler)


@pytest.fixture
def CleanCLI():
    return _CleanCLI()


class LogCheck:
    def __init__(self, caplog) -> None:
        self.name = None
        self.log = None
        self.caplog = caplog
        self.start("test.log")

    def start(self, name):
        self.name = name
        self.log = logging.getLogger(self.name)
        self.caplog.set_level(logging.DEBUG, logger=self.name)

    def check(self, records):
        records = [
            (self.name, getattr(logging, level), message) for level, message in records
        ]
        assert self.caplog.record_tuples == records


@pytest.fixture
def logcheck(caplog):
    return LogCheck(caplog)


def _check_error(error, *strings):
    message = error.value.args[0]
    for string in strings:
        assert string in message


@pytest.fixture
def errcheck():
    return _check_error


def _outtext(path):
    with open(path) as f:
        return f.read()


@pytest.fixture
def outtext():
    return _outtext


#####
# File Paths
#####


@pytest.fixture
def project(tmp_path):
    project = Path(tmp_path) / "project"
    project.mkdir()
    return project


@pytest.fixture
def missing(project):
    return project / "missing"


def _folder(project, name):
    path = project / name
    path.mkdir()
    return path


@pytest.fixture
def inputs(project):
    return _folder(project, "inputs")


@pytest.fixture
def outputs(project):
    return _folder(project, "outputs")


def _make_file(folder, name):
    path = folder / name
    with open(path, "w") as file:
        file.write("An existing file")
    return path


@pytest.fixture
def raster(inputs):
    return _make_file(inputs, "test-raster.tif")


@pytest.fixture
def vector(inputs):
    return _make_file(inputs, "test-vector.shp")
