"""
Commands to assess and map post-wildfire debris-flow hazards
----------
Wildcat is a command line interface (CLI) and Python package that provides
routines to assess and map post-fire debris-flow hazards. Key routines in the
package include:

* initialize -- Creates a project folder for a wildcat assessment
* preprocess -- Cleans and preprocesses input datasets
* assess     -- Implements a hazard assessment
* export     -- Exports results to common GIS formats (such as Shapefile and GeoJSON)

The simplest way to use wildcat is from the command line:

    $ wildcat <command> <arg1> <arg2> ...

Or you can run commands from within a Python session:

    >>> from wildcat import preprocess
    >>> preprocess(...)

Please see the documentation, CLI help text, or function docstrings for detailed
usage information.
----------
Functions:
    initialize  - Initializes a project folder for a wildcat assessment
    preprocess  - Preprocesses input datasets
    assess      - Runs a hazard assessment using preprocessed data
    export      - Exports hazard assessment results to GIS file formats
    version     - Returns the wildcat version string

Misc:
    errors      - Module holding custom Exception classes used by wildcat
    typing      - Subpackage with type hints used throughout the package

Internal subpackages:
    _cli        - Subpackage implementing the command line interface
    _commands   - Subpackage implementing wildcat commands
    _utils      - Subpackage of utilities used to implement wildcat commands
"""

# Note: The following functions make the wildcat commands directly importable from
# the wildcat namespace. The imports are inside the functions (rather than at the
# top of this file) because many wildcat commands rely on numba (via pysheds), which
# takes a long time to import. Placing the imports inside the functions only runs
# the long import when necessary, so tasks that don't require pysheds can still run
# quickly. Most importantly, this allows users to query the command-line help text:
#
#    $ wildcat -h
#    $ wildcat <command> -h
#
# without waiting a long time.

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from typing import Optional

    from wildcat.typing import CRS, Check, ConfigType, Pathlike, scalar, strs, vector


def version():
    """
    Returns the version string of the currently installed wildcat package
    ----------
    version()
    Returns the version string.
    ----------
    Outputs:
        str: The current wildcat version string
    """
    from importlib.metadata import version

    return version("wildcat")


def initialize(
    project: Optional[Pathlike] = None,
    config: ConfigType = "default",
    inputs: str | None = "inputs",
) -> None:
    """
    Initializes a project folder with a config file and inputs subfolder
    ----------
    initialize(project)
    Creates a project folder at the indicated path. If the folder already exists,
    then it must be empty. If the folder is None, attempts to initialize a project
    in the current directory. Saves a default configuration file in the project
    folder and creates an empty "inputs" subfolder.

    initialize(..., config)
    Specifies the type of configuration file to save in the folder. Options are:
    "default": Creates a config file with the most commonly used config fields
    "full": Creates a config file with all configurable fields
    "empty": Creates a config file that lists the wildcat version and nothing else
    "none": Does not create a config file

    initialize(..., inputs)
    Specifies the name of the empty "inputs" subfolder. By default, names the
    folder "inputs". Alternatively, set inputs=None to not create an empty
    subfolder.
    ----------
    Inputs:
        project: The path to the project folder
        config: The type of config file to create. Options are "default", "full",
            "empty", and "none"
        inputs: The name for the empty inputs subfolder, or None to disable the
            creation of the subfolder.

    Saves:
        Creates a project folder with an optional "configuration.py" config file,
        and an optional empty inputs subfolder.
    """
    from wildcat._commands.initialize import initialize

    initialize(project, config, inputs)


