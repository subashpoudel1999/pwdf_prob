Python API
==========

.. highlight:: python

The complete reference guide for using wildcat within a Python session.

----

.. py:module:: wildcat

    Commands to assess and map post-wildfire debris-flow hazards

    .. list-table::
        :header-rows: 1

        * - Function
          - Description
        * - :ref:`initialize <python.initialize>`
          - Creates a project folder for a wildcat assessment and adds a config file
        * - :ref:`preprocess <python.preprocess>`
          - Reprojects and cleans input datasets in preparation for an assessment
        * - :ref:`assess <python.assess>`
          - Implements a hazard assessment using preprocessed inputs
        * - :ref:`export <python.export>`
          - Exports assessment results to common GIS formats (such as Shapefile and GeoJSON)
        * - :ref:`version <python.version>`
          - Returns the version string for the currently installed wildcat package

----

.. _python.initialize:

.. py:function:: initialize(project, config = "default", inputs = "inputs")

    Initializes a project folder with a config file and inputs subfolder

    .. dropdown:: Initialize project

        ::

            initialize(project)

        Creates a project folder at the indicated path. If the folder already exists, then it must be empty. If the folder is None, attempts to initialize a project in the current directory. Saves a default configuration file in the project folder and creates an empty ``inputs`` subfolder.

    .. dropdown:: Config File Style

        ::

            initialize(..., config)

        Specifies the type of configuration file to save in the folder. Options are:

        .. list-table::
            :header-rows: 1

            * - Option
              - Description
            * - ``"default"``
              - Creates a config file with the most commonly used config fields
            * - ``"full"``
              - Creates a config file with all configurable fields
            * - ``"empty"``
              - Creates a config file that lists the wildcat version and nothing else
            * - ``"none"``
              - Does not create a config file

    .. dropdown:: Inputs subfolder

        ::

            initialize(..., inputs)

        Specifies the name of the empty **inputs** subfolder. By default, names the folder ``inputs``. Alternatively, set ``inputs=None`` to not create an empty subfolder.

    :Inputs:
        * **project** *Path-like* -- The path to the project folder
        * **config** *str* -- The type of config file to  create. Options are: default, full, empty, and none
        * **inputs** *str | None* -- The name for the empty inputs subfolder, or None to disable the creation of the subfolder.

    :Saves:
        Creates a project folder with an optional  ``configuration.py`` config file, and an optional empty ``inputs`` subfolder.

----

.. _python.preprocess:

.. py:function:: preprocess(project, *, config, inputs, preprocessed, perimeter, dem, dnbr, severity, kf, evt,retainments, excluded, included, iswater, isdeveloped, buffer_km, resolution_limits_m, resolution_check, dnbr_scaling_check, constrain_dnbr, dnbr_limits, severity_field, estimate_severity, severity_thresholds, contain_severity, kf_field, constrain_kf, max_missing_kf_ratio, missing_kf_check, kf_fill, kf_fill_field, water, developed, excluded_evt)

    Reproject and clean input datasets prior to hazard assessment. Please read the :doc:`preprocess overview </commands/preprocess>` for details.

    .. dropdown:: Preprocess Project

        ::

            preprocess(project, ...)
            preprocess(..., config)

        Runs the preprocessor for the indicated project folder. If project=None, interprets the current folder as the project folder. Preprocessor settings are determined by keyword inputs, configuration file values, and default wildcat settings. Settings are prioritized via the following hierachy:

            Keyword Args > Config File > Defaults

        Essentially, settings are first initialized to the wildcat defaults. These settings are then overridden by any settings defined in the configuration file. Finally, the settings are overridden by any values provided as keyword arguments. By default, searches for a configuration file named ``configuration.py`` at the root of the project. Use the ``config`` option to specify a different configuration file path.

    
    .. dropdown:: IO Folders

        ::

            preprocess(..., inputs, preprocessed)

        Specifies IO folders for the preprocessor. The ``inputs`` folder is the default folder in which the preprocessor will search for input datasets. The ``preprocessed`` folder is the folder in which preprocessed rasters will be saved.

    
    .. dropdown:: Data files

        ::

            preprocess(..., <files>)

        Specifies the path to an input datasets. Specific filenames are detailed in the following syntaxes. Relative paths are parsed relative to the ``inputs`` folder. If a path lacks an extension, scans supported extensions for a file with a matching file stem.


    .. dropdown:: Required Datasets

        ::

            preprocess(..., perimeter)
            preprocess(..., dem)

        Specifies paths to datasets required to run the preprocessor. The preprocessor will raise an error if it cannot locate these datasets. The extent of the buffered perimeter is used to define the spatial domain of the preprocessor, and the DEM is used to set the CRS, resolution, and alignment of the preprocessed rasters.

    
    .. dropdown:: Recommended Datasets

        ::

            preprocess(..., dnbr)
            preprocess(..., severity)
            preprocess(..., kf)
            preprocess(..., evt)

        Paths to datasets recommmended for most hazard assessments. The preprocessor will still run if these datasets are missing, but most users will need them later to implement an assessment. Set an input to False to disable the preprocessor for that dataset. The dnbr, severity, and kf datasets also support using a constant value across the watershed. This can be useful when a spatially complete dataset is not available. To implement a constant value, set the dataset equal to a number instead of a file path.

    
    .. dropdown:: Optional Datasets

        ::

            preprocess(..., retainments)
            preprocess(..., excluded)
            preprocess(..., included)
            preprocess(..., iswater)
            preprocess(..., isdeveloped)

        Paths to optional datasets. Neither the preprocessor nor the assessment requires these datasets. The ``retainments`` dataset indicates the location of debris retainment features, ``excluded`` and ``iswater`` indicate areas that should not be used for network delineation, and ``included`` and ``isdeveloped`` can be used to customize network filtering. Set an input to False to disable the preprocessor for that dataset.

    
    .. dropdown:: Buffered Perimeter

        ::

            preprocess(..., buffer_km)

        Specifies the burn perimeter buffer in kilometers.

    
    .. dropdown:: DEM

        ::

            preprocess(..., resolution_limits_m)
            preprocess(..., resolution_check)

        Options to check that the DEM has the expected resolution. In general, the DEM should have approximately 10 meter resolution, as wildcat's assessment models were calibrated using data from a 10 meter DEM. The ``resolution_limits_m`` input specifies a minimum and maximum allowed resolution in meters. The ``resolution_check`` option indicates what should happen when the DEM resolution is outside these limits. Options are:

        * ``"warn"``: Issues a warning
        * ``"error"``: Raises an error
        * ``"none"``: Does nothing

    
    .. dropdown:: dNBR

        ::

            preprocess(..., dnbr_scaling_check)
            preprocess(..., constrain_dnbr)
            preprocess(..., dnbr_limits)
        
        Options for preprocessing dNBR. The scaling check indicates what should happen if the dNBR values do not appear to be scaled correctly. Options are:

        * ``"warn"``: Issues a warning
        * ``"error"``: Raises an error
        * ``"none"``: Does nothing

        Use the ``constrain_dnbr`` switch to indicate whether the preprocessor should constrain dNBR values to a valid range. The ``dnbr_limits`` input is a 2-element vector specifying the lower and upper bound of the valid range.

    
    .. dropdown:: Burn Severity

        ::

            preprocess(..., severity_field)
            preprocess(..., estimate_severity)
            preprocess(..., severity_thresholds)
            preprocess(..., contain_severity)

        Options for preprocessing burn severity. Use the ``severity_field`` input to specify an attribute field holding severity data when the severity  is a set of Polygon features. Use the ``estimate_severity`` switch to indicate whether the preprocessor should estimate from dNBR when no other severity dataset is detected. The ``severity_thresholds`` input specifies the dNBR thresholds used to estimate severity from dNBR. Finally, use the ``contain_severity`` switch to indicate whether the preprocessor should contain severity data values to the fire perimeter mask.

    
    .. dropdown:: KF-factors

        ::

            preprocess(..., kf_field)
            preprocess(..., constrain_kf)
            preprocess(..., max_missing_kf_ratio)
            preprocess(..., missing_kf_check)
            preprocess(..., kf_fill)
            preprocess(..., kf_fill_field)

        Options for preprocessing KF-factors. Use ``kf_field`` to specify an attribute field holding KF-factor data when the KF-factor dataset is a set of Polygon features. The ``constrain_kf`` switch indicates whether the preprocessor should constrain KF-factor data to positive values. 
        
        The remaining options indicate what should happen when the KF-factor dataset has missing data. The ``max_missing_kf_ratio`` specifies a maximum allowed proportion of missing data in the KF-factor dataset. The ratio should be a value on the interval from 0 to 1. The ``missing_kf_check`` option indicates what should happen when the amount of missing data exceeds this ratio. Options are:
        
        * ``"warn"``: Issues a warning
        * ``"error"``: Raises an error
        * ``"none"``: Does nothing
        
        The ``missing_kf_threshold`` is the proportion of the KF-factor dataset that must be missing to trigger ``missing_kf_check``. The threshold should be a value on the interval from 0 to 1.
        
        Alternatively, users can provide fill values for missing KF-factor data using the ``kf_fill option``. Using fill values will disable the missing_kf_check. Options are:

        .. list-table::
            :header-rows: 1

            * - Option
              - Description
            * - ``False``
              - Does not fill missing KF-factor values
            * - ``True``
              - Fills missing values with the median value in the buffered perimeter
            * - Number
              - Fills missing values with the indicated value
            * - File path
              - Path to a file dataset used to implement spatially-varying fill values

        If ``kf_fill`` is a file path, then use the ``kf_fill_field`` input to indicate the name of fill file field that holds KF-factor fill data.

    
    .. dropdown:: EVT Masks

        ::

            preprocess(..., water)
            preprocess(..., developed)
            preprocess(..., excluded_evt)

        Indicate EVT integer codes that should be used to build processing masks. EVT pixels matching a water code or an excluded_evt code will be excluded from network delineation. EVT pixels matching a developed code will be used to build a human-development mask for network filtering. If you provide a set of EVT codes (``water``, ``developed``, ``excluded_evt``) and the corresponding input datasets (``iswater``, ``isdeveloped``, ``excluded``), then then two masks will be merged.


    :Inputs:
        * **project** *Path | str* -- The path to the project folder
        * **config** *Path | str* -- The path to the configuration file. Defaults to ``configuration.py`` in the project folder
        * **inputs** *Path | str* -- The path of the default folder used to locate input datasets
        * **preprocessed** *Path | str* -- The path of the folder in which preprocessed rasters are saved
        * **perimeter** *Path | str* -- A fire perimeter dataset
        * **dem** *Path | str* -- A digital elevation model dataset, ideally at 10 meter resolution
        * **dnbr** *Path | str* -- A difference normalized burn ratio (dNBR) dataset
        * **severity** *Path | str* -- A BARC4-like burn severity dataset
        * **kf** *Path | str* -- A KF-factor dataset
        * **evt** *Path | str* -- An existing vegetation type classification dataset
        * **retainments** *Path | str* -- Locations of debris retainment features
        * **excluded** *Path | str* -- Area that should be excluded from network delineation.
        * **included** *Path | str* -- Areas that should always be retained when filtering a network
        * **iswater** *Path | str* -- Areas that are water bodies
        * **isdeveloped** *Path | str* -- Areas that are human development
        * **buffer_km** *float* -- The buffer for the fire perimeter in kilometers
        * **resolution_limits_m** *[float, float]* -- The minimum and maximum allowed resolution in meters
        * **resolution_check** *str* -- What to do when the DEM does not have approximately 10 meter resolution. Options are "warn", "error", "none"
        * **dnbr_scaling_check** *str* -- What to do when the dNBR does not appear to be scaled properly. Options are "warn", "error", "none"
        * **constrain_dnbr** *bool* -- Whether to constrain dNBR values to a valid data range
        * **dnbr_limits** *[float, float]* -- The lower and upper bounds of the valid dNBR data range
        * **severity_field** *str* -- The data attribute field holding severity data when the severity dataset is a set of Polygon features
        * **estimate_severity** *bool* -- Whether to estimate severity from dNBR when no severity dataset is detected
        * **severity_thresholds** *[float, float, float]* -- The dNBR thresholds used to estimate severity classes
        * **contain_severity** *bool* -- Whether to contain severity data to the fire perimeter mask
        * **kf_field** *str* -- The data attribute field holding KF-factor data when the KF-factor dataset is a set of Polygon features
        * **constrain_kf** *bool* -- Whether KF-factor data should be constrained to positive values
        * **max_missing_kf_ratio** *float* -- The maximum allowed proportion of missing KF-factor data. Exceeding this level will trigger the missing_kf_check.
        * **missing_kf_check** *str* -- What to do when the KF-factor dataset has missing values. Options are "warn", "error", "none"
        * **kf_fill** *bool | float | Path | str* -- How to fill missing KF-factor values. Options are False, True (median value), a scalar value, or a path to a spatially dataset
        * **kf_fill_field** *str* -- The data attribute field holding KF-factor fill data when the kf_fill input is a set of Polygon features.
        * **water** *[float, ...]* -- EVT codes that should be classified as water
        * **developed** *[float, ...]* -- EVT codes that should be classified as human development
        * **excluded_evt** *[float, ...]* -- EVT codes that should be excluded from network delineation

    :Saves:
        Saves the collection of preprocessed rasters to the ``preprocessed`` folder. Also records the final config settings in configuration.txt.

