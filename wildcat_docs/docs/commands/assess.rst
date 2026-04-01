assess
======

.. _Staley et al., 2017: https://doi.org/10.1016/j.geomorph.2016.10.019

.. _Gartner et al., 2014: https://doi.org/10.1016/j.enggeo.2014.04.008

.. _Cannon et al., 2010: https://doi.org/10.1130/B26459.1

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat assess project

    .. tab-item:: Python

        .. code:: python

            from wildcat import assess
            assess(project)


The ``assess`` command conducts a hazard assessment, estimating debris-flow likelihoods, volumes, hazards, and rainfall thresholds for the indicated project. If a project is not provided, the command interprets the current folder as the project.

The assessment proceeds as follows:

* Uses the DEM and burn severity to :ref:`characterize the watershed <characterize>`,
* :ref:`Delineates <delineate>` an initial stream segment network.
* :ref:`Filters the network <filter>` to remove segments that do not meet various criteria for debris-flow risk,
* Characterizes stream segment catchments,
* Uses characterizations to :ref:`run hazard assessment models <models>`,
* Locates terminal outlets and :ref:`basins`, and
* Saves :ref:`results <default-properties>` to GeoJSON

The command estimates hazards using the following models:

.. list-table::
    :header-rows: 1

    * - Result
      - Units
      - Model
    * - :ref:`Debris-flow likelihoods <likelihoods>`
      - 0 to 1
      - M1 model from `Staley et al., 2017`_. Likelihoods are estimated only for 15-minute durations.
    * - :ref:`Potential sediment volume <volumes>`
      - Cubic meters (m³)
      - Emergency Assessment model from `Gartner et al., 2014`_.
    * - :ref:`Combined hazard classification <combined-hazard>`
      - | 1: low 
        | 2: moderate
        | 3: high
      - Modified version of the scheme presented by `Cannon et al., 2010`_. The modification groups likelihoods into 4 categories, rather than 3.
    * - :ref:`Rainfall Accumulations <thresholds>`
      - mm over the duration
      - The inverted M1 model from `Staley et al., 2017`_. Rainfall accumulations may be estimated for 15, 30, and 60 minute durations.
    * - :ref:`Rainfall Intensities <thresholds>`
      - mm/hour
      - The inverted M1 model from `Staley et al., 2017`_. Rainfall intensities may be estimated for 15, 30, and 60 minute durations.

The command saves the assessment results in the ``assessment`` folder. The command includes results for the stream segments (as LineString features), network outlet points (as Point features), and outlet catchment basins (as Polygon features). The following sections examine the assessment steps in greater detail.

----

.. _characterize:

Characterize Watershed
----------------------
*Related settings:* :confval:`dem_per_m`

.. _severity-masks:

**Burn Severity Masks**
    The assessment begins by using the burn severity dataset to build two masks: 

    * A burned area mask, and
    * A mask of areas burned as moderate-or-high severity

    The burn mask will inform the network delineation, and the moderate-or-high mask will be used by the hazard assessment models.

**DEM Analysis**
    The assessment next leverages the DEM. After conditioning the DEM to account for pits, depressions, and flat areas, the routine uses the DEM to determine D8 flow directions and slopes. It also uses the flow directions to determine vertical reliefs within the watershed.

**Flow Accumulation**
    The routine then uses the flow directions to compute various flow accumulations and flow paths. First, the command computes catchment areas across the watershed. Next, it uses the burned area mask to compute burned catchment area across the watershed. Finally, if retainment features are provided, the routine locates all areas downstream of the retainment features.


----

.. _network:

Stream Segment Network
----------------------

The stream segment network is collection of flow paths through the watershed. The network is selected to include segments at risk for debris flows, while minimizing extraneous segments. The network design process consists of the following steps:

* :ref:`Delineates <delineate>` an initial network,
* :ref:`Filters <filter>` the network to remove segments not considered at risk, and
* :ref:`Removes <remove-ids>` any segments explicitly listed by the user


.. _delineate:

Delineation
+++++++++++
*Related settings:* :confval:`min_area_km2`, :confval:`min_burned_area_km2`, :confval:`max_length_m`

The routine begins by delineating an initial network. The following flowchart summarizes this process:

.. image:: /images/delineate.svg

The assessment uses a delineation mask to build the initial network. This mask indicates pixels that may possibly represent a stream segment. The delineation mask considers two criteria:

* Whether a pixel could be a valid stream segment, and
* Whether a pixel could be at risk of debris flows

