wildcat initialize
==================

Synopsis
--------

**wildcat initialize** [project] [options]


Description
-----------

Initializes a project folder for a wildcat assessment. Adds a ``configuration.py`` config file and an empty ``inputs`` subfolder to the project. Note that if the project folder already exists, then it must be empty. If a project folder is not provided, attempts to initialize the project in the current directory.

Examples::

    # Initialize project 
    wildcat initialize my-project

    # Initialize project in current folder
    wildcat initialize




Options
-------

.. program:: wildcat initialize


Config File
+++++++++++
Options used to customize the initialization of the ``configuration.py`` config file

.. option:: -c STYLE, --config STYLE

    Indicates the type of configuration file that should be created. There are four supported config styles, as follows:

    .. list-table::
        :header-rows: 1

        * - ``STYLE``
          - Description
        * - ``default``
          - File includes the most commonly used configuration fields
        * - ``full``
          - File includes every configurable field
        * - ``empty``
          - Creates a blank config file
        * - ``none``
          - Does not create a config file

    Example::

        wildcat initialize my-project -c full


Inputs Folder
+++++++++++++

.. option:: --inputs NAME

    Specifies the name for the empty subfolder created in the project folder. Names the folder ``inputs`` if not specified.

    Example::

        wildcat initialize --inputs my-folder

.. option:: --no-inputs

    Does not create an empty subfolder in the project folder. This option cannot be used with the :option:`--inputs option <wildcat initialize --inputs>`.


Logging
+++++++

.. option:: -q, --quiet

    Does not print progress messages to the console. Warnings and errors will still be printed.

.. option:: -v, --verbose

    Print detailed progress messages to the console. Useful for debugging.

.. option:: --log PATH

    Prints a `DEBUG level`_ log record to the indicated file. If the file does not exists, creates the file. If the file already exists, appends the log record to the end.

    Example::

        wildcat assess --log my-log.txt

.. _DEBUG level: https://docs.python.org/3/library/logging.html#logging.DEBUG


Traceback
+++++++++

.. option:: -t, --traceback

    Prints the full error traceback to the console when an error occurs (useful for debugging). If this option is not provided, then only the final error message is printed. 