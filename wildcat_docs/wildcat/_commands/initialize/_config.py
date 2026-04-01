"""
Functions to help write a configuration file
----------
Main function:
    write           - Builds the configuration file

Misc:
    _how_to_full    - Writes a section indicating how to generate a full config file
    _heading        - Adds a section heading

Sections:
    _folders        - Adds an IO folder section
    _preprocess     - Adds a preprocessing section
    _assess         - Adds an assessment section
    _export         - Adds an export section
"""

from __future__ import annotations

import typing
from pathlib import Path

import wildcat._utils._defaults.defaults as _defaults
from wildcat._utils import _paths
from wildcat._utils._config import record

if typing.TYPE_CHECKING:
    from logging import Logger
    from typing import TextIO

    from wildcat.typing import ConfigType


def write(project: Path, inputs: str, style: ConfigType, log: Logger) -> None:
    "Initializes a configuration file"

    # Just exit if not creating a file
    if style == "none":
        return
    log.debug("    Writing configuration file")

    # Collect default values
    defaults = {
        name: getattr(_defaults, name)
        for name in dir(_defaults)
        if not name.startswith("_")
    }
    defaults["inputs"] = inputs

    # Convert default path strings to Path objects
    paths = _paths.folders() + _paths.preprocess.standard() + _paths.assess.all()
    for path in paths:
        defaults[path] = Path(defaults[path])

    # Initialize file with the wildcat version. Exit if empty. If default, show how
    # to get a full config file
    with open(project / "configuration.py", "w") as file:
        record.version(file, "Configuration file")
        if style == "empty":
            return
        elif style == "default":
            _how_to_full(file)

        # Add each section of the config file
        isfull = style == "full"
        _folders(file, defaults)
        _preprocess(file, defaults, isfull)
        _assess(file, defaults, isfull)
        _export(file, defaults, isfull)


#####
# Misc
#####


def _how_to_full(file: TextIO) -> None:
    "Adds a note indicating how to generate a full config file"
    file.write(
        "# Note that this file only lists the most common configuration values.\n"
        "# For the complete list of configuration values, run:\n"
        "#\n"
        "#     wildcat initialize --config full\n"
    )


def _heading(file: TextIO, title: str, description: list[str]) -> None:
    "Writes a section heading"

    # Build dynamic strings
    underline = "-" * len(title)
    footer = ""
    for line in description:
        footer = footer + f"# {line}\n"

    # Write the heading
    file.write(
        f"\n" f"#####\n" f"# {title}\n" f"# {underline}\n" f"{footer}" f"#####\n" "\n"
    )


#####
# Sections
#####


def _folders(file: TextIO, defaults: dict) -> None:
    "Adds IO folder config fields"

    _heading(
        file,
        "Folders",
        [
            "These values specify the paths to the default folders that wildcat should use",
            "when searching for files and saving results. Paths should either be absolute,",
            "or relative to the folder containing this configuration file.",
        ],
    )
    record.section(
        file,
        "IO Folders",
        ["inputs", "preprocessed", "assessment", "exports"],
        defaults,
        paths=defaults,
    )


def _preprocess(file: TextIO, defaults: dict, isfull: bool) -> None:
    "Adds preprocessing options to the config file"

    # Add the heading
    _heading(
        file,
        "Preprocessing",
        ["These values determine the implementation of the preprocessor."],
    )

    # Datasets
    record.section(
        file,
        "Datasets",
        ["perimeter", "dem", "dnbr", "severity", "kf", "evt"],
        defaults,
        paths=defaults,
    )

    # Optional datasets
    fields = ["retainments", "excluded"]
    if isfull:
        fields += ["included", "iswater", "isdeveloped"]
    record.section(file, "Optional Datasets", fields, defaults, defaults)

    # Perimeter and DEM
    record.section(file, "Perimeter", ["buffer_km"], defaults)
    if isfull:
        record.section(
            file, "DEM", ["resolution_limits_m", "resolution_check"], defaults
        )

    # dNBR
    fields = ["dnbr_limits"]
    if isfull:
        fields = ["dnbr_scaling_check", "constrain_dnbr"] + fields
    record.section(file, "dNBR", fields, defaults)

    # Burn severity
    fields = ["severity_thresholds"]
    if isfull:
        fields = ["severity_field", "contain_severity", "estimate_severity"] + fields
    record.section(file, "Burn severity", fields, defaults)

    # KF-factor
    fields = ["kf_field", "kf_fill", "kf_fill_field"]
    if isfull:
        fields = fields + ["constrain_kf", "max_missing_kf_ratio", "missing_kf_check"]
    record.section(file, "KF-factors", fields, defaults)

    # EVT Masks
    fields = ["water", "developed"]
    if isfull:
        fields += ["excluded_evt"]
    record.section(file, "EVT Masks", fields, defaults)


def _assess(file: TextIO, defaults: dict, isfull: bool) -> None:
    "Adds assessment options to the config file"

    # Add the heading
    _heading(file, "Assessment", ["Values used to implement the hazard assessment."])

    # Required rasters
    if isfull:
        record.section(
            file,
            "Required rasters",
            ["perimeter_p", "dem_p", "dnbr_p", "severity_p", "kf_p"],
            defaults,
            paths=defaults,
        )

        # Optional masks
        record.section(
            file,
            "Optional raster masks",
            ["retainments_p", "excluded_p", "included_p", "iswater_p", "isdeveloped_p"],
            defaults,
            paths=defaults,
        )

        # Unit conversions
        record.section(file, "Unit conversions", ["dem_per_m"], defaults)

    # Delineation
    record.section(
        file,
        "Network Delineation",
        ["min_area_km2", "min_burned_area_km2", "max_length_m"],
        defaults,
    )

    # Filtering
    fields = [
        "max_area_km2",
        "max_exterior_ratio",
        "min_burn_ratio",
        "min_slope",
        "max_developed_area_km2",
        "max_confinement",
    ]
    if isfull:
        fields += ["confinement_neighborhood", "flow_continuous"]
    record.section(file, "Filtering", fields, defaults)

    # Specific IDs
    record.section(file, "Remove specific segments", ["remove_ids"], defaults)

    # Modeling
    record.section(
        file,
        "Modeling parameters",
        ["I15_mm_hr", "volume_CI", "durations", "probabilities"],
        defaults,
    )

    # Basins
    if isfull:
        record.section(
            file, "Basins", ["locate_basins", "parallelize_basins"], defaults
        )


def _export(file: TextIO, defaults: dict, isfull: bool) -> None:

    # Heading and output files
    _heading(file, "Export", ["Settings for exporting saved assessment results"])
    record.section(
        file, "Output files", ["format", "export_crs", "prefix", "suffix"], defaults
    )

    # Properties
    if isfull:
        record.section(
            file,
            "Properties",
            ["properties", "exclude_properties", "include_properties"],
            defaults,
        )
        record.section(
            file,
            "Property formatting",
            ["order_properties", "clean_names", "rename"],
            defaults,
        )
    else:
        record.section(file, "Properties", ["properties", "rename"], defaults)
