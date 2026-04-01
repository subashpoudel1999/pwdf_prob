wildcat preprocess
==================

.. highlight:: bash

Synopsis
--------

**wildcat preprocess** [project] [options]


Description
-----------

Reprojects and cleans input datasets in preparation for an assessment. Datasets are converted to rasters with the same CRS, bounds, alignment, and resolution. Also implements various data validation and cleaning routines. Please read the :doc:`Preprocess Overview </commands/preprocess>` for more details.

.. note::
    
    The options presented on this page will override their associated settings in ``configuration.py``.


Options
-------

.. program:: preprocess

Paths
+++++

.. option:: project

    Indicates the project folder in which to run the preprocessor. If not specified, interprets the current folder as the project folder. The project folder is also the default location where the command will search for a configuration file.

    Example::

        # Preprocess a project
        wildcat preprocess my-project

        # Preprocess the current folder
        wildcat preprocess


.. option:: -c PATH, --config PATH

    Specifies the path to the configuration file. If a relative path, then the path is interpreted relative to the project folder. Defaults to ``configuration.py``.

    Example::

        # Use an alternate config file
        wildcat preprocess --config my-alternate-config.py


.. option:: -i PATH, --inputs PATH

    The folder in which to search for input dataset files.

    Example::

        # Preprocess datasets in a different folder
        wildcat preprocess --inputs my-other-inputs

    *Overrides setting:* :confval:`inputs`


.. option:: -o PATH, --preprocessed PATH

    The folder in which to save preprocessed rasters.

    Example::

        # Save preprocessed rasters in a different folder
        wildcat preprocess --preprocessed my-other-folder

    *Overrides setting:* :confval:`preprocessed`


Required Datasets
+++++++++++++++++

These datasets are required to run the preprocessor. An error will be raised if they cannot be found.

Example::

    # Provide the path to a dataset
    wildcat preprocess --perimeter my-perimeter.shp

.. option:: --perimeter PATH

    The path to a fire perimeter mask. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask.
    
    The mask will be :ref:`buffered <buffer-perimeter>`, and the extent of the buffered perimeter will define the domain of the analysis. Pixels within the perimeter may be used to :ref:`delineate <delineate>` the initial network, and stream segments sufficiently within the perimeter are retained during :ref:`network filtering <filter>`.

    Most users will likely want to run wildcat for an active or recent fire, but you can also find links to historical fire perimeters here: :ref:`Fire perimeter datasets <data-fires>`

    *Overrides setting:* :confval:`perimeter`


.. option:: --dem PATH

    The path to the digital elevation model (DEM) raster dataset. This dataset sets the CRS, resolution, and alignment of the preprocessed rasters. Also used to :ref:`characterize the watershed <characterize>`, including determining flow directions.

    The DEM must be georeferenced and we strongly recommend using a DEM with 10 meter resolution (±3 meters). This is because wildcat's hazard assessment models were calibrated using data from a 10 meter DEM. Read also `Smith et al., 2019 <https://esurf.copernicus.org/articles/7/475/2019/>`_ for a discussion of the effects of DEM resolution on topographic analysis.

    You can find links to 10-meter DEM datasets here: :ref:`DEM datasets <data-dem>`

    *Overrides setting:* :confval:`dem`


Recommended Datasets
++++++++++++++++++++

These datasets are not required to run the preprocessor, but they are either required or recommended for :doc:`running an assessment </commands/assess>`. To explicitly disable the preprocessor for one of these datasets, set its value to None.

Example::

    # Disable the dNBR preprocessor
    wildcat preprocess --dnbr None


