Configuring Wildcat
===================

.. highlight:: python

When you generate a ``configuration.py`` file (config file) with the :doc:`initialize command </commands/initialize>`, the config values are all set to their defaults. The default values are selected to implement a USGS-style hazard assessment, but many users may wish to alter these settings. Editing the values in the ``configuration.py`` file is the standard way to configure settings for wildcat commands.

Each config file is unique to its associated project folder. This means that you can use different config settings for the assessments in different project. Advanced users can also temporarily override a project's config settings, which is :ref:`detailed below <override>`. If a project does not have a config file, or if a setting is not included in the file, then wildcat will use the default value for that setting.

.. note::

    The ``configuration.py`` file is imported and executed when you run a wildcat command. Please :ref:`read below <execute-config>` for implications.

.. tip::

    Read the :doc:`Config API </api/config/index>` for a complete guide to available config settings.


Python Primer
-------------

The ``configuration.py`` file is a Python file. These means that config settings should be set using standard Python syntax. This section provides a brief introduction to this syntax for users unfamiliar with Python.

**Text values** should be provided within either single quotes ``''`` or double-quotes ``""``. For example::

    # A text setting
    format = "GeoJSON"  # double quotes
    format = 'GeoJSON'  # single quotes

**File paths** follow a similar syntax, but should have an ``r`` character before the first quote. (This stops Python from interpreting ``\`` folder separators as escape sequences). Alternatively, users familiar with Python may instead use a `pathlib.Path object <https://docs.python.org/3/library/pathlib.html>`_::

    # A file path (works for both / and \ separators)
    perimeter = r"path/to/my-fire-perimeter.shp"
    perimeter = r"path\to\my-fire-perimeter"

    # Using a Path object
    from pathlib import Path
    perimeter = Path("my-inputs") / "my-fire-perimeter.shp"

**Numeric values** are provided directly, without quotes::

    # A numeric value
    min_area_km2 = 0.025

Some settings permit a **list of values**. The items in the list should follow the rules described above. The items should be separated by commas and enclosed within square brackets ``[]``::

    # A list of numeric values
    I15_mm_hr = [16, 20, 24]

    # A list of text values
    properties = ["Area_km2", "BurnRatio", "Slope"]

Finally, the :confval:`rename` setting should be a `Python dict`_ with a more complex syntax. You can learn more about this setting on the :ref:`next page <rename>`.

.. _Python dict: https://docs.python.org/3/tutorial/datastructures.html#dictionaries


.. _execute-config:

Executing ``configuration.py``
------------------------------

The ``configuration.py`` file is imported and executed when you run a wildcat command. This means you can run arbitrarily complex Python code within your config file. Advanced users may find this useful for determining config settings programmatically. 


.. admonition:: Advanced Use

    If you run Python code within the config file, and the code has side effects, then those side effects will be in effect for the wildcat command. In general, we recommend avoiding code with side effects in the config file, as these effects are not evident from the wildcat command signatures. Developers who want to implement side effects should instead run wildcat within a Python session and implement the side effects prior to the wildcat commands.


.. _override:

Overriding ``configuration.py``
-------------------------------

Advanced users may be interested in temporarily overriding the config settings in ``configuration.py``. For example, to examine how different assessment parameters affect the final network. Although you could do this by editing ``configuration.py`` and then rerunning the command, it's usually easier to override the config settings. You can do this via the command line or via a Python session.

Command line options have higher priority than the values in ``configuration.py``, so these will override any config file settings. Note that any ``configuration.txt`` records will reflect the overridden config settings, so will still exactly reproduce the command outputs. You can learn more about the command line arguments in the :doc:`Command Line API </api/cli/index>`.

For users working in a Python session, the function kwargs act analogously to the command line arguments, overriding any values in ``configuration.py``. You can learn about the kwarg options in the :doc:`Python API </api/python>`.

.. tip::
  
    When running multiple versions of a command, it's often useful to also override the default output folder. This way, existing results are not overwritten.


Example 1: Different Filters
++++++++++++++++++++++++++++

For example, say we want to examine how different slope thresholds affect the filtered network. Our configuration file has:

.. code:: python

    # In configuration.py
    min_slope = 0.12

but we would also like to examine the network using a minimum slope of 0.2. We could implement this using:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            # Filters network using 0.12 from the config file
            wildcat assess my-project

            # Reruns, using min_slope of 0.2 and saving results to a different folder
            wildcat assess my-project --min-slope 0.2 --assessment slope20

    .. tab-item:: Python

        .. code:: python

            # Filters network using 0.12 from the config file
            assess("my-project")

            # Reruns, using min_slope of 0.2 and saving results to a different folder
            assess("my-project", min_slope=0.2, assessment="slope20")

We can now use the results in the ``assessment`` and ``slope20`` folders to examine the changes to the network. The config record in the ``assessment`` folder will indicate a slope of 0.12, and the record in ``slope20`` will indicate 0.2.


Example 2: Multiple Exports
+++++++++++++++++++++++++++

Sometimes, it may be useful to export an assessment multiple times. For example, you might export results to different GIS formats to accommodate different hazard assessment users. In this example, we'll use command-line arguments to export results as Shapefiles and GeoJSON. To keep the results organized, we'll place each set of exports into a different subfolder of ``exports``:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            # First, export shapefiles into a "shapefile" subfolder
            wildcat export --format Shapefile --exports exports/shapefile

            # Then, export GeoJSON into a "geojson" subfolder
            wildcat export --format GeoJSON --exports exports/geojson

    .. tab-item:: Python

        .. code:: python

            # First, export shapefiles into a "shapefile" subfolder
            export(format="Shapefile", exports="exports/shapefile")

            # Then, export GeoJSON into a "geojson" subfolder
            export(format="GeoJSON", exports="exports/geojson")

Our file tree would resemble the following:

.. code:: none

    my-project
    ├── configuration.py
    ├── ...
    └── exports
        ├── shapefile
        |   ├── segments.shp
        |   ├── basins.shp
        |   ├── outlets.shp
        |   └── configuration.txt
        └── geojson
            ├── segments.json
            ├── basins.json
            ├── outlets.json
            └── configuration.txt

and we could then send the different export subfolders to the different assessment users.