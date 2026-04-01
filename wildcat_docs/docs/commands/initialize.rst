initialize
==========

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash

            wildcat initialize project

    .. tab-item:: Python

        .. code:: python

            from wildcat import initialize
            initialize(project)


The initialize command creates a project folder for a wildcat assessment. The project folder will contain a ``configuration.py`` config file and an empty ``inputs`` subfolder. The fields of the config file will all be set to wildcat's defaults. By default, the initialized config file will only contain the most commonly configured fields. However, users can instead initialize a config file with *every* configuration setting using:

.. tab-set::

    .. tab-item:: CLI

        .. code:: bash
            
            wildcat initialize project --config full

    .. tab-item:: Python

        .. code:: python
            
            from wildcat import initialize
            initialize(project, config="full")

A complete list of supported config styles is as follows:

.. list-table::
    :header-rows: 1

    * - Style
      - Description
    * - ``default``
      - Creates a config file with the most commonly edited settings
    * - ``full``
      - Creates a config file with every available setting
    * - ``empty``
      - Creates a config file that notes the wildcat version by includes no fields
    * - ``none``
      - Does not create a config file
    
