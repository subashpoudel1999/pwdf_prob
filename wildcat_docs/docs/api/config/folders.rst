IO Folder Configuration
=======================

These fields specify the folders where wildcat commands should search for input files and save output files. If these fields are relative paths (as is usually the case), then they are interpreted relative to the project folder.

.. confval:: inputs
    :type: ``str | Path``
    :default: ``r"inputs"``

    The folder where the :doc:`preprocess command </commands/preprocess>` should search for input datasets, when those datasets are provided as relative paths..
    
.. confval:: preprocessed
    :type: ``str | Path``
    :default: ``r"preprocessed``

    The folder where wildcat should store preprocessed datasets. The :doc:`preprocess command </commands/preprocess>` will save its outputs to this folder, and the :doc:`assess command </commands/assess>` will search this folder for preprocessed inputs.

.. confval:: assessment
    :type: ``str | Path``
    :default: ``r"assessment"``

    The folder where wildcat should store assessment results. The :doc:`assess command </commands/assess>` will save its outputs to this folder, and the :doc:`export command </commands/export>` will export the datasets saved in this folder.

.. confval:: exports
    :type: ``str | Path``
    :default: ``r"exports"``

    The folder where the :doc:`export command </commands/export>` should save exported assessment results.
