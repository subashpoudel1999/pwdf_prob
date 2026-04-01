Preprocessing Configuration
===========================

.. highlight:: python

These fields specify settings used to :doc:`run the preprocessor </commands/preprocess>`. Many of these fields are paths to input datasets. When a file path is a relative path, then it is interpreted relative to the **inputs** subfolder. If a file name does not include an extension, then wildcat will scan its parent folder for a file with a :doc:`supported extension </guide/file-formats>`.


----

Required Datasets
-----------------
These datasets are required to run the preprocessor. An error will be raised if they cannot be found.

Examples::

    # Absolute file path (may be outside the project folder)
    perimeter = r"/absolute/path/to/perimeter.shp"

    # Relative to the "inputs" subfolder
    perimeter = r"perimeter.shp"


.. _perimeter:

.. confval:: perimeter
    :type: ``str | Path``
    :default: ``r"perimeter"``

    The path to a fire perimeter mask. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask.
    
    The mask will be :ref:`buffered <buffer-perimeter>`, and the extent of the buffered perimeter will define the domain of the analysis. Pixels within the perimeter may be used to :ref:`delineate <delineate>` the initial network, and stream segments sufficiently within the perimeter are retained during :ref:`network filtering <filter>`.

    Most users will likely want to run wildcat for an active or recent fire, but you can also find links to historical fire perimeters here: :ref:`Fire perimeter datasets <data-fires>`

    *CLI option:* :option:`--perimeter <preprocess --perimeter>`

    *Python kwarg:* |perimeter kwarg|_

.. |perimeter kwarg| replace:: ``perimeter``

.. _perimeter kwarg: ./../python.html#python-preprocess


.. _dem:

.. confval:: dem
    :type: ``str | Path``
    :default: ``r"dem"``

    The path to the digital elevation model (DEM) raster dataset. This dataset sets the CRS, resolution, and alignment of the preprocessed rasters. Also used to :ref:`characterize the watershed <characterize>`, including determining flow directions.

    The DEM must be georeferenced and we strongly recommend using a DEM with approximately 10 meter resolution. This is because wildcat's hazard assessment models were calibrated using data from a 10 meter DEM. Read also `Smith et al., 2019 <https://esurf.copernicus.org/articles/7/475/2019/>`_ for a discussion of the effects of DEM resolution on topographic analysis.

    You can find links to 10-meter DEM datasets here: :ref:`DEM datasets <data-dem>`

    *CLI option:* :option:`--dem <preprocess --dem>`

    *Python kwarg:* |dem kwarg|_

.. |dem kwarg| replace:: ``dem``

.. _dem kwarg: ./../python.html#python-preprocess


----

Recommended Datasets
--------------------
These datasets are not required to run the preprocessor, but they are either required or recommended for :doc:`running an assessment </commands/assess>`. To explicitly disable the preprocessor for one of these datasets, set its value to None.

Examples::

    # Absolute path (may be outside the project folder)
    dnbr = r"/absolute/path/to/dnbr.tif"

    # A file in the "inputs" subfolder
    dnbr = r"dnbr.tif"

    # Disable the preprocessor for a dataset
    dnbr = None


.. _dnbr:

.. confval:: dnbr
    :type: ``str | Path | float | None``
    :default: ``r"dnbr"``

    The differenced normalized burn ratio (dNBR) dataset. Used to estimate debris-flow :ref:`likelihoods <likelihoods>` and :ref:`rainfall thresholds <thresholds>`. Optionally used to :ref:`estimate burn severity <estimate-severity>`. Should be (raw dNBR * 1000) with values ranging from approximately -1000 to 1000. This is usually a raster dataset, but you can instead use a constant value across the watershed by setting the field equal to a number.

    Most users will likely want to run wildcat for an active or recent fire, but you can also find links to historical dNBR datasets here: :ref:`dNBR datasets <data-fires>`

    Examples::

        # From a raster file
        dnbr = r"path/to/my-dnbr.tif"

        # Using a constant value
        dnbr = 500

    *CLI option:* :option:`--dnbr <preprocess --dnbr>`

    *Python kwarg:* |dnbr kwarg|_

