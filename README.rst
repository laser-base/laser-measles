==============================
Welcome to laser-measles
==============================

.. start-badges

.. image:: https://img.shields.io/pypi/v/laser-measles.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/laser-measles/

.. image:: https://img.shields.io/pypi/l/laser-measles.svg
    :alt: MIT License
    :target: https://github.com/InstituteforDiseaseModeling/laser-measles/blob/main/LICENSE

.. image:: https://readthedocs.org/projects/laser-measles/badge/?style=flat
    :alt: Documentation Status
    :target: https://laser-measles.readthedocs.io/en/latest/

.. image:: https://codecov.io/gh/InstituteforDiseaseModeling/laser-measles/branch/main/graphs/badge.svg?branch=main
    :alt: Coverage Status
    :target: https://app.codecov.io/github/InstituteforDiseaseModeling/laser-measles


.. end-badges

laser-measles helps you build and analyze spatial models of measles implemented with the `LASER framework <https://github.com/InstituteforDiseaseModeling/laser>`_.

.. code-block:: bash

    pip install laser-measles


Getting Started
---------------

**Recommended stable release: version 0.9**

New users should install the v0.9 release, which is the current stable version:

.. code-block:: bash

    pip install "laser-measles==0.9"

Version 0.9 is the recommended starting point for all new projects. Development continues on the ``main`` branch, but v0.9 is the version that has been validated and is supported for most use cases.

Our recommended first example is here: `Quick Start Tutorial <https://laser-measles.readthedocs.io/en/latest/tutorials/tut_quickstart_hello_world.html>`_

AI-Powered On-Ramp: JENNER-MEASLES
==================================

The fastest way to get started with laser-measles is through `JENNER-MEASLES <https://chatgpt.com/g/g-678ae681f5b48191b3e91619e649e598-jenner-measles>`_, a chat-based AI assistant purpose-built for this framework.

JENNER-MEASLES can help you:

- Understand the modeling framework and architecture
- Walk through tutorials and examples interactively
- Debug your model configurations and code
- Explore epidemiological scenarios and parameter choices

.. note::

    JENNER-MEASLES is currently pinned to **version 0.9** of laser-measles. If you are using a newer version, some details may differ.

Access requires a ChatGPT account and organization access. If you have access, this is the recommended on-ramp before diving into the documentation or source code.


MCP Server for Claude Code Users
================================

If you use Claude Code (or any MCP-compatible AI assistant), you can connect it directly to laser-measles and laser-core documentation and source via a local MCP server.

See the `laser-mcp README <https://github.com/InstituteforDiseaseModeling/laser-mcp/blob/main/README.md>`_ for setup instructions (requires organization access).

This gives Claude Code (and similar tools) deep, up-to-date context about laser-measles and laser-core — making it an excellent alternative to JENNER-MEASLES for developers who prefer working in their local environment with their own AI tooling.


What to Expect: Performance and Compute
-----------------------------------------

All tutorials and examples included in this repository are designed to run in **under one minute on a standard laptop or desktop computer**. No special compute resources, cloud instances, or GPU hardware are required to get started.

Special compute becomes relevant only when you move to:

- **Calibration workflows**: Fitting model parameters to data using optimization or MCMC methods
- **Large-scale parameter sweeps**: Exploring wide parameter spaces across many simulation runs

For day-to-day exploration, scenario building, and learning the framework, your local machine is all you need.


Documentation
-------------

Full documentation is available at `laser-measles.readthedocs.io <https://laser-measles.readthedocs.io/en/latest/>`_.

The documentation includes:

- Getting started guides and installation instructions
- API reference for all model types and components
- Tutorials covering the ABM, biweekly compartmental, and daily compartmental model types
- Examples demonstrating spatial transmission, importation, and vaccination scenarios


Model Types
-----------

laser-measles provides three modeling approaches:

- **ABM (Agent-Based Model)**: Individual-level simulation with stochastic agents. Best for detailed heterogeneity and contact structure.
- **Biweekly Compartmental Model**: Population-level SEIR dynamics with 2-week timesteps. Recommended for scenario building and policy analysis.
- **Compartmental Model**: Population-level SEIR dynamics with daily timesteps. Recommended for parameter estimation and outbreak modeling.


Contributing
------------

Contributions are welcome. Please see the documentation for development guidelines, including how to write tests, follow code style conventions, and submit pull requests.

Bug reports and feature requests can be filed on the `GitHub issue tracker <https://github.com/InstituteforDiseaseModeling/laser-measles/issues>`_.
