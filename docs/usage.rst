=====
Usage
=====

Overview
--------

laser-measles is a spatial epidemiological modeling toolkit for measles transmission dynamics, built on the `LASER framework <https://github.com/InstituteforDiseaseModeling/laser>`_.
It provides a flexible, component-based architecture for disease simulation with support for multiple geographic scales and demographic configurations.

Key features include:

* **Spatial modeling**: Support for geographic regions with administrative boundaries and population distributions
* **Multiple model types**: Biweekly and Generic models for different use cases
* **Component-based architecture**: Interchangeable disease dynamics components
* **High-performance computing**: Optimized data structures and Numba JIT compilation
* **Type-safe parameters**: Pydantic-based configuration management

Installation and Setup
----------------------

Install laser-measles using pip (requires Python 3.10+):

.. code-block:: bash

    pip install laser-measles

For development installation with all dependencies (recommended: use `uv` for faster package management):

.. code-block:: bash

    # Using uv (recommended)
    uv pip install -e ".[dev]"
    # or for full installation including examples
    uv pip install -e ".[full]"

    # Alternative: using pip
    pip install -e ".[dev]"

**Major Dependencies:**

* ``laser-core>=1.0.0``: Core LASER framework
* ``pydantic>=2.11.5``: Parameter validation and serialization
* ``polars>=1.30.0``: High-performance data manipulation
* ``alive-progress>=3.2.0``: Progress bars and status indicators
* ``rastertoolkit>=0.3.11``: Raster data processing utilities
* ``patito>=0.8.3``: Polars DataFrame validation

----------


Model Types
-----------

laser-measles provides three complementary modeling approaches, each optimized for different use cases:

1. **ABM (Agent-Based Model)**: Individual-level simulation with stochastic agents
2. **Biweekly Compartmental Model**: Population-level SIR dynamics with 2-week timesteps
3. **Compartmental Model**: Population-level SEIR dynamics with daily timesteps

Each model type offers different trade-offs between computational efficiency, temporal resolution, and modeling detail.

----------

ABM (Agent-Based Model)
~~~~~~~~~~~~~~~~~~~~~~~

The ABM model provides individual-level simulation with stochastic agents, allowing for detailed tracking of disease dynamics at the person level.

**Key Characteristics:**

* **Individual agents**: Each person is represented as a discrete agent with properties like age, location, and disease state
* **Daily timesteps**: Fine-grained temporal resolution for precise modeling
* **Stochastic processes**: Individual-level probabilistic events for realistic variability
* **Spatial heterogeneity**: Agents can move between patches and have location-specific interactions
* **Flexible demographics**: Full support for births, deaths, aging, and migration

**Example usage:**

.. code-block:: python

    from laser.measles.abm import ABMModel, ABMParams

    # Configure model parameters
    params = ABMParams(
        num_ticks=7300,  # 20 years of daily timesteps
        seed=12345
    )

    # Initialize and run model
    model = ABMModel(scenario_data, params)
    model.run()

----------

Biweekly Model
~~~~~~~~~~~~~~

The Biweekly Model is a compartmental model optimized for fast simulation and parameter exploration with 2-week timesteps.

**Key Characteristics:**

* **Compartmental approach**: SIR (Susceptible-Infected-Recovered) structure.
  The exposed (E) compartment is omitted because the 14-day timestep is
  comparable to measles' typical incubation period (~10-14 days), making
  the distinction between exposed and infectious states negligible at this
  temporal resolution. For detailed SEIR dynamics with explicit incubation
  periods, use the Compartmental Model with daily timesteps.
* **Time resolution**: 14-day fixed time steps (26 ticks per year)
* **High performance**: Uses Polars DataFrames for efficient data manipulation
* **Stochastic sampling**: Binomial sampling for realistic variability
* **Policy analysis**: Recommended for scenario building and intervention assessment

**Example usage:**