.. |dnbr kwarg| replace:: ``dnbr``

.. _dnbr kwarg: ./../python.html#python-preprocess


.. _severity:

.. confval:: severity
    :type: ``str | Path | float | None``
    :default: ``r"severity"``

    The path to a `BARC4-like <https://burnseverity.cr.usgs.gov/baer/faqs>`_ soil burn severity dataset. Usually a raster, but may also be a Polygon or MultiPolygon feature file. If a Polygon/MultiPolygon file, then you must provide the :confval:`severity_field` setting. Also supports using a constant severity across the watershed. To implement a constant value, set the field equal to a number, rather than a file path.
    
    The burn severity raster is used to :ref:`locate burned areas <severity-masks>`, which are used to :ref:`delineate <delineate>` the stream segment network. Also used to locate areas burned at moderate-or-high severity, which are used to estimate debris flow :ref:`likelihoods <likelihoods>`, :ref:`volumes <volumes>`, and :ref:`rainfall thresholds <thresholds>`. If missing, this dataset will be :ref:`estimated from the dNBR <estimate-severity>` using the values from the :confval:`severity_thresholds` setting.

    You can find links to burn severity datasets here: :ref:`Burn severity datasets <data-sbs>`. Most users will likely want to run wildcat for an active or recent fire, but you can also find links to historical burn severity datasets here: :ref:`historical severity datasets <data-fires>`

    Examples::

        # From a raster file
        severity = r"path/to/my-severity.tif"

        # From a Polygon file
        severity = r"path/to/my-severity.shp"
        severity_field = "MY_FIELD"

        # Using a constant value
        severity = 3


    *CLI option:* :option:`--severity <preprocess --severity>`

    *Python kwarg:* |severity kwarg|_

.. |severity kwarg| replace:: ``severity``

.. _severity kwarg: ./../python.html#python-preprocess


.. _kf:

.. confval:: kf
    :type: ``str | Path | float | None``
    :default: ``r"kf"``

    The path to a soil KF-factor dataset. Often a Polygon or MultiPolygon feature file, but may also be a numeric raster. If a Polygon/MultiPolygon file, then you must also provide the :confval:`kf_field` setting. Also supports using a constant KF-factor across the watershed. To implement a constant value, set the field equal to a number, rather than a file path.

    The KF-factors are used to estimate debris-flow :ref:`likelihoods <likelihoods>` and :ref:`rainfall thresholds <thresholds>`. Values should be positive, and the preprocessor will :ref:`convert non-positive values to NoData <constrain-kf>` by default.

    You can find links to KF-factor datasets here: :ref:`KF-factor datasets <data-kf>`

    Examples::

        # From a raster
        kf = r"path/to/my-kf.tif"

        # From a Polygon file
        kf = r"path/to/my-kf.shp"
        kf_field = "MY_FIELD"

        # Using a constant value
        kf = 0.2

    *CLI option:* :option:`--kf <preprocess --kf>`

    *Python kwarg:* |kf kwarg|_

.. |kf kwarg| replace:: ``kf``

.. _kf kwarg: ./../python.html#python-preprocess


.. _kf-factors:

.. admonition:: What's a KF-factor?
        
    Kf factors are defined as saturated hydraulic conductivity of the fine soil (< 2mm) fraction in inches/hour. Essentially, this is a soil erodibility factor that represents both (1) the susceptibility of soil to erosion, and (2) the rate of runoff, for soil material with <2mm equivalent diameter. Read Chapter 3 of `USDA Agricultural Handbook 703`_ for additional details on its definition and calculation.

.. _USDA Agricultural Handbook 703: https://www.researchgate.net/profile/Pablo_Alvarez-Figueroa/post/soil_erosion/attachment/59d6460279197b80779a110f/AS:455706810818560@1485660378747/download/Renard_1997_+Predicting+soil+erosion+by+water_a+guide+to+conservation+planing+with+RUSLE.pdf