def preprocess(
    # Paths
    project: Pathlike = None,
    *,
    config: Pathlike = None,
    inputs: Pathlike = None,
    preprocessed: Pathlike = None,
    # Required datasets
    perimeter: Pathlike = None,
    dem: Pathlike = None,
    # Recommended datasets
    dnbr: Optional[Pathlike | scalar] = None,
    severity: Optional[Pathlike | scalar] = None,
    kf: Optional[Pathlike | scalar] = None,
    evt: Optional[Pathlike] = None,
    # Optional datasets
    retainments: Optional[Pathlike] = None,
    excluded: Optional[Pathlike] = None,
    included: Optional[Pathlike] = None,
    iswater: Optional[Pathlike] = None,
    isdeveloped: Optional[Pathlike] = None,
    # Perimeter
    buffer_km: scalar = None,
    # DEM
    resolution_limits_m: tuple[scalar, scalar] = None,
    resolution_check: Check = None,
    # dNBR
    dnbr_scaling_check: Check = None,
    constrain_dnbr: bool = None,
    dnbr_limits: tuple[scalar, scalar] = None,
    # Burn severity
    severity_field: Optional[str] = None,
    estimate_severity: bool = None,
    severity_thresholds: tuple[scalar, scalar, scalar] = None,
    contain_severity: bool = None,
    # KF-factors
    kf_field: Optional[str] = None,
    constrain_kf: bool = None,
    max_missing_kf_ratio: scalar = None,
    missing_kf_check: Check = None,
    kf_fill: bool | float | Pathlike = None,
    kf_fill_field: Optional[str] = None,
    # EVT masks
    water: vector = None,
    developed: vector = None,
    excluded_evt: vector = None,
) -> None:
    """
    Cleans datasets prior to hazard assessment
    ----------
    preprocess(project, ...)
    preprocess(..., config)
    Runs the preprocessor for the indicated project folder. If project=None,
    interprets the current folder as the project folder.

    The preprocessing algorithm is as follows: Starts by creating a buffered
    burn perimeter. Locates all other input datasets and loads them as rasters
    within the buffered perimeter. Checks the DEM is georeferenced and has a
    resolution of approximately 10 meters. Reprojects all datasets to the CRS,
    resolution, and alignment of the DEM. Clips all datasets to the bounds of the
    buffered perimeter. Checks dNBR scaling, and constrains dNBR values to a valid
    range. Estimates burn severity from dNBR if otherwise unavailable, and
    contains burn severity data to the fire perimeter mask. Constrains KF-factor
    values to positive values, and optionally fills missing values. Builds water,
    development, and exclusion masks from an EVT. Saves preprocessed rasters for
    later assessment.

    Preprocessor settings are determined by keyword inputs, configuration file
    values, and default wildcat settings. Settings are prioritized via the
    following hierachy:
        Keyword Args > Config File > Defaults
    Essentially, settings are first initialized to the wildcat defaults. These
    settings are then overridden by any settings defined in the configuration
    file. Finally, the settings are overridden by any values provided as keyword
    arguments. By default, searches for a configuration file named "configuration.py"
    at the root of the project. Use the `config` option to specify a different
    configuration file path.

    preprocess(..., inputs, preprocessed)
    Specifies IO folders for the preprocessor. The "inputs" folder is the default
    folder in which the preprocessor will search for input datasets. The
    "preprocessed" folder is the folder in which preprocessed rasters will be saved.

    preprocess(..., <files>)
    Specifies the path to an input datasets. Specific filenames are detailed in
    the following syntaxes. Relative paths are parsed relative to the "inputs"
    folder. If a path lacks an extension, scans supported extensions for a file
    with a matching file stem.

    preprocess(..., perimeter)
    preprocess(..., dem)
    Specifies paths to datasets required to run the preprocessor. The preprocessor
    will raise an error if it cannot locate these datasets. The perimeter (after
    being buffered) is used to define the spatial domain of the preprocessor, and
    the DEM is used to set the CRS, resolution, and alignment of the preprocessed
    rasters.

    preprocess(..., dnbr)
    preprocess(..., severity)
    preprocess(..., kf)
    preprocess(..., evt)
    Paths to datasets recommmended for most hazard assessments. The preprocessor
    will still run if these datasets are missing, but most users will need them
    later to implement an assessment. Set an input to False to disable the
    preprocessor for that dataset. The dnbr, severity, and kf datasets also support
    using a constant value across the watershed. This can be useful when a spatially
    complete dataset is not available. To implement a constant value, set the dataset
    equal to a number instead of a file path.

    preprocess(..., retainments)
    preprocess(..., excluded)
    preprocess(..., included)
    preprocess(..., iswater)
    preprocess(..., isdeveloped)
    Paths to optional datasets. Neither the preprocessor nor the assessment
    requires these datasets. The retainments dataset indicates the location of
    debris retainment features, excluded and iswater indicate areas that should
    not be used for network delineation, and included and isdeveloped can be used
    to customize network filtering. Set an input to False to disable the preprocessor
    for that dataset.

    preprocess(..., buffer_km)
    Specifies the burn perimeter buffer in kilometers

    preprocess(..., resolution_limits_m)
    preprocess(..., resolution_check)
    Options to check that the DEM has the expected resolution. In general, the DEM
    should have approximately 10 meter resolution, as wildcat's assessment models were
    calibrated using data from a 10 meter DEM. The "resolution_limits_m" input specifies
    a minimum and maximum allowed resolution in meters. The "resolution_check" option
    indicates what should happen when the DEM resolution is outside these limits.
    Options are:
        "warn": Issues a warning
        "error": Raises an error
        "none": Does nothing

    preprocess(..., dnbr_scaling_check)
    preprocess(..., constrain_dnbr)
    preprocess(..., dnbr_limits)
    Options for preprocessing dNBR. The scaling check indicates what should happen
    if the dNBR values do not appear to be scaled correctly. Options are "warn",
    "error", and "none". Use the constrain_dnbr switch to indicate whether the
    preprocessor should constrain dNBR values to a valid range. The dnbr_limits
    input is a 2-element vector specifying the lower and upper bound of the valid range.

    preprocess(..., severity_field)
    preprocess(..., estimate_severity)
    preprocess(..., severity_thresholds)
    preprocess(..., contain_severity)
    Options for preprocessing burn severity. Use the severity_field input to
    specify an attribute field holding severity data when the severity dataset
    is a set of Polygon features. Use the estimate_severity switch to indicate
    whether the preprocessor should estimate from dNBR when no other severity
    dataset is detected. The severity_thresholds input specifies the dNBR thresholds
    used to estimate severity from dNBR. Finally, use the contain_severity switch
    to indicate whether the preprocessor should contain severity data values to
    the fire perimeter mask.

    preprocess(..., kf_field)
    preprocess(..., constrain_kf)
    preprocess(..., max_missing_kf_ratio)
    preprocess(..., missing_kf_check)
    preprocess(..., kf_fill)
    preprocess(..., kf_fill_field)
    Options for preprocessing KF-factors. Use kf_field to specify an attribute
    field holding KF-factor data when the KF-factor dataset is a set of Polygon
    features. The constrain_kf switch indicates whether the preprocessor should
    constrain KF-factor data to positive values.

    The remaining options indicate what should happen when the KF-factor dataset has
    missing data. The max_missing_kf_ratio specifies a maximum allowed proportion of
    missing data in the KF-factor dataset. The ratio should be a value on the interval
    from 0 to 1. The missing_kf_check option indicates what should happen when the
    amount of missing data exceeds this ratio. Options are "warn", "error", and "none".

    Alternatively, users can provide fill values for missing KF-factor data using the
    kf_fill option. Using fill values will disable the missing_kf_check. Options for the
    kf_fill input are:
        False: Does not fill missing KF-factor values
        True: Fills missing values with the median value in the buffered perimeter
        int | float: Fills missing values with the indicated value
        File path: Path to a file dataset used to implement spatially-varying fill values
    If kf_fill is a file path, then you must use the kf_fill_field input to indicate the
    name of fill file field that holds KF-factor fill data.

    preprocess(..., water)
    preprocess(..., developed)
    preprocess(..., excluded_evt)
    Indicate EVT integer codes that should be used to build processing masks.
    EVT pixels matching a water code or an excluded_evt code will be excluded
    from network delineation. EVT pixels matching a developed code will be used
    to build a human-development mask for network filtering. If you provide both
    water codes and an iswater input dataset, then the two masks will be merged.
    If you provide both excluded_evt codes and an excluded dataset, then the two
    masks will be merged.
    ----------
    Inputs:
        project: The path to the project folder
        config: The path to the configuration file
        inputs: The path of the default folder used to locate input datasets
        preprocessed: The path of the folder in which preprocessed rasters are saved
        perimeter: A fire perimeter dataset
        dem: A digital elevation model dataset, ideally at 10 meter resolution
        dnbr: A difference normalized burn ratio (dNBR) dataset. Either a file path or
            a number.
        severity: A BARC4-like burn severity dataset. Either a file path or a number.
        kf: A KF-factor dataset. Either a file path or a positive number.
        evt: An existing vegetation type classification dataset
        retainments: Locations of debris retainment features
        excluded: Area that should be excluded from network delineation.
        included: Areas that should always be retained when filtering a network
        iswater: Areas that are water bodies
        isdeveloped: Areas that are human development
        buffer_km: The buffer for the fire perimeter in kilometers
        resolution_limits_m: The minimum and maximum allowed resolution in meters.
        resolution_check: What to do when the DEM does not have approximately
            10 meter resolution. Options are "warn", "error", "none"
        dnbr_scaling_check: What to do when the dNBR does not appear to be scaled
            properly. Options are "warn", "error", "none"
        constrain_dnbr: Whether to constrain dNBR values to a valid data range
        dnbr_limits: The lower and upper bounds of the valid dNBR data range
        severity_field: The data attribute field holding severity data when the
            severity dataset is a set of Polygon features
        estimate_severity: Whether to estimate severity from dNBR when no severity
            dataset is detected
        severity_thresholds: The dNBR thresholds used to estimate severity classes
        contain_severity: Whether to contain severity data to the fire perimeter mask
        kf_field: The data attribute field holding KF-factor data when the KF-factor
            dataset is a set of Polygon features
        constrain_kf: Whether KF-factor data should be constrained to positive values
        max_missing_kf_ratio: The maximum allowed proportion of missing data in the
            KF-factor dataset.
        missing_kf_check: What to do when the amount of missing KF-factor dataset
            the maximum allowed level. Options are "warn", "error", "none"
        kf_fill: How to fill missing KF-factor values. Options are False,
            True (median value), a scalar value, or a path to a spatially dataset
        kf_fill_field: The data attribute field holding KF-factor fill data when
            the kf_fill input is a set of Polygon features.
        water: EVT codes that should be classified as water
        developed: EVT codes that should be classified as human development
        excluded_evt: EVT codes that should be excluded from network delineation

    Saves:
        Saves the collection of preprocessed rasters to the "preprocessed" folder.
        Also saves the final settings in configuration.txt.
    """

    from wildcat._commands.preprocess import preprocess

    preprocess(locals())