----

.. _python.assess:

.. py:function:: assess(project, *, config, preprocessed, assessment, perimeter_p, dem_p, dnbr_p, severity_p, kf_p, retainments_p, excluded_p, included_p, iswater_p, isdeveloped_p, dem_per_m, min_area_km2, min_burned_area_km2, max_length_m, max_area_km2, max_exterior_ratio, min_burn_ratio, min_slope, max_developed_area_km2, max_confinement, confinement_neighborhood, flow_continuous, remove_ids, I15_mm_hr, volume_CI, durations, probabilities, locate_basins, parallelize_basins)

    Implements a hazard assessment using preprocessed datasets. Please read the :doc:`assess overview </commands/assess>` for details.

    
    .. dropdown:: Hazard Assessment

        ::

            assess(project, ...)
            assess(..., config)

        Runs an assessment for the indicated project folder. If ``project=None``, interprets the current folder as the project folder. Assessment settings are determined by keyword inputs, configuration file values, and default wildcat settings. Settings are prioritized via the following hierachy:

            Keyword Args > Config File > Defaults

        Essentially, settings are first initialized to the wildcat defaults. These settings are then overridden by any settings defined in the configuration file. Finally, the settings are overridden by any values provided as keyword arguments. By default, searches for a configuration file named ``configuration.py`` at the root of the project. Use the ``config`` option to specify a different configuration file path.

    
    .. dropdown:: IO Folders

        ::

            assess(..., preprocessed)
            assess(..., assessment)

        Specify paths to IO folders for the assessment. The  ``preprocessed`` folder is the default folder in which the assessment will search for preprocessed rasters. The ``assessment`` folder is where the assessment will save its results.

    
    .. dropdown:: Required datasets

        ::

            assess(..., perimeter_p)
            assess(..., dem_p)
            assess(..., dnbr_p)
            assess(..., severity_p)
            assess(..., kf_p)

        Specify the paths to preprocessed datasets required for the assessment. Most users will not need these inputs, as preprocessed datasets will be detected automatically from the ``preprocessed`` folder. Use these inputs if you want to override a preprocessed dataset with some other file.

    
    .. dropdown:: Optional datasets

        ::

            assess(..., retainments_p)
            assess(..., excluded_p)
            assess(..., included_p)
            assess(..., iswater_p)
            assess(..., isdeveloped_p)

        Specify the paths to optional preprocessed datasets. Use these inputs if you want to override one of the preprocessed datasets in the ``preprocessed`` folder. You can explicitly disable the use of a dataset by setting it equal to False.

    
    .. dropdown:: DEM Units

        ::

            assess(..., dem_per_m)

        By default, the assessment assumes the DEM is in meters. If this is not the case, use the ``dem_per_m`` option to indicate the conversion factor between DEM units and meters.

    
    .. dropdown:: Delineation

        ::

            assess(..., min_area_km2)
            assess(..., min_burned_area_km2)
            assess(..., max_length_m)

        :ref:`Network delineation <delineate>` parameters. The ``min_area_km2`` option indicates the minimum catchment area for considered pixels in square kilometers. Similarly, ``min_burned_area_km2`` is the minimum burned catchment area. The ``max_length_m`` parameter indicates the maximum allowed stream segment length in meters. Segments longer than this length will be split into multiple pieces.

    
    .. dropdown:: Filtering

        ::

            assess(..., max_area_km2)
            assess(..., max_exterior_ratio)
            assess(..., min_burn_ratio)
            assess(..., min_slope)
            assess(..., max_developed_area_km2)
            assess(..., max_confinement)
            assess(..., confinement_neighborhood)
            assess(..., flow_continuous)

        :ref:`Filtering <filter>` parameters. The ``max_area_km2`` input indicates the maximum catchment area (in kilometers^2) for retained segments. Segments that pass this check must also either (1) Be considered in the perimeter, or (2) Meet physical criteria for debris-flow risk. A segment is considered in the perimeter if both (A) the segment intersects the perimeter at any point, and (B) the segment's catchment is sufficiently within the perimeter. If the proportion of a catchment that is outside the perimeter exceeds ``max_exterior_ratio``, then the segment is not considered to be in the perimeter, and must pass the physical criteria check. To pass the physical criteria check, a segment must be sufficiently burned, steep, confined, and developed. Here, ``min_burn_ratio`` is the minimum proportion of burned catchment area to pass, ``min_slope`` is the minimum slope gradient, ``max_developed_area_km2`` is the maximum developed catchment area in kilometers^2, and ``max_confinement`` is the maximum allowed confinement angle (in degrees). Use the ``confinement_neighborhood`` to set the pixel radius used to compute confinement angle slopes. Finally, use the ``flow_continuous`` switch to indicate whether the filtering algorithm should preserve flow continuity.

    
    .. dropdown:: Remove IDs

        ::

            assess(..., remove_ids)

        Lists the IDs of segments that should be removed from the network. Use this option to remove problem segments after filtering. Note that any changes to network delineation will alter the segment IDs.

    
    .. dropdown:: Modeling Parameters

        ::

            assess(..., I15_mm_hr)
            assess(..., volume_CI)
            assess(..., durations)
            assess(..., probabilities)

        Set :ref:`hazard modeling <models>` parameters. ``I15_mm_hr`` are the 15-minute rainfall intensities (in millimeters per hour) used to estimate debris flow likelihoods, potential sediment volumes, and combined hazard classifications. The ``volume_CI`` input lists the confidence intervals that should be computed for the potential sediment volumes; these values should be on the interval from 0 to 1. The ``durations`` input are the rainfall durations that should be used to compute rainfall thresholds. Supported durations include 15, 30, and 60 minute intervals. The ``probabilities`` are the debris-flow probabilities that should be used to estimate rainfall thresholds. These should be on the interval from 0 to 1.

    
    .. dropdown:: Basins

        ::

            assess(..., locate_basins)
            assess(..., parallelize_basins)

        Options for locating terminal :ref:`outlet basins <basins>`. Locating outlet basins is a computationally expensive task, and these settings provide options to help with this step. Use ``locate_basins`` to indicate whether the assessment should attempt to locate basins at all. If False, the assessment will not save a ``basins.geojson`` output file, and you will not be able to export basin results. Use the ``parallelize_basins`` switch to indicate whether the assessment can locate the basins in parallel, using multiple CPUs. This option is disabled by default, as the parallelization overhead can worsen for small watershed. As a rule of thumb, parallelization will often improve runtime if the assessment requires more than 10 minutes to locate basins.

    :Inputs:
        * **project** *str | Path* -- The path to the project folder
        * **config** *str | Path* -- The path to the configuration file. Defaults to ``configuration.py`` in the project folder
        * **preprocessed** *str | Path* -- The path to the folder holding preprocessed rasters
        * **assessment** *str | Path* -- The path to the folder where assessment results will be saved
        * **perimeter_p** *str | Path* -- Path to the preprocessed perimeter
        * **dem_p** *str | Path* -- Path to the preprocessed DEM
        * **dnbr_p** *str | Path* -- Path to the preprocessed dNBR
        * **severity_p** *str | Path* -- Path to the preprocessed burn severity
        * **kf_p** *str | Path* -- Path to the preprocessed KF-factors
        * **retainments_p** *str | Path* -- Path to preprocessed retainment feature locations
        * **excluded_p** *str | Path* -- Path to preprocessed excluded area dataset
        * **included_p** *str | Path* -- Path to preprocessed dataset of areas retained during filtering
        * **iswater_p** *str | Path* -- Path to preprocessed water mask
        * **isdeveloped_p** *str | Path* -- Path to preprocessed human development mask
        * **dem_per_m** *float* Conversion factor between DEM units and meters
        * **min_area_km2** *float* -- Minimum catchment area in kilometers^2 of stream segment pixels
        * **min_burned_area_km2** *float* -- Minimum burned catchment area in kilometers^2 of stream segment pixels
        * **max_length_m** *float* -- Maximum stream segment length in meters
        * **max_area_km2** *float* -- Maximum catchment area in kilometers^2 of filtered segments
        * **max_exterior_ratio** *float* -- The maximum proportion of catchment area that can be outside the perimeter for a segment to still be considered inside the perimeter. On the interval from 0 to 1.
        * **min_burn_ratio** *float* -- The minimum proportion of burned catchment area needed to pass the physical filtering check. On the interval from 0 to 1.
        * **min_slope** *float* -- The minimum slope gradient needed to pass the physical filtering check
        * **max_developed_area_km2** *float* -- The maximum amount of developed catchment area (in kilometers^2) needed to pass the physical filtering check
        * **max_confinement** *float* -- The maximum confinement angle (in degrees) needed to pass the physical filtering check.
        * **confinement_neighborhood** *int* -- The pixel radius used to compute confinement angle slopes.
        * **flow_continuous** *bool* -- Whether to preserve flow continuity when filtering
        * **remove_ids** *[int, ...]* -- IDs of segments that should be removed from the filtered network
        * **I15_mm_hr** *[float, ...]* --: Peak 15-minute rainfall intensities (in millimeters per hour) used to compute likelihoods, volumes, and combined hazard
        * **volume_CI** *[float, ...]* -- The confidence intervals to computed for the volume estimates. On the interval from 0 to 1.
        * **durations** *[float, ...]* -- Rainfall durations (in minutes) used to estimate rainfall thresholds. Supports 15, 30, and 60 minute intervals.
        * **probabilities** *[float, ...]* -- Probability levels used to estimate rainfall thresholds. On the interval from 0 to 1.
        * **locate_basin** *bool* -- Whether to locate terminal outlet basins
        * **parallelize_basins** *bool* -- Whether to use multiple CPUs to locate basins

    :Saves:
        Saves ``segments.geojson``, ``outlets.geojson``, and optionally ``basins.geojson`` in the ``assessment`` folder. Also records the final config settings in ``configuration.txt``

