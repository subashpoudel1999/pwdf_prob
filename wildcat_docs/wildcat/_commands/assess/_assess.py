"""
Function implementing the "assess" command
----------
Functions:
    assess  - Implements the "assess" command
"""

from __future__ import annotations

import typing

from wildcat._commands.assess import _load, _model, _network, _save, _watershed
from wildcat._utils import _find, _setup

if typing.TYPE_CHECKING:
    from wildcat.typing import Config


def assess(locals: Config) -> None:
    "Runs an assessment"

    # Start log. Parse config settings. Locate IO folders
    config, log = _setup.command("assess", "Assessment", locals)
    preprocessed, assessment = _find.io_folders(
        config, "preprocessed", "assessment", log
    )

    # Locate and load preprocessed datasets
    paths = _find.preprocessed(config, preprocessed, log)
    rasters = _load.datasets(paths, log)

    # Analyze watershed
    _watershed.severity_masks(rasters, log)
    _watershed.characterize(config, rasters, log)
    _watershed.accumulation(rasters, log)

    # Delineate and filter the network. Remove listed IDs and locate basins
    segments = _network.delineate(config, rasters, log)
    properties = _network.filter(config, segments, rasters, log)
    _network.remove_ids(config, segments, properties, log)
    _network.locate_basins(config, segments, log)

    # Run the hazard assessment models
    _model.i15_hazard(config, segments, rasters, properties, log)
    _model.thresholds(config, segments, rasters, properties, log)

    # Save results
    _save.results(assessment, config, segments, properties, log)
    _save.config(assessment, config, paths, log)