def assess(
    # Folders
    project: Pathlike = None,
    *,
    config: Pathlike = None,
    preprocessed: Pathlike = None,
    assessment: Pathlike = None,
    # Required datasets
    perimeter_p: Pathlike = None,
    dem_p: Pathlike = None,
    dnbr_p: Pathlike = None,
    severity_p: Pathlike = None,
    kf_p: Pathlike = None,
    # Optional mask
    retainments_p: Optional[Pathlike] = None,
    excluded_p: Optional[Pathlike] = None,
    included_p: Optional[Pathlike] = None,
    iswater_p: Optional[Pathlike] = None,
    isdeveloped_p: Optional[Pathlike] = None,
    # Unit conversions
    dem_per_m: scalar = None,
    # Delineation
    min_area_km2: scalar = None,
    min_burned_area_km2: scalar = None,
    max_length_m: scalar = None,
    # Filtering
    max_area_km2: scalar = None,
    max_exterior_ratio: scalar = None,
    min_burn_ratio: scalar = None,
    min_slope: scalar = None,
    max_developed_area_km2: scalar = None,
    max_confinement: scalar = None,
    confinement_neighborhood: scalar = None,
    flow_continuous: bool = None,
    # Remove specific segments
    remove_ids: vector = None,
    # Hazard Modeling
    I15_mm_hr: Optional[vector] = None,
    volume_CI: Optional[vector] = None,
    durations: Optional[vector] = None,
    probabilities: Optional[vector] = None,
    # Basins
    locate_basins: bool = None,
    parallelize_basins: bool = None,
) -> None:
    """
    Implements a hazard assessment using preprocessed datasets
    ----------
    assess(project, ...)
    assess(..., config)
    Runs an assessment for the indicated project folder. If project=None,
    interprets the current folder as the project folder.

    An assessment proceeds as follows: Analyzes a watershed to determine burn
    severity masks, flow directions, slopes, vertical relief, and flow accumulations.
    Delineates an initial network. Characterizes the segments in the initial
    network, then uses the characterizations to filter the network to model-worthy
    segments. Estimates debris-flow likelihood using the Staley 2017 M1 model.
    Estimates potential sediment volumes using the Gartner 2014 emergency model.
    Classifies combined hazard using a modification of the Cannon 2010 classification
    scheme. Estimate rainfall thresholds by inverting the Staley 2017 M1 model.
    Exports results for the segments, basins, and terminal outlets to GeoJSON.
    Note that saved results should not be used directly - instead, use the
    export command to save results in their final format.

    Assessment settings are determined by keyword inputs, configuration file
    values, and default wildcat settings. Settings are prioritized via the
    following hierachy:
        Keyword Args > Config File > Defaults
    Essentially, settings are first initialized to the wildcat defaults. These
    settings are then overridden by any settings defined in the configuration
    file. Finally, the settings are overridden by any values provided as keyword
    arguments. By default, searches for a configuration file named "configuration.py"
    at the root of the project. Use the `config` option to specify a different
    configuration file path.

    assess(..., preprocessed)
    assess(..., assessment)
    Specify paths to IO folders for the assessment. The "preprocessed" folder is
    the default folder in which the assessment will search for preprocessed rasters.
    The "assessment" folder is where the assessment will save its results.

    assess(..., perimeter_p)
    assess(..., dem_p)
    assess(..., dnbr_p)
    assess(..., severity_p)
    assess(..., kf_p)
    Specify the paths to preprocessed datasets required for the assessment. Most
    users will not need these inputs, as preprocessed datasets will be detected
    automatically from the "preprocessed" folder. Use these inputs if you want
    to override a preprocessed dataset with some other file.

    assess(..., retainments_p)
    assess(..., excluded_p)
    assess(..., included_p)
    assess(..., iswater_p)
    assess(..., isdeveloped_p)
    Specify the paths to optional preprocessed datasets. Use these inputs if you
    want to override one of the preprocessed datasets in the "preprocessed" folder.
    You can explicitly disable the use of a dataset by setting it equal to False.

    assess(..., dem_per_m)
    By default, the assessment assumes the DEM is in meters. If this is not the
    case, use the dem_per_m option to indicate the conversion factor between
    DEM units and meters.

    assess(..., min_area_km2)
    assess(..., min_burned_area_km2)
    assess(..., max_length_m)
    Network delineation parameters. The min_area_km2 option indicates the minimum
    catchment area for considered pixels in kilometers^2. Similarly, min_burned_area_km2
    is the minimum burned catchment area. The max_length_m parameter indicates
    the maximum allowed stream segment length in meters. Segments longer than this
    length will be split into multiple pieces.

    assess(..., max_area_km2)
    assess(..., max_exterior_ratio)
    assess(..., min_burn_ratio)
    assess(..., min_slope)
    assess(..., max_developed_area_km2)
    assess(..., max_confinement)
    assess(..., confinement_neighborhood)
    assess(..., flow_continuous)
    Filtering parameters. The max_area_km2 input indicates the maximum catchment
    area (in kilometers^2) for retained segments. Segments that pass this check
    must also either (1) Be considered in the perimeter, or (2) Meet physical
    criteria for debris-flow risk. A segment is considered in the perimeter if
    both (A) the segment intersects the perimeter at any point, and (B) the segment's
    catchment is sufficiently within the perimeter. If the proportion of a catchment
    that is outside the perimeter exceeds max_exterior_ratio, then the segment is
    not considered to be in the perimeter, and must pass the physical criteria check.
    To pass the physical criteria check, a segment must be sufficiently burned,
    steep, confined, and developed. Here, min_burn_ratio is the minimum proportion
    of burned catchment area to pass, min_slope is the minimum slope gradient,
    max_developed_area_km2 is the maximum developed catchment area in kilometers^2,
    and max_confinement is the maximum allowed confinement angle (in degrees). Use the
    confinement_neighborhood to set the pixel radius used to compute confinement
    angle slopes. Finally, use the flow_continuous switch to indicate whether
    the filtering algorithm should preserve flow continuity.

    assess(..., remove_ids)
    Lists the IDs of segments that should be removed from the network. Use this
    option to remove problem segments after filtering. Note that any changes to
    network delineation will alter the segment IDs.

    assess(..., I15_mm_hr)
    assess(..., volume_CI)
    assess(..., durations)
    assess(..., probabilities)
    Set hazard modeling parameters. I15_mm_hr are the 15-minute rainfall intensities
    (in millimeters per hour) used to estimate debris flow likelihoods, potential
    sediment volumes, and combined hazard classifications. The volume_CI input
    lists the confidence intervals that should be computed for the potential
    sediment volumes; these values should be on the interval from 0 to 1. The
    durations input are the rainfall durations that should be used to compute
    rainfall thresholds. Supported durations include 15, 30, and 60 minute intervals.
    The probabilities are the debris-flow probabilities that should be used to estimate
    rainfall thresholds. These should be on the interval from 0 to 1.

    assess(..., locate_basins)
    assess(..., parallelize_basins)
    Options for locating terminal outlet basins. Locating outlet basins is a
    computationally expensive task, and these settings provide options to help
    with this step. Use locate_basins to indicate whether the assessment should
    attempt to locate basins at all. If False, the assessment will not save a
    "basins.geojson" output file, and you will not be able to export basin results.
    Use the parallelize_basins switch to indicate whether the assessment can locate
    the basins in parallel, using multiple CPUs. This option is disabled by default,
    as the parallelization overhead can worsen for small watershed. As a rule of
    thumb, parallelization will often improve runtime if the assessment requires
    >10 minutes to locate basins.
    ----------
    Inputs:
        project: The path to the project folder
        config: The path to the configuration file
        preprocessed: The path to the folder holding preprocessed rasters
        assessment: The path to the folder where assessment results will be saved
        perimeter_p: Path to the preprocessed perimeter
        dem_p: Path to the preprocessed DEM
        dnbr_p: Path to the preprocessed dNBR
        severity_p: Path to the preprocessed burn severity
        kf_p: Path to the preprocessed KF-factors
        retainments_p: Path to preprocessed retainment feature locations
        excluded_p: Path to preprocessed excluded area dataset
        included_p: Path to preprocessed dataset of areas retained during filtering
        iswater_p: Path to preprocessed water mask
        isdeveloped_p: Path to preprocessed human development mask
        dem_per_m: Conversion factor between DEM units and meters
        min_area_km2: Minimum catchment area in kilometers^2 of stream segment pixels
        min_burned_area_km2: Minimum burned catchment area in kilometers^2 of
            stream segment pixels
        max_length_m: Maximum stream segment length in meters
        max_area_km2: Maximum catchment area in kilometers^2 of filtered segments
        max_exterior_ratio: The maximum proportion of catchment area that can be
            outside the perimeter for a segment to still be considered inside
            the perimeter. On the interval from 0 to 1.
        min_burn_ratio: The minimum proportion of burned catchment area needed
            to pass the physical filtering check. On the interval from 0 to 1.
        min_slope: The minimum slope gradient needed to pass the physical filtering check
        max_developed_area_km2: The maximum amount of developed catchment area
            (in kilometers^2) needed to pass the physical filtering check
        max_confinement: The maximum confinement angle (in degrees) needed to pass
            the physical filtering check.
        confinement_neighborhood: The pixel radius used to compute confinement
            angle slopes.
        flow_continuous: Whether to preserve flow continuity when filtering
        remove_ids: IDs of segments that should be removed from the filtered network
        I15_mm_hr: Peak 15-minute rainfall intensities (in millimeters per hour)
            used to compute likelihoods, volumes, and combined hazard
        volume_CI: The confidence intervals to computed for the volume estimates.
            On the interval from 0 to 1.
        durations: Rainfall durations (in minutes) used to estimate rainfall
            thresholds. Supports 15, 30, and 60 minute intervals.
        probabilities: Probability levels used to estimate rainfall thresholds.
            On the interval from 0 to 1.
        locate_basin: Whether to locate terminal outlet basins
        parallelize_basins: Whether to use multiple CPUs to locate basins

    Saves:
        Saves "segments.geojson", "outlets.geojson", and optionally "basins.geojson"
        in the "assessment" folder. Also saves the final settings in "configuration.txt"
    """
    from wildcat._commands.assess import assess

    assess(locals())