**Valid Pixels**
    Valid pixels are determined using total catchment area, water bodies, excluded areas, and retainment features. A pixel is valid if it:

    * Has a sufficiently large catchment (catchment area ≥ :confval:`min_area_km2`),
    * Is not in a water body (:confval:`water`, :confval:`iswater`),
    * Is not in an excluded area (:confval:`excluded`, :confval:`excluded_evt`), and
    * Is not downstream of a retainment feature (:confval:`retainments`)

**At Risk**
    A pixel is considered at risk if it either:

    * Is in the fire perimeter (:confval:`perimeter`), or
    * | Is downstream of a sufficiently large burned area 
      | (burned catchment area ≥ :confval:`min_burned_area_km2`)

The routine then uses the flow directions to map all the stream segments in this mask. Segments longer than a maximum length (:confval:`max_length_m`) are split into multiple pieces. The resulting stream segment network is the **initial network**.




.. _filter:

Filtering
+++++++++
*Related settings:* :confval:`max_area_km2`, :confval:`max_exterior_ratio`, :confval:`min_burn_ratio`, :confval:`min_slope`, :confval:`max_developed_area_km2`, :confval:`max_confinement`, :confval:`confinement_neighborhood`, :confval:`flow_continuous`

Next, the routine filters the network to remove segments that fail to meet various criteria for debris-flow risk. The following flowchart summarizes this process:

.. image:: /images/filter.svg

The filtering routine begins by checking for a mask of :confval:`included` areas. If the masks exists, then any segments intersecting the mask are automatically retained in the network. They are not required to pass any additional filtering criteria. Next, the assessment examines the catchment size of the remaining segments. Segments with sufficiently large catchments are discarded, as hazards in these segments are more likely to exhibit flood-like, rather than debris flow-like behavior.

.. important::

    Flood-like segments can still represent major hazards, and emergency managers should still account for these areas. However, flood-like hazards are outside the scope of wildcat, hence their removal from the assessment.

Each of the segments that pass the catchment size criterion must then pass one of two criteria to remain in the network. Segments must either:

* Meet physical criteria for debris-flow risk, or
* Be considered as within the fire perimeter

.. _physical-filter:

**Physical Criterion**
    The physical criterion consists of four checks. A segment and its catchment must be sufficiently:
    
    * Burned (burned catchment proportion ≥ :confval:`min_burn_ratio`),
    * Steep (slope gradient ≥ :confval:`min_slope`),
    * Confined (confinement angle ≤ :confval:`max_confinement`), and
    * Undeveloped (developed catchment area ≤ :confval:`max_developed_area_km2`)

    .. note::

        Developed areas can still have major debris-flow risks. This segments are removed from the network because human development can alter flow behavior, which is not accounted for by wildcat's assessment models.

.. _perimeter-filter:

**Perimeter Criterion**
    The perimeter criterion consists of two checks:

    * The segment must intersect the fire perimeter, and
    * The catchment must be sufficiently within the perimeter (proportion of catchment *outside* the perimeter < :confval:`max_exterior_ratio`)

Any segment that is not flood-like, and passes either the physical criterion or the perimeter criterion will be retained in the network. Note that you can disable the perimeter criterion (effectively requiring all segments to pass the physical criterion) by setting :confval:`max_exterior_ratio` to 0.

Segments that fail to pass one of these criteria are now slated for removal from the network. However, before removing segments, the routine first examines them for flow continuity. Segments whose removal would disrupt flow continuity are preserved and remain in the network. This preserves the overall continuity of the network, which is usually preferred. However, this behavior can also be disabled by setting :confval:`flow_continuous` to ``False``. In this case, the routine removes all segments that (1) are not in an included area, and (2) fail to pass the filters.



.. _remove-ids:

Remove IDs
++++++++++
*Related settings:* :confval:`remove_ids`

After filtering, the assessment will remove any segments whose IDs are explicitly provided by the user. This can provide a quick solution when the network contains a small number of problem segments that should be removed. You can obtain Segment IDs by examining the ``Segment_ID`` field in the :ref:`assessment results <default-properties>`.

.. _id-changes:

.. important::

    Segment IDs are fixed at network delineation, so remain constant given changes to network filtering parameters. However, changes to network delineation will alter the IDs. As such, you should only remove IDs *after* finalizing the delineation settings. Settings that affect delineation include: :confval:`min_area_km2`, :confval:`min_burned_area_km2`, :confval:`max_length_m`, :confval:`perimeter`, :confval:`dem`, :confval:`severity`, :confval:`water`, :confval:`iswater`, :confval:`excluded`, :confval:`excluded_evt`, and :confval:`retainments`. If you estimate severity from the dNBR, then :confval:`severity_thresholds`, :confval:`dnbr`, :confval:`dnbr_limits`, and :confval:`constrain_dnbr` can also affect delineation.



