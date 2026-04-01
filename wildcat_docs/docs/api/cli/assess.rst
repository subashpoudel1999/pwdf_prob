wildcat assess
==============

.. highlight:: bash


Synopsis
--------

**wildcat assess** [project] [options]


Description
-----------
Implements a hazard assessment using preprocessed input datasets. The major steps of the assessment are to characterize the watershed, design the stream segment network, run hazard assessment models, and save results to GeoJSON. . Please read the :doc:`Assess Overview </commands/assess>` for more details.

.. note::
    
    The options presented on this page will override their associated settings in ``configuration.py``.


Options
-------

.. program:: assess

Folders
+++++++

.. option:: project

    The project folder in which to run the assessment. If not provided, interprets the current folder as the project folder. The project folder is also the default location where the command will search for a configuration file.

    Examples::

        # Run hazard assessment
        wildcat assess my-project

        # Run assessment on current folder
        wildcat assess


.. option:: -c PATH, --config PATH

    Specifies the path to the configuration file. If a relative path, then the path is interpreted relative to the project folder. Defaults to ``configuration.py``.

    Example::

        # Use an alternate config file
        wildcat assess --config my-alternate-config.py


.. option:: -i PATH, --preprocessed PATH

    The folder in which to search for preprocessed datasets.

    Example::

        # Run assessment using preprocessed data from a different project subfolder
        wildcat assess --preprocessed my-other-preprocess

    *Overrides setting:* :confval:`preprocessed`


.. option:: -o PATH, --assessment PATH

    The folder in which to save assessment results.

    Example::

        # Save results to a specific subfolder
        wildcat assess --assessment my-other-assessment

    *Overrides setting:* :confval:`assessment`


Required Datasets
+++++++++++++++++

Paths to preprocessed datasets required for the assessment. Most users will not need these options, as the assessment will detect preprocessed datasets in the ``preprocessed`` folder automatically. Use these options when a preprocessed dataset is not in the ``preprocessed`` folder.

.. option:: --perimeter-p PATH

    Path to the preprocessed buffered fire perimeter.

    *Overrides setting:* :confval:`perimeter_p`


.. option:: --dem-p PATH

    Path to the preprocessed DEM dataset.

    *Overrides setting:* :confval:`dem_p`


.. option:: --dnbr-p PATH

    Path to the preprocessed dNBR dataset.

    *Overrides setting:* :confval:`dnbr_p`


.. option:: --severity-p PATH

    Path to the preprocessed burn severity dataset.

    *Overrides setting:* :confval:`severity_p`


.. option:: --kf-p PATH

    Path to the preprocessed KF-factor dataset.

    *Overrides setting:* :confval:`kf_p`


Optional Masks
++++++++++++++

Paths to optional preprocessed masks used to implement an assessment. Most users will not need these options as the command will detect preprocessed datasets in the ``preprocessed`` folder automatically. The most common use of these options is to disable the use of a preprocessed raster. Do this by setting an option's path to None.

Example::

    # Run assessment without an exclusion mask
    wildcat assess --excluded-p None


.. option:: --retainments-p PATH

    Path to a preprocessed retainment feature location mask.

    *Overrides setting:* :confval:`retainments_p`


.. option:: --excluded-p PATH

    Path to a preprocessed mask of pixels excluded from network delineation.

    *Overrides setting:* :confval:`excluded_p`


.. option:: --included-p PATH

    Path to a mask of areas retained during network filtering.

    *Overrides setting:* :confval:`included_p`


.. option:: --iswater-p PATH

    Path to a preprocessed water mask.

    *Overrides setting:* :confval:`iswater_p`


.. option:: --isdeveloped-p PATH

    Path to a preprocessed human development mask.

    *Overrides setting:* :confval:`isdeveloped_p`


DEM Units
+++++++++

.. option:: --dem-per-m FACTOR

    The number of DEM elevation units per meter. Use this option when the DEM uses units other than meters.

    Example::

        # Run assessment for a DEM measured in feet
        wildcat assess --dem-per-m 3.28

    *Overrides setting:* :confval:`dem_per_m`


