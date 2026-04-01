import logging
from pathlib import Path

from pyproj import CRS

from wildcat._utils import _setup


def test(project, logcheck):

    path = project / "configuration.py"
    with open(path, "w") as file:
        file.write('exports = "test_config_file"')

    locals = {
        # Folders
        "project": project,
        "config": None,
        "assessment": None,
        "exports": None,
        # Output files
        "prefix": None,
        "suffix": "test",
        "format": "Shapefile",
        "export_crs": 4326,
        # Properties
        "properties": ["test", "properties"],
        "exclude_properties": None,
        "include_properties": None,
        # Formatting
        "order_properties": None,
        "clean_names": True,
        "rename": {},
    }
    logcheck.start("wildcat.export")
    config, log = _setup.command("export", "Test Heading", locals)
    assert config == {
        # Folders
        "project": project,
        "config": project / "configuration.py",
        "assessment": Path("assessment"),
        "exports": Path("test_config_file"),
        # Output files
        "prefix": "",
        "suffix": "test",
        "format": "Shapefile",
        "export_crs": CRS(4326),
        # Properties
        "properties": ["test", "properties"],
        "exclude_properties": [],
        "include_properties": [],
        # Formatting
        "order_properties": True,
        "clean_names": True,
        "rename": {},
    }

    assert isinstance(log, logging.Logger)
    assert log.name == "wildcat.export"
    logcheck.check(
        [
            ("INFO", "----- Test Heading -----"),
            ("INFO", "Parsing configuration"),
            ("DEBUG", "    Locating project folder"),
            ("DEBUG", f"        {project}"),
            ("DEBUG", "    Reading configuration file"),
            ("DEBUG", f"        {project / 'configuration.py'}"),
        ]
    )
