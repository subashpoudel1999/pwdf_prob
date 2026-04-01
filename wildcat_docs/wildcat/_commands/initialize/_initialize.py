"""
Implements the "initialize" command
----------
Command Function:
    initialize  - Implements the wildcat initialization routine

Substeps:
    _validate_project   - Checks that project folder is an empty directory
    _inputs_folder      - Optionally creates an inputs subfolder
"""

from __future__ import annotations

import os
import typing
from logging import getLogger
from pathlib import Path

from wildcat._commands.initialize import _config
from wildcat._utils import _defaults, _validate

if typing.TYPE_CHECKING:
    from logging import Logger
    from typing import Optional

    from wildcat.typing import ConfigType, Pathlike


def initialize(
    project: Optional[Pathlike] = None,
    config: ConfigType = "default",
    inputs: str | None = "inputs",
) -> None:
    "Initializes a project folder"

    # Start log
    log = getLogger("wildcat.initialize")
    log.info("Initializing project")

    # Initial validation
    settings = {"project": project, "config": config, "inputs": inputs}
    _validate.initialize(settings)
    project, config, inputs = settings.values()

    # Start log. Validate project. Create config file and optional inputs folder
    project = _validate_project(project, log)
    inputs = _inputs_folder(project, inputs, log)
    _config.write(project, inputs, config, log)


#####
# Substeps
#####


def _validate_project(project: Path | None, log: Logger) -> Path:
    "Checks that the project folder is a path to a non-existent or empty directory"

    # Use the current directory if None
    if project is None:
        project = Path.cwd()

    # Resolve path. Create if it does not exist
    project = project.resolve()
    if not project.exists():
        log.debug(f"    Creating project folder: {project}")
        project.mkdir(parents=True)

    # Error if the path is not an empty directory
    elif not project.is_dir():
        raise ValueError(
            f"The project path is not a directory\nProject path: {project}"
        )
    elif len(os.listdir(project)) > 0:
        raise FileExistsError(
            f"Cannot initialize project because the project folder is not empty. "
            f"Either delete the contents or use a different folder.\n"
            f"Project path: {project}"
        )

    # Notify of existing folder. Return the folder path
    else:
        log.debug(f"    Located project folder: {project}")
    return project


def _inputs_folder(project: Path, inputs: str | None, log: Logger) -> str:
    "Optionally initializes an empty inputs subfolder"

    # If None, use default name for config files
    if inputs is None:
        inputs = _defaults.folders.inputs

    # Otherwise, create the folder
    else:
        log.debug(f"    Initializing {inputs} subfolder")
        (project / inputs).mkdir()
    return inputs