.. _evt:

.. confval:: evt
    :type: ``str | Path | None``
    :default: ``r"evt"``

    The path to an existing vegetation type (EVT) raster. This is typically a raster of classification code integers. Although not required for an assessment, the EVT is used to :ref:`build water, development, and exclusion masks <evt-masks>`, which can improve the design of the stream segment network.

    You can find links to EVT datasets here: :ref:`EVT datasets <data-evt>`

    *CLI option:* :option:`--evt <preprocess --evt>`

    *Python kwarg:* |evt kwarg|_

.. |evt kwarg| replace:: ``evt``

.. _evt kwarg: ./../python.html#python-preprocess


----

Optional Datasets
-----------------

These datasets are optional. They are neither required to run the preprocessor, nor to run an assessment. To explicitly disable the preprocessor for one of these datasets, set its value to None.

Examples::

    # Absolute path (may be outside the project folder)
    excluded = r"/absolute/path/to/excluded.shp"

    # Relative to the "inputs" subfolder
    excluded = r"excluded"

    # Disable the preprocessor for a dataset
    excluded = None


.. confval:: retainments
    :type: ``str | Path | None``
    :default: ``r"retainments"``

    The path to a dataset indicating the locations of debris retainment features. Usually a Point or MultiPoint feature file, but may also be a raster mask. Pixels downstream of these features will not be used for :ref:`network delineation <delineate>`.

    *CLI option:* :option:`--retainments <preprocess --retainments>`

    *Python kwarg:* |retainments kwarg|_

.. |retainments kwarg| replace:: ``retainments``

.. _retainments kwarg: ./../python.html#python-preprocess


.. confval:: excluded
    :type: ``str | Path | None``
    :default: ``r"excluded"``

    The path to a dataset of areas that should be excluded from :ref:`network delineation <delineate>`. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. Pixels in these areas will not be used to delineate the network. If provided in conjunction with the :confval:`excluded_evt` setting, then the two masks will be combined to produce the final preprocessed exclusion mask.

    *CLI option:* :option:`--excluded <preprocess --excluded>`

    *Python kwarg:* |excluded kwarg|_

.. |excluded kwarg| replace:: ``excluded``

.. _excluded kwarg: ./../python.html#python-preprocess


.. confval:: included
    :type: ``str | Path | None``
    :default: ``r"included"``

    The path to a dataset of areas that should be retained when :ref:`filtering <filter>` the network. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. Any stream segment that intersects one of these areas will automatically be retained in the network - it will not need to pass any other filtering criteria.

    *CLI option:* :option:`--included <preprocess --included>`

    *Python kwarg:* |included kwarg|_

.. |included kwarg| replace:: ``included``

.. _included kwarg: ./../python.html#python-preprocess


.. confval:: iswater
    :type: ``str | Path | None``
    :default: ``r"iswater"``

    The path to a water body mask. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. Pixels in the mask will not be used for :ref:`network delineation <delineate>`. If provided in conjunction with the :confval:`water` setting, then the two masks will be combined to produce the final preprocessed water mask.

    *CLI option:* :option:`--iswater <preprocess --iswater>`

    *Python kwarg:* |iswater kwarg|_

.. |iswater kwarg| replace:: ``iswater``

.. _iswater kwarg: ./../python.html#python-preprocess


.. confval:: isdeveloped
    :type: ``str | Path | None``
    :default: ``r"isdeveloped"``

    The path to a human-development mask. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. The development mask is used to inform :ref:`network filtering <filter>`. If provided in conjunction with the :confval:`developed` setting, then the two masks will be combined to produce the final preprocessed development raster.

    *CLI option:* :option:`--isdeveloped <preprocess --isdeveloped>`

    *Python kwarg:* |isdeveloped kwarg|_

.. |isdeveloped kwarg| replace:: ``isdeveloped``

.. _isdeveloped kwarg: ./../python.html#python-preprocess


----

Perimeter
---------
Settings used to build the :ref:`buffered perimeter <buffer-perimeter>`.

