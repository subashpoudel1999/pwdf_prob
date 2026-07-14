"""
Modules that return lists of path inputs that meet a criterion
----------
Modules:
    preprocess  - Lists of datasets that meet preprocessing criteria
    assess      - Lists of datasets that meet assessment criteria

Function:
    folders     - List of args that represent IO folders
"""

from wildcat._utils._paths import assess, preprocess


def folders() -> list[str]:
    "Returns a list of args that represent IO folders"
    return ["inputs", "preprocessed", "assessment", "exports"]
