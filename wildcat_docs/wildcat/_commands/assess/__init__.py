"""
Subpackage to implement an assessment
----------
Main Function:
    assess      - Implements an assessment using preprocessed inputs

Internal Modules:
    _assess     - Implements the "assess" function
    _load       - Functions that load preprocessed datasets
    _model      - Functions that implement hazard models
    _network    - Functions to design and manage the stream segment network
    _save       - Functions to save results to file
    _watershed  - Functions to analyze watersheds
"""

from wildcat._commands.assess._assess import assess
