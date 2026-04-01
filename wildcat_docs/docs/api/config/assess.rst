Assessment Configuration
========================

.. highlight:: python

These fields specify settings used to :doc:`run an assessment </commands/assess>`.


Required Datasets
-----------------
Paths to preprocessed datasets that are required to run an assessment. Most users will not need these settings as the assessment will automatically detect datasets in the ``preprocessed`` folder. Use these fields if a preprocessed dataset is located in a different folder.

.. confval:: perimeter_p
    :type: ``str | Path``
    :default: ``r"perimeter"``

    The path to the preprocessed fire perimeter raster.

    *CLI option:* :option:`--perimeter-p <assess --perimeter-p>`

    *Python kwarg:* |perimeter_p kwarg|_

.. |perimeter_p kwarg| replace:: ``perimeter_p``

.. _perimeter_p kwarg: ./../python.html#python-assess


.. confval:: dem_p
    :type: ``str | Path``
    :default: ``r"dem"``

    The path to the preprocessed DEM raster.

    *CLI option:* :option:`--dem-p <assess --dem-p>`

    *Python kwarg:* |dem_p kwarg|_

.. |dem_p kwarg| replace:: ``dem_p``

.. _dem_p kwarg: ./../python.html#python-assess


.. confval:: dnbr_p
    :type: ``str | Path``
    :default: ``r"dnbr"``

    The path to the preprocessed dNBR raster.

    *CLI option:* :option:`--dnbr-p <assess --dnbr-p>`

    *Python kwarg:* |dnbr_p kwarg|_

.. |dnbr_p kwarg| replace:: ``dnbr_p``

.. _dnbr_p kwarg: ./../python.html#python-assess


.. confval:: severity_p
    :type: ``str | Path``
    :default: ``r"severity"``

    The path to the preprocessed burn severity raster.

    *CLI option:* :option:`--severity-p <assess --severity-p>`

    *Python kwarg:* |severity_p kwarg|_

.. |severity_p kwarg| replace:: ``severity_p``

.. _severity_p kwarg: ./../python.html#python-assess


.. confval:: kf_p
    :type: ``str | Path``
    :default: ``r"kf"``

    The path to the preprocessed KF-factor raster.

    *CLI option:* :option:`--kf-p <assess --kf-p>`

    *Python kwarg:* |kf_p kwarg|_

.. |kf_p kwarg| replace:: ``kf_p``

.. _kf_p kwarg: ./../python.html#python-assess



Optional Masks
--------------
Paths to optional data masks used to implement an assessment.  Most users will not need these settings as the assessment will automatically detect datasets in the ``preprocessed`` folder. The most common use of these fields is to disable the use of a preprocessed raster. Do this by setting the field's value to ``None``.

Example::

    # Run assessment without an exclusion mask
    excluded_p = None

.. confval:: retainments_p
    :type: ``str | Path``
    :default: ``r"retainments"``

    The path to the preprocessed retainment feature mask.

    *CLI option:* :option:`--retainments-p <assess --retainments-p>`

    *Python kwarg:* |retainments_p kwarg|_

.. |retainments_p kwarg| replace:: ``retainments_p``

.. _retainments_p kwarg: ./../python.html#python-assess


.. confval:: excluded_p
    :type: ``str | Path``
    :default: ``r"excluded"``

    The path to the preprocessed excluded area mask.

    *CLI option:* :option:`--excluded-p <assess --excluded-p>`

    *Python kwarg:* |excluded_p kwarg|_

.. |excluded_p kwarg| replace:: ``excluded_p``

.. _excluded_p kwarg: ./../python.html#python-assess


.. confval:: included_p
    :type: ``str | Path``
    :default: ``r"included"``

    The path to the preprocessed included area mask.

    *CLI option:* :option:`--included-p <assess --included-p>`

    *Python kwarg:* |included_p kwarg|_

.. |included_p kwarg| replace:: ``included_p``

.. _included_p kwarg: ./../python.html#python-assess


.. confval:: iswater_p
    :type: ``str | Path``
    :default: ``r"iswater"``

    The path to the preprocessed water mask.

    *CLI option:* :option:`--iswater-p <assess --iswater-p>`

    *Python kwarg:* |iswater_p kwarg|_

