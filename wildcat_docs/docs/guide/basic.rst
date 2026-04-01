Basic Usage
===========

This page describes how to run a basic hazard assessment using wildcat.


Running commands
----------------

After :doc:`installing wildcat </install>`, you can run wildcat commands from the command line (CLI) or from within a Python session. For example:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat assess <args>

    .. tab-item:: Python

        .. code:: python

            from wildcat import assess
            assess(...)

There are four main commands in wildcat:

.. list-table::
    :header-rows: 1

    * - Command
      - Description
    * - :doc:`initialize </commands/initialize>`
      - Creates a project folder for an assessment
    * - :doc:`preprocess </commands/preprocess>`
      - Reprojects and cleans input datasets
    * - :doc:`assess </commands/assess>`
      - Conducts a hazard assessment using preprocessed datasets
    * - :doc:`export </commands/export>`
      - Export asssessment results to GIS formats (such as Shapefiles and GeoJSON)

You can learn more about each command by following the links in the table, but we recommend reading this page first for a general introduction.


Getting Started
---------------
Most users will start by using the :doc:`initialize command </commands/initialize>` to initialize a project folder for an assessment. The command requires the path to a project folder as input. When run, ``wildcat initialize`` will create the indicated folder and add a default configuration file. It will also create an empty ``inputs`` subfolder, which you can use to store input datasets for the assessment.

For example, running:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat initialize my-project

    .. tab-item:: Python

        .. code:: python

            from wildcat import initialize
            initialize(project="my-project")

will create the following file tree in the current folder::

    my-project
    ├── configuration.py
    └── inputs


The ``configuration.py`` file holds the settings that will be used to run wildcat commands for the assessment. When you initialize a project, the config settings will all be set to the wildcat defaults, which will implement a USGS-style hazard assessment. This should be sufficient for many users, but you can also edit ``configuration.py`` to change these settings. You can learn more about the configuration file and its settings in the :doc:`configuration section <config>`.

.. tip::

    The default config file will only hold the most commonly edited fields. To initialize a config file with *every* possible setting, use:

    .. code:: bash

        wildcat initialize project --config full


.. _datasets:

Input Datasets
--------------
Next, we'll want to add various input dataset files to the project. Most assessments will need at least the following datasets:

.. _standard-datasets:

.. list-table::
    :header-rows: 1

    * - Dataset
      - Description
    * - :confval:`perimeter`
      - A fire perimeter mask. The mask will be :ref:`buffered <buffer-perimeter>`, and the extent of the buffered perimeter will define the domain of the analysis. Pixels in the perimeter may used used to :ref:`delineate <delineate>` the stream segment network, and segments sufficiently within the perimeter are retained during :ref:`network filtering <filter>`. Usually a Polygon or MultiPolygon feature file, but may also be a raster mask.
    * - :confval:`dem`
      - Digital elevation model (DEM) raster. Used by the preprocessor to :ref:`set the CRS <reproject>`, resolution, and alignment of the preprocessed rasters. Used by the assessment to :ref:`characterize <characterize>` the watershed (including flow directions). Should have approximately 10 meter resolution.
    * - :confval:`dnbr`
      - Differenced normalized burn ratios (dNBRs). Used to estimate debris-flow :ref:`likelihoods <likelihoods>` and :ref:`rainfall thresholds <thresholds>`. Optionally used to :ref:`estimate burn severity <estimate-severity>`. Should be (raw dNBR * 1000) with values ranging from approximately -1000 to 1000. Usually a raster, but also supports using a constant value throughout the watershed.
    * - :confval:`severity`
      - `BARC4-like <https://burnseverity.cr.usgs.gov/baer/faqs>`_ burn severity. Used to :ref:`locate burned areas <severity-masks>`, which are used to :ref:`delineate <delineate>` the stream segment network. Also used to locate areas burned at moderate-or-high severity, which are used to estimate debris flow :ref:`likelihoods <likelihoods>`, :ref:`volumes <volumes>`, and :ref:`rainfall thresholds <thresholds>`. If missing, :ref:`estimated <estimate-severity>` from the dNBR dataset. Usually a raster, but may also be a Polygon or MultiPolygon feature file. Also supports using a constant value throughout the watershed.
    * - :confval:`kf`
      - :ref:`Soil KF-factors <kf-factors>`. Used to estimate :ref:`likelihoods <likelihoods>` and :ref:`rainfall thresholds <thresholds>`. Values should be positive, and the preprocessor will :ref:`convert non-positive <constrain-kf>` values to NoData by default. Often a Polygon or MultiPolygon feature file, but may also be a numeric raster. Also supports using a constant value throughout the watershed.
    * - :confval:`evt`
      - Existing vegetation type raster. Although not required for an assessment, the EVT is used to :ref:`build water, development, and exclusion masks <evt-masks>`, which can improve the design of the stream segment network. Usually a raster of classification code integers.

