Logging
=======

By default, wildcat will log progress messages to the console. This page provides instructions for customizing this logging process.


Command Line
------------
If you are running wildcat from the command line, you can suppress logging messages using the ``-q`` or ``--quiet`` options. The logger will still print warnings and error messages to the console, but progress messages are disabled. Alternatively, you can print highly detailed messages using the ``-v`` or ``--verbose`` options, which can be useful for debugging.

Finally, you can use the ``--log PATH`` option to log detailed (`DEBUG level <https://docs.python.org/3/library/logging.html#logging.DEBUG>`_) progress to the indicated file. If the file does not exist, then wildcat will create a new file. If the log file already exists, then wildcat will append its log record to the end of the file.

Note that the console and file logs are independent. For example, you could use:

.. code:: bash

    wildcat assess --quiet --log my-log.txt

which would log detailed progress to ``my-log.txt``, but would not print messages to the console.

.. note::

    You cannot modify the logging streams or format from the command line. If you want to do this, you should run wildcat from within a Python session.


Python
------

.. tip::

    These instructions are mostly intended for developers. Typical wildcat users will not need this section.

Wildcat does not configure the logger when running within a Python session. This means you can modify the log streams and formats using the standard `logging library <https://docs.python.org/3/library/logging.html>`_. Wildcat uses a uniquely named logger for each command. Following standard Python conventions, these are named: ``wildcat.initialize``, ``wildcat.preprocess``, ``wildcat.assess``, and ``wildcat.export``.

For example, you can use the following snippet to log detailed preprocessing messages to the console in the CLI style:

.. code:: python

    import logging
    logger = logging.getLogger('wildcat.preprocess')
    logger.setLevel(logging.DEBUG)

    to_console = logging.StreamHandler()
    to_console.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    to_console.setFormatter(formatter)
    logger.addHandler(to_console)

Analogously, the following snippet will log detailed progress messages to file in the CLI style:

.. code:: python

    import logging
    logger = logging.getLogger('wildcat.preprocess')
    logger.setLevel(logging.DEBUG)

    to_file = logging.FileHandler('my-file.txt')
    to_file.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
    to_file.setFormatter(formatter)
    logger.addHandler(to_file)