.. code-block:: python

    from laser.measles.biweekly import BiweeklyModel, BiweeklyParams

    # Configure model parameters
    params = BiweeklyParams(
        num_ticks=520,  # 20 years of bi-weekly time steps
        seed=12345
    )

    # Initialize and run model
    model = BiweeklyModel(scenario_data, params)
    model.run()

----------

Compartmental Model
~~~~~~~~~~~~~~~~~~~

The Compartmental Model provides population-level SEIR dynamics with daily timesteps, optimized for parameter estimation and detailed outbreak modeling.

**Key Characteristics:**

* **Daily timesteps**: Fine-grained temporal resolution (365 ticks per year)
* **SEIR dynamics**: Detailed compartmental structure with exposed compartment
* **Parameter estimation**: Recommended for fitting to surveillance data
* **Outbreak modeling**: Ideal for detailed temporal analysis of disease dynamics
* **Deterministic core**: Efficient ODE-based dynamics with optional stochastic elements

**Example usage:**

.. code-block:: python

    from laser.measles.compartmental import CompartmentalModel, CompartmentalParams

    # Configure model parameters
    params = CompartmentalParams(
        num_ticks=7300,  # 20 years of daily time steps
        seed=12345
    )

    # Initialize and run model
    model = CompartmentalModel(scenario_data, params)
    model.run()

----------

Demographics Package
--------------------

The demographics package provides comprehensive geographic data handling capabilities for spatial epidemiological modeling.

**Core Features:**

* **GADM Integration**: ``GADMShapefile`` class for administrative boundary management
* **Raster Processing**: ``RasterPatchGenerator`` for population distribution handling
* **Shapefile Utilities**: Functions for geographic data visualization and analysis
* **Flexible Geographic Scales**: Support from national to sub-district administrative levels

**Key Classes:**

* ``GADMShapefile``: Manages administrative boundaries from GADM database
* ``RasterPatchParams``: Configuration for raster-based population patches
* ``RasterPatchGenerator``: Creates population patches from raster data
* ``get_shapefile_dataframe``: Utility for shapefile data manipulation
* ``plot_shapefile_dataframe``: Visualization functions for geographic data

**Example usage:**

.. code-block:: python

    from laser.measles.demographics import GADMShapefile, RasterPatchGenerator, RasterPatchParams

    # Load administrative boundaries
    shapefile = GADMShapefile("ETH", admin_level=1)  # Ethiopia, admin level 1

    # Generate population patches
    params = RasterPatchParams(
        shapefile_path="path/to/shapefile.shp",
        raster_path="path/to/population.tif",
        patch_size=1000  # 1km patches
    )
    generator = RasterPatchGenerator(params)
    patches = generator.generate_patches()

Technical Features
------------------

Pydantic Integration
~~~~~~~~~~~~~~~~~~~~

laser-measles uses Pydantic for type-safe parameter management, providing automatic validation and documentation.

**Parameter Classes:**

* ``ABMParams``: Configuration for agent-based models with individual-level parameters
* ``BiweeklyParams``: Configuration for biweekly models with epidemiological parameters
* ``CompartmentalParams``: Configuration for compartmental models with daily dynamics

**Component Classes:**
Components come in "process" and "tracker" categories and each component has a corresponding parameter class.
Each model (ABM, Biweekly, or Compartmental) has its own set of components. See the :doc:`API documentation <api/index>` for more details.

**Benefits:**

* **Type safety**: Automatic validation of parameter types and ranges
* **Documentation**: Built-in parameter descriptions and constraints
* **Serialization**: JSON export/import of model configurations
* **IDE support**: Enhanced autocomplete and error detection

**Example:**

.. code-block:: python

    from laser.measles.biweekly import BiweeklyParams

    params = BiweeklyParams(
        num_ticks=520,  # Validated as positive integer
        seed=12345      # Random seed for reproducibility
    )

    # Export configuration
    config_json = params.model_dump_json()

High-Performance Computing
~~~~~~~~~~~~~~~~~~~~~~~~~~