And wildcat also supports the following optional datasets:

.. _optional-datasets:

.. list-table::
    :header-rows: 1

    * - Dataset
      - Description
    * - :confval:`retainments`
      - Locations of debris retainment features. Pixels downstream of these features are not used for :ref:`network delineation <delineate>`. Usually a Point or MultiPoint feature file, but may also be a raster mask.
    * - :confval:`excluded`
      - Mask of areas that should be excluded from network delineation. Pixels in these areas will not be used to :ref:`delineate <delineate>` the network. Often a Polygon or MultiPolygon feature file, but may also be a raster mask.
    * - :confval:`included`
      - Mask of areas that should be retained during :ref:`network filtering <filter>`. Any stream segments that intersect the mask will be retained in the network. Often a Polygon or MultiPolygon feature file, but may also be a raster mask.
    * - :confval:`iswater`
      - Pre-computed water body mask. Areas within the mask will be excluded from :ref:`network delineation <delineate>`. Often a Polygon or MultiPolygon feature file, but may also be a raster mask.
    * - :confval:`isdeveloped`
      - Pre-defined human development mask. Used to inform :ref:`network filtering <filter>`. Often a Polygon or MultiPolygon feature file, but may also be a raster mask.
    * - :confval:`kf_fill`
      - Spatially varying :ref:`KF-factor <kf-factors>` fill values. Missing KF-factor values :ref:`will be replaced <fill-kf>` with the co-located fill value. Often a Polygon or MultiPolygon feature file, but may also be a numeric raster.

You can follow the links in the tables to learn more about using each dataset, but we recommend reading this page first for an general introduction.

Constant valued datasets
++++++++++++++++++++++++

The :confval:`kf`, :confval:`dnbr`, and :confval:`severity` datasets all support using a constant value throughout the watershed. This can be useful when a spatially complete dataset is not available. You can implement a constant value by setting a dataset equal to a number, rather than a file path.




Add Data to Project
-------------------

Once you have collected the dataset files, you should update ``configuration.py`` with the paths to these files. If a data file is in the ``inputs`` subfolder, then you only need to provide the file name. If a data file is elsewhere on your machine, then you should provide the absolute file path. The latter is useful when you have large data files that you don't want to copy or move into the project folder. 

For example, say we've collected the 6 standard datasets in the :ref:`above table <standard-datasets>`. Four of our datasets are small, so we place them in the ``inputs`` folder, but two of the datasets (EVT and KF-factors) are large, so we keep them on an external drive. Our file tree resembles the following::

    .
    ├── my-project
    |   ├── configuration.py
    |   └── inputs
    |       ├── my-perimeter.shp
    |       ├── my-dnbr.tif
    |       ├── my-severity.tif
    |       └── my-dem-tile.tif
    └── external-drive
        └── large-files
            ├── EVT-CONUS.tif
            └── soil-data.shp

We should now update the indicated sections of ``configuration.py`` as follows:

.. code:: python

    # Required Datasets
    perimeter = r"my-perimeter.shp"
    dem = r"my-dem-tile.tif"

    # Recommended Datasets
    dnbr = r"my-dnbr.tif"
    severity = r"my-severity.tif"
    kf = r"/external-drive/large-files/soil-data.shp"
    evt = r"/external-drive/large-files/EVT-CONUS.shp"

Note that we used absolute paths for the files on the external drive.

.. admonition:: What's with the ``r``?

    The ``r`` character at the start of the file paths stops Python from interpreting ``\`` characters (used as folder separators on Windows) as escape sequences. This ensures that the config file behaves the same across different operating systems.


