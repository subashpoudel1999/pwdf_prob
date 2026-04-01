export
======

The ``export`` command converts saved assessment results from `GeoJSON <https://geojson.org/>`_ to :ref:`other GIS formats <vector-formats>`. The command also includes options to (1) reproject results to a preferred CRS, and (2) select, organize, and rename data fields in the exported files. This page provides an overview of the command's steps, but read also the :doc:`Property Guide </guide/properties>` for detailed information on exporting data fields.


Select Properties
-----------------
*Related settings*: :confval:`properties`, :confval:`exclude_properties`, :confval:`include_properties`

The command begins by determining the data property fields that will be included in the exported files. The command begins with the fields listed by the :confval:`properties` setting, and then removes any properties specified by the :confval:`exclude_properties` settings. Then, the command adds in any properties specified by the :confval:`include_properties` setting. You can add properties to these settings using names, prefixes, and/or groups. You can learn more about these selection options here: :ref:`Selecting Properties <select-props>`.


.. _reorder:

Order Properties
----------------
*Related settings:* :confval:`order_properties`

Next, the routine reorders the exported properties to group related values together. Properties are grouped as follows, excluding any properties not being exported:

* ``Segment_ID``,
* Hazard, likelihood, and volume results -- grouped by I15 values,
* Rainfall accumulations and thresholds -- grouped first by duration, then by probability level,
* Model inputs (in :ref:`this order <input-props>`),
* Watershed variables (in :ref:`this order <watershed-props>`), and
* Filtering variables (in :ref:`this order <filter-props>`)

You can disable this reordering by setting :confval:`order_properties` to ``False``. In this case, properties will be exported in the order they are listed. If a property is listed multiple times, then its order will match its first occurrence in the property list. For example, the following configuration lists ``Segment_ID`` twice:

.. code:: python

    order_properties = False
    properties = ["Segment_ID", "results", "watershed"]

First, the field is listed by name, and then as a member of the :ref:`watershed group <watershed-props>`. In the exported files, ``Segment_ID`` will be the first property (rather than with the other watershed variables), because it is first listed by name in the property list.


Rename Properties
-----------------
*Related settings:* :confval:`rename`, :confval:`clean_names`

Next, the routine renames data fields as appropriate. The command first applies a default renaming scheme to result fields, which you can disable by setting :confval:`clean_names` to ``False``. The command then applies any user-specified names to the exported fields. You can learn more about renaming options in the :ref:`Renaming Guide <rename>`.


Reproject Results
-----------------
*Related settings:* :confval:`export_crs`

The command then reprojects the exported segment, basin, and outlet geometries to the requested coordinate reference system (CRS). If you disable reprojection, then the exported geometries will remain in the base assessment CRS, which is the CRS of the preprocessed DEM.


File Format
-----------
*Related settings:* :confval:`format`

The export command then exports the selected results to the indicated file format. The command supports many common GIS formats including Shapefiles, GeoJSON, Geopackage, and File Geodatabases. You can find a complete list of supported export formats in the :ref:`Vector Format Guide <vector-formats>`.


File Names
----------
*Related settings:* :confval:`prefix`, :confval:`suffix`

The exported files will be named:

* ``segments``, 
* ``basins``, and 
* ``outlets`` 

followed by the appropriate extension for the export format. You can also use the :confval:`prefix` and :confval:`suffix` settings to add text to the beginning and end of the file names. As these are file names, only ASCII letters, numbers, hyphens (``-``), and underscores (``_``) are permitted in the prefix and suffix. For example, you could use the following configuration:

.. code:: python

    prefix = "fire-id_"
    suffix = "_2024-01-01"

to export files named:

* ``fire-id_segments_2024-01-01``, 
* ``fire-id_outlets_2024-01-01``, and 
* ``fire-id_basins_2024-01-01``

The exported files will also include a ``configuration.txt`` config record, which can be used to exactly reproduce the exported files.