laser-measles is optimized for performance through several technical approaches:

**LaserFrame Architecture:**
    High-performance array-based structure for agent populations, built on the LASER framework

**numba JIT Compilation:**
    Performance-critical operations implemented in numba for maximum speed

**Polars DataFrames:**
    Efficient data manipulation using Polars for biweekly model operations with Arrow backend

**Component Modularity:**
    Modular architecture allows for selective component usage and optimization

**Progress Tracking:**
    Integrated progress bars using alive-progress for long-running simulations

**Python 3.10+ Support:**
    Optimized for modern Python features and performance improvements

Component System
~~~~~~~~~~~~~~~~

The component system provides a uniform interface for disease dynamics with interchangeable modules built on a hierarchical base class architecture.

**Base Architecture:**

* **BaseLaserModel**: Abstract base class for all model types with common functionality
* **BaseComponent**: Base class for all components with standardized interface
* **BasePhase**: Components that execute every tick (inherit from BaseComponent)
* **Inheritance-based design**: Base components define shared functionality and abstract interfaces

**Base Component Classes:**

* ``base_transmission.py``: Base transmission/infection logic
* ``base_vital_dynamics.py``: Base births/deaths logic
* ``base_importation.py``: Base importation pressure logic
* ``base_tracker.py``: Base tracking/metrics logic
* ``base_infection.py``: Base infection state transitions
* ``base_tracker_state.py``: Base state tracking functionality

**Component Naming Convention:**

* **Process components**: ``process_*.py`` - Modify model state (births, deaths, infection, transmission)
* **Tracker components**: ``tracker_*.py`` - Record metrics and state over time

**Component Creation Patterns:**

.. code-block:: python

    # Component with parameters using Pydantic
    from laser.measles.components.base_infection import BaseInfectionProcess

    class MyInfectionProcess(BaseInfectionProcess):
        def __init__(self, model, verbose=False, **params):
            super().__init__(model, verbose)
            # Initialize with validated parameters

    # Add to model
    model.components = [MyInfectionProcess]

----------


Gotchas & FAQ
-------------

This section documents common pitfalls when writing ``laser-measles`` models.
If you encounter unexpected ``ImportError``, tracker shape mismatches, or
component configuration errors, check the items below first.

These issues occur frequently when users are learning the component system
or adapting code between the ABM, biweekly, and compartmental models.

1. Where does ``create_component`` come from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``create_component`` is always imported from
``laser.measles.components``, regardless of which model type you are using.

It lives in the shared components package because it works with **all model
types** (ABM, biweekly, and compartmental).

.. code-block:: python

   # CORRECT
   from laser.measles.components import create_component

   # WRONG — ImportError
   from laser.measles.abm import create_component
   from laser.measles.biweekly import create_component
   from laser.measles.compartmental import create_component


2. How do I access component classes and their parameter classes?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each model package exports a ``components`` module. All component classes
and their corresponding parameter (Pydantic) classes should be accessed
through that module using **dot access**, rather than through deep imports.

.. code-block:: python

   # CORRECT — import the components namespace
   from laser.measles.abm import ABMModel, ABMParams, components
   from laser.measles.components import create_component

   model.components = [
       components.NoBirthsProcess,

       create_component(
           components.InfectionSeedingProcess,
           params=components.InfectionSeedingParams(target_patches=["patch_0"])
       ),

       components.InfectionProcess,

       create_component(
           components.StateTracker,
           params=components.StateTrackerParams(aggregation_level=0)
       ),
   ]

Deep imports are discouraged because parameter classes may not exist in the
same module or may move between versions.

.. code-block:: python

   # DISCOURAGED — fragile deep imports
   from laser.measles.abm.components import InfectionSeedingProcess
   from laser.measles.abm.params import InfectionSeedingParams


The same pattern applies to the biweekly and compartmental models:

.. code-block:: python

   from laser.measles.biweekly import BiweeklyModel, BiweeklyParams, components
   from laser.measles.compartmental import CompartmentalModel, CompartmentalParams, components


