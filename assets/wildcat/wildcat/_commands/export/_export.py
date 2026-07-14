"""
Function implementing the "export" command
----------
Functions:
    export  - Implements the "export" command
"""

from __future__ import annotations

import typing

from wildcat._commands.export import _load, _names, _properties, _reproject, _save
from wildcat._utils import _find, _setup

if typing.TYPE_CHECKING:
    from wildcat.typing import Config


def export(locals: Config) -> None:
    "Exports assessment results"

    # Start log. Parse config settings. Locate IO folders and load hazard parameters
    config, log = _setup.command("export", "Exporting Results", locals)
    assessment, exports = _find.io_folders(config, "assessment", "exports", log)
    parameters = _load.parameters(assessment, log)

    # Secondary validation accounting for dynamic property names
    _properties.validate(config, parameters)
    _names.validate(config, parameters)

    # Parse properties and get final names in exported file
    properties = _properties.parse(config, parameters, log)
    names = _names.parse(config, parameters, properties, log)

    # Load the assessment results, then export to desired format
    results = _load.results(assessment, log)
    results = _reproject.results(results, config, log)
    _save.results(exports, config, results, names, log)
    _save.config(exports, config, log)