Delineation
+++++++++++
Options used to :ref:`delineate` the initial stream segment network.

.. option:: --min-area-km2 AREA

    The minimum catchment area in square kilometers (km²). Pixels with smaller catchments will not be used to delineate the stream segment network.

    Example::

        # Require catchment of at least 0.025 km2
        wildcat assess --min-area-km2 0.025

    *Overrides setting:* :confval:`min_area_km2`


.. option:: --min-burned-area-km2 AREA

    The minimum burned catchment area in square kilometers (km²). Pixels outside of the fire perimeter with less burned catchment area will not be used to delineate stream segments.

    Example::

        # Require at least 0.01 km2 of burned area outside the perimeter
        wildcat assess --min-burned-area-km2 0.01

    *Overrides setting:* :confval:`min_burned_area_km2`


.. option:: --max-length-m LENGTH

    The maximum allowed stream segment length in meters. Stream segments longer than this length will be split into multiple segments.

    Example::

        # Split segments longer than 500 meters
        wildcat assess --max-length-m 500

    *Overrides setting:* :confval:`max_length_m`


Filtering
+++++++++
Options used to :ref:`filter` the stream segment network.

.. option:: --max-area-km2 AREA

    Maximum catchment area in square kilometers (km²). Segments whose catchments exceed this size are considered to have flood-like behavior, rather than debris flow-like behavior. These segments will be removed from the network unless they intersect an included area mask.

    Example::

        # Discard segments with catchments over 8 km2
        wildcat assess --max-area-km2 8

    *Overrides setting:* :confval:`max_area_km2`


.. option:: --max-exterior-ratio RATIO

    Maximum proportion of catchment outside the fire perimeter (from 0 to 1). Used to determine whether segments are considered in the fire perimeter. If a segment's catchment is greater than or equal to this value, then the segment is considered outside the perimeter.

    Examples::

        # Set the threshold to 95% within the perimeter
        wildcat assess --max-exterior-ratio 0.95

    *Overrides setting:* :confval:`max_exterior_ratio`


.. option:: --min-burn-ratio RATIO

    The minimum proportion of burned catchment area (from 0 to 1). Used to check if a segment is sufficiently burned. A segment will fail the check if the burned proportion of its catchment is less than this value. 

    Example::

        # Require the catchment to be at least 25% burned
        wildcat assess --min-burn-ratio 0.25

    *Overrides setting:* :confval:`min_burn_ratio`


.. option:: --min-slope GRADIENT

    The minimum average slope gradient along the stream segment. Used to check if a stream segment is sufficiently steep. A segment will fail the check if its average slope gradient is less than this value.

    Example::

        # Require a slope of at least 12%
        wildcat assess --min-slope 0.12

    *Overrides setting:* :confval:`min_slope`


.. option:: --max-developed-area-km2 AREA

    The maximum amount of developed catchment area in square kilomters. Used to check if a segment is sufficiently undeveloped. A segment will fail the check if the amount of developed catchment is greater than this value.

    Example::

        # Segments cannot have more the 0.025 km2 of development
        wildcat assess --max-developed-area-km2 0.025

    *Overrides setting:* :confval:`max_developed_area_km2`


.. option:: --max-confinement ANGLE

    The maximum confinement angle in degrees. Used to check if a segment is sufficiently confined. A segment will fail the check if its confinement angle is greater than this value.

    Example::

        # Do not allow confinement angles greater than 174 degrees
        wildcat assess --max-confinement 174

    *Overrides setting:* :confval:`max_confinement`


.. option:: --neighborhood N

    The pixel radius used to compute confinement angles.

    Example::

        # Use a 4-pixel radius to compute confinement angles
        wildcat assess --neighborhood 4

    *Overrides setting:* :confval:`confinement_neighborhood`


