=============
API reference
=============

.. currentmodule:: laser.measles

This page lists laser-measles's API.

.. contents:: Contents
   :local:
   :depth: 2

Base Components
===============

.. currentmodule:: laser.measles.components

Components (e.g., infection, aging, vital dynamics, etc.) setup and affect the model, its structure and dynamics.
Shared base classes that provide common interfaces and functionality across all model types.
Model-specific implementations inherit from these base classes.

Component Architecture
----------------------

The laser-measles framework follows a hierarchical component architecture:

1. **Base Components** (``laser.measles.components``) define abstract interfaces and common functionality
2. **Model-Specific Implementations** (``laser.measles.{model}.components``) inherit from base classes and implement model-specific behavior
3. **Parameter Classes** use Pydantic for validation and are paired with their respective component classes
4. **Numpy/Numba Pattern** - Components can provide both numpy and numba implementations for performance optimization

**Inheritance Pattern Example:**

.. code-block:: python

   # Base class in laser.measles.components
   class BaseInitializeEquilibriumStatesProcess(BasePhase):
       # Common interface and default behavior
       pass

   # Model-specific implementation in laser.measles.abm.components
   class InitializeEquilibriumStatesProcess(BaseInitializeEquilibriumStatesProcess):
       # ABM-specific implementation
       pass

Process Base Classes
--------------------

Abstract base classes for components that modify population states and drive model dynamics:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   BaseInitializeEquilibriumStatesProcess
   BaseVitalDynamicsProcess
   BaseConstantPopProcess
   BaseInfectionProcess

Note that each component has a corresponding parameter class that is used to configure the component.
For example, the ``BaseInfectionProcess`` has a corresponding ``BaseInfectionParams`` class.
The parameter class is used to configure the component and defaults can be overridden using the
``create_component`` function.

Tracker Base Classes
--------------------

Abstract base classes for components that monitor and record model state for analysis:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   BaseStateTracker
   BaseCaseSurveillanceTracker
   BasePopulationTracker
   BaseFadeOutTracker

Utilities
---------

Component creation and management utilities:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   component
   create_component

----

ABM Model
=========

.. currentmodule:: laser.measles.abm

Core Model
----------

Agent based model:

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :nosignatures:

   model
   params
   base
   utils

Process Components
------------------

Components that modify population states and drive model dynamics.
Most inherit from base classes in ``laser.measles.components``:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.InitializeEquilibriumStatesProcess
   components.VitalDynamicsProcess
   components.ConstantPopProcess
   components.InfectionProcess
   components.InfectionSeedingProcess
   components.ImportationPressureProcess
   components.SIACalendarProcess

ABM-Specific Process Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Components unique to the ABM model:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.NoBirthsProcess
   components.TransmissionProcess
   components.DiseaseProcess

Tracker Components
------------------

Components that monitor and record model state for analysis.
All inherit from base classes in ``laser.measles.components``:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.StateTracker
   components.CaseSurveillanceTracker
   components.PopulationTracker
   components.FadeOutTracker

----

Compartmental Model
===================

.. currentmodule:: laser.measles.compartmental

Core Model
----------

Compartmental model with daily timesteps:

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :nosignatures:

   model
   params
   base

Process Components
------------------

Components that modify population states and drive model dynamics.
All inherit from base classes in ``laser.measles.components``:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.InitializeEquilibriumStatesProcess
   components.InfectionSeedingProcess
   components.InfectionProcess
   components.ImportationPressureProcess
   components.VitalDynamicsProcess
   components.ConstantPopProcess
   components.SIACalendarProcess

Tracker Components
------------------

Components that monitor and record model state for analysis.
All inherit from base classes in ``laser.measles.components``:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.StateTracker
   components.CaseSurveillanceTracker
   components.PopulationTracker
   components.FadeOutTracker

----

Biweekly Model
==============

.. currentmodule:: laser.measles.biweekly

Core Model
----------

Compartmental model with 2-week timesteps

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :nosignatures:

   model
   params
   base

Process Components
------------------

Components that modify population states and drive model dynamics.
All inherit from base classes in ``laser.measles.components``:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.InitializeEquilibriumStatesProcess
   components.InfectionSeedingProcess
   components.InfectionProcess
   components.VitalDynamicsProcess
   components.ImportationPressureProcess
   components.ConstantPopProcess
   components.SIACalendarProcess

Tracker Components
------------------

Components that monitor and record model state for analysis.
Most inherit from base classes in ``laser.measles.components``:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.StateTracker
   components.CaseSurveillanceTracker
   components.PopulationTracker
   components.FadeOutTracker

Biweekly-Specific Tracker Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Components unique to the Biweekly model:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   components.FadeOutTracker

Utilities
---------

Core Framework
==============

.. currentmodule:: laser.measles

Base Classes
------------

Foundation classes that provide the component architecture:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   base.BaseComponent
   base.BaseLaserModel

Utilities
---------

Core utilities and computation functions:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   create_component

----

Demographics Package
====================

.. currentmodule:: laser.measles.demographics

Geographic data handling for spatial epidemiological modeling:

Shapefile Utilities
-------------------

Functions for processing and visualizing geographic shapefiles:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   get_shapefile_dataframe
   plot_shapefile_dataframe
   GADMShapefile

Raster Processing
-----------------

Tools for handling raster data and patch generation:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   RasterPatchParams
   RasterPatchGenerator

----

Mixing Models
=============

.. currentmodule:: laser.measles.mixing

Spatial mixing models for population movement and disease transmission between geographic patches
(see `laser-core <https://laser.idmod.org/laser-generic/>`_ for more details):

Base Classes
------------

Abstract base class that defines the interface for all mixing models:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   base.BaseMixing

Mixing Implementations
----------------------

Specific mixing model implementations for different types of population movement:

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   gravity.GravityMixing
   stouffer.StoufferMixing
   radiation.RadiationMixing
   competing_destinations.CompetingDestinationsMixing

----

Scenarios
=========

.. currentmodule:: laser.measles.scenarios

Pre-built synthetic scenario factories for quickly constructing common spatial configurations.
Each function returns a :class:`polars.DataFrame` suitable for passing directly to a model.

**Import paths:**

.. code-block:: python

   # Functions are re-exported at the scenarios package level
   from laser.measles.scenarios import single_patch_scenario, two_patch_scenario
   from laser.measles.scenarios import two_cluster_scenario, satellites_scenario

   # Access via the synthetic submodule directly
   from laser.measles.scenarios import synthetic
   scenario = synthetic.single_patch_scenario(population=50_000)

   # synthetic is also re-exported at the top level
   from laser.measles import synthetic

synthetic module
----------------

The ``synthetic`` module contains all scenario-builder functions and a detailed reference
for the scenario DataFrame schema. Its documentation is reproduced below:

.. autosummary::
   :toctree: _autosummary
   :template: custom-module-template.rst
   :nosignatures:

   synthetic

Scenario Functions
------------------

.. autosummary::
   :toctree: _autosummary
   :template: custom-function-template.rst
   :nosignatures:

   single_patch_scenario
   two_patch_scenario
   two_cluster_scenario
   satellites_scenario
