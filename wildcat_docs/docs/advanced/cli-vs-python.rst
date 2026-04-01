CLI vs Python
=============

Developers building off the wildcat framework may wonder whether to build off the CLI or Python interface. When possible, we recommend building off of the Python interface, as this provides various development options not availabe for the CLI. As discussed on the :doc:`logging page <logging>`, the logging streams and format can be customized within a Python session, but are fixed when run from the CLI. The Python interface also allows developers to address `error Exceptions <https://docs.python.org/3/tutorial/errors.html>`_ not handled by wildcat. For example, you could use something like the following to address a DEM georeferencing error:

.. code:: python

    from wildcat.errors import GeoreferencingError
    from wildcat import preprocess

    try:
        preprocess()
    except GeoreferencingError:
        # Code that adds georeferencing to the DEM
        pass
        # Rerun the preprocessor with the updated DEM
        preprocess()

Also, the CLI suppresses error tracebacks by default, setting the global `sys.tracebacklimit <https://docs.python.org/3/library/sys.html#sys.tracebacklimit>`_ to 0. By contrast, the Python commands do not alter this setting, and display error messages as normal.
    

Disabling Files
---------------
Developers should be aware of a subtle difference between the command line and Python interfaces when disabling an input file. Although the ``configuration.py`` and command line settings disable a file path using ``None``, you should use ``False`` to disable a file path when using Python kwargs. This is because the Python functions use ``None`` to indicate the lack of a configuration override.

.. tab-set::

    .. tab-item:: Python

        .. code:: python

            # Disable the KF-factor preprocessor
            from wildcat import preprocess
            preprocess(kf=False)

    .. tab-item:: ``configuration.py``

        .. code:: python

            # Disable the KF-factor preprocessor
            kf = None

    .. tab-item:: CLI

        .. code:: bash

            # Disable the KF-factor preprocessor
            wildcat preprocess --kf None





