"""
Subpackage to implement the wildcat command-line interface (CLI)
----------
Entry point function:
    main        - The entry point for the wildcat CLI

Submodules / Subpackages:
    _parsers    - Subpackage to build argument parsers for CLI commands
    _kwargs     - Module to convert CLI args to command functions kwargs
    _main       - Module implementing the "main" function
"""

from wildcat._cli._main import main
