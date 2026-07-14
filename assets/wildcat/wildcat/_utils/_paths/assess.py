"""
Functions that return lists of datasets that meet a criterion for the assessment
----------
Functions:
    all             - All possible assessment datasets
    required        - All datasets required to run an assessment
    masks           - Datasets that are boolean masks
    _preprocessed   - Appends "_p" to the end of dataset names
"""


def _preprocessed(names: list[str]) -> list[str]:
    "Appends '_p' to the end of dataset names"
    return [f"{name}_p" for name in names]


def all() -> list[str]:
    "All assessment datasets"
    return _preprocessed(
        [
            "perimeter",
            "dem",
            "dnbr",
            "severity",
            "kf",
            "retainments",
            "excluded",
            "included",
            "iswater",
            "isdeveloped",
        ]
    )


def required() -> list[str]:
    "Datasets required to run an assessment"
    return _preprocessed(["perimeter", "dem", "dnbr", "severity", "kf"])


def masks() -> list[str]:
    "Datasets that are boolean masks"
    return _preprocessed(
        ["perimeter", "excluded", "included", "iswater", "isdeveloped"]
    )
