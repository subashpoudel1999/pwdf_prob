"""
Builds the CLI parser for the "preprocess" command
----------
Main function:
    parser  - Adds the "preprocess" parser to the subparsers

Dataset Groups:
    _datasets       - Adds a dataset argument group
    _required       - Adds required datasets
    _recommended    - Adds recommended datasets
    _optional       - Adds optional datasets

Preprocessing Options:
    _check      - Adds a warn, error, none option
    _perimeter  - Adds the perimeter group with a buffer option
    _dem        - Adds a DEM group with a resolution check option
    _dnbr       - Adds the dNBR group with scaling check and valid range options
    _severity   - Adds the severity group with data field and dNBR estimation options
    _kf         - Adds the KF-factor group with data field and positive constraint options
    _evt_mask   - Adds the EVT group with water, development, and excluded options
"""

from __future__ import annotations

import typing

from wildcat._cli._parsers._utils import create_subcommand, io_folders, logging, switch

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


def parser(subparsers) -> None:
    "Creates the parser for the preprocess command"

    # Initialize with project folder, IO folders, logging
    parser = create_subcommand(subparsers, "preprocess")
    io_folders(parser, "inputs", "preprocessed")
    logging(parser)

    # Dataset collections
    _required(parser)
    _recommended(parser)
    _optional(parser)

    # Specific dataset options
    _perimeter(parser)
    _dem(parser)
    _dnbr(parser)
    _severity(parser)
    _kf(parser)
    _evt_masks(parser)


#####
# Dataset collections
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
            f"--{name}",
            metavar=f"PATH{extra_metavar}",
            help=description,
        )


def _required(parser: ArgumentParser) -> None:
    "Required datasets for the preprocessor"

    datasets = {
        "perimeter": "Fire burn perimeter (polygons or raster)",
        "dem": "Digital elevation model (raster)",
    }
    description = (
        "Paths to datasets required to run the preprocessor. Paths should either\n"
        "be absolute, or relative to the 'inputs' folder."
    )
    _datasets(parser, "Required", description, datasets)


def _recommended(parser: ArgumentParser) -> None:
    "Recommended datasets for the assessment"

    # Create group
    description = (
        "Datasets recommended for most hazard assessments. File paths should\n"
        "either be absolute, or relative to the 'inputs' folder. The dNBR, severity,\n"
        "and kf datasets also support using a constant value throughout the watershed.\n"
        "Set a dataset to None to disable the preprocessor for that dataset."
    )
    parser = parser.add_argument_group(f"Recommended Datasets", description)

    # Datasets that may also be constant
    datasets = {
        "dnbr": "Differenced normalized burn ratio (raster or number)",
        "severity": "BARC4-like burn severity (polygons, raster, or number)",
        "kf": "Soil KF-factors (polygons, raster, or number)",
    }
    for name, description in datasets.items():
        parser.add_argument(
            f"--{name}",
            metavar=f"PATH | VALUE | None",
            help=description,
        )

    # EVT cannot be a constant
    parser.add_argument(
        "--evt",
        metavar="PATH | None",
        help="Existing vegetation type (raster)",
    )


def _optional(parser: ArgumentParser) -> None:
    "Optional datasets"

    datasets = {
        "retainments": "Debris retention feature locations (points or raster)",
        "excluded": "Areas that should be excluded from network delineation (polygons or raster)",
        "included": "Areas that should be retained during network filtering (polygons or raster)",
        "iswater": "Water mask (polygons or raster)",
        "isdeveloped": "Development mask (polygons or raster)",
    }
    description = (
        "Paths to optional datasets. Paths should either be absolute, or relative\n"
        "to the 'inputs' folder. Set a path to None to disable the preprocessor\n"
        "for that dataset."
    )
    _datasets(parser, "Optional", description, datasets, extra_metavar=" | None")


#####
# Specific Datasets
#####


