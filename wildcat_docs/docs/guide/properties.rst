Data Fields
===========

.. highlight:: python

When wildcat runs an assessment, it stores a variety of data fields (often called **properties**) in the output ``segments.geojson`` and ``basins.geojson`` files. Users may read these fields directly from the output files, or use the :doc:`export command </commands/export>` to extract specific variables of interest. Users can also use the export command to rename data fields from their default names. The remainder of this page describes these data fields and various export options.

----

.. _default-properties:

Assessment Properties
---------------------

When wildcat runs an assessment, it saves a variety of data fields in the output ``segments.geojson`` and ``basins.geojson`` files. First are a set of variables characterizing the stream segment watersheds:

.. _watershed-props:

.. list-table::
    :header-rows: 1

    * - Watershed Variable
      - Description
      - Units
    * - ``Segment_ID``
      - A unique, constant ID for each segment in the network. Set during network delineation.
      - N/A
    * - ``Area_km2``
      - Total catchment area
      - Square kilometers (km²)
    * - ``ExtRatio``
      - The proportion of catchment area that is outside the fire perimeter
      - From 0 to 1
    * - ``BurnRatio``
      - The proportion of burned catchment area.
      - From 0 to 1
    * - ``Slope``
      - The average slope gradient along the stream segment.
      - Gradient
    * - ``ConfAngle``
      - The average confinement angle along the stream segment
      - Degrees
    * - ``DevAreaKm2``
      - The total developed catchment area
      - Square kilometers (km²)

Next are a series of boolean (0/False or 1/True) variables used to implement network filtering:

.. _filter-props:

.. list-table::
    :header-rows: 1

    * - Filter Check
      - Description
    * - ``IsIncluded``
      - True if the segment intersects an included area mask.
    * - ``IsFlood``
      - True if the segment's catchment exceeds the maximum size
    * - ``IsAtRisk``
      - True if the segment passes either of the perimeter or physical filtering criteria
    * - ``IsInPerim``
      - True if the segment passes the fire perimeter criterion
    * - ``IsXPerim``
      - True if the segment intersects the fire perimeter
    * - ``IsExterior``
      - True if the segment's catchment is considered outside the fire perimeter
    * - ``IsPhysical``
      - True if the segment passes the physical criterion
    * - ``IsBurned``
      - True if a sufficient proportion of the catchment area is burned
    * - ``IsSteep``
      - True if the segment has a sufficiently steep slope gradient
    * - ``IsConfined``
      - True if the segment has a sufficiently low confinement angle
    * - ``IsUndev``
      - True if the segment's catchment is sufficiently undeveloped.
    * - ``IsFlowSave``
      - True if a segment should be retained to preserve flow continuity.

And then a series of variables used as inputs to the hazard assessment models:

.. _input-props:

.. list-table::
    :header-rows: 1

    * - Model Input
      - Description
    * - ``Terrain_M1``
      - Terrain variable for the M1 model. The proportion of catchment area with both (1) moderate-or-high burn severity, and (2) slope angle ≥ 23 degrees
    * - ``Fire_M1``
      - Fire variable for the M1 model. Mean catchment dNBR divided by 1000.
    * - ``Soil_M1``
      - Soil variable for the M1 model. Mean catchment KF-factor.
    * - ``Bmh_km2``
      - Catchment area burned at moderate or high severity in square kilometers. Used to implement the volume model.
    * - ``Relief_m``
      - Vertical relief in meters. Used to implement the volume model.


The number of hazard model results will depend on the number of values used for each hazard modeling parameter. To accommodate this, wildcat assigns result names using a prefixed indexing scheme. When you export hazard model results, wildcat will replace these indices with simplified parameter values. To generate these name, ``probabilities`` and ``volume_CI`` values are first multiplied by 100. Then, all parameter values are rounded to the nearest integer and subsitituted for the relevant index. The following table summarizes these names:

.. _result-props:

.. list-table::
  :header-rows: 1

  * - Assessment Name
    - Exported Name
    - Description
  * - ``H_{i}``
    - ``H_{I15}mmh``
    - Combined hazard classifications for the ith I15 value
  * - ``P_{i}``
    - ``P_{I15}mmh``
    - Debris-flow likelihoods for the ith I15 value
  * - ``V_{i}``
    - ``V_{I15}mmh``
    - Potential sediment volumes for the ith I15 value
  * - ``Vmin_{i}_{j}``
    - ``Vmin_{I15}_{CI}``
    - Lower bound of the jth confidence interval for potential sediment volumes for the ith I15 value
  * - ``Vmax_{i}_{j}``
    - ``Vmax_{I15}_{CI}``
    - Upper bound of the jth confidence interval for potential sediment volumes for the ith I15 value
  * - ``R_{d}_{p}``
    - ``R{dur}_{prob}``
    - Rainfall accumulations for the dth rainfall duration and the pth probability level
  * - ``I_{d}_{p}``
    - ``I{dur}_{prob}``
    - Rainfall intensities for the dth rainfall duration and the pth probability level