.. option:: --dnbr PATH | VALUE | None

    The differenced normalized burn ratio (dNBR) dataset. Used to estimate debris-flow :ref:`likelihoods <likelihoods>` and :ref:`rainfall thresholds <thresholds>`. Optionally used to :ref:`estimate burn severity <estimate-severity>`. Should be (raw dNBR * 1000) with values ranging from approximately -1000 to 1000. This is usually the path to a raster dataset, but you can instead use a constant value across the watershed by setting the field equal to a number.

    Most users will likely want to run wildcat for an active or recent fire, but you can also find links to historical dNBR datasets here: :ref:`dNBR datasets <data-fires>`

    Examples::

        # From a raster
        wildcat preprocess --dnbr path/to/my-dnbr.tif

        # Using a constant value
        wildcat preprocess --dnbr 500

    *Overrides setting:* :confval:`dnbr`


.. option:: --severity PATH | VALUE | None

    The path to a `BARC4-like <https://burnseverity.cr.usgs.gov/baer/faqs>`_ soil burn severity dataset. Usually a raster, but may also be a Polygon or MultiPolygon feature file. If a Polygon/MultiPolygon file, then you must provide the :confval:`severity_field` setting. Also supports using a constant severity across the watershed. To implement a constant value, set the field equal to a number, rather than a file path.
    
    The burn severity raster is used to :ref:`locate burned areas <severity-masks>`, which are used to :ref:`delineate <delineate>` the stream segment network. Also used to locate areas burned at moderate-or-high severity, which are used to estimate debris flow :ref:`likelihoods <likelihoods>`, :ref:`volumes <volumes>`, and :ref:`rainfall thresholds <thresholds>`. If missing, this dataset will be :ref:`estimated from the dNBR <estimate-severity>` using the values from the :confval:`severity_thresholds` setting.

    Most users will likely want to run wildcat for an active or recent fire, but you can also find links to historical burn severity datasets here: :ref:`severity datasets <data-fires>`

    Examples::

        # From a raster
        wildcat preprocess --severity path/to/my-severity.tif

        # From Polygon features
        wildcat preprocess --severity path/to/my-severity.shp --severity-field MY_FIELD

        # Using a constant value
        wildcat preprocess --severity 3

    *Overrides setting:* :confval:`severity`


.. option:: --kf PATH | VALUE | None

    The path to a :ref:`soil KF-factor <kf-factors>` dataset. Often a Polygon or MultiPolygon feature file, but may also be a numeric raster. If a Polygon/MultiPolygon file, then you must also provide the :confval:`kf_field` setting. Also supports using a constant KF-factor across the watershed. To implement a constant value, set the field equal to a number, rather than a file path.

    The KF-factors are used to estimate debris-flow :ref:`likelihoods <likelihoods>` and :ref:`rainfall thresholds <thresholds>`. Values should be positive, and the preprocessor will :ref:`convert non-positive values to NoData <constrain-kf>` by default.

    You can find links to KF-factor datasets here: :ref:`KF-factor datasets <data-kf>`

    Examples::

        # From a raster
        wildcat preprocess --kf path/to/my-kf.tif

        # From Polygon features
        wildcat preprocess --kf path/to/my-kf.shp --kf-field MY_FIELD

        # Using a constant value
        wildcat preprocess --kf 0.2

    *Overrides setting:* :confval:`kf`


.. option:: --evt PATH | VALUE | None

    The path to an existing vegetation type (EVT) raster. This is typically a raster of classification code integers. Although not required for an assessment, the EVT is used to :ref:`build water, development, and exclusion masks <evt-masks>`, which can improve the design of the stream segment network.

    You can find links to EVT datasets here: :ref:`EVT datasets <data-evt>`

    *Overrides setting:* :confval:`evt`


Optional Datasets
+++++++++++++++++

These datasets are optional. They are neither required to run the preprocessor, nor to run an assessment. To explicitly disable the preprocessor for one of these datasets, set its value to None.

Example::

    # Disable the preprocessor for the exclusion mask
    wildcat preprocess --excluded None


.. option:: --retainments PATH | None
    
    The path to a dataset indicating the locations of debris retainment features. Usually a Point or MultiPoint feature file, but may also be a raster mask. Pixels downstream of these features will not be used for :ref:`network delineation <delineate>`.

    *Overrides setting:* :confval:`retainments`