.. confval:: buffer_km
    :type: ``float``
    :default: ``3``

    The number of kilometers to buffer the fire perimeter. The extent of the buffered perimeter defines the domain of the analysis.

    Example::

        buffer_km = 3.0

    *CLI option:* :option:`--buffer-km <preprocess --buffer-km>`

    *Python kwarg:* |buffer_km kwarg|_

.. |buffer_km kwarg| replace:: ``buffer_km``

.. _buffer_km kwarg: ./../python.html#python-preprocess


----

DEM
---
Settings for preprocessing the :ref:`DEM <dem>`.

.. confval:: resolution_limits_m
    :type: ``[float, float]``
    :default: ``[6.5, 11]``

    The allowed range of DEM resolutions in meters. Should be a list of 2 values. The first value is the minimum allowed resolution, and the second is the maximum resolution. If either the X-axis or the Y-axis of the DEM has a resolution outside of this range, then this will trigger the :confval:`resolution_check`.

    The default values are selected to permit all DEM tiles from the USGS National Map within the continental US. In general, the DEM should have approximately 10 meter resolution. This is because wildcat's assessment models were calibrated using data from a 10 meter DEM.

    Example::

        # Require resolution between 8 and 12 meters
        resolution_limits_m = [8, 12]

    *CLI option:* :option:`--resolution-limits-m <preprocess --resolution-limits-m>`

    *Python kwarg:* |resolution_limits_m kwarg|_

.. |resolution_limits_m kwarg| replace:: ``resolution_limits_m``

.. _resolution_limits_m kwarg: ./../python.html#python-preprocess


.. confval:: resolution_check
    :type: ``"error" | "warn" | "none"``
    :default: ``"error"``

    What should happen when the DEM does not have an allowed resolution. Options are:

    * ``"error"``: Raises an error and stops the preprocessor
    * ``"warn"``: Logs a warning to the console, but continues preprocessing
    * ``"none"``: Does nothing and continues preprocessing

    Example::

        # Issue a warning instead of an error
        resolution_check = "warn"

    *CLI option:* :option:`--resolution-check <preprocess --resolution-check>`

    *Python kwarg:* |resolution_check kwarg|_

.. |resolution_check kwarg| replace:: ``resolution_check``

.. _resolution_check kwarg: ./../python.html#python-preprocess


----

dNBR
----
Settings for preprocessing the :ref:`dNBR <dnbr>` raster.

.. confval:: dnbr_scaling_check
    :type: ``"error" | "warn" | "none"``
    :default: ``"error"``

    What should happen when the dNBR fails the :ref:`scaling check <dnbr-scaling>`. The dNBR will fail this check if all the dNBR data values are between -10 and 10. Options are:

    * ``"error"``: Raises an error and stops the preprocessor
    * ``"warn"``: Logs a warning to the console, but continues preprocessing
    * ``"none"``: Does nothing and continues preprocessing

    Example::

        # Issue a warning instead of an error
        dnbr_scaling_check = "warn"

    *CLI option:* :option:`--dnbr-scaling-check <preprocess --dnbr-scaling-check>`

    *Python kwarg:* |dnbr-scaling-check kwarg|_

.. |dnbr-scaling-check kwarg| replace:: ``dnbr_scaling_check``

.. _dnbr-scaling-check kwarg: ./../python.html#python-preprocess


.. confval:: constrain_dnbr
    :type: ``bool``
    :default: ``True``

    Whether the preprocessor should :ref:`constrain dNBR <constrain-dnbr>` data values to a valid range. Any dNBR values outside the valid range are converted to the nearest bound of the valid range.

    Example::

        # Do not constrain dNBR
        constrain_dnbr = False

    *CLI option:* :option:`--no-constrain-dnbr <preprocess --no-constrain-dnbr>`

    *Python kwarg:* |constrain-dnbr kwarg|_

.. |constrain-dnbr kwarg| replace:: ``constrain_dnbr``

.. _constrain-dnbr kwarg: ./../python.html#python-preprocess


