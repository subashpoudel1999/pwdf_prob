Install Wildcat
===============

.. note:: 

    These instructions are for wildcat users. If you plan to develop wildcat, you should do a :ref:`developer installation <dev-install>` instead.


Prerequisites
-------------

Python
++++++
Wildcat requires `Python 3.11+ <https://www.python.org/downloads/>`_.


.. _install-environment:

Virtual Environment
+++++++++++++++++++
We **strongly recommend** installing wildcat in a clean virtual environment. This is because other geospatial software can sometimes interfere with wildcat's backend. There are many tools for managing virtual environments including `miniforge`_, `conda`_, `venv`_, and `virtualenv`_. If you are not familiar with virtual environments, then `miniforge`_ may be a good starting point.

For example, after installing miniforge, you can create a new python environment using::

    conda create -n wildcat python --yes

and then activate the environment with::

    conda activate wildcat

.. _miniforge: https://github.com/conda-forge/miniforge
.. _conda: https://anaconda.org/anaconda/conda
.. _venv: https://docs.python.org/3/library/venv.html
.. _virtualenv: https://virtualenv.pypa.io/en/latest


Quick Install
-------------

You can install the latest release using::

    pip install wildcat -i https://code.usgs.gov/api/v4/groups/859/-/packages/pypi/simple

The URL in this command instructs `pip <https://pip.pypa.io/en/stable/>`_ to install wildcat from the official USGS package registry. This ensures that you are installing an official USGS product, and not a similarly named package from a third party. The ``859`` in the URL is the code for packages released by the `Landslide Hazards Program <https://www.usgs.gov/programs/landslide-hazards>`_.


.. _install-lock:

Building from Lock
------------------
In rare cases, wildcat may break due to changes in a dependency library. For example, when a dependency releases a new version that breaks backwards compatibility. If this is the case, you can use `poetry <https://python-poetry.org/>`_ to install wildcat from known working dependencies. This method requires you `install poetry <https://python-poetry.org/docs/#installation>`_ in addition to the usual prerequisites.

To use this method, you should first clone the wildcat repository at the desired release. For example, if you have `git <https://git-scm.com/>`_ installed, then you can clone the 1.1.0 release to the current directory using::

    git clone https://code.usgs.gov/ghsc/lhp/wildcat.git --branch 1.1.0

Next, use poetry to install wildcat from the ``poetry.lock`` file::

    poetry install

The ``poetry.lock`` file records the dependencies used to test wildcat, so represents a collection of known-working dependencies.