Finalize Configuration
----------------------
We can now make any additional changes to ``configuration.py`` that we deem necessary. Continuing the example, the KF-factor dataset ``soil-data.shp`` appears to be a Polygon shapefile, so we will need to use the :confval:`kf_field` config setting to indicate the data attribute field that holds the KF-factor data:

.. code:: python

    # In configuration.py
    kf_field = "KFFACT"

You can find a guide to all available config settings in the :doc:`config file API </api/config/index>`.


Preprocess
----------

We're now ready to run the other wildcat commands. We'll start by using the :doc:`preprocess command </commands/preprocess>` to clean and reproject the input datasets:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat preprocess my-project

    .. tab-item:: Python

        .. code:: python

            from wildcat import preprocess
            preprocess("my-project")

This will create a ``preprocessed`` subfolder within our project. This subfolder contains the preprocessed rasters ready for the assessment and also a record of the config settings used to run the preprocessor. The ``preprocessed`` folder can be of interest for archival purposes, as it contains the minimum dataset needed to reproduce a hazard assessment.

Continuing the example, our file tree is now::

    my-project
    ├── configuration.py
    ├── inputs
    |   └── ...
    └── preprocessed
        ├── perimeter.tif
        ├── dem.tif
        ├── dnbr.tif
        ├── severity.tif
        ├── kf.tif
        ├── evt.tif
        ├── iswater.tif
        ├── isdeveloped.tif
        └── configuration.txt

where ``configuration.txt`` is the config record for the preprocessor. Most wildcat commands will create similarly named config records. As a rule, you can use the record to exactly reproduce a command's outputs by copying the  record into a ``configuration.py`` file and rerunning the command.

.. tip::

    If you add a dataset to a project *after* running the preprocessor, then you will need to rerun the preprocessor to include the new dataset in the assessment. This most commonly occurs when adding an :ref:`excluded area mask <optional-datasets>` to a project.




Assess
------
We're now ready to run an assessment using the :doc:`assess command </commands/assess>`:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat assess my-project

    .. tab-item:: Python

        .. code:: python

            from wildcat import assess
            assess("my-project")

This will characterize the watershed, design a stream segment network, and estimate debris-flow likelihoods, volumes, hazards, and rainfall thresholds. The command will create an ``assessment`` subfolder in our project, which contains the assessment results. Specifically, these are:

.. list-table::
    :header-rows: 1

    * - File
      - Description
    * - ``segments.geojson``
      - Results for the stream segments as LineString features
    * - ``outlets.geojson``
      - Results for the drainage outlets as Point features
    * - ``basins.geojson``
      - Results for the outlet catchment basins as Polygon features
    * - ``configuration.txt``
      - Record of the config settings used to run the assessment

Our file tree is now::

    my-project
    ├── configuration.py
    ├── inputs
    |   └── ...
    ├── preprocessed
    |   └── ...
    └── assessment
        ├── segments.geojson
        ├── outlets.geojson
        ├── basins.geojson
        └── configuration.txt

If you are comfortable working with GeoJSON, then you may use these results directly, and the saved data fields are documented in the :ref:`assessment properties section <default-properties>`. However, most users prefer to use the :doc:`export command </commands/export>` instead. This command can export results to other GIS formats, and also includes options to help format the output data fields.

.. warning::

    You should treat these output files as read-only. Altering their contents can cause other wildcat commands to fail unexpectedly.


Export
------
Our final step is to run the :doc:`export command </commands/export>`:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat export my-project

    .. tab-item:: Python

        .. code:: python

            from wildcat import export
            export("my-project")


This will created an ``exports`` subfolder in our project with exported results and the usual config record. By default, the command will export results to Shapefile in WGS 84 (EPSG: 4326), but you can also export to many other :ref:`GIS formats <vector-formats>` and :ref:`coordinate reference systems <export-crs>`. The command also includes a variety of options to help format exported data fields, which you can learn about on the :doc:`next page <properties>`.

Our final file tree will be::

    my-project
    ├── configuration.py
    ├── inputs
    |   └── ...
    ├── preprocessed
    |   └── ...
    ├── assessment
    |   └── ...
    └── exports
        ├── segments.shp
        ├── outlets.shp
        ├── basins.shp
        └── configuration.txt

.. note::

    The ``exports`` folder will also include the ``.cpg``, ``.dbf``, ``.prj``, and ``.shx`` files associated with each Shapefile, but we have omitted them here for brevity.