.. |iswater_p kwarg| replace:: ``iswater_p``

.. _iswater_p kwarg: ./../python.html#python-assess


.. confval:: isdeveloped_p
    :type: ``str | Path``
    :default: ``r"isdeveloped"``

    The path to the preprocessed development mask.

    *CLI option:* :option:`--isdeveloped-p <assess --isdeveloped-p>`

    *Python kwarg:* |isdeveloped_p kwarg|_

.. |isdeveloped_p kwarg| replace:: ``isdeveloped_p``

.. _isdeveloped_p kwarg: ./../python.html#python-assess



DEM Units
---------

.. confval:: dem_per_m
    :type: ``float``
    :default: ``1``

    The number of DEM elevation units per meter. Use this setting when the DEM has units other than meters.

    Example::

        # Run assessment for a DEM measured in feet
        dem_per_m = 3.28

    *CLI option:* :option:`--dem-per-m <assess --dem-per-m>`

    *Python kwarg:* |dem_per_m kwarg|_

.. |dem_per_m kwarg| replace:: ``dem_per_m``

.. _dem_per_m kwarg: ./../python.html#python-assess


Delineation
-----------
Settings used to :ref:`delineate <delineate>` the initial stream segment network.

.. confval:: min_area_km2
    :type: ``float``
    :default: ``0.025``

    The minimum catchment area in square kilometers (km²). Pixels with smaller catchments will not be used to delineate stream segments.

    *CLI option:* :option:`--min-area-km2 <assess --min-area-km2>`

    *Python kwarg:* |min_area_km2 kwarg|_

.. |min_area_km2 kwarg| replace:: ``min_area_km2``

.. _min_area_km2 kwarg: ./../python.html#python-assess


.. confval:: min_burned_area_km2
    :type: ``float``
    :default: ``0.01``

    The minimum burned catchment area in square kilometers (km²). Pixels outside of the fire perimeter with less burned catchment area will not be used to delineate stream segments.

    *CLI option:* :option:`--min-burned-area-km2 <assess --min-burned-area-km2>`

    *Python kwarg:* |min_burned_area_km2 kwarg|_

.. |min_burned_area_km2 kwarg| replace:: ``min_burned_area_km2``

.. _min_burned_area_km2 kwarg: ./../python.html#python-assess


.. confval:: max_length_m
    :type: ``float``
    :default: ``500``

    The maximum allowed stream segment length in meters. Stream segments longer than this length will be split into multiple segments.

    *CLI option:* :option:`--max-length-m <assess --max-length-m>`

    *Python kwarg:* |max_length_m kwarg|_

.. |max_length_m kwarg| replace:: ``max_length_m``

.. _max_length_m kwarg: ./../python.html#python-assess



Filtering
---------
Settings used to :ref:`filter <filter>` the stream segment network.

.. confval:: max_area_km2
    :type: ``float``
    :default: ``8``

    Maximum catchment area in square kilometers (km²). Segments whose catchments exceed this size are considered to have flood-like behavior, rather than debris flow-like behavior. These segments will be removed from the network unless they intersect an included area mask.
    
    Example::

        # Discard segments with catchments over 8 km2
        max_area_km2 = 8

    *CLI option:* :option:`--max-area-km2 <assess --max-area-km2>`

    *Python kwarg:* |max_area_km2 kwarg|_

.. |max_area_km2 kwarg| replace:: ``max_area_km2``

.. _max_area_km2 kwarg: ./../python.html#python-assess


.. confval:: max_exterior_ratio
    :type: ``float``
    :default: ``0.95``

    Maximum proportion of catchment outside the fire perimeter (from 0 to 1). Used to determine whether segments are considered in the fire perimeter. If a segment's catchment is greater than or equal to this value, then the segment is considered outside the perimeter. Set this parameter to 0 to require all segments to pass the :ref:`physical filtering <physical-filter>` criterion.

    Examples::

        # Set the threshold to 95% within the perimeter
        max_exterior_ratio = 0.95

        # Require all segments to pass the physical criterion
        max_exterior_ratio = 0

    *CLI options:* :option:`--max-exterior-ratio <assess --max-exterior-ratio>`, :option:`--filter-in-perimeter <assess --filter-in-perimeter>`

    *Python kwarg:* |max_exterior_ratio kwarg|_

