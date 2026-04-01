Custom Errors
=============

.. _wildcat.errors:

.. py:module:: wildcat.errors

    Custom error exceptions implemented by wildcat.


.. py:exception:: ConfigError
    :module: wildcat.errors

    Bases: :py:class:`Exception`

    When a configuration file cannot be read.


.. py:exception:: ConfigRecordError
    :module: wildcat.errors

    Bases: :py:class:`~wildcat.errors.ConfigError`

    When a recorded ``configuration.txt`` file cannot be read


.. py:exception:: GeoreferencingError
    :module: wildcat.errors

    Bases: :py:class:`Exception`

    When a DEM does not have valid georeferencing.