wildcat
=======

Wildcat is a software tool to assess and map post-wildfire debris-flow hazards. It provides routines to:

* Preprocess input datasets,
* Design stream segment networks
* Estimate debris-flow hazards and rainfall thresholds, and
* Export results to common GIS formats (such as Shapefiles and GeoJSON)

Wildcat can be run from the command line, or within a Python session. The package is intended for users who are interested in conducting and communicating hazard assessments. By default, wildcat implements assessments in the USGS style, but users can also configure the tool to run with modified settings.

.. tip::

    Wildcat is designed to implement a USGS hazard assessment framework. If you want to modify wildcat routines or develop new assessment frameworks, you may be interested in the `pfdf library <https://ghsc.code-pages.usgs.gov/lhp/pfdf/>`_ instead.


Using these docs
----------------
These docs contain a variety of resources for wildcat users. The :doc:`User Guide </guide/index>` is designed to introduce new users to the toolbox and is usually the best place to start. After reading the guide, you should be able to implement a basic hazard assessment.

Wildcat commands are complex, multi-step processes. You can use the :doc:`Commands </commands/index>` section to find detailed overviews of the steps and settings for each command. Reading this section is not necessary for running wildcat, but users may benefit by understanding how wildcat works under the hood.

The :doc:`API </api/index>` is the complete reference guide to using wildcat. Use it to learn about the configuration settings available via config files, CLI options, and Python kwargs. Most users will find the :doc:`configuration.py API <api/config/index>` sufficient for their needs. This section provides detailed explanations of all settings available via a configuration file, including tips and best practices. The API can also be useful for troubleshooting error messages, as many wildcat error messages will reference the associated configuration file settings.

Finally, you can find links to:

* :doc:`FAQs and troubleshooting tips <resources/faqs>`,
* :doc:`Commonly used datasets <resources/datasets>`, 
* :doc:`Contribution guidelines <resources/contributing>`,
* :doc:`Citation guidelines <resources/citation>`
* :doc:`Legal documents </resources/legal>`
* :doc:`Release notes <resources/release-notes/index>`, and
* `The latest release <https://code.usgs.gov/ghsc/lhp/wildcat/-/releases/permalink/latest>`_

under the *Resources* section of the navigation sidebar.


What's in a name?
-----------------
The name "wildcat" is a loose acronym of post-(wil)dfire (d)ebris-flow hazard (c)ommunication and (a)ssessment (t)ool.


Citation
--------
If you use wildcat for a publication, please consider citing it. Consult the :doc:`Citation Guide <resources/citation>` for more details.


.. toctree::
    :caption: Documentation
    :hidden:

    Introduction <self>
    Installation <install>
    User Guide <guide/index>
    Commands <commands/index>
    Advanced Topics <advanced/index>
    API <api/index>


.. toctree::
    :caption: Resources
    :hidden:

    FAQs / Troubleshooting <resources/faqs>
    Datasets <resources/datasets>
    Contributing <resources/contributing>
    Citation <resources/citation>
    Legal <resources/legal>

.. toctree::
    :caption: Releases
    :hidden:
    
    Release Notes <resources/release-notes/index>
    Latest Release <https://code.usgs.gov/ghsc/lhp/wildcat/-/releases/permalink/latest>