.. confval:: dnbr_limits
    :type: ``[float, float]``
    :default: ``[-2000, 2000]``

    The lower and upper bounds of the :ref:`dNBR valid data range <constrain-dnbr>`. These values are ignored when :confval:`constrain_dnbr` is ``False``.

    Example::

        # Set the valid range from -1500 to 3000
        constrain_dnbr = True
        dnbr_limits = [-1500, 3000]

    *CLI option:* :option:`--dnbr-limits <preprocess --dnbr-limits>`

    *Python kwarg:* |dnbr-limits kwarg|_

.. |dnbr-limits kwarg| replace:: ``dnbr_limits``

.. _dnbr-limits kwarg: ./../python.html#python-preprocess


----

Burn Severity
-------------
Settings for preprocessing the :ref:`burn severity <severity>` dataset.

.. confval:: severity_field
    :type: ``str | None``
    :default: ``None``

    The name of the data attribute field from which to read burn severity data when the :confval:`severity` dataset is a Polygon or MultiPolygon feature file. Ignored if the severity dataset is a raster, or if severity is estimated from the dNBR.

    Example::

        # Read severity data from the "Burn_Sev" data field
        severity = r"severity.shp"
        severity_field = "Burn_Sev"
        
    *CLI option:* :option:`--severity-field <preprocess --severity-field>`

    *Python kwarg:* |severity-field kwarg|_

.. |severity-field kwarg| replace:: ``severity_field``

.. _severity-field kwarg: ./../python.html#python-preprocess



.. confval:: contain_severity
    :type: ``bool``
    :default: ``True``

    Whether the preprocessor should :ref:`contain burn severity <contain-severity>` data to within the fire perimeter.

    Example::

        # Do not contain severity within the perimeter
        contain_severity = False
        
    *CLI option:* :option:`--no-contain-severity <preprocess --no-contain-severity>`

    *Python kwarg:* |contain-severity kwarg|_

.. |contain-severity kwarg| replace:: ``contain_severity``

.. _contain-severity kwarg: ./../python.html#python-preprocess


.. confval:: estimate_severity
    :type: ``bool``
    :default: ``True``

    Whether to :ref:`estimate burn severity <estimate-severity>` from the dNBR when the severity dataset is missing. This option is irrelevant if a burn severity dataset is provided.

    Example::

        # Estimate severity from the dNBR
        severity = None
        estimate_severity = True

    *CLI option:* :option:`--no-estimate-severity <preprocess --no-estimate-severity>`

    *Python kwarg:* |estimate-severity kwarg|_

.. |estimate-severity kwarg| replace:: ``estimate_severity``

.. _estimate-severity kwarg: ./../python.html#python-preprocess


.. confval:: severity_thresholds
    :type: ``[float, float, float]``
    :default: ``[125, 250, 500]``

    When :ref:`estimating severity <estimate-severity>` from the dNBR, specifies the dNBR thresholds used to classify severity levels. The first value is the breakpoint between unburned and low severity. The second value is the breakpoint between low and moderate severity, and the third value is the breakpoint between moderate and high severity. A dNBR value that exactly equals a breakpoint will be classified at the lower severity level. This option is ignored if a severity dataset is provided, or if :confval:`estimate_severity` is ``False``.

    Example::

        # Estimate severity using dNBR breakpoints of 100, 325, and 720
        severity = None
        estimate_severity = True
        severity_thresholds = [100, 325, 720]

    *CLI option:* :option:`--severity-thresholds <preprocess --severity-thresholds>`

    *Python kwarg:* |severity-thresholds kwarg|_

.. |severity-thresholds kwarg| replace:: ``severity_thresholds``

.. _severity-thresholds kwarg: ./../python.html#python-preprocess


----

KF-factors
----------
Settings for preprocessing the :ref:`KF-factor <kf>` dataset.