def _check(parser: ArgumentParser, name: str, description: str) -> None:
    "Adds an error-warning-none check option"
    parser.add_argument(
        f"--{name}-check",
        type=str,
        choices=["warn", "error", "none"],
        help=f"Specify what happens when {description}",
    )


def _perimeter(parser: ArgumentParser) -> None:
    "Adds the perimeter group with a buffer option"
    parser = parser.add_argument_group("Perimeter")
    parser.add_argument(
        "--buffer-km",
        type=float,
        metavar="DISTANCE",
        help="The distance to buffer the fire perimeter in kilometers",
    )


def _dem(parser: ArgumentParser) -> None:
    "Adds the DEM group with a resolution check"

    parser = parser.add_argument_group("DEM")
    parser.add_argument(
        "--resolution-limits-m",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="The minimum and maximum allowed resolution in meters",
    )
    _check(parser, "resolution", "the DEM resolution is outside the allowed limits")


def _dnbr(parser: ArgumentParser) -> None:
    "Adds the dNBR group with scaling check and valid range options"

    # Add the group, include scaling check option
    parser = parser.add_argument_group("dNBR")
    _check(parser, "dnbr-scaling", "the dNBR fails the scaling check")

    # Add valid range options
    constrain = parser.add_mutually_exclusive_group()
    constrain.add_argument(
        "--dnbr-limits",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="A valid data range for the dNBR",
    )
    switch(parser, "no-constrain-dnbr", "Do not constrain the dNBR data range")


def _severity(parser: ArgumentParser) -> None:
    "Adds the severity group with data field and dNBR estimation options"

    # Add group and data field option
    parser = parser.add_argument_group("Burn Severity")
    parser.add_argument(
        "--severity-field",
        type=str,
        metavar="NAME",
        help="Polygon data field holding burn severity values",
    )

    # dNBR estimation options
    parser.add_argument(
        "--severity-thresholds",
        nargs=3,
        type=float,
        metavar=("LOW", "MODERATE", "HIGH"),
        help="dNBR thresholds used to estimate burn severity when missing",
    )
    switch(parser, "no-estimate-severity", "Never estimate severity from dNBR")

    # Fire perimeter containment
    switch(
        parser,
        "no-contain-severity",
        "Do not restrict severity data to the perimeter mask",
    )


def _kf(parser: ArgumentParser) -> None:
    "Adds the KF-factor group with data field and positive constraint options"

    # Create group and add polygon field option
    parser = parser.add_argument_group("KF-factors")
    parser.add_argument(
        "--kf-field",
        type=str,
        metavar="NAME",
        help="Polygon data field holding KF-factor values",
    )

    # Add options to disable constraints
    switch(parser, "no-constrain-kf", "Do not constrain KF-factors to positive values")

    # Add missing KF options
    parser.add_argument(
        "--max-missing-kf-ratio",
        type=float,
        metavar="RATIO",
        help="The maximum allowed proportion of missing KF-factor data (from 0 to 1)",
    )
    _check(
        parser,
        "missing-kf",
        "the amount of missing KF-factor data exceeds the maximum allowed level and there is no fill value",
    )
    parser.add_argument(
        "--kf-fill",
        metavar="VALUE | PATH | True | False",
        help="Fill value option for missing KF-factor data",
    )
    parser.add_argument(
        "--kf-fill-field",
        type=str,
        metavar="NAME",
        help="Polygon data field holding KF-factor fill values when kf-fill is a file",
    )


def _evt_masks(parser: ArgumentParser) -> None:
    "Adds the EVT group with water, development, and excluded options"

    # Create EVT group. Add water options
    parser = parser.add_argument_group("EVT masks")
    masks = {
        "water": "represent water",
        "developed": "represent human development",
        "excluded-evt": "should be excluded from network delineation",
    }
    for name, description in masks.items():
        mask = parser.add_mutually_exclusive_group()
        mask.add_argument(
            f"--{name}", type=float, nargs="*", help=f"EVT classes that {description}"
        )
        name = name.split("-")[0]
        switch(mask, f"no-find-{name}", f"Do not search the EVT for {name} pixels")
