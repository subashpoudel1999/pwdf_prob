"""
Functions that raise warnings or errors if a condition is not met.
----------
Checks:
    resolution      - Checks that the DEM has approximately 10 meter resolution
    dnbr_scaling    - Checks that the dNBR has values outside the interval [-10, 10]
    missing_kf      - Checks if the KF-factor raster has missing values

Utilities:
    _isunexpected   - True if a resolution is outside the expected range
    _check          - Logs a warning or raises and error if a condition is not met
"""

from __future__ import annotations

import typing

import numpy as np

if typing.TYPE_CHECKING:
    from logging import Logger

    from pfdf.raster import Raster

    from wildcat.typing import Check, Config, RasterDict


def _check(check: Check, failed: bool, message: str, log: Logger) -> None:
    "Logs a warning or raises an error if a check fails"

    message = f"\n{message}\n"
    if failed and check == "warn":
        log.warning(message)
    elif failed and check == "error":
        raise ValueError(message)


def _isunexpected(resolution: float, limits: tuple[float, float]) -> bool:
    "True if an axis resolution is outside the expected range"
    return resolution < limits[0] or resolution > limits[1]


def resolution(config: Config, dem: Raster, log: Logger) -> None:
    "Checks that the DEM has approximately 10 meter resolution"

    # Log resolution
    xres, yres = dem.resolution(units="meters")
    log.debug(f"    Resolution: {xres:.2f} x {yres:.2f} meters")

    # Just exit if not checking
    check = config["resolution_check"]
    if check == "none":
        return

    # Check for 10m resolution, allowing for 3 meter error buffer
    limits = config["resolution_limits_m"]
    unexpected = _isunexpected(xres, limits) or _isunexpected(yres, limits)
    message = (
        f"WARNING: The DEM does not have an allowed resolution.\n"
        f"    Allowed resolutions: from {limits[0]} to {limits[1]} meters\n"
        f"    DEM resolution: {xres:.2f} x {yres:.2f} meters\n"
        f"\n"
        f"    The hazard assessment models in wildcat were calibrated using\n"
        f"    a 10 meter DEM, so this resolution is recommended for most\n"
        f"    applications. See also Smith et al., (2019) for a discussion\n"
        f"    of the effects of DEM resolution on topographic analysis:\n"
        f"    https://doi.org/10.5194/esurf-7-475-2019\n"
        f"\n"
        f"    To continue with the current DEM, add either of the following lines to\n"
        f"    configuration.py:\n"
        "\n"
        '     resolution_check = "warn"\n'
        "     OR\n"
        '     resolution_check = "none"'
    )
    _check(check, unexpected, message, log)


def dnbr_scaling(config: Config, rasters: RasterDict, log: Logger) -> None:
    """Checks dNBR scaling by ensuring that at least some dNBR data values are
    outside the interval [-10, 10]. Optionally warns user or raises error if not"""

    # Just exit if not checking
    check = config["dnbr_scaling_check"]
    if check == "none" or "dnbr" not in rasters:
        return

    # Get the min and max values
    log.info("Checking dNBR scaling")
    dnbr = rasters["dnbr"]
    values = dnbr.values[dnbr.data_mask]
    min = np.nanmin(values)
    max = np.nanmax(values)

    # Check scaling. Inform user if check failed
    failed = min >= -10 and max <= 10
    message = (
        "WARNING: The dNBR may not be scaled properly. Wildcat expects dNBR\n"
        "    inputs to be (raw dNBR * 1000). Typical values of scaled datasets\n"
        "    range roughly between -1000 and 1000, but the values in the input\n"
        "    raster are between -10 and 10. You may need to multiply your dNBR\n"
        "    values by 1000 to scale them correctly.\n"
        "\n"
        "    To continue with the current dNBR, edit configuration.py to include\n"
        "    one of the following lines:\n"
        "\n"
        '    dnbr_check = "warn"\n'
        "    OR\n"
        '    dnbr_check = "none"'
    )
    _check(check, failed, message, log)


def missing_kf(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Checks if the KF-factor dataset has missing values"

    # Exit if not checking, or if a fill option is selected
    check = config["missing_kf_check"]
    kf_fill = config["kf_fill"]
    filling = not isinstance(kf_fill, bool) or kf_fill == True
    if check == "none" or "kf" not in rasters or filling:
        return

    # Compute the proportion of missing data
    log.info("Checking for missing KF-factor data")
    kf = rasters["kf"]
    proportion = np.sum(kf.nodata_mask) / kf.size
    log.debug(f"    Proportion of missing data: {proportion}")

    # Inform the user if the check failed
    failed = proportion > config["max_missing_kf_ratio"]
    message = (
        "WARNING: The KF-factor raster has missing data. This may indicate that\n"
        "    the KF-factor dataset is incomplete, but can also occur for normal\n"
        "    reasons (such as the analysis domain intersecting a water feature).\n"
        "    We recommend examining the KF-factor dataset for missing data before\n"
        "    continuing.\n"
        "    \n"
        "    If the dataset appears satisfactory, you can disable this message\n"
        "    by adding the following line to configuration.py:\n"
        '    missing_kf_check = "none"\n'
        "    \n"
        '    Alternatively, see the "kf_fill" config value for options to fill missing\n'
        "    KF-factor data pixels."
    )
    _check(check, failed, message, log)