.. confval:: kf_field
    :type: ``str | None``
    :default: ``None``

    The name of the data attribute field from which to read KF-factor data when the :confval:`kf` dataset is a Polygon or MultiPolygon feature file. Ignored if the KF-factor dataset is a raster.

    Example::

        # Load KF-factor values from the "KFFACT" data field
        kf = r"soil-data.shp"
        kf_field = "KFFACT"

    *CLI option:* :option:`--kf-field <preprocess --kf-field>`

    *Python kwarg:* |kf-field kwarg|_

.. |kf-field kwarg| replace:: ``kf_field``

.. _kf-field kwarg: ./../python.html#python-preprocess


.. confval:: constrain_kf
    :type: ``bool``
    :default: ``True``

    Whether to :ref:`constrain KF-factor data <constrain-kf>` to positive values. When constrained, negative and 0-valued KF-factors are replaced with NoData.

    Example::

        # Do not constrain KF-factors
        constrain_kf = False

    *CLI option:* :option:`--no-constrain-kf <preprocess --no-constrain-kf>`

    *Python kwarg:* |constrain-kf kwarg|_

.. |constrain-kf kwarg| replace:: ``constrain_kf``

.. _constrain-kf kwarg: ./../python.html#python-preprocess


.. confval:: max_missing_kf_ratio
    :type: ``float``
    :default: ``0.05``

    A maximum allowed proportion of missing data in the KF-factor dataset. Exceeding this level will trigger the :confval:`missing_kf_check`. The threshold should be a value from 0 to 1.

    Example::

        # Warn if more than 5% of the KF-factor data is missing
        max_missing_kf_ratio = 0.05

    *CLI option:* :option:`--max-missing-kf-ratio <preprocess --max-missing-kf-ratio>`

    *Python kwarg:* |max-missing-kf-ratio kwarg|_

.. |max-missing-kf-ratio kwarg| replace:: ``max_missing_kf_ratio``

.. _max-missing-kf-ratio kwarg: ./../python.html#python-preprocess


.. confval:: missing_kf_check
    :type: ``"error" | "warn" | "none"``
    :default: ``"warn"``

    What to do if the proportion of :ref:`missing KF-factor data <missing-kf>` exceeds the maximum level and there is no fill value. Options are:

    * ``"error"``: Raises an error and stops the preprocessor
    * ``"warn"``: Logs a warning to the console, but continues preprocessing
    * ``"none"``: Does nothing and continues preprocessing

    This option is ignored if :confval:`kf_fill` is not ``False``.

    Example::

        # Disable the KF-factor warning
        kf_fill = False
        missing_kf_check = "none"

    *CLI option:* :option:`--missing-kf-check <preprocess --missing-kf-check>`

    *Python kwarg:* |missing-kf-check kwarg|_


.. |missing-kf-check kwarg| replace:: ``missing_kf_check``

.. _missing-kf-check kwarg: ./../python.html#python-preprocess


.. confval:: kf_fill
    :type: ``bool | float | str | Path``
    :default: ``False``

    Indicates how to :ref:`fill missing KF-factor values <fill-kf>`. Options are
    
    * ``False``: Does not fill missing values
    * ``True``: Replaces missing values with the median KF-factor in the dataset
    * ``float``: Replaces missing values with the indicated number
    * ``str | Path``: Uses the indicated dataset to implement spatially varying fill values. Missing KF-factor values are replaced with the co-located value in the fill-value dataset. Usually a Polygon or MultiPolygon feature file, but may also be a raster dataset. If a Polygon/MultiPolygon file, then you must also provide the :confval:`kf_fill_field` setting.

    Examples::

        # Do not fill missing values
        kf_fill = False

        # Replace missing values with the median
        kf_fill = True

        # Replace with a specific number
        kf_fill = 0.8

        # Replace using a spatially varying dataset
        kf_fill = r"kf-fill.shp"
        kf_fill_field = "FILL_VALUE"

    *CLI option:* :option:`--kf-fill <preprocess --kf-fill>`

    *Python kwarg:* |kf-fill kwarg|_

.. |kf-fill kwarg| replace:: ``kf_fill``

.. _kf-fill kwarg: ./../python.html#python-preprocess