.. option:: --filter-in-perimeter

    Require all segments to pass the :ref:`physical filtering <physical-filter>` criterion. Segments in the perimeter do not receive a separate filter. This option is a shortcut used to set :confval:`max_exterior_ratio` to 0. Using this option will also override any value passed via the :option:`--max-exterior-ratio <assess --max-exterior-ratio>` command line option.

    Example::

        # Require segments in the perimeter to pass physical filters
        # (i.e. disable the perimeter criterion)
        wildcat assess --filter-in-perimeter

    *Overrides setting:* :confval:`max_exterior_ratio`


.. option:: --not-continuous

    Do not preserve flow continuity in the network. All segments that fail both the perimeter and physical filtering criteria will be discarded.

    Example::

        # Do not preserve flow continuity
        wildcat assess --not-continuous

    *Overrides setting:* :confval:`flow_continuous`


Remove IDs
++++++++++

.. option:: --remove-ids ID...

    The segment IDs of segments that should be removed from the network after filtering. Useful when the network contains a small number of problem segments. You can obtain Segment IDs by examining the ``Segment_ID`` field in the :ref:`assessment results <default-properties>`. Segment IDs are constant after delineation, but can change if you alter :ref:`delineation settings <id-changes>`.

    Example::

        # Remove segments 7, 19, and 22
        wildcat assess --remove-ids 7 19 22

    *Overrides setting:* :confval:`remove_ids`


Hazard Modeling
+++++++++++++++

Parameters for running the :ref:`hazard assessment models <models>`. 

.. option:: --I15-mm-hr INTENSITY...

    Peak 15-minute rainfall intensities in millimeters per hour. Used to compute debris-flow likelihoods and volumes, which are used to classify combined hazards.

    Example::

        # Estimate likelihood, volumes and hazards
        # for I15 of 16, 20, 24, and 40 mm/hour
        wildcat assess --I15-mm-hr 16 20 24 40

    *Overrides setting:* :confval:`I15_mm_hr`


.. option:: --volume-CI CI...

    The confidence intervals to calculate for the volume estimates (from 0 to 1).

    Example::

        # Compute 90% and 95% confidence intervals
        wildcat assess --volume-CI 0.9 0.95

    *Overrides setting:* :confval:`volume_CI`


.. option:: --durations DURATION

    The rainfall durations (in minutes) that should be used to estimate rainfall thresholds. Only values of 15, 30, and 60 are supported.

    Example::

        # Compute thresholds for all 3 rainfall durations
        wildcat assess --durations 15 30 60

    *Overrides setting:* :confval:`durations`


.. option:: --probabilities P...

    The debris-flow probability levels used to estimate rainfall thresholds (from 0 to 1).

    Example::

        # Compute thresholds for 50% and 75% probability levels
        wildcat assess --probabilities 0.5 0.75

    *Overrides setting:* :confval:`probabilities`


Basins
++++++
Options for locating :ref:`outlet basins <basins>`.


.. option:: --parallel

    Use multiple CPUs to locate outlet basins. Uses the number of available CPUs - 1. (One is reserved for the current process). 
    
    .. tip::
        
        Parallelization overhead can actually *slow down* the analysis for small watersheds. As a rule of thumb, this option is most appropriate if the analysis requires 10+ minutes to locate basins.

    Example::

        # Use multiple CPUs to locate basins
        wildcat assess --parallel

    *Overrides setting:* :confval:`parallelize_basins`


.. option:: --no-basins

    Does not locate terminal outlet basins. This can significantly speed up runtime, but the output hazard assessment results will not include values for the basins.

    Example::

        # Do not locate outlet basins
        wildcat assess --no-basins


Logging
+++++++

.. option:: -q, --quiet

    Does not print progress messages to the console. Warnings and errors will still be printed.

.. option:: -v, --verbose

    Print detailed progress messages to the console. Useful for debugging.

.. option:: --log PATH

    Prints a `DEBUG level`_ log record to the indicated file. If the file does not exists, creates the file. If the file already exists, appends the log record to the end.

    Example::

        wildcat assess --log my-log.txt

.. _DEBUG level: https://docs.python.org/3/library/logging.html#logging.DEBUG


Traceback
+++++++++

.. option:: -t, --traceback

    Prints the full error traceback to the console when an error occurs. (Useful for debugging). If this option is not provided, then only the final error message is printed. 
