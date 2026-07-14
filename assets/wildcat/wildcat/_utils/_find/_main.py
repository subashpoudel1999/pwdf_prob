"""
Functions to locate file paths from config settings and log the results
----------
Functions:
    io_folders      - Locates IO folders and logs the paths
    inputs          - Locates input datasets for the preprocessor
    preprocessed    - Locates preprocessed rasters for the assessment
    _collect_paths  - Initializes path dict with datasets that are Paths
    _resolved_paths - Resolves config paths and logs the locations
"""

from __future__ import annotations

import typing
from pathlib import Path

from wildcat._utils import _paths
from wildcat._utils._find import _file, _folders

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing import Config, IOFolders, PathDict


def io_folders(config: Config, inputs: str, outputs: str, log: Logger) -> IOFolders:
    "Locates IO folders using config settings and logs the paths"

    return _folders.io_folders(
        config["project"],
        config[inputs],
        inputs,
        config[outputs],
        outputs,
        log,
    )


def inputs(config: Config, folder: Path, log: Logger) -> PathDict:
    "Locate the paths to input datasets for the preprocessor"

    paths = _collect_paths(config, _paths.preprocess.all())
    return _resolved_paths(
        "input datasets",
        paths,
        folder,
        required=_paths.preprocess.required(),
        features=_paths.preprocess.features(),
        log=log,
    )


def preprocessed(config: Config, folder: Path, log: Logger) -> PathDict:
    "Locate the paths to preprocessed rasters for the assessment"

    paths = _collect_paths(config, _paths.assess.all())
    return _resolved_paths(
        "preprocessed rasters",
        paths,
        folder,
        required=_paths.assess.required(),
        features=[],
        log=log,
    )


def _collect_paths(config: Config, datasets: list[str]) -> PathDict:
    "Initialize a Path dict with all datasets that are Paths"

    paths = {}
    for name in datasets:
        if isinstance(config[name], Path):
            paths[name] = config[name]
    return paths


def _resolved_paths(
    title: str,
    paths: PathDict,
    folder: Path,
    required: list[str],
    features: list[str],
    log: Logger,
) -> PathDict:
    "Resolves config paths and logs the locations"

    # Start logger and get message padding
    log.info(f"Locating {title}")
    padding = max([len(name) for name in paths]) + 3

    # Resolve the path to each dataset
    for name, input in paths.items():
        paths[name] = _file.file(
            folder, input, name, name in required, name in features
        )

        # Log each path
        heading = f"{name}: ".ljust(padding, " ")
        log.debug(f"    {heading}{paths[name]}")

    # Remove any keys whose path could not be located
    return {name: path for name, path in paths.items() if path is not None}