def export(
    # Paths
    project: Pathlike = None,
    *,
    config: Pathlike = None,
    assessment: Pathlike = None,
    exports: Pathlike = None,
    # Output files
    format: str = None,
    export_crs: CRS = None,
    prefix: str = None,
    suffix: str = None,
    # Properties
    properties: strs = None,
    exclude_properties: strs = None,
    include_properties: strs = None,
    # Property formatting
    order_properties: bool = None,
    clean_names: bool = None,
    rename: dict[str, str] = None,
) -> None:
    """
    Export assessment results to desired format(s)
    ----------
    export(project, ...)
    export(..., config)
    Exports assessment results for the indicated project. If project=None, interprets
    the current folder as the project folder.

    The "export" command allows users to convert assessment results to desired
    GIS file formats. Wildcat assessments include a large number of saved data
    fields (also known as "properties"), and so this command also allows users to
    select the fields that should be included in exported files. Finally, the
    command allows users to apply custom naming schemes to the exported properties.

    Export settings are determined by keyword inputs, configuration file
    values, and default wildcat settings. Settings are prioritized via the
    following hierachy:
        Keyword Args > Config File > Defaults
    Essentially, settings are first initialized to the wildcat defaults. These
    settings are then overridden by any settings defined in the configuration
    file. Finally, the settings are overridden by any values provided as keyword
    arguments. By default, searches for a configuration file named "configuration.py"
    at the root of the project. Use the `config` option to specify a different
    configuration file path.

    export(..., assessment)
    export(..., exports)
    Specify paths to the IO folders for the export. The "assessment" folder is
    the default folder in which the command will search for saved assessment
    results. The "exports" folder is where the command will save exported files.

    export(..., format)
    Specifies the file format of the exported files. Exports results for the segments,
    basins, and outlets to this file format. Commonly used formats include
    "Shapefile" and "GeoJSON". See the documentation for a complete list of supported
    file formats.

    export(..., export_crs)
    Specifies the coordinate reference system (CRS) that the exported segment, basin,
    and outlet geometries should use. The base geometries from the assessment results
    will be reprojected into this CRS prior to export. Accepts a variety of CRS
    indicators, including: EPSG codes, CRS names, well-known text, and PROJ4 parameter
    strings. Consult the pyproj documentation details on supported inputs.

    Alternatively, set this option to "base" to leave the geometries in the base
    assessment CRS. In practice, this is the CRS of the preprocessed DEM used to derive
    the stream segment network.

    export(..., prefix)
    export(..., suffix)
    Modifies the names of exported files. But default, exports files named "segments",
    "basins", and "outlets" holding the results for the respective features. Use
    these options to modify the names of the exported files. The "prefix" option
    specifies a string that will be prepended to each file name, and the "suffix"
    option is a string appended to the end of each name. As filenames, these
    options may only contain ASCII letters, numbers, hyphens (-), and underscores (_).

    export(..., properties)
    export(..., exclude_properties)
    export(..., include_properties)
    Specify the properties that should be included in the exported files. These
    inputs should be a lists of strings that specify assessment properties. We
    refer users to the documentation for a complete explanation of property strings,
    but in brief: strings may be property names, result prefixes, or property group
    names.

    Property names are the most simple, and refer to an explicit property. Watershed
    variables, filter checks, and model inputs all have constant names.
    By contrast, hazard assessment results depend on the hazard modeling parameters
    used to run the assessment. As such, result properties use dynamic names based
    on the indices of the assessment parameters used to compute a particular result.

    Rather than selecting result properties by name, it is typically easier to
    select results using result prefixes. These strings can be used to select all
    properties corresponding to a particular type of result. These include:
        H: Combined hazard classifications
        P: Debris-flow likelihoods
        V: Potential sediment volumes
        Vmin: Lower bounds of potential sediment volumes
        Vmax: Upper bounds of potential sediment volumes
        R: Rainfall thresholds as accumulations
        I: Rainfall thresholds as intensities

    Finally, the command supports various strings that select groups of related
    properties. These include:
        default: Results, hazard model inputs, and watershed characteristics
        results: Hazard model results
        model inputs: Hazard model inputs
        modeling: Results and model inputs
        watershed: Watershed characteristics
        filters: Boolean filter checks
        filtering: Watershed characteristics and filter checks
        all: All saved properties

    The "properties" input specifies a base set of properties for export. The
    "exclude_properties" indicates properties that should be removed from this
    base group. This can be used to exclude specific properties when the "properties"
    input contains one or more property groups. Finally, the "include_properties"
    input indicates properties that should be added to the export, after
    "exclude_properties" has been implemented. This is typically used at the
    temporarily used at the command line to temporarily restore excluded properties.

    export(..., order_properties)
    Indicates whether the command should attempt to group related properties in
    the exported file. When True (default),  wildcat will cluster H, P, V, Vmin,
    and Vmax results by I15 values. Next, it will cluster R and I thresholds,
    first by rainfall duration, and then by probability level. Next, wildcat will
    group model result properties, then watershed characteristics, and finally
    filter checks. If order_properties=False, exports properties in the order
    they are listed.

    export(..., clean_names)
    Indicates whether the command should attempt to convert dynamically named
    result properties to names that are more human-readable. Under-the-hood, wildcat
    uses a dynamic naming scheme for result properties using the indices of the
    hazard assessment parameters used to compute a particular result. When
    clean_names=True (default), the command will update the names such that parameter
    indices are converted to simplified parameter values. I15 values are converted
    to the nearest integer, volume CIs are multiplied by 100 and set to the nearest
    integer, rainfall durations are converted to integers, and probability levels
    are multiplied by 100 and set to the nearest integer. When clean_names=False,
    exported properties retain their raw (index-based) names.

    export(..., rename)
    A dict specifying new names for exported properties. This input should be a
    dict with string keys. Keys may be property names, result prefixes, or hazard
    modeling parameters. Keys that are property names or result prefixes should have
    a string value. If a property name, the string is the name of the property in
    the exported files. If a result prefix, the prefixes of exported results are
    updated, but any hazard modeling parameters in the name are retained. If the
    key is a hazard modeling parameter, then the value should be a list with one
    element per parameter. Each element should be a string, which will replace the
    parameter index or value in any associated property names.

    Complete property names have highest priority. So if a renaming dict contains
    a complete result property name, then its renaming value will override any result
    prefix or modeling parameter renaming options. Note that you may use any string
    as a renaming option, but not all file formats will support all names. For
    example, Shapefiles do not support property names with more than 10 characters.
    As a rule, wildcat will not check that renaming options are valid for a given
    export format. Verifying that new names are valid is left to the user.
    ----------
    Inputs:
        project: The path to the project folder
        config: The path to the configuration file
        assessment: The path to the folder holding saved assessment results
        exports: The path to the folder in which to save exported files
        format: A string indicating the format of the exported files
        export_crs: The CRS for the exported feature geometries
        prefix: A string prepended to the beginning of exported file names
        suffix: A string appended to the end of exported file names
        properties: A base list of properties that should be included in the
            exported files.
        exclude_properties: Properties that should be removed from the base
            list of exported properties.
        include_properties: Properties that should be added to the list of exported
            properties, following the removal of any excluded properties
        order_properties: True to cluster groups of related properties. False to
            export properties in listed order.
        clean_names: True to replace hazard parameter indices with simplified
            parameter values in result property names. False to retain the indices
            in the names.
        rename: A dict specifying renaming rules for exported properties

    Saves:
        Vector feature files for the segments, basins, and outlets. Also saves
        configuration.txt with the config settings for the export.
    """
    from wildcat._commands.export import export

    export(locals())