.. option:: --excluded PATH | None

    The path to a dataset of areas that should be excluded from :ref:`network delineation <delineate>`. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. Pixels in these areas will not be used to delineate the network. If provided in conjunction with the :confval:`excluded_evt` setting, then the two masks will be combined to produce the final preprocessed exclusion mask.

    *Overrides setting:* :confval:`excluded`


.. option:: --included PATH | None

    The path to a dataset of areas that should be retained when :ref:`filtering <filter>` the network. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. Any stream segment that intersects one of these areas will automatically be retained in the network - it will not need to pass any other filtering criteria.

    *Overrides setting:* :confval:`included`


.. option:: --iswater PATH | None

    The path to a water body mask. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. Pixels in the mask will not be used for :ref:`network delineation <delineate>`. If provided in conjunction with the :confval:`water` setting, then the two masks will be combined to produce the final preprocessed water mask.

    *Overrides setting:* :confval:`iswater`


.. option:: --isdeveloped PATH | None

    The path to a human-development mask. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask. The development mask is used to inform :ref:`network filtering <filter>`. If provided in conjunction with the :confval:`developed` setting, then the two masks will be combined to produce the final preprocessed development raster.

    *Overrides setting:* :confval:`isdeveloped`


Perimeter
+++++++++
Options for building the :ref:`buffered perimeter <buffer-perimeter>`.

.. option:: --buffer-km DISTANCE

    The number of kilometers to buffer the fire perimeter. The extent of the buffered perimeter defines the domain of the analysis.

    Example::

        # Buffer the perimeter 3.5 kilometers
        wildcat preprocess --buffer-km 3.5

    *Overrides setting:* :confval:`buffer_km`


DEM
+++
Options for preprocessing the :ref:`DEM <dem>`.

.. option:: --resolution-limits-m MIN MAX

    The allowed range of DEM resolutions in meters. The first value is the minimum allowed resolution, and the second is the maximum resolution. If either the X-axis or the Y-axis of the DEM has a resolution outside of this range, then this will trigger the :confval:`resolution_check`.

    Example::

        # Require resolution between 8 and 12 meters
        wildcat preprocess --resolution-limits-m 8 12

    *Overrides setting:* :confval:`resolution_limits_m`


.. option:: --resolution-check <warn | error | none>

    Specify what should happen when the DEM does not have an allowed resolution. Options are:

    * ``error``: Raises an error and stops the preprocessor
    * ``warn``: Logs a warning to the console, but continues preprocessing
    * ``none``: Does nothing and continues preprocessing

    Example::

        # Issue a warning instead of an error
        wildcat preprocess --resolution-check warn

    *Overrides setting:* :confval:`resolution_check`


dNBR
++++
Options for preprocessing the :ref:`dNBR <dnbr>` raster.

.. option:: --dnbr-scaling-check <warn | error | none>

    Specify what should happen when the dNBR fails the :ref:`scaling check <dnbr-scaling>`. The dNBR will fail this check if all the dNBR data values are between -10 and 10. Options are:

    * ``error``: Raises an error and stops the preprocessor
    * ``warn``: Logs a warning to the console, but continues preprocessing
    * ``none``: Does nothing and continues preprocessing

    Example::

        # Raise an error if the dNBR fails the check
        wildcat preprocess --dnbr-scaling-check error

    *Overrides setting:* :confval:`dnbr_scaling_check`


.. option:: --dnbr-limits MIN MAX

    Specify the lower and upper bounds of the :ref:`dNBR valid data range <constrain-dnbr>`.

    Example::

        # Constrain dNBR values between -1500 and 2000
        wildcat preprocess --dnbr-limits -1500 2000

    *Overrides setting:* :confval:`dnbr_limits`


