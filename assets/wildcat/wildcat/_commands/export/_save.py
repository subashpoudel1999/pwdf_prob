"""
Functions that save exported files
----------
Main Functions:
    results             - Saves the segments, basins, and outlets
    config              - Saves the configuration.txt file for the export

Utilities:
    _property_schema    - Returns the property schema for the exported results
    _features           - Exports a collection of vector features to the indicated format
"""

from __future__ import annotations

import typing

import fiona

from wildcat._utils import _extensions
from wildcat._utils._config import record

if typing.TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from fiona.crs import CRS

    from wildcat.typing._export import (
        Config,
        PropNames,
        PropSchema,
        Records,
        Results,
        Schema,
    )


def results(
    exports: Path, config: Config, results: Results, names: PropNames, log: Logger
) -> None:
    "Exports the segments, basins, and outlets to the desired format"

    # Start log and extract results
    log.info(f'Exporting results to {config["format"]}')
    crs, schema, segments, basins, outlets = results

    # Finalize property schema, then export files
    pschema = _property_schema(names, schema)
    _features(segments, exports, config, crs, log, names, pschema)
    _features(basins, exports, config, crs, log, names, pschema)
    _features(outlets, exports, config, crs, log)


def _property_schema(names: PropNames, schema: Schema) -> PropSchema:
    "Builds the property schema for the export"
    return {name: schema["properties"][raw] for raw, name in names.items()}


def _features(
    features: Records | None,
    exports: Path,
    config: Config,
    crs: CRS,
    log: Logger,
    names: PropNames = {},
    pschema: PropSchema = {},
) -> None:
    "Exports saved features to the indicated file format"

    # Just exit if the records don't exist
    if features is None:
        return

    # Extract config values
    prefix = config["prefix"]
    suffix = config["suffix"]
    format = config["format"]

    # Parse the geometry and file name.
    geometry_type = features[0]["geometry"]["type"]
    filenames = {"Point": "outlets", "LineString": "segments", "Polygon": "basins"}
    name = filenames[geometry_type]
    log.debug(f"    Exporting {name}")

    # Determine the file path
    filename = f"{prefix}{name}{suffix}"
    ext = _extensions.from_format(format)
    path = exports / f"{filename}{ext}"

    # Build the records
    records = []
    for feature in features:
        geometry = {
            "type": geometry_type,
            "coordinates": feature["geometry"]["coordinates"],
        }
        properties = {name: feature["properties"][raw] for raw, name in names.items()}
        record = {"geometry": geometry, "properties": properties}
        records.append(record)

    # Save
    schema = {"geometry": geometry_type, "properties": pschema}
    with fiona.open(path, "w", driver=format, crs=crs, schema=schema) as file:
        file.writerecords(records)


def config(exports: Path, config: Config, log: Logger) -> None:
    "Save the configuration settings for the export"

    # Start log and get path
    log.debug("    Saving configuration.txt")
    path = exports / "configuration.txt"

    # Finalize CRS
    if config["export_crs"] is not None:
        config["export_crs"] = config["export_crs"].name

    # Write each section
    with open(path, "w") as file:
        record.version(file, "Export configuration")
        record.section(
            file, "Output files", ["format", "export_crs", "prefix", "suffix"], config
        )
        record.section(file, "Properties", ["properties", "order_properties"], config)
        record.section(file, "Property names", ["clean_names", "rename"], config)