Wildcat follows Python conventions and uses 0-indexing to indicate parameter values. So the first value of a parameter will have an index of 0, the second value will have an index of 1, and so on.

.. tip:: 

    You can learn more about how wildcat estimates hazards in the :doc:`assess command overview</commands/assess>`.


Example Result Names
++++++++++++++++++++
This section provides an example of how model result property names are generated. Consider an assessment run with the following configuration::

    I15_mm_hr = [16, 20, 24]
    volume_CI = [0.9, 0.95]
    durations = [15, 30, 60]
    probabilities = [0.5, 0.75]

In this case, the output assessment files will include the following properties:

.. dropdown:: Show Properties

    .. list-table::
      :header-rows: 1

      * - Assessment Name
        - Exported Name
        - Description
      * - ``H_0``
        - ``H_16mmh``
        - Combined hazard classification for a peak 15-minute rainfall intensity of 16 mm/hour
      * - ``H_1``
        - ``H_20mmh``
        - Combined hazard classification for a peak 15-minute rainfall intensity of 20 mm/hour
      * - ``H_2``
        - ``H_24mmh``
        - Combined hazard classification for a peak 15-minute rainfall intensity of 24 mm/hour
      * - ``P_0``
        - ``P_16mmh``
        - Debris-flow likelihoods for a peak 15-minute rainfall intensity of 16 mm/hour
      * - ``P_1``
        - ``P_20mmh``
        - Debris-flow likelihoods for a peak 15-minute rainfall intensity of 20 mm/hour
      * - ``P_2``
        - ``P_24mmh``
        - Debris-flow likelihoods for a peak 15-minute rainfall intensity of 24 mm/hour
      * - ``V_0``
        - ``V_16mmh``
        - Potential sediment volumes for a peak 15-minute rainfall intensity of 16 mm/hour
      * - ``V_1``
        - ``V_20mmh``
        - Potential sediment volumes for a peak 15-minute rainfall intensity of 20 mm/hour
      * - ``V_2``
        - ``V_24mmh``
        - Potential sediment volumes for a peak 15-minute rainfall intensity of 24 mm/hour
      * - ``Vmin_0_0``, ``Vmax_0_0``
        - ``Vmin_16_90``, ``Vmax_16_90``
        - Upper and lower bounds of the 90% confidence interval for potential sediment volumes for a peak 15-minute rainfall intensity of 16 mm/hour
      * - ``Vmin_0_1``, ``Vmax_0_1``
        - ``Vmin_16_95``, ``Vmax_16_95``
        - Upper and lower bounds of the 95% confidence interval for potential sediment volumes for a peak 15-minute rainfall intensity of 16 mm/hour 
      * - ``Vmin_1_0``, ``Vmax_1_0``
        - ``Vmin_20_90``, ``Vmax_20_90``
        - Upper and lower bounds of the 90% confidence interval for potential sediment volumes for a peak 15-minute rainfall intensity of 20 mm/hour
      * - ``Vmin_1_1``, ``Vmax_1_1``
        - ``Vmin_20_95``, ``Vmax_20_95``
        - Upper and lower bounds of the 95% confidence interval for potential sediment volumes for a peak 15-minute rainfall intensity of 20 mm/hour 
      * - ``Vmin_2_0``, ``Vmax_2_0``
        - ``Vmin_24_90``, ``Vmax_24_90``
        - Upper and lower bounds of the 90% confidence interval for potential sediment volumes for a peak 15-minute rainfall intensity of 24 mm/hour
      * - ``Vmin_2_1``, ``Vmax_2_1``
        - ``Vmin_24_95``, ``Vmax_24_95``
        - Upper and lower bounds of the 95% confidence interval for potential sediment volumes for a peak 15-minute rainfall intensity of 24 mm/hour 
      * - ``R_0_0``, ``I_0_0``
        - ``R15_50``, ``I15_50``
        - Rainfall accumulations and intensities for a 15-minute rainfall duration at a 50% probability level
      * - ``R_0_1``, ``I_0_1``
        - ``R15_75``, ``I15_75``
        - Rainfall accumulations and intensities for a 15-minute rainfall duration at a 75% probability level
      * - ``R_1_0``, ``I_1_0``
        - ``R30_50``, ``I30_50``
        - Rainfall accumulations and intensities for a 30-minute rainfall duration at a 50% probability level
      * - ``R_1_1``, ``I_1_1``
        - ``R30_75``, ``I30_75``
        - Rainfall accumulations and intensities for a 30-minute rainfall duration at a 75% probability level
      * - ``R_2_0``, ``I_2_0``
        - ``R60_50``, ``I60_50``
        - Rainfall accumulations and intensities for a 60-minute rainfall duration at a 50% probability level
      * - ``R_2_1``, ``I_2_1``
        - ``R60_75``, ``I60_75``
        - Rainfall accumulations and intensities for a 60-minute rainfall duration at a 75% probability level

