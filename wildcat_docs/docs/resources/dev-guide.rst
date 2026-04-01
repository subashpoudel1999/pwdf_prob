Developer Guide
===============

Git Workflow
------------
You should use a `forking workflow <https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html>`_ to develop wildcat. In brief, you should make a fork of the official repository, and then create merge requests from the fork to the main branch of the official repository. These requests will then be reviewed before merging.



.. _dev-install:

Installation
------------

.. admonition:: Prerequisites

    Wildcat requires `Python 3.11+ <https://www.python.org/downloads/>`_, and these instructions also require `git <https://git-scm.com/downloads>`_.

We recommend using `poetry <https://python-poetry.org/>`_ to install wildcat. This will provide various :ref:`command line scripts <dev-scripts>` useful for developing the project.

You can install poetry using::

    pip install poetry

and read also the `poetry documentation <https://python-poetry.org/docs/#installation>`_ for alternative installation instructions.

Next, clone your fork of the project and navigate to the cloned repository. Then, use::

    poetry install --with dev

which will install wildcat and various development libraries.


Formatting
----------
This project uses `isort <https://pycqa.github.io/isort/>`_ and `black <https://black.readthedocs.io/en/stable/>`_ to format the code. You can apply these formatters using::

    poe format

This should format the code within the ``wildcat`` and ``tests`` directories. We also note that many IDEs include tools to automatically apply these formats. 

You can also use::

    poe lint

to verify that all code is formatted correctly. The Gitlab pipeline requires that this check passes before code can be merged.


Testing
-------
This project uses the `pytest <https://docs.pytest.org/>`_ framework to implement tests. Before adding new code, the Gitlab pipeline requires:

1. All tests passing, and
2. 100% test coverage

So as a rule, all new code should include accompanying tests. The tests should follow a parallel structure to the wildcat package, and the tests for a given module should be named ``test_<module>.py`` or ``test_<folder>_<module>.py`` in the case of duplicate module names.

Within a test module, multiple tests for the same function should be grouped into a class. Test class names should use capitalized camel-case. Underscores are discouraged, except when needed to distinguish between public and private routines with the same name. Individual tests should be named using standard Python snakecase (lowercase separated by underscores).

Note that you can check the status of the tests using::

    poe tests


Documentation
-------------

The documentation is built using `sphinx <https://www.sphinx-doc.org/en/master/index.html>`_ with the `furo theme <https://pradyunsg.me/furo/>`_. The content is written in `reStructuredText Markup (reST) <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_. You can find a nice `introduction to reST <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_ in the sphinx documentation, and the full documentation is here: `reST Specification <https://docutils.sourceforge.io/rst.html>`_.

The docs use the `sphinx_design <https://sphinx-design.readthedocs.io/en/rtd-theme/>`_ extension to enable dropdowns and tabbed panels within the content. The final website is deployed using `Gitlab Pages <https://docs.gitlab.com/ee/user/project/pages/>`_ via a manual job in the `Gitlab pipeline <https://docs.gitlab.com/ee/ci/pipelines/>`_. You must trigger this job manually to deploy new docs.

You can build the docs locally using::

    poe docs

This will create the documentation HTML pages within the ``public`` folder of the repository. You can open these docs in a browser using::

    poe open-docs


Gitlab Pipeline
---------------

The Gitlab pipeline requires that:

* Code dependencies pass a security check,
* All code is formatted correctly, and
* The tests pass with 100% coverage

You can mimic the pipeline using::
    
    poe pipeline


.. _dev-scripts:

Scripts
-------
Development scripts are available via the `poethepoet <https://poethepoet.natn.io/index.html>`_ interface, and are defined in ``pyproject.toml``.

The following table provides a complete list of available scripts:

.. list-table::
    :header-rows: 1

    * - Script Name
      - Description
    * - ``safety check``
      - Checks dependencies for security vulnerabilities
    * - ``format``
      - Applies formatters to ``wildcat`` and ``tests``
    * - ``lint``
      - Checks that ``wildcat`` and ``tests`` are formatted correctly
    * - ``tests``
      - Runs tests and requires 100% coverage
    * - ``docs``
      - Rebuilds the docs locally
    * - ``open-docs``
      - Opens locally built docs in a web browser
    * - ``pipeline``
      - Mimics the Gitlab pipeline by running the ``safety``, ``lint``, and ``tests`` scripts
