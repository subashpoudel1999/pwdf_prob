"""
Builds the CLI parser for the "assess" command
----------
Main function
    parser  - Adds the "assess" parser to the subparsers

Dataset options:
    _datasets   - Adds a dataset group
    _required   - Adds the required datasets
    _optional   - Adds optional raster masks

Option groups:
    _dem_units      - Add option for DEM units per meter
    _delineation    - Adds options for network delineation
    _filtering      - Add filtering options
    _remove_ids     - Adds option to remove specific IDs
    _modeling       - Adds hazard modeling parameters
    _basins         - Options for locating basins
"""

from __future__ import annotations

import typing

from wildcat._cli._parsers._utils import create_subcommand, io_folders, logging, switch

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


def parser(subparsers) -> None:
    "Builds the parser for the assess command"

    # Initialize with project folder, IO folders, logging, data files
    parser = create_subcommand(subparsers, "assess")
    io_folders(parser, "preprocessed", "assessment")
    logging(parser)

    # Option groups
    _required(parser)
    _optional(parser)
    _dem_units(parser)
    _delineation(parser)
    _filtering(parser)
    _remove_ids(parser)
    _modeling(parser)
    _basins(parser)


#####
# Dataset paths
#####


def _datasets(
    parser: ArgumentParser,
    title: str,
    description: str,
    datasets: dict[str, str],
    extra_metavar: str = "",
) -> None:
    "Adds a dataset argument group"

    # Create the group
    parser = parser.add_argument_group(f"{title} Datasets", description)

    # Add the dataset options
    for name, description in datasets.items():
        parser.add_argument(
            f"--{name}-p",
            metavar=f"PATH{extra_metavar}",
            help=description,
        )


def _required(parser: ArgumentParser) -> None:
    "Datasets required for the assessment"

    datasets = {
        "perimeter": "Fire perimeter raster",
        "dem": "Digital elevation model (DEM) raster",
        "dnbr": "Differenced normalized burn ratio (dNBR) raster",
        "severity": "BARC4-like burn severity raster",
        "kf": "KF-factor raster",
    }
    description = (
        "Paths to preprocessed raster datasets used to run the assessment.\n"
        "Paths should either be absolute, or relative to the 'preprocessed' folder."
    )
    _datasets(parser, "Required", description, datasets)


def _optional(parser: ArgumentParser) -> None:
    "Optional raster masks for the assessment"

    datasets = {
        "retainments": "Retainment feature locations",
        "excluded": "Areas excluded during network delineation",
        "included": "Areas included during filtering",
        "iswater": "Water body mask",
        "isdeveloped": "Human development mask",
    }
    description = (
        "Paths to optional preprocessed raster masks used to run the assessment.\n"
        "Paths should either be absolute, or relative to the 'preprocessed' folder.\n"
        "Alternatively, set a path to None to exclude the mask from the assessment."
    )
    _datasets(parser, "Optional Masks", description, datasets, extra_metavar=" | None")


#####
# Argument groups
#####


def _dem_units(parser: ArgumentParser) -> None:
    "Adds option for DEM units per meter"
    parser = parser.add_argument_group("DEM Units")
    parser.add_argument(
        "--dem-per-m",
        type=float,
        metavar="FACTOR",
        help="The number of DEM elevation units per meter",
    )


def _delineation(parser: ArgumentParser) -> None:
    "Add delineation group with min area, min burned area, and max length"

    # Create group and get help text descriptions
    parser = parser.add_argument_group("Network delineation")
    fields = {
        "min-area-km2": ("Minimum catchment area in square kilometers (km²)", "AREA"),
        "min-burned-area-km2": (
            "Minimum burned catchment area in square kilometers (km²)",
            "AREA",
        ),
        "max-length-m": ("Maximum stream segment length in meters", "LENGTH"),
    }

    # Add each option to the group
    for field, (description, metavar) in fields.items():
        parser.add_argument(
            f"--{field}",
            type=float,
            metavar=metavar,
            help=description,
        )


def _filtering(parser: ArgumentParser) -> None:
    "Adds filtering options including parameters and flow continuity"

    # Create group and get help text descriptions
    parser = parser.add_argument_group("Filtering")
    thresholds = {
        "max-area-km2": ["Maximum catchment area in square kilometers (km²)", "AREA"],
        "max-exterior-ratio": [
            "Maximum proportion of catchment outside the fire perimeter (from 0 to 1)",
            "RATIO",
        ],
        "min-burn-ratio": [
            "Minimum proportion of burned catchment (from 0 to 1)",
            "RATIO",
        ],
        "min-slope": ["Minimum slope gradient", "GRADIENT"],
        "max-developed-area-km2": [
            "Maximum developed catchment area in square kilometers (km²)",
            "AREA",
        ],
        "max-confinement": ["Maximum confinement angle in degrees", "ANGLE"],
    }

    # Add each filtering parameter to the group
    for name, (description, metavar) in thresholds.items():
        parser.add_argument(f"--{name}", type=float, metavar=metavar, help=description)

    # Add pixel neighborhood option for confinement angles
    parser.add_argument(
        "--neighborhood",
        type=int,
        metavar="N",
        help="Pixel neighborhood used to compute confinement angles",
    )

    # Add flow continuity and perimeter options
    switch(
        parser,
        "filter-in-perimeter",
        "Require segments in the fire perimeter to pass physical filtering checks",
    )
    switch(parser, "not-continuous", "Do not preserve flow continuity when filtering")


def _remove_ids(parser: ArgumentParser) -> None:
    "Adds option to remove specific IDs"

    parser = parser.add_argument_group("Remove IDs")
    parser.add_argument(
        "--remove-ids",
        type=int,
        nargs="*",
        metavar="ID",
        help="IDs of segments that should be removed from the network after filtering",
    )


def _modeling(parser: ArgumentParser) -> None:
    "Add hazard modeling option group"

    # Create group and get CLI help text descriptions
    parser = parser.add_argument_group("Hazard Modeling")
    fields = {
        "I15-mm-hr": [
            "Peak 15-minute rainfall intensities (in millimeters per hour) used to estimate likelihood, volume, and hazard",
            "INTENSITY",
        ],
        "volume-CI": [
            "Confidence intervals to compute for volume estimates (from 0 to 1)",
            "CI",
        ],
        "durations": [
            "Rainfall durations (in minutes) used to estimate rainfall thresholds",
            "DURATION",
        ],
        "probabilities": [
            "Probability levels used to estimate rainfall thresholds (from 0 to 1)",
            "P",
        ],
    }

    # Add each parameter to the group
    for field, (description, metavar) in fields.items():
        parser.add_argument(
            f"--{field}", type=float, nargs="*", metavar=metavar, help=description
        )


def _basins(parser: ArgumentParser) -> None:
    "Adds basins group with parallelization options"

    parser = parser.add_argument_group("Basins")
    parser = parser.add_mutually_exclusive_group()
    switch(parser, "parallel", "Use multiple CPUs to locate outlet basins")
    switch(parser, "no-basins", "Do not locate outlet basins")
