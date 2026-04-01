"""
Organize default configuration settings
----------
The modules in this subpackage hold related groups of default configuration values.
This makes it easier to locate and change the default values for various commands.
This subpackage is mostly for internal organization. Note the "defaults" module,
which collects all default values into a single namespace. Most internal applications,
such as the configuration parser, make use of this collective namespace.
----------
Modules:
    folders     - Default IO folder names
    preprocess  - Default settings for the preprocessor
    assess      - Default hazard assessment settings
    export      - Default export settings
    defaults    - Collective namespace holding all default values
"""