3. ``model.components`` is assigned *after* construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The model constructors only accept ``scenario`` and ``params``.

Components must be attached by assigning to ``model.components`` **after**
the model object is created.

.. code-block:: python

   # CORRECT
   model = BiweeklyModel(scenario=scenario, params=params)

   model.components = [
       components.InitializeEquilibriumStatesProcess,
       components.ImportationPressureProcess,
       components.InfectionProcess,
       components.VitalDynamicsProcess,
       components.StateTracker,
   ]

The model internally instantiates the component classes when the list is
assigned.

.. code-block:: python

   # WRONG — TypeError: unexpected keyword argument "components"
   model = BiweeklyModel(
       scenario=scenario,
       params=params,
       components=[...]
   )

This applies to all three model types:

- ``ABMModel``
- ``BiweeklyModel``
- ``CompartmentalModel``


4. There is no ``lm`` object in ``laser.measles``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The top-level ``laser.measles`` package does **not** export a convenience
object such as ``lm``.

Some tutorials or AI-generated examples use this alias, but it is not part
of the package API.

.. code-block:: python

   # WRONG — ImportError
   from laser.measles import lm

   # CORRECT
   from laser.measles.abm import ABMModel, ABMParams, components


5. ``StateTracker`` output shape depends on ``aggregation_level``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``StateTracker`` component stores time-series data differently depending
on how it is configured.

Default behavior (global aggregation)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default configuration aggregates across all patches.

Arrays are **1-D** with shape::

   (num_ticks,)

.. code-block:: python

   tracker = model.get_instance("StateTracker")[0]

   peak_I = int(tracker.I.max())


Patch-level tracking
^^^^^^^^^^^^^^^^^^^^

If ``aggregation_level=0`` is used, the tracker stores values **per patch**.

Arrays become **2-D** with shape::

   (num_ticks, n_patches)

.. code-block:: python

   tracker = model.get_instance("StateTracker")[0]

   peak_patch_0 = int(tracker.I[:, 0].max())


Retrieve the tracker instance after ``model.run()``:

.. code-block:: python

   tracker = model.get_instance("StateTracker")[0]


6. Cast NumPy scalars before building a Polars DataFrame
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tracker arrays are NumPy arrays, so operations like ``.max()`` return
NumPy scalar types (``np.int64``, ``np.float64``).

Polars expects **Python primitive types** when constructing row-oriented
DataFrames. Passing NumPy scalars can trigger ``TypeError`` or
``DataOrientationWarning``.

.. code-block:: python

   # WRONG
   rows.append([patch_id, tracker.I[:, p].max()])

   # CORRECT
   rows.append([patch_id, int(tracker.I[:, p].max())])

An alternative is to use ``.item()``:

.. code-block:: python

   rows.append([patch_id, tracker.I[:, p].max().item()])


7. Components are classes, not instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Components should be passed as **classes**, not instantiated objects.

The model constructs the component instances internally.

.. code-block:: python

   # CORRECT
   model.components = [
       components.InfectionProcess
   ]

   # WRONG
   model.components = [
       components.InfectionProcess()
   ]


If parameters are needed, use ``create_component``:

.. code-block:: python

   model.components = [
       create_component(
           components.InfectionProcess,
           params=components.InfectionParams(beta=0.8)
       )
   ]


8. Scenario DataFrame must contain required columns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All models expect the scenario DataFrame to contain at least the following
columns:

- ``id`` — patch identifier
- ``lat`` — latitude
- ``lon`` — longitude
- ``pop`` — population size
- ``mcv1`` — routine vaccination coverage

Missing columns will trigger a validation error when constructing the model.

.. code-block:: python

   scenario = pl.DataFrame({
       "id": ["patch_0"],
       "lat": [0.0],
       "lon": [0.0],
       "pop": [50000],
       "mcv1": [0.8],
   })
