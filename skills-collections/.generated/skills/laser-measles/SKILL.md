---
name: laser-measles
description: Use when working with laser-measles or the LASER framework for spatial measles modeling — including writing models (ABM, biweekly, or compartmental), debugging component or import errors, building scenarios, configuring spatial mixing, or analyzing simulation output. Trigger any time the user mentions laser-measles, LASER framework, measles modeling, spatial epidemiology with LASER, or uses imports like `laser.measles`.
license: MIT
metadata:
  author: "IDM"
  version: "1.0"
---

# Laser Measles

## Overview

laser-measles helps you build and analyze spatial models of measles implemented with the [LASER framework](https://github.com/InstituteforDiseaseModeling/laser).

## Rules (18)

Read individual rule files for detailed explanations and code examples on particular tasks or topics:

| Title | Topic | Description |
| --- | --- | --- |
| [Authors](./rules/authors.md) | authors |  |
| [Welcome to laser-measles](./rules/index.md) | index | laser-measles helps you build and analyze spatial models of measles implemented with the [LASER framework](https://github.com/InstituteforDiseaseModeling/laser). |
| [Installation](./rules/install.md) | install | At the command line: |
| [Tutorials](./rules/tutorials.md) | tutorials | These tutorials show how you can use laser-measles. |
| [Usage](./rules/usage.md) | usage | laser-measles is a spatial epidemiological modeling toolkit for measles transmission dynamics, built on the [LASER framework](https://github.com/InstituteforDiseaseModeling/laser). It provides a flexible, component-based architecture for disease simulation with support for multiple geographic scales and demographic configurations. |
| [What's new](./rules/whatsnew.md) | whatsnew |  |
| [ABM Model Introduction](./rules/tut_abm_intro.md) | tutorials | This tutorial serves as an introduction to the ABM model in laser-measles |
| [Vital Dynamics](./rules/tut_abm_vital_dynamics.md) | tutorials | This tutorial serves as an introduction to the different options for incorporating vital dynamics (births, deaths, and age structure) into the ABM model. |
| [Creating And Running Models](./rules/tut_basic_model.md) | tutorials | This tutorial demonstrates how to initialize and run a model using the laser-measles framework. |
| [Creating Custom Components](./rules/tut_creating_component.md) | tutorials | This tutorial demonstrates how to create custom components for the compartmental model. We'll build a PIRI component that periodically strengthens vaccination coverage. |
| [Model Structure](./rules/tut_model_structure.md) | tutorials | This tutorial goes over how a laser-measles models run. It compares the structure of compartmental and agent-based models, focusing on their LaserFrame data structures and how they operate. |
| [Parameter Validation](./rules/tut_pydantic_component_parameters.md) | tutorials | This tutorial demonstrates the strengths of using Pydantic's `BaseModel` to define simulation parameters. Pydantic provides type validation, documentation, and error handling that makes component configuration more robust and user-friendly. |
| [Quick Start: Hello World](./rules/tut_quickstart_hello_world.md) | tutorials | **If you're new to laser-measles—or an AI assistant looking for a quick start example—start here.** |
| [Random Numbers and Reproducibility](./rules/tut_random_numbers.md) | tutorials | This tutorial covers how random numbers are handled in laser-measles models to ensure reproducibility. Understanding this is crucial for debugging, testing, and scientific reproducibility. |
| [Creating Model Scenarios](./rules/tut_scenarios.md) | tutorials | The initial conditions of the simulation are dictated by demographics (e.g., population, age distribution, etc.). The laser-measles package provides a number of tools to help you generate demographics for your simulation. These can be used for the *abm*, *compartmental*, and *biweekly* models. |
| [Spatial Mixing Models Tutorial](./rules/tut_spatial_mixing.md) | tutorials | This tutorial demonstrates how to choose and configure different spatial mixing models in the laser-measles framework and shows how they affect disease transmission patterns. |
| [State Arrays](./rules/tut_state_arrays.md) | tutorials | This tutorial covers StateArray, a key data structure in laser-measles that provides convenient access to epidemiological state compartments. |
| [Vaccination Modeling Approaches](./rules/tut_vaccination.md) | tutorials | This tutorial demonstrates three approaches for modeling vaccination in laser-measles and explains when to use each one. |

## Other Resources

For additional information, see:
- Full Documentation: https://laser-measles.readthedocs.io/en/latest/
- GitHub Repo (Open Source): https://github.com/InstituteforDiseaseModeling/laser-measles