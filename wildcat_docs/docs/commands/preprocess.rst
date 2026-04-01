preprocess
==========

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat preprocess project

    .. tab-item:: Python

        .. code:: python

            from wildcat import preprocess
            preprocess(project)


The ``preprocess`` command reprojects and cleans input datasets for the indicated project. If a project is not provided, the command interprets the current folder as the project. The preprocessor ensures that all input datasets are rasters with the same CRS, resolution, alignment, and bounds. This is done by reprojecting all datasets to match the CRS, resolution, and alignment of the DEM. The datasets are then clipped to the bounds of a buffered fire perimeter. The preprocessor also implements various data validation and cleaning steps, which are described below.

----

.. _inputs:

Input Datasets
--------------

The preprocessor supports the following input datasets. The following table summarizes these datasets, and you can find additional details in the :ref:`Dataset Guide <datasets>`:

.. list-table::
    :header-rows: 1

    * - Dataset
      - Description
    * - **Required**
      - 
    * - :confval:`perimeter`
      - A fire perimeter mask. The extent of the buffered perimeter defines the preprocessing domain.
    * - :confval:`dem`
      - Digital elevation model raster. :ref:`Sets the CRS <reproject>`, resolution, and alignment of the preprocessed rasters. Should have approximately 10 meter resolution.
    * - 
      -
    * - **Recommended**
      - 
    * - :confval:`dnbr`
      - Differenced normalized burn ratios. Optionally used to :ref:`estimate burn severity <estimate-severity>`. Should be (raw dNBR * 1000) with values ranging from approximately -1000 to 1000.
    * - :confval:`severity`
      - `BARC4-like <https://burnseverity.cr.usgs.gov/baer/faqs>`_ burn severity. If missing, :ref:`estimated <estimate-severity>` from the dNBR dataset. If a Polygon or MultiPolygon feature file, then you must provide the :confval:`severity_field` setting.
    * - :confval:`kf`
      - Soil :ref:`KF-factors <kf-factors>`. Values should be positive. If a Polygon or MultiPolygon feature file, the you must provide the :confval:`kf_field` setting.
    * - :confval:`evt`
      - Existing vegetation type raster. Used to :ref:`build water, development and exclusion masks <evt-masks>`.
    * - 
      - 
    * - **Optional**
      - 
    * - :confval:`retainments`
      - Locations of debris retainment features.
    * - :confval:`excluded`
      - Areas that should be excluded from :ref:`network delineation <delineate>`. If provided in conjunction with the :confval:`excluded_evt` setting, then the EVT exclusion mask will be combined with this dataset to produce the final preprocessed exclusion mask.
    * - :confval:`included`
      - Mask of areas that should be retained during :ref:`network filtering <filter>`.
    * - :confval:`iswater`
      - Pre-defined water body mask. If provided in conjunction with the :confval:`water` setting, then the water mask from the EVT will be combined with this dataset to produce the final preprocessed water mask.
    * - :confval:`isdeveloped`
      - Pre-defined human development mask. If provided in conjunction with the :confval:`developed` setting, then the EVT development mask will be combined with this dataset to produce the final preprocessed development mask.
    * - :confval:`kf_fill`
      - Spatially varying :ref:`KF-factor <kf-factors>` fill values. Missing KF-factors values :ref:`are replaced <fill-kf>` with the co-located fill value.

The **required** datasets are both essential for running the preprocessor, and the routine will raise an error if they are missing. The **recommended** datasets are not needed to run the preprocessor, but are usually needed to run the :doc:`assess command </commands/assess>`. The **optional** datasets are neither required for the preprocessor, nor for the assess command. Users can explicitly disable the preprocessor for a dataset by setting its config path to ``None``. For example:

.. code:: python

    # Disables the KF-factor preprocessor
    kf = None   # (in configuration.py)


----

Preprocessor Steps
------------------
This section provides an overview of the tasks implemented by the preprocessor.


.. _buffer-perimeter:

Buffered Perimeter
++++++++++++++++++
*Related settings:* :confval:`buffer_km`

The preprocessor's first step is to load and buffer the fire perimeter. Buffering adds a border of NoData pixels matching the specified distance to the edges of the mask. The extent of this buffered perimeter defines the preprocessing domain.



.. _load:

Load Datasets
+++++++++++++
*Related settings:* :confval:`kf_field`, :confval:`kf_fill_field`, :confval:`severity_field`

The routine next loads the remaining datasets and converts vector features to rasters. To accommodate large input file datasets, the command attempts to reduce memory use whenever possible. For raster datasets, the command uses windowed reading to only load data within the extent of the buffered perimeter. Vector feature files are loaded in their entirety, but only features intersecting the buffered perimeter are converted to rasters.