.. |max_exterior_ratio kwarg| replace:: ``max_exterior_ratio``

.. _max_exterior_ratio kwarg: ./../python.html#python-assess


.. confval:: min_slope
    :type: ``float``
    :default: ``0.12``

    The minimum average slope gradient along the stream segment. Used to check if a stream segment is sufficiently steep. A segment will fail the check if its average slope gradient is less than this value.

    Example::

        # Require a slope of at least 12%
        min_slope = 0.12

    *CLI option:* :option:`--min-slope <assess --min-slope>`

    *Python kwarg:* |min_slope kwarg|_

.. |min_slope kwarg| replace:: ``min_slope``

.. _min_slope kwarg: ./../python.html#python-assess



.. confval:: min_burn_ratio
    :type: ``float``
    :default: ``0.25``

    The minimum proportion of burned catchment area (from 0 to 1). Used to check if a segment is sufficiently burned. A segment will fail the check if the burned proportion of its catchment is less than this value. 

    Example::

        # Require the catchment to be at least 25% burned
        min_burn_ratio = 0.25

    *CLI option:* :option:`--min-burn-ratio <assess --min-burn-ratio>`

    *Python kwarg:* |min_burn_ratio kwarg|_

.. |min_burn_ratio kwarg| replace:: ``min_burn_ratio``

.. _min_burn_ratio kwarg: ./../python.html#python-assess



.. confval:: max_developed_area_km2
    :type: ``float``
    :default: ``0.025``

    The maximum amount of developed catchment area in square kilomters. Used to check if a segment is sufficiently undeveloped. A segment will fail the check if the amount of developed catchment is greater than this value.

    Example::

        # Segments cannot have more the 0.025 km2 of development
        max_developed_area_km2 = 0.025

    *CLI option:* :option:`--max-developed-area-km2 <assess --max-developed-area-km2>`

    *Python kwarg:* |max_developed_area_km2 kwarg|_

.. |max_developed_area_km2 kwarg| replace:: ``max_developed_area_km2``

.. _max_developed_area_km2 kwarg: ./../python.html#python-assess



.. confval:: max_confinement
    :type: ``float``
    :default: ``174``

    The maximum confinement angle in degrees. Used to check if a segment is sufficiently confined. A segment will fail the check if its confinement angle is greater than this value.

    Example::

        # Do not allow confinement angles greater than 174 degrees
        max_confinement = 174

    *CLI option:* :option:`--max-confinement <assess --max-confinement>`

    *Python kwarg:* |max_confinement kwarg|_

.. |max_confinement kwarg| replace:: ``max_confinement``

.. _max_confinement kwarg: ./../python.html#python-assess



.. confval:: confinement_neighborhood
    :type: ``int``
    :default: ``4``

    The pixel radius used to compute confinement angles.

    Example::

        # Use a 4-pixel radius to compute confinement angles
        confinement_neighborhood = 4

    *CLI option:* :option:`--neighborhood <assess --neighborhood>`

    *Python kwarg:* |confinement_neighborhood kwarg|_

.. |confinement_neighborhood kwarg| replace:: ``confinement_neighborhood``

.. _confinement_neighborhood kwarg: ./../python.html#python-assess



.. confval:: flow_continuous
    :type: ``bool``
    :default: ``True``

    Whether to preserve flow continuity in the network. If ``True``, segments whose removal would break flow continuity will be retained in the network, even if they fail the filters. If ``False``, all segments that fail the filters will be removed.

    Example::

        # Do not preserve flow continuity
        flow_continuous = False

    *CLI option:* :option:`--not-continuous <assess --not-continuous>`

    *Python kwarg:* |flow_continuous kwarg|_

.. |flow_continuous kwarg| replace:: ``flow_continuous``

.. _flow_continuous kwarg: ./../python.html#python-assess



Remove IDs
++++++++++