----

.. _python.export:

.. py:function:: export(project, *, config, assessment, exports, format, export_crs, prefix, suffix, properties, exclude_properties, include_properties, order_properties, clean_names, rename)

    Export saved assessment results to GIS file formats.
    
    .. dropdown:: Export Results

        ::

            export(project, ...)
            export(..., config)

        Exports assessment results for the indicated project. If ``project=None``, interprets the current folder as the project folder.

        The ``export`` command allows users to convert assessment results to desired GIS file formats. Wildcat assessments include a large number of saved data fields (also known as **properties**), and so this command also allows users to select the fields that should be included in exported files. Finally, the command allows users to apply custom naming schemes to the exported properties.

        Export settings are determined by keyword inputs, configuration file values, and default wildcat settings. Settings are prioritized via the following hierachy:

            Keyword Args > Config File > Defaults

        Essentially, settings are first initialized to the wildcat defaults. These settings are then overridden by any settings defined in the configuration file. Finally, the settings are overridden by any values provided as keyword arguments. By default, searches for a configuration file named ``configuration.py`` at the root of the project. Use the ``config`` option to specify a different configuration file path.

    
    .. dropdown:: IO Folders

        ::

            export(..., assessment)
            export(..., exports)

        Specify paths to the IO folders for the export. The ``assessment`` folder is the default folder in which the command will search for saved assessment results. The ``exports`` folder is where the command will save exported files.

    
    .. dropdown:: File Format

        ::

            export(..., format)

        Specifies the file format of the exported files. Exports results for the segments, basins, and outlets to this file format. Commonly used formats include "Shapefile" and "GeoJSON". Consult the documentation for a complete list of :ref:`supported file formats <vector-formats>`.


    .. dropdown:: Coordinate Reference System (CRS)

        ::

            export(..., export_crs)

        Specifies the coordinate reference system (CRS) that the exported segment, basin, and outlet geometries should use. The base geometries from the assessment results will be reprojected into this CRS prior to export. Accepts a variety of CRS indicators, including: EPSG codes, CRS names, well-known text, and PROJ4 parameter strings. Consult the pyproj documentation details on supported inputs.

        Alternatively, set this option to "base" to leave the geometries in the base assessment CRS. In practice, this is the CRS of the preprocessed DEM used to derive the stream segment network.

    
    .. dropdown:: File Names

        ::

            export(..., prefix)
            export(..., suffix)

        Modifies the names of exported files. By default, exports files named ``segments``, ``basins``, and ``outlets`` holding the results for the respective features. Use these options to modify the names of the exported files. The ``prefix`` option specifies a string that will be prepended to each file name, and the ``suffix`` option is a string appended to the end of each name. As filenames, these options may only contain ASCII letters, numbers, hyphens ``-``, and underscores ``_``.

    
    .. dropdown:: Exported Properties

        ::

            export(..., properties)
            export(..., exclude_properties)
            export(..., include_properties)

        Specify the properties that should be included in the exported files. These inputs should be lists of strings and may include any combination of property names, result prefixes, and property groups. Read the :ref:`Property Guide <select-props>` for more details.

        The ``properties`` input specifies a base set of properties for export. The ``exclude_properties`` indicates properties that should be removed from this base group. This can be used to exclude specific properties when the ``properties`` input contains one or more property groups. Finally, the ``include_properties`` input indicates properties that should be added to the export, after ``exclude_properties`` has been implemented. This is typically used at the temporarily used at the command line to temporarily restore excluded properties.

    
    .. dropdown:: Property Order

        ::

            export(..., order_properties)

        Indicates whether the command should attempt to group related properties in the exported file. When True (default),  wildcat will cluster H, P, V, Vmin, and Vmax results by I15 values. Next, it will cluster R and I thresholds, first by rainfall duration, and then by probability level. Next, wildcat will group model result properties, then watershed characteristics, and finally filter checks. If ``order_properties=False``, exports properties in the order they are listed.

    
    .. dropdown:: Result Property Names

        ::

            export(..., clean_names)

        Indicates whether the command should attempt to convert dynamically named result properties to names that are more human-readable. Under-the-hood, wildcat uses a dynamic naming scheme for result properties using the indices of the hazard assessment parameters used to compute a particular result. When ``clean_names=True`` (default), the command will update the names such that parameter indices are converted to simplified parameter values. I15 values are converted to the nearest integer, volume CIs are multiplied by 100 and set to the nearest integer, rainfall durations are converted to integers, and probability levels are multiplied by 100 and set to the nearest integer. When ``clean_names=False``, exported properties retain their raw (index-based) names.

    
    .. dropdown:: Rename Properties

        ::

            export(..., rename)

        A dict specifying new names for exported properties. This input should be a dict with string keys. Keys may be property names, result prefixes, or hazard modeling parameters. Please read the :ref:`Renaming Guide <rename>` for more details. Keys that are property names or result prefixes should have a string value. If a property name, the string is the name of the property in the exported files. If a result prefix, the prefixes of exported results are updated, but any hazard modeling parameters in the name are retained. If the key is a hazard modeling parameter, then the value should be a list with one element per parameter. Each element should be a string, which will replace the parameter index or value in any associated property names.

        Complete property names have highest priority. So if a renaming dict contains a complete result property name, then its renaming value will override any result prefix or modeling parameter renaming options. 
        
        .. note:: 
            
            You may use any string as a renaming option, but not all file formats will support all names. For example, Shapefiles do not support property names with more than 10 characters. As a rule, wildcat will not check that renaming options are valid for a given export format. Verifying that new names are valid is left to the user.

    :Inputs:
        * **project** *Path | str* -- The path to the project folder
        * **config** *Path | str* -- The path to the configuration file. Defaults to ``configuration.py`` in the project folder
        * **assessment** *Path | str* -- The path to the folder holding saved assessment results
        * **exports** *Path | str* -- The path to the folder in which to save exported files
        * **format** *str* -- A string indicating the format of the exported files
        * **export_crs** *str | int | "base"* -- The CRS for the exported feature geometries
        * **prefix** *str* -- A string prepended to the beginning of exported file names
        * **suffix** *str* -- A string appended to the end of exported file names
        * **properties** *[str, ...]* -- A base list of properties that should be included in the exported files.
        * **exclude_properties** *[str, ...]* -- Properties that should be removed from the base list of exported properties.
        * **include_properties** *[str, ...]* -- Properties that should be added to the list of exported properties, following the removal of any excluded properties
        * **order_properties** *bool* -- True to cluster groups of related properties. False to export properties in listed order.
        * **clean_names** *bool* -- True to replace hazard parameter indices with simplified parameter values in result property names. False to retain the indices in the names.
        * **rename** *dict* -- A dict specifying renaming rules for exported properties

    :Saves:
        Saves vector features files for the segments, basins, and outlets in the indicated file format in the ``exports`` subfolder. Also records the final config settings in ``configuration.txt``.

----

.. _python.version:

.. py:function:: version()

    ::

        version()

    Returns the version string of the currently installed wildcat package.

    :Outputs:
        *str* -- The current wildcat version string