.. option:: --no-constrain-dnbr

    Do not :ref:`constrain dNBR <constrain-dnbr>` data values to a valid range.

    Example::

        # Do not constrain dNBR
        wildcat preprocess --no-constrain-dnbr

    *Overrides setting:* :confval:`constrain_dnbr`


Burn Severity
+++++++++++++
Options for preprocessing the :ref:`burn severity <severity>` dataset.

.. option:: --severity-field NAME

    The name of the data attribute field from which to read burn severity data when the :confval:`severity` dataset is a Polygon or MultiPolygon feature file. Ignored if the severity dataset is a raster, or if severity is estimated from the dNBR.

    Example::

        # Read severity data from the "Burn_Sev" field
        wildcat preprocess --severity-field Burn_Sev

    *Overrides setting:* :confval:`severity_field`


.. option:: --severity-thresholds LOW MODERATE HIGH

    Specifies the dNBR thresholds used to classify severity levels when :ref:`estimating severity <estimate-severity>` from the dNBR, . The first value is the breakpoint between unburned and low severity. The second value is the breakpoint between low and moderate severity, and the third value is the breakpoint between moderate and high severity. A dNBR value that exactly equals a breakpoint will be classified at the lower severity level. This option is ignored if a severity dataset is provided, or if :confval:`estimate_severity` is ``False``.

    Example::

        # Estimate severity using dNBR breakpoints at 100, 250, and 500
        wildcat preprocess --severity-thresholds 100 250 500

    *Overrides setting:* :confval:`severity_thresholds`


.. option:: --no-estimate-severity

    Do not :ref:`estimate severity <estimate-severity>` from dNBR, even when the severity dataset is missing.

    Example::

        # Never estimate severity from dNBR
        wildcat preprocess --no-estimate-severity

    *Overrides setting:* :confval:`estimate_severity`


.. option:: --no-contain-severity

    Do not :ref:`contain burn severity <contain-severity>` values within the fire perimeter. Burn severity values outside the perimeter will be left unaltered.

    Example::

        # Do not contain severity within the perimeter
        wildcat preprocess --no-contain-severity

    *Overrides setting:* :confval:`contain_severity`

KF-factors
++++++++++
Settings for preprocessing the :ref:`KF-factor <kf>` dataset.

.. option:: --kf-field NAME

    The name of the data attribute field from which to read KF-factor data when the :confval:`kf` dataset is a Polygon or MultiPolygon feature file. Ignored if the KF-factor dataset is a raster.

    Example::

        # Load KF-factor values from the "KFFACT" data field
        wildcat preprocess --kf-field KFFACT

    *Overrides setting:* :confval:`kf_field`


.. option:: --no-constrain-kf

    Do not :ref:`constrain KF-factor data <constrain-kf>` to positive values.

    Example::

        # Do not constrain KF-factors
        wildcat preprocess --no-constrain-kf
    
    *Overrides setting:* :confval:`constrain_kf`


.. option:: --max-missing-kf-ratio RATIO

    A maximum allowed proportion of missing KF-factor data. Exceeding this level will trigger the :confval:`missing_kf_check`. The ratio should be a value from 0 to 1.

    Example::

        # Issue warning if 5% of the KF-factor data is missing
        wildcat preprocess --max-missing-kf-ratio 0.05

    *Overrides setting:* :confval:`max_missing_kf_ratio`


.. option:: --missing-kf-check <error | warn | none>

    What to do if the proportion of :ref:`missing KF-factor data <missing-kf>` exceeds the maximum level and there is no fill value. Options are:

    * ``error``: Raises an error and stops the preprocessor
    * ``warn``: Logs a warning to the console, but continues preprocessing
    * ``none``: Does nothing and continues preprocessing

    This option is ignored if :confval:`kf_fill` is not ``False``.

    Example::

        # Disable the KF-factor warning
        wildcat preprocess --missing-kf-check none

    *Overrides setting:* :confval:`missing_kf_check`


