============
Installation
============

At the command line:

.. code-block:: bash

    pip install laser-measles


You can also install the in-development version with:

.. code-block:: bash

    pip install git+https://github.com/InstituteforDiseaseModeling/laser-measles.git@main

Optional Dependencies
=====================

The package supports several optional dependency groups that can be installed for additional functionality:

.. code-block:: bash

    # Development dependencies (testing, linting)
    pip install laser-measles[dev]

    # Documentation dependencies (Sphinx, autodoc)
    pip install laser-measles[docs]

    # Example dependencies (Jupyter, notebooks, plotting)
    pip install laser-measles[examples]

    # All optional dependencies
    pip install laser-measles[full]

Dependency Groups
-----------------

**dev**: Development tools for testing and code quality
    - pytest: Testing framework
    - pytest-order: Ordered test execution

**docs**: Documentation building tools
    - sphinx-autodoc-typehints: Type hint documentation
    - sphinxcontrib-napoleon: Google/NumPy docstring support

**examples**: Tools for running examples and tutorials
    - jupytext: Jupyter notebook text conversion
    - notebook: Jupyter notebook interface
    - seaborn: Statistical data visualization
    - ipykernel: Jupyter kernel support

**full**: All optional dependencies combined
    - Includes all packages from dev, docs, and examples groups

Development
===========

You can use this github codespace for fast development:

.. raw:: html

   <a href='https://codespaces.new/InstituteforDiseaseModeling/laser-measles'><img src='https://github.com/codespaces/badge.svg' alt='Open in GitHub Codespaces' style='max-width: 100%;'></a>


To run all the tests run:

.. code-block:: bash

    tox

And to build the documentation run:

.. code-block:: bash

    tox -e docs

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox

You can check that the bump versioning works by running:

.. code-block:: bash

    uvx bump-my-version bump minor --dry-run -vv
