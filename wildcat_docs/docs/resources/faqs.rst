FAQs / Troubleshooting
======================

* :ref:`faq-errors`
* :ref:`faq-where`
* :ref:`faq-kf-field`
* :ref:`faq-missing-dataset`
* :ref:`faq-modify-network`
* :ref:`faq-os-errors`
* :ref:`faq-dep-errors`

----

.. _faq-errors:

Troubleshooting errors
----------------------
Wildcat strives to provide informative error messages, so if you provide an invalid setting, then the error message will usually mention the invalid configuration field by name. You can use the :doc:`configuration.py API </api/config/index>` to look up the invalid field and help understand what went wrong. The invalid field will be in the section of the API corresponding to whatever command you were trying to run.

If an error message is vague or you think wildcat has a bug, you can also use the ``-t`` or ``--show-traceback`` option to return the full error traceback. This can help provide more context for what went wrong. For example::

    # Prints a detailed traceback if an error occurs
    wildcat preprocess my-project --show-traceback

----

.. _faq-where:

Where to run wildcat commands
-----------------------------

You can run wildcat commands from any folder on your computer. One common option is to run commands from a wildcat project folder. When in a project folder, you can run a command without any extra arguments. For example, say you have a collection of assessments in an ``assessments`` folder, and you want to preprocess the ``demo-project`` project. Then you could use::

    cd /path/to/assessments/demo-project
    wildcat preprocess

You can also run wildcat outside of a project folder. When this is the case, you will need to provide the path to the project at the end of the command. For example::

    cd /path/to/assessments
    wildcat preprocess demo-project

or alternatively::

    wildcat preprocess /path/to/assessments/demo-project

would also preprocess the demo project.


----

.. _faq-kf-field:

kf is a vector feature file, so kf_field cannot be None
-------------------------------------------------------
This error will occur if you build the KF-factor dataset from a Polygon feature file, but forget to provide the associated :confval:`kf_field` setting. This setting should be a string indicating the data field in the Polygon file that holds the KF-factor data. For example, if you are using KF-factor data from the `STATSGO Shapefile archive <https://www.sciencebase.gov/catalog/item/631405c5d34e36012efa3187>`_, then the :confval:`kf_field` setting should be set to ``KFFACT``::

    # In configuration.py
    kf = r"path/to/my-statsgo-dataset.shp"
    kf_field = "KFFACT"



----

.. _faq-missing-dataset:

Estimating missing datasets
---------------------------

Sometimes, you may be missing one of the datasets needed for an assessment. This is most common for the :confval:`kf`, :confval:`dnbr`, and :confval:`severity` datasets. For example, not all areas have a KF-factor dataset. Analogously, dNBR and burn severity datasets may not be available for active or recently contained fires.

If the burn severity dataset is missing, then wildcat can estimate a burn severity raster from the dNBR. This is the default behavior, so you don't need to do anything extra to enable this estimate. You can also refine the estimate by using the :confval:`severity_thresholds` setting to control the dNBR breaks used to classify different burn severity levels.

Otherwise, you can set wildcat to use a constant value for a missing :confval:`kf`, :confval:`dnbr`, and/or :confval:`severity` dataset. This allows you to run an assessment using a reasonable parameter when a spatially-varying dataset is not available. You can implement this by setting the missing dataset equal to the desired number. For example, in the configuration file::

    # Use a constant KF-factor
    kf = 0.2

    # Use a constant dNBR
    dnbr = 500



----

.. _faq-modify-network:

Modifying the stream network
----------------------------
Sometimes, you may wish to modify the stream network for an assessment. Perhaps the network contains some odd-looking segments, or perhaps you'd like to stop the segments at a particular topographic feature. You can use many settings to modify the stream network, but two of the most common are the :confval:`remove_ids` and :confval:`excluded` settings.

The :confval:`remove_ids` setting allows you to remove specific segments from the final network by listing their IDs. This is useful when you have a limited number of problem segments that you want to remove. This setting is implemented *after* network delineation, so the network will not change aside from the removal of the segments. Note that altering network delineation will also alter the IDs, so it's best to only use :confval:`remove_ids` once you've finalized the other assessment settings.

The :confval:`excluded` setting allows you block the network from undesired areas. This input is a set of Polygon features, and stream segments will never be drawn in the polygons. This option can be useful when you want to prevent the network from intersecting certain topographic features. This setting will alter network delineation, so the shape of the network may change after applying an exclusion mask. Note that an exclusion mask only affects the locations of the stream segments; basins are not affected, so an excluded area may still appear in a basin if the area drains into a segment further downstream.


----

.. _faq-os-errors:

Arcane errors referencing the operating system
----------------------------------------------

This may indicate that another geospatial software tool is interfering with wildcat's backend. Try installing wildcat :ref:`in a clean virtual environment <install-environment>`.


----

.. _faq-dep-errors:

Errors originating from pysheds or another dependency
-----------------------------------------------------

This may indicate that a dependency library has issued a new release that breaks backwards compatibility. Try :ref:`installing wildcat from lock <install-lock>`.


