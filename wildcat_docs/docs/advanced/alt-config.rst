Alternate Configuration Files
=============================
In some cases, you may want to use a different file than ``configuration.py`` as the configuration file. Some common use cases include (1) running a wildcat command several times with different settings, and (2) running wildcat alongside other tools that also use configuration files. More detailed examples are provided below.

You can use the ``config`` override to specify a different configuration file than ``configuration.py``. Using the assess command as an example:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat assess --config my-alternate-config.py

    .. tab-item:: Python

        .. code:: python

            from wildcat import assess
            assess(config="my-alternate-config.py")

This override should indicate the path to the desired configuration file. If ``config`` is a relative path, then it is interpreted relative to the **project** folder, rather than the current folder.

Examples
--------

Running a Command Multiple Times
++++++++++++++++++++++++++++++++
A common use case for alternate configuration files is running a wildcat multiple times with different settings. In this case, it can be convenient to use a different configuration file to record to settings for each run of the command. 

For example, say we want to export our assessment results in both WGS 84, and in NAD 83 projections. We'd also like each export to include a custom file suffix indicating the projection. We can implement this by using two different configuration files - one with settings for WGS 84, and a second for NAD 83. We could start by creating two configuration files with the following contents:

::

    # This file is named `wgs84-config.py`
    format = "GeoJSON"
    export_crs = "WGS 84"
    suffix = "_WGS84"

::

    # And this file is `nad83-config.py`
    format = "GeoJSON"
    export_crs = "NAD 83"
    suffix = "_NAD83"

We could then run the two different exports using:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat export --config wgs84-config.py
            wildcat export --config nad83-config.py

    .. tab-item:: Python

        .. code:: python

            from wildcat import export
            export(config="wgs84-config.py")
            export(config="nad83-config.py")


Multiple Tools that use Config Files
++++++++++++++++++++++++++++++++++++

Another use case for alternate configuration files is running wildcat alongside other software tools that also use configuration files. In this case, it can be useful to help distinguish the different configuration files from one another. For example, you might name the wildcat configuration file ``wildcat-configuration.py`` to be more explicit. In this case, you could run wildcat using the following:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat preprocess --config wildcat-configuration.py
            wildcat assess --config wildcat-configuration.py
            wildcat export --config wildcat-configuration.py

    .. tab-item:: Python

        .. code:: python

            from wildcat import preprocess, assess, export
            preprocess(config="wildcat-configuration.py")
            assess(config="wildcat-configuration.py")
            export(config="wildcat-configuration.py")