----

.. _models:

Hazard Models
-------------


.. _likelihoods:

Likelihood
++++++++++
*Related settings:* :confval:`I15_mm_hr`

Wildcat estimates debris-flow likelihoods using the M1 model from `Staley et al., 2017`_. This model takes the form:

.. math::

    p = \mathrm{\frac{e^X}{1 + e^X}}


.. math::

    \mathrm{X = -3.63 + 0.41 * T * R15 + 0.67 * F * R15 + 0.70 * S * R15}

where:

.. list-table::

    * - **Variable**
      - **Description**
    * - p
      - Debris-flow likelihood (0 to 1)
    * - T
      - Terrain variable. The proportion of catchment area with both (1) moderate-or-high burn severity, and (2) slope angle ≥ 23 degrees.
    * - F
      - Fire severity variable. Mean catchment dNBR divided by 1000.
    * - S
      - Soil variable. Mean catchment KF-factor.
    * - R15
      - Peak 15-minute rainfall accumulation in millimeters.



.. _volumes:

Volume
++++++
*Related settings:* :confval:`I15_mm_hr`, :confval:`volume_CI`

Wildcat estimates debris-flow potential sediment volumes using the emergency assessment model from `Gartner et al., 2014`_. This model takes the form:

.. math::

    lnV = 4.22 + 0.39\ \mathrm{sqrt}(I15) + 0.36\ \mathrm{ln}(Bmh) + 0.13\ \mathrm{sqrt}(R)

.. math::

    V = \mathrm{exp}(lnV)


where:

.. list-table::
    :header-rows: 1

    * - Variable
      - Description
      - Units
    * - V
      - Potential sediment volume
      - cubic meters (m³)
    * - lnV
      - Natural log of potential sediment volume
      -
    * - I15
      - Peak 15-minute rainfall intensity
      - mm/hour
    * - Bmh
      - Catchment area burned at moderate or high intensity
      - square kilometers (km²)
    * - R
      - Watershed relief
      - meters

Confidence intervals are calculated using:

.. math::

    \mathrm{V_{min}} = \mathrm{exp}(lnV - 1.04 \ X)

.. math::

    \mathrm{V_{max}} = \mathrm{exp}(lnV + 1.04 \ X)

.. math::

    X = \mathrm{norm.ppf}(1 - \frac{1 - \mathrm{CI}}{2})

where:

.. list-table::
    :header-rows: 1

    * - Term
      - Description
    * - :math:`V_{min}`
      - Lower bound of the confidence interval
    * - :math:`V_{max}`
      - Upper bound of the confidence interval
    * - :math:`lnV`
      - Natural log of potential sediment volume
    * - 1.04
      - Residual standard error of the model
    * - :math:`X`
      - Quantile at the upper tail of a two-tailed normal distribution.
    * - :math:`CI`
      - The desired confidence interval (on the interval from 0 to 1)



.. _combined-hazard:

Combined Hazard Classification
++++++++++++++++++++++++++++++
*Related settings:* :confval:`I15_mm_hr`

The combined hazard classification is a modification of the scheme presented by `Cannon et al., 2010`_. The model begins by scoring likelihood and volume estimates using the following tables:

.. note:: 
  
    Square brackets ``[]`` indicate a closed interval, whereas parentheses ``()`` indicate an open interval.


.. list-table::
    :header-rows: 1

    * - Likelihood Range
      - Score
    * - [0, 0.2]
      - 1
    * - (0.2, 0.4]
      - 2
    * - (0.4, 0.6]
      - 3
    * - (0.6, 0.8]
      - 4
    * - (0.8, 1]
      - 5

.. list-table::
    :header-rows: 1

    * - Volume Range (cubic meters)
      - Score
    * - [0, 10³]
      - 1
    * - (10³, 10⁴]
      - 2
    * - (10⁴, 10⁵]
      - 3
    * - > 10⁵
      - 4

The two scores are then added together, and the resulting sum used to classify the combined hazard:

.. list-table::
    :header-rows: 1

    * - Summed Scores
      - Hazard Class
    * - 1 - 3
      - 1 -- Low Hazard
    * - 4 - 6
      - 2 -- Moderate Hazard
    * - 7+
      - 3 -- High Hazard


.. _thresholds:

Rainfall Thresholds
+++++++++++++++++++
*Related settings:* :confval:`durations`, :confval:`probabilities`

Rainfall thresholds are estimated by inverting the M1 model of `Staley et al., 2017`_ for the provided probability levels. This model takes the form:

.. math::

    \mathrm{R} = \frac{\mathrm{ln}(\frac{p}{1-p}) - \mathrm{B}}{\mathrm{C_t\ T\ R + C_f\ F\ R + C_s\ S\ R}}

where:

.. list-table::

    * - **Variable**
      - **Description**
    * - R
      - Total rainfall accumulation (in millimeters) over a given duration.
    * - p
      - Probability level (0 to 1)
    * - B
      - | Model intercept. Varies with rainfall duration
        | 15-minutes: -3.63
        | 30-minutes: -3.61
        | 60-minutes: -3.21
    * - Ct
      - | Terrain coefficient. Varies by rainfall duration:
        | 15-minutes: 0.41
        | 30-minutes: 0.26
        | 60-minutes: 0.17
    * - T
      - Terrain variable. The proportion of catchment area with both (1) moderate-or-high burn severity, and (2) slope angle ≥ 23 degrees.
    * - Cf
      - | Fire severity coefficient. Varies by rainfall duration:
        | 15-minutes: 0.67
        | 30-minutes: 0.39
        | 60-minutes: 0.20
    * - F
      - Fire severity variable. Mean catchment dNBR divided by 1000.
    * - Cs
      - | Soil coefficient. Varies by rainfall duration:
        | 15-minutes: 0.70
        | 30-minutes: 0.50
        | 60-minutes: 0.22
    * - S
      - Soil variable. Mean catchment KF-factor.

Rainfall intensities are computed by converting R to millimeters per hour. Effectively:

.. math::

    I = R * X

where:

.. list-table::
    :header-rows: 1

    * - Term
      - Description
    * - I
      - Rainfall intensity in millimeters per hour.
    * - R
      - Millimeters of rainfall accumulated over a duration.
    * - X 
      - | Unit conversion multiplier. Varies with rainfall duration.
        | 15-minutes: X = 4
        | 30-minutes: X = 2
        | 60-minutes: X = 1


----

.. _basins:

Locating Basins
---------------
*Related settings:* :confval:`locate_basins`, :confval:`parallelize_basins`

After running the hazard assessment models, wildcat next locates the terminal outlet points and basins. An outlet point is a point where a connected set of stream segments flow out of the network. The outlet basins are the catchment basins of these points. Locating outlet basins is a computationally difficult task, and is often the slowest step of an assessment. You can skip locating these basins by setting :confval:`locate_basins` to ``False``. In this case, the assessment will not attempt to locate basins, and will only save results for the stream segments and the outlet points. This has the potential to greatly speed up an assessment.

Alternatively, you can attempt to speed up basin location by using multiple CPUs. You can do this by setting :confval:`parallelize_basins` to ``True``. Parallelization incurs a computational overhead, so this option is usually only worthwhile when the basins require 10+ minutes to locate. Otherwise, the overhead time can actually cause the assessment to run *slower*.

.. important::

    You cannot use the parallelization option from an interactive Python session. However, you *can* use parallelization for Python scripts run from the command line. When this is the case, the Python script MUST be within a ``if __name__ == "__main__"`` code block. Failing to do this will cause an infinite loop that will crash wildcat. Consult the `pfdf docs <https://ghsc.code-pages.usgs.gov/lhp/pfdf/guide/segments/parallel.html#requirements>`_ for additional details.


----

Assessment Results
------------------
Finally, the assessment will save the following files within the ``assessment`` folder:

.. list-table::
    :header-rows: 1

    * - File
      - Description
    * - ``segments.geojson``
      - Results for the stream segments (LineString geometries)
    * - ``basins.geojson``
      - Results for the outlet basins (Polygon geometries). Not saved if you set :confval:`locate_basins` to ``False``.
    * - ``outlets.geojson``
      - Locations of the outlet points (Point geometries)
    * - ``configuration.txt``
      - The config record for the assessment.


The assessment results are in the `GeoJSON format <https://geojson.org/>`_, and can be converted to other formats using the :doc:`export command </commands/export>`. You can learn about the data fields saved in these output files in the :doc:`Property Guide </guide/properties>`. The ``configuration.txt`` file contains the config record for the assessment. Running the ``assess`` command with these settings should exactly reproduce the current assessment results.


.. note::

    The ``outlets.geojson`` file will not contain any data fields. This is to prevent misinterpretations of hazard assessment results at confluence points. When a confluence occurs on the border of the network, it is assigned two outlet points -- one for each of the merging catchments. However, the two outlets are colocated, with one point overlapping the other. This raises the potential for misinterpretation, as a user could unknowingly inspect the wrong outlet point for a confluence catchment. As such, the saved outlets only contain spatial information, and data fields should instead be obtained from the segment and basin results.