.. _resolution-check:

DEM Resolution
++++++++++++++
*Related settings:* :confval:`resolution_limits_m`, :confval:`resolution_check`

The preprocessor next checks that the DEM dataset has an allowed resolution. The allowed resolutions are determined by the :confval:`resolution_limits_m` setting, which defaults to resolutions from 6.5 to 11 meters. This range is selected to allow all DEM tiles from the USGS National Map within the continental US.

In general, the DEM should have an approximately 10 meter resolution. This is because wildcat's assessment models were calibrated using data from a 10-meter DEM. Read also `Smith et al., 2019 <https://esurf.copernicus.org/articles/7/475/2019/>`_ for a discussion of the effects of DEM resolution on topographic analysis.



.. _reproject:

Reprojection
++++++++++++
Next, all the datasets are reprojected to match the CRS, resolution, and alignment of the DEM. They are then clipped to exactly match the bounds of the buffered fire perimeter.


.. _dnbr-scaling:

dNBR Scaling
++++++++++++
*Related settings:* :confval:`dnbr_scaling_check`

Typically, dNBR datasets are provided as (raw dNBR * 1000), and wildcat expects this convention when running an assessment. As such, the preprocessor next checks that the dNBR appears to follow this scaling. Expected dNBR values range from approximately -1000 to 1000, whereas raw dNBR values range from approximately -1 to 1. The preprocessor validates dNBR scaling by checking for data values outside the range from -10 to 10. By default, raises an error if no data values are outside this range.



.. _constrain-dnbr:

Constrain dNBR
++++++++++++++
*Related settings:* :confval:`constrain_dnbr`, :confval:`dnbr_limits`

Some dNBR datasets can have processing artifacts that manifest as pixels with very large magnitudes. To account for this, the preprocessor next constrains the dNBR data values to a valid range. Data values outside this range are converted to the nearest bound.



.. _estimate-severity:

Estimate Severity
+++++++++++++++++
*Related settings:* :confval:`estimate_severity`, :confval:`severity_thresholds`

.. note::

    This step only occurs when the severity dataset is missing.

Burn severity datasets are not always available, so the preprocessor will estimate burn severity from the dNBR if the severity dataset is missing.



.. _contain-severity:

Contain Severity
++++++++++++++++
*Related settings:* :confval:`contain_severity`

The areas outside the (unbuffered) fire perimeter are expected to be unburned, but some severity datasets may have burned classes outside the perimeter. To account for this, the preprocessor next sets all pixels outside the fire perimeter to an "unburned" severity.



.. _constrain-kf:

Constrain KF-factors
++++++++++++++++++++
*Related settings:* :confval:`constrain_kf`

KF-factors are expected to have positive values, so the preprocessor next converts negative and 0-valued KF-factors to NoData.



.. _missing-kf:

Notify Users of Missing KF-factors
++++++++++++++++++++++++++++++++++
*Related settings:* :confval:`max_missing_kf_ratio`, :confval:`missing_kf_check`

.. note::

    This step only occurs if you do not specify a KF-factor fill value.

Some KF-factor datasets can have large areas of missing data, but NoData values are also reasonable over areas such as water bodies. To address this, the preprocessor checks the KF-factor dataset for missing data. If the proportion of missing data exceeds a certain threshold, then the preprocessor notifies the user, advising them to examine the dataset and ensure its validity.



.. _fill-kf:

Fill Missing KF-factors
+++++++++++++++++++++++
*Related settings:* :confval:`kf_fill`, :confval:`kf_fill_field`

Alternatively, users can provide options for filling missing KF-factors. If one of these options is provided, the preprocessor fills the missing values and does not advise the user to examine the dataset.



.. _evt-masks:

EVT Masks
+++++++++
*Related settings:* :confval:`water`, :confval:`developed`, :confval:`excluded_evt`

The preprocessor next builds water, development, and exclusion masks from the EVT. These masks are used to improve the design of the stream segment network. For a given mask, EVT pixels matching the relevant EVT codes will be included in the mask. When built in conjunction with the :confval:`iswater`, :confval:`isdeveloped`, or :confval:`excluded` datasets, the EVT mask will be combined with the input dataset to produce the final preprocessed mask.



Save Results
++++++++++++
The preprocessor's final step is to save the preprocessed rasters to the ``preprocessed`` subfolder. The datasets in this subfolder represent the minimal datasets needed to reproduce an assessment. The subfolder will also include a ``configuration.txt`` config record. Running the ``preprocess`` command with these settings should exactly reproduce the current preprocessing results.

