Export Configuration
====================

.. highlight:: python

These fields specify settings used to :doc:`export assessment results </commands/export>`.


Output file
+++++++++++
These settings affect the format and names of the exported files.

.. confval:: format
    :type: ``str``
    :default: ``"Shapefile"``

    The GIS file format of the exported files. The :ref:`Vector Format Guide <vector-formats>` lists the supported format options in the first column. Format names are case-insensitive.

    Example::

        # Export results to Shapefile
        format = "Shapefile"

    *CLI option:* :option:`--format <export --format>`

    *Python kwarg:* |format kwarg|_

.. |format kwarg| replace:: ``format``

.. _format kwarg: ./../python.html#python-export


.. _export-crs:

.. confval:: export_crs
    :type: ``str | int``
    :default: ``"WGS 84"``

    Specifies the coordinate reference system (CRS) that the exported segment, basin, and outlet geometries should use. The base geometries from the assessment results will be reprojected into this CRS prior to export. Accepts a variety of CRS indicators, including: EPSG codes, CRS names, well-known text, and PROJ4 parameter strings. Consult the `pyproj documentation <https://pyproj4.github.io/pyproj/stable/examples.html>`_ for more details on supported inputs.

    Alternatively, set ``export_crs = "base"`` to leave the geometries in the base assessment CRS. In practice, this is the CRS of the preprocessed DEM used to derive the stream segment network.

    Examples::

        # EPSG codes (supports multiple formats)
        export_crs = "EPSG: 4326"
        export_crs = "4326"
        export_crs = 4326

        # CRS names
        export_crs = "WGS 84"
        export_crs = "NAD83 / UTM zone 11N"

        # Disable reprojection
        export_crs = "base"

    *CLI option:* :option:`--crs <export --crs>`

    *Python kwarg:* |export_crs kwarg|_

.. |export_crs kwarg| replace:: ``export_crs``

.. _export_crs kwarg: ./../python.html#python-export


.. confval:: prefix
    :type: ``str``
    :default: ``""``

    A string that should be prepended to the beginning of exported file names. May only include ASCII letters, numbers, hyphens (``-``), and/or underscores (``_``).

    Example::

        # Add "fire-id" to the beginning of exported file names
        prefix = "fire-id"

    *CLI option:* :option:`--prefix <export --prefix>`

    *Python kwarg:* |prefix kwarg|_

.. |prefix kwarg| replace:: ``prefix``

.. _prefix kwarg: ./../python.html#python-export



.. confval:: suffix
    :type: ``str``
    :default: ``""``

    A string that should be appended to the end of exported file names (but before the file extension). May only include ASCII letters, numbers, hyphens (``-``), and/or underscores (``_``).

    Example::

        # Add "YYYY-MM-DD" to the end of exported file names
        suffix = "YYYY-MM-DD"

    *CLI option:* :option:`--suffix <export --suffix>`

    *Python kwarg:* |suffix kwarg|_

.. |suffix kwarg| replace:: ``suffix``

.. _suffix kwarg: ./../python.html#python-export



Properties
++++++++++

Settings that :ref:`select exported properties <select-props>`.

.. confval:: properties
    :type: ``[str, ...]``
    :default: ``["default"]``

    The list set of exported properties. May include property names, result prefixes, and property groups.

    Example::

        # Export catchment area, hazard results, and model inputs
        properties = ["Area_km2", "H", "model inputs"]

    *CLI option:* :option:`--properties <export --properties>`

    *Python kwarg:* |properties kwarg|_

.. |properties kwarg| replace:: ``properties``

.. _properties kwarg: ./../python.html#python-export



.. confval:: exclude_properties
    :type: ``[str, ...]``
    :default: ``[]``

    Properties that should be removed from the base property list. May include property names, result prefixes, and property groups.

    Example::

        # Export watershed variables, except for Segment_ID
        properties = ["watershed"]
        exclude_properties = ["Segment_ID"]

    *CLI option:* :option:`--exclude-properties <export --exclude-properties>`

    *Python kwarg:* |exclude_properties kwarg|_

.. |exclude_properties kwarg| replace:: ``exclude_properties``

.. _exclude_properties kwarg: ./../python.html#python-export



.. confval:: include_properties
    :type: ``[str, ...]``
    :default: ``[]``

    Properties that should be added to the property list, after excluded properties have been removed. May include property names, result prefixes, and property groups.

    Example::

        # Export default fields, but exclude watershed variables (except for Segment_ID)
        properties = ["default"]
        exclude_properties = ["watershed"]
        include_properties = ["Segment_ID"]

    *CLI option:* :option:`--include-properties <export --include-properties>`

    *Python kwarg:* |include_properties kwarg|_

.. |include_properties kwarg| replace:: ``include_properties``

.. _include_properties kwarg: ./../python.html#python-export



Property Order
++++++++++++++

.. confval:: order_properties
    :type: ``bool``
    :default: ``True``

    Whether to :ref:`reorder <reorder>` the exported properties, such that related properties are grouped together. If ``False``, does not reorder the properties. In this case,  properties will be ordered in the order they are listed.

    Example::

        # Do not reorder the properties
        order_properties = False

    *CLI option:* :option:`--no-order-properties <export --no-order-properties>`

    *Python kwarg:* |order_properties kwarg|_

.. |order_properties kwarg| replace:: ``order_properties``

.. _order_properties kwarg: ./../python.html#python-export



Rename
++++++
Settings used to :ref:`rename <rename>` the exported properties.

.. confval:: clean_names
    :type: ``bool``
    :default: ``True``

    Whether to rename result properties, such that hazard parameter indices are replaced with simplified parameter values. If ``False``, exported result properties will retain the index naming scheme.

    Example::

        # Do not rename result indices to values
        clean_names = False

    *CLI option:* :option:`--no-clean-names <export --no-clean-names>`

    *Python kwarg:* |clean_names kwarg|_

.. |clean_names kwarg| replace:: ``clean_names``

.. _clean_names kwarg: ./../python.html#python-export



.. confval:: rename
    :type: ``dict``
    :default: ``{}``

    A dict with custom renaming settings. The keys may include property names, hazard prefixes, or hazard parameter names. Please read the :ref:`Renaming Guide <rename>` for more details.

    Example::

        # Implement a custom renaming scheme
        rename = {
            "Segment_ID": "SID",
            "H": "Hazard",
            "probabilities": ["P50", "P75"],
        }

    *CLI options:* :option:`--rename <export --rename>`, :option:`--rename-parameter <export --rename-parameter>`

    *Python kwarg:* |rename kwarg|_

.. |rename kwarg| replace:: ``rename``

.. _rename kwarg: ./../python.html#python-export