.. option:: --kf-fill <False | True | NUMBER | PATH>

    Indicates how to :ref:`fill missing KF-factor values <fill-kf>`. Options are
    
    * ``False``: Does not fill missing values
    * ``True``: Replaces missing values with the median KF-factor in the dataset
    * ``NUMBER``: Replaces missing values with the indicated number
    * ``PATH``: Uses the indicated dataset to implement spatially varying fill values. Missing KF-factor values are replaced with the co-located value in the fill-value dataset. Usually a Polygon or MultiPolygon feature file, but may also be a raster dataset. If a Polygon/MultiPolygon file, then you must also provide the :confval:`kf_fill_field` setting.

    Examples::

        # Do not fill missing values
        wildcat preprocess --kf-fill False

        # Replace missing values with the median
        wildcat preprocess --kf-fill True

        # Replace with a specific number
        wildcat preprocess --kf-fill 0.8

        # Replace using a spatially varying dataset
        wildcat preprocess --kf-fill my-kf-fill-file.shp

    *Overrides setting:* :confval:`kf_fill`


.. option:: --kf-fill-field NAME

    The name of the data attribute field from which to read KF-factor fill values when :confval:`kf_fill` is the path to a Polygon or MultiPolygon feature file. Ignored if :confval:`kf_fill` is anything else.

    Example::

        # Read fill value data from the "FILL_VALUE" field
        wildcat preprocess --kf-fill-field FILL_VALUE

    *Overrides setting:* :confval:`kf_fill_field`


EVT Masks
+++++++++

.. option:: --water VALUE...

    A list of EVT values that should be classified as water bodies. These pixels will not be used for :ref:`network delineation <delineate>`. Ignored if there is no :confval:`evt` dataset. If provided in conjunction with the :confval:`iswater` dataset, then the two masks will be combined to produce the final preprocessed water mask.

    Examples::

        # Classify EVT values as water
        wildcat preprocess --water 1 2 3

    *Overrides setting:* :confval:`water`


.. option:: --no-find-water

    Do not build a water mask from the EVT. Cannot be used with the :option:`--water <preprocess --water>` option.

    Example::

        # Do not build a water mask from the EVT
        wildcat preprocess --no-find-water

    *Overrides setting:* :confval:`water`


.. option:: --developed VALUE...

    A list of EVT values that should be classified as human development. The development mask will be used to inform :ref:`network filtering <filter>`. Ignored if there is no :confval:`evt` dataset. If provided in conjunction with the :confval:`isdeveloped` dataset, then the two masks will be combined to produce the final preprocessed development mask.

    Example::

        # Classify EVT values as development
        wildcat preprocess --developed 7296 7297 7298 7299

    *Overrides setting:* :confval:`developed`


.. option:: --no-find-developed

    Do not build a development mask from the EVT. Cannot be used with the :option:`--developed <preprocess --developed>` option.

    Example::

        # Do not built a development mask from the EVT
        wildcat preprocess --no-find-developed

    *Overrides setting:* :confval:`developed`


.. option:: --excluded-evt VALUE...
    
    A list of EVT values that should be classified as excluded areas. These pixels will not be used for :ref:`network delineation <delineate>`. Ignored if there is no :confval:`evt` dataset. If provided in conjunction with the :confval:`excluded` dataset, then the two masks will be combined to produce the final preprocessed exclusion mask.

    Example::

        # Classify EVT values as excluded areas
        wildcat preprocess --excluded-evt 1 2 3

    *Overrides setting:* :confval:`excluded_evt`


.. option:: --no-find-excluded

    Do not build an exclusion mask from the EVT. Cannot be used with the :option:`--excluded-evt <preprocess --excluded-evt>` option.

    Example::

        # Do not build an exclusion mask from the EVT
        wildcat preprocess --no-find-excluded

    *Overrides setting:* :confval:`excluded_evt`