.. confval:: remove_ids
    :type: ``[int, ...]``
    :default: ``[]``

    The segment IDs of segments that should be removed from the network after filtering. Useful when the network contains a small number of problem segments. You can obtain Segment IDs by examining the ``Segment_ID`` field in the :ref:`assessment results <default-properties>`. Segment IDs are constant after delineation, but can change if you alter :ref:`delineation settings <id-changes>`.

    Example::

        # Remove segments 7, 19, and 22
        remove_ids = [7, 19, 22]

    *CLI option:* :option:`--remove-ids <assess --remove-ids>`

    *Python kwarg:* |remove_ids kwarg|_

.. |remove_ids kwarg| replace:: ``remove_ids``

.. _remove_ids kwarg: ./../python.html#python-assess



Hazard Modeling
+++++++++++++++
Numeric parameters used to :ref:`run the hazard assessment models <models>`.

.. confval:: I15_mm_hr
    :type: ``[float, ...]``
    :default: ``[16, 20, 24, 40]``

    Peak 15-minute rainfall intensities in millimeters per hour. Used to compute debris-flow likelihoods and volumes, which are used to classify combined hazards.

    Example::

        # Estimate likelihood, volumes and hazards
        # for I15 of 16, 20, 24, and 40 mm/hour
        I15_mm_hr = [16, 20, 24, 40]

    *CLI option:* :option:`--I15-mm-hr <assess --I15-mm-hr>`

    *Python kwarg:* |I15_mm_hr kwarg|_

.. |I15_mm_hr kwarg| replace:: ``I15_mm_hr``

.. _I15_mm_hr kwarg: ./../python.html#python-assess



.. confval:: volume_CI
    :type: ``[float, ...]``
    :default: ``[0.95]``

    The confidence intervals to calculate for the volume estimates (from 0 to 1).

    Example::

        # Compute 90% and 95% confidence intervals
        volume_CI = [0.9, 0.95]

    *CLI option:* :option:`--volume-CI <assess --volume-CI>`

    *Python kwarg:* |volume_CI kwarg|_

.. |volume_CI kwarg| replace:: ``volume_CI``

.. _volume_CI kwarg: ./../python.html#python-assess



.. confval:: durations
    :type: ``[float, ...]``
    :default: ``[15, 30, 60]``

    The rainfall durations (in minutes) that should be used to estimate rainfall thresholds. Only values of 15, 30, and 60 are supported.

    Example::

        # Compute thresholds for all 3 rainfall durations
        durations = [15, 30, 60]

    *CLI option:* :option:`--durations <assess --durations>`

    *Python kwarg:* |durations kwarg|_

.. |durations kwarg| replace:: ``durations``

.. _durations kwarg: ./../python.html#python-assess



.. confval:: probabilities
    :type: ``[float, ...]``
    :default: ``[0.5, 0.75]``

    The debris-flow probability levels used to estimate rainfall thresholds (from 0 to 1).

    Example::

        # Compute thresholds for 50% and 75% probability levels
        probabilities = [0.5, 0.75]

    *CLI option:* :option:`--probabilities <assess --probabilities>`

    *Python kwarg:* |probabilities kwarg|_

.. |probabilities kwarg| replace:: ``probabilities``

.. _probabilities kwarg: ./../python.html#python-assess



Basins
++++++
Options for locating :ref:`outlet basins <basins>`.

.. confval:: locate_basins
    :type: ``bool``
    :default: ``True``

    Whether to locate outlet basins. Setting this to ``False`` can significantly speed up runtime, but the assessment results will not include values for the basins.

    Example::

        # Do not locate outlet basins
        locate_basins = False

    *CLI option:* :option:`--no-basins <assess --no-basins>`

    *Python kwarg:* |locate_basins kwarg|_

.. |locate_basins kwarg| replace:: ``locate_basins``

.. _locate_basins kwarg: ./../python.html#python-assess


.. confval:: parallelize_basins
    :type: ``bool``
    :default: ``False``

    Whether to use multiple CPUs to locate outlet basins. Using this option creates restrictions for running wildcat within Python. Consult the following for details: :ref:`Parallelizing Basins <basins>`
    
    Example::

        # Use multiple CPUs to locate basins
        parallelize_basins = True

    *CLI option:* :option:`--parallel <assess --parallel>`

    *Python kwarg:* |parallelize_basins kwarg|_

.. |parallelize_basins kwarg| replace:: ``parallelize_basins``

.. _parallelize_basins kwarg: ./../python.html#python-assess