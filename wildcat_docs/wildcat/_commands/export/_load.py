"""
Functions that load saved assessment files:
----------
These functions load values that were saved in the assessment folder. The user
should not have altered the files in this folder.
----------
Main Functions:
    parameters  - Loads the hazard modeling parameters from the configuration.txt file
    results     - Load the CRS, schema, segments, basins, and outlets from the assessment

Utilities:
    _geojson    - Converts fiona records to GeoJSON-like dicts
    _segments   - Loads the saved segments, as well as the CRS and schema
    _features   - Optionally loads basins or outlets
"""

from __future__ import annotations

import typing

import fiona

from wildcat._utils import _config, _parameters, _validate
from wildcat.errors import ConfigRecordError

if typing.TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    import fiona.model

    from wildcat.typing._export import CRS, Config, Records, Results, Schema

    FionaFeatures = list[fiona.model.Feature]


def parameters(assessment: Path, log: Logger) -> Config:
    "Loads the modeling parameters from the recorded configuration.txt file"

    # Require an existing file
    log.info("Loading assessment parameters")
    path = assessment / "configuration.txt"
    if not path.exists():
        raise FileNotFoundError(
            "Could not locate the configuration.txt record for the assessment. "
            f"It may have been deleted.\nMissing Path: {path}"
        )
    elif not path.is_file():
        raise ConfigRecordError(
            "The recorded configuration.txt is not a file. The assessment results "
            "may have been altered."
        )

    # Compile the namespace
    try:
        record = _config.load(path)
    except Exception as error:
        raise ConfigRecordError(
            "Could not load the recorded configuration.txt file for the assessment. "
            "The assessment results may have been altered."
        ) from error

    # Require hazard modeling parameters
    for parameter in _parameters.names():
        if parameter not in record:
            raise ConfigRecordError(
                "The recorded configuration.txt file for the assessment is "
                f'missing the "{parameter}" parameter. The assessment results may '
                "have been altered."
            )

    # Validate the parameters
    try:
        _validate.model_parameters(record)
    except Exception as error:
        raise ConfigRecordError(
            "The recorded configuration.txt file for the assessment is invalid. "
            "The assessment results may have been altered."
        ) from error
    return record


def results(assessment: Path, log: Logger) -> Results:

    log.info("Loading assessment results")
    crs, schema, segments = _segments(assessment, log)
    basins = _features(assessment, "basins", log)
    outlets = _features(assessment, "outlets", log)
    return crs, schema, segments, basins, outlets


def _geojson(records: FionaFeatures) -> list[dict]:
    "Converts fiona records to geojson-like dicts"
    return [record.__geo_interface__ for record in records]


def _segments(assessment: Path, log: Logger) -> tuple[CRS, Schema, Records]:
    "Loads the segments as list of GeoJSON-like dicts"

    # Path must be an existing file
    log.debug("    Loading segments")
    path = assessment / "segments.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"Could not locate the segments.geojson file for the assessment. "
            f"It may have been deleted\nMissing Path: {path}"
        )
    elif not path.is_file():
        raise TypeError(
            "The saved segments.geojson is not a file. The assessment results "
            "may have been altered."
        )

    # Load from file
    try:
        with fiona.open(path) as file:
            crs = file.crs
            schema = file.schema
            records = list(file)

    # Informative error if failed
    except Exception as error:
        raise RuntimeError(
            "Could not load the saved segments.geojson file for the assessment. "
            "The assessment results may have been altered."
        ) from error

    # Return with CRS, schema, and geojson-like records
    return crs, schema, _geojson(records)


def _features(assessment: Path, name: str, log: Logger) -> Records | None:
    "Loads the basins or outlets, if available"

    # Just exit if the path doesn't exist
    path = assessment / f"{name}.geojson"
    if not path.exists():
        return

    # Attempt to load from file
    log.debug(f"    Loading {name}")
    try:
        with fiona.open(path) as file:
            records = list(file)

    # Basins and outlets are not mandatory. If file loading fails, log an error
    # and report the stack trace but let the routine continue
    except Exception:
        log.exception(
            f"\n"
            f"ERROR: Could not load the saved {name}.geojson file for the assessment.\n"
            f"    The assessment results may have been altered. Skipping {name} export.\n"
        )
        log.error("")  # Adds a trailing newline
        return

    # Return as geojson-like dicts
    return _geojson(records)