----

.. _select-props:

Exporting Properties
--------------------

By default, wildcat will export :ref:`model results <result-props>`, :ref:`model inputs <input-props>`, and :ref:`watershed variables <watershed-props>`. However, you can use the :confval:`properties`, :confval:`exclude_properties`, and :confval:`include_properties` settings to select specific properties for export. To select properties, you may use any combination of property names, result prefixes, and/or property groups.

Property names are the most basic and allow you to select a property by providing its name. If selecting a specific hazard model result, you should use the indexed variant of its name. For example::

    properties = ["Area_km2", "H_0", "IsConfined", "R_1_2"]

A result prefix is the fixed text at the beginning of a model result field. You can use a result prefix to select all fields corresponding to particular hazard model result. For example::

    # Export all volume estimates and confidence intervals
    properties = ["V", "Vmin", "Vmax"]

Property groups allow you to select a group of related properties. Wildcat supports the following groups:

.. list-table::
    :header-rows: 1

    * - Name
      - Description
    * - ``watershed``
      - All :ref:`watershed variables <watershed-props>`
    * - ``filters``
      - All :ref:`filter checks <filter-props>`
    * - ``model inputs``
      - All :ref:`hazard model inputs <input-props>`
    * - ``results``
      - All :ref:`model results <result-props>`
    * - ``default``
      - All watershed variables, model inputs, and model results
    * - ``modeling``
      - All model inputs and results
    * - ``filtering``
      - All filter checks and watershed variables
    * - ``all``
      - All available properties

For example::

    # Export model results and watershed variables
    properties = ["results", "watershed"]

----

.. _rename:

Renaming Properties
-------------------

Wildcat's default property names are designed to work for a variety of export file formats. In particular, the default names are all less than 10 characters, which is a requirement for Shapefile exports. However, some users may want to use different names for exported properties -- either because they are exporting to less restrictive file formats, or because they simply prefer a different naming convention. You can apply custom names to exported variables using the :confval:`rename` config setting.

.. important::

    If you rename properties, wildcat will not check that the new names are valid for the export format. You are responsible for validating property names for different export formats.

The :confval:`rename` setting should be a Python ``dict`` specifying any renaming options. The keys of the dict should be strings corresponding to any combination of full property names, result prefixes, and/or hazard modeling parameters. Full property names are the most basic. The value for the name should be a string indicating the name for the property in the exported file. If renaming a specific hazard modeling result, then you should use the indexed variant of the name. For example::

    rename = {
        "Segment_ID": "SID",
        "Area_km2": "Total catchment area (km2)",
        "H_0": "Combined-Hazard-16mmh",
        "R_1_1": "RainAcc_30min_75%",
    }

The :confval:`rename` setting can also include result prefixes. In this case, the value for the prefix should be a string indicating a new name for the prefix. The new name will replace all instances of the prefix in the exported files. For example, if you ran an assessment with the following settings::

    I15_mm_hr = [16, 20, 24]
    properties = ["H", "P"]
    rename = {
        "H": "Hazard",
    }

then the combined hazard results in the exported file would be named: ``Hazard_16mmh``, ``Hazard_20mmh``, and ``Hazard_24mmh``. Note that the parameter indices are still converted to values, although you can disable this using the :confval:`clean_names` setting.

Finally, :confval:`rename` can include hazard modeling parameter names. The value for a parameter should be a list with one element per parameter. Each element should be a string indicating the name for the associated parameter value in exported names. For example, if you ran an assessment with the following settings::

    durations = [15, 30, 60]
    probabilities = [0.5, 0.75]

    rename = {
        "durations": ["_15min", "_30min", "_60min"],
        "probabilities": ["P50", "P75"],
    }

then the rainfall accumulation results in the exported file would be named: ``R_15min_P50``, ``R_15min_P75``, ``R_30min_P50``, ``R_30min_P75``, ``R_60min_P50``, and ``R_60min_P75``. Note that we included an underscore in the renamed durations because the default export names do not include an underscore between the ``R`` prefix and the rainfall duration value.

.. note::

    Full property names have the highest priority. If you rename a result prefix or parameter, but also rename a specific result, then the name for the result will override the prefix and parameter options. For example, if you ran an assessment with the following config settings::

        I15_mm_hr = [16, 20, 24]
        rename = {
            "H": "hazard",
            "I15_mm_hr": ["16_mm_hr", "20_mm_hr", "24_mm_hr"],
            "H_0": "My hazard legend",
        }

    then the combined hazard results in the exported file would be named: ``My hazard legend``, ``hazard_20_mm_hr``, and ``hazard_24_mm_hr``.