.. confval:: kf_fill_field
    :type: ``str | None``
    :default: ``None``

    The name of the data attribute field from which to read KF-factor fill values when :confval:`kf_fill` is the path to a Polygon or MultiPolygon feature file. Ignored if :confval:`kf_fill` is anything else.

    Example::

        # Read fill value data from the "FILL_VALUE" field
        kf_fill = r"kf-fill.shp"
        kf_fill_field = "FILL_VALUE"

    *CLI option:* :option:`--kf-fill-field <preprocess --kf-fill-field>`

    *Python kwarg:* |kf-fill-field kwarg|_

.. |kf-fill-field kwarg| replace:: ``kf_fill_field``

.. _kf-fill-field kwarg: ./../python.html#python-preprocess


----

EVT Masks
---------
Options for :ref:`building raster masks <evt-masks>` from the :ref:`EVT <evt>` dataset.

.. confval:: water
    :type: ``[float, ...]``
    :default: ``[7292]``

    A list of EVT values that should be classified as water bodies. These pixels will not be used for :ref:`network delineation <delineate>`. Use an empty list to stop the preprocessor from building a water mask from the EVT. Ignored if there is no :confval:`evt` dataset. If provided in conjunction with the :confval:`iswater` dataset, then the two masks will be combined to produce the final preprocessed water mask.

    Examples::

        # Classify EVT values as water
        water = [1, 2, 3]

        # Do not build a water mask from the EVT
        water = []

        # Combine EVT mask with pre-computed mask
        iswater = r"iswater.shp"
        water = [7292]

    *CLI options:* :option:`--water <preprocess --water>`, :option:`--no-find-water <preprocess --no-find-water>`

    *Python kwarg:* |water kwarg|_

.. |water kwarg| replace:: ``water``

.. _water kwarg: ./../python.html#python-preprocess


.. confval:: developed
    :type: ``[float, ...]``
    :default: ``[7296, 7297, 7298, 7299, 7300]``

    A list of EVT values that should be classified as human development. The development mask will be used to inform :ref:`network filtering <filter>`. Use an empty list to stop the preprocessor from building a development mask from the EVT. Ignored if there is no :confval:`evt` dataset. If provided in conjunction with the :confval:`isdeveloped` dataset, then the two masks will be combined to produce the final preprocessed development mask.

    Examples::

        # Classify EVT values as developed
        developed = [1, 2, 3]

        # Do not build a development mask from the EVT
        developed = []

        # Combine EVT mask with pre-computed mask
        isdeveloped = r"isdeveloped.shp"
        developed = [7296, 7297, 7298, 7299, 7300]

    *CLI options:* :option:`--developed <preprocess --developed>`, :option:`--no-find-developed <preprocess --no-find-developed>`

    *Python kwarg:* |developed kwarg|_

.. |developed kwarg| replace:: ``developed``

.. _developed kwarg: ./../python.html#python-preprocess


.. confval:: excluded_evt
    :type: ``[float, ...]``
    :default: ``[]``

    A list of EVT values that should be classified as excluded areas. These pixels will not be used for :ref:`network delineation <delineate>`. Use an empty list to stop the preprocessor from building an exclusion mask from the EVT. Ignored if there is no :confval:`evt` dataset. If provided in conjunction with the :confval:`excluded` dataset, then the two masks will be combined to produce the final preprocessed exclusion mask.

    Examples::

        # Classify EVT values as excluded areas
        excluded_evt = [1, 2, 3]

        # Do not build an exclusion mask from the EVT
        excluded_evt = []

        # Combine EVT mask with pre-computed mask
        excluded = r"excluded.shp"
        excluded_evt = [1, 2, 3]

    *CLI options:* :option:`--excluded-evt <preprocess --excluded-evt>`, :option:`--no-find-excluded <preprocess --no-find-excluded>`

    *Python kwarg:* |excluded-evt kwarg|_

.. |excluded-evt kwarg| replace:: ``excluded_evt``

.. _excluded-evt kwarg: ./../python.html#python-preprocess

