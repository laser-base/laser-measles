=====
Usage
=====

Overview
--------

laser-measles is a spatial epidemiological modeling toolkit for measles transmission dynamics, built on the `LASER framework <https://github.com/InstituteforDiseaseModeling/laser>`_.
It provides a flexible, component-based architecture for disease simulation with support for multiple geographic scales and demographic configurations.

Key features include:

* **Spatial modeling**: Support for geographic regions with administrative boundaries and population distributions
* **Multiple model types**: ABM, Biweekly, and Compartmental models for different use cases
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

.. warning::

   **All three model constructors require both** ``scenario`` **and** ``params``.
   There is no default — omitting ``params`` raises ``TypeError`` immediately:

   .. code-block:: python

      # WRONG — raises TypeError: missing 1 required positional argument: 'params'
      model = ABMModel(scenario=scenario)
      model = BiweeklyModel(scenario=scenario)
      model = CompartmentalModel(scenario=scenario)

   Always create the ``*Params`` object first, then pass both to the constructor:

   .. code-block:: python

      # CORRECT — both arguments are required
      params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
      model  = ABMModel(scenario=scenario, params=params)

      params = BiweeklyParams(num_ticks=130, seed=42, start_time="2000-01")
      model  = BiweeklyModel(scenario=scenario, params=params)

      params = CompartmentalParams(num_ticks=730, seed=42, start_time="2000-01")
      model  = CompartmentalModel(scenario=scenario, params=params)

   Components are added **after** construction via ``model.add_component()``.
   ``params`` configures duration, seed, and start date — not components.

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

.. _complete-examples:

Complete Worked Examples
------------------------

These end-to-end scripts are copy-paste runnable. Each one shows the
**full** pattern — imports, scenario, params, model construction, component
wiring, running, and result retrieval — with detailed inline comments on
every line that commonly causes errors.

The three non-negotiable constructor facts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

   **Read this before writing any model code.**

   These three facts are the source of the most common runtime failures.
   They apply to every model type without exception.

**Fact 1 — The only three model classes are** ``ABMModel``, ``BiweeklyModel``, ``CompartmentalModel``

Import them from their respective subpackages:

.. code-block:: python

   from laser.measles.abm           import ABMModel,           ABMParams
   from laser.measles.biweekly      import BiweeklyModel,      BiweeklyParams
   from laser.measles.compartmental import CompartmentalModel, CompartmentalParams

.. warning::

   The following names **do not exist** in the package and will raise
   ``AttributeError`` or ``ImportError``:

   .. code-block:: python

      lm.abm.Model          # ← does not exist
      lm.abm.ABM            # ← does not exist
      lm.abm.LaserABM       # ← does not exist
      lm.Model              # ← does not exist
      lm.BiweeklyModel      # ← does not exist
      lm.CompartmentalModel # ← does not exist
      lm.create_model(...)  # ← does not exist

   There is no convenience shortcut. Always import from the subpackage.

**Fact 2 — The constructor signature is always** ``Model(scenario, params)``

.. code-block:: python

   params = ABMParams(num_ticks=365, seed=42)      # ALL settings go here
   model  = ABMModel(scenario, params)              # then params goes here

.. warning::

   **params is not optional.** Calling the constructor with only a scenario
   raises ``TypeError`` immediately, before the simulation runs:

   .. code-block:: python

      ABMModel(scenario=scenario)                   # TypeError: missing 1 required positional argument: 'params'
      BiweeklyModel(scenario=scenario)              # TypeError: missing 1 required positional argument: 'params'
      CompartmentalModel(scenario=scenario)         # TypeError: missing 1 required positional argument: 'params'

   The ``*Params`` object is always the **second positional argument**.
   It is mandatory — there is no default and no shortcut.

   Passing simulation settings directly as keyword arguments also fails:

   .. code-block:: python

      ABMModel(scenario, num_ticks=365)             # TypeError
      ABMModel(scenario, n_ticks=365)               # TypeError
      ABMModel(scenario, seed=42)                   # TypeError
      ABMModel(scenario, params, components=[...])  # TypeError
      BiweeklyModel(scenario, n_ticks=26)           # TypeError
      CompartmentalModel(scenario, num_ticks=730)   # TypeError

   Every simulation setting — duration, seed, start date, verbosity —
   goes into the ``*Params`` object. Then the populated ``*Params``
   object is the second argument to the model constructor.

**Fact 3 —** ``start_time`` **must be** ``"YYYY-MM"``, **never** ``"YYYY-MM-DD"``

.. code-block:: python

   # CORRECT — "YYYY-MM" format
   params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")

.. warning::

   Passing a full date string raises a Pydantic ``ValidationError`` at
   construction time, before the simulation runs:

   .. code-block:: python

      # WRONG — raises ValidationError: start_time must be in 'YYYY-MM' format
      params = ABMParams(num_ticks=365, seed=42, start_time="2000-01-01")


Example 1 — ABM: single-patch outbreak with StateTracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One population of 100,000 people, no births, outbreak seeded from
``InfectionSeedingProcess``, peak infectious tracked with ``StateTracker``.
This is the minimal correct ABM script.

.. code-block:: python

   import numpy as np
   import polars as pl
   from laser.measles.abm import ABMModel, ABMParams
   from laser.measles.abm import NoBirthsProcess, InitializeEquilibriumStatesProcess
   from laser.measles.abm import InfectionSeedingProcess, InfectionProcess, StateTracker
   from laser.measles.scenarios import single_patch_scenario

   # ── 1. Scenario ─────────────────────────────────────────────────────────────
   # single_patch_scenario returns a polars DataFrame with the required columns:
   # id, lat, lon, pop, mcv1.  Pass it directly to the model constructor.
   scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.0)

   # ── 2. Params ────────────────────────────────────────────────────────────────
   # ABMParams holds ALL simulation settings.  num_ticks is in days (365 = 1 year).
   # start_time must be "YYYY-MM" — not "YYYY-MM-DD".
   params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")

   # ── 3. Model construction ────────────────────────────────────────────────────
   # The ONLY valid signature is ABMModel(scenario, params).
   # There is no ABMModel(scenario, num_ticks=...) or ABMModel(scenario, seed=...).
   model = ABMModel(scenario, params)

   # ── 4. Components ────────────────────────────────────────────────────────────
   # Components are added one at a time via add_component().
   # Pass the CLASS (not an instance) for components that need no parameters.
   # Pass create_component(CLASS, params=...) when parameters are required.
   #
   # NoBirthsProcess: keeps population fixed (use instead of VitalDynamicsProcess
   # for short runs where demographics don't matter).
   model.add_component(NoBirthsProcess)

   # InitializeEquilibriumStatesProcess: sets the initial S/E/I/R split to
   # the endemic equilibrium for the scenario's mcv1 coverage and default R0.
   model.add_component(InitializeEquilibriumStatesProcess)

   # InfectionSeedingProcess: introduces a small number of infectious individuals
   # at the start of the simulation to spark an outbreak.
   model.add_component(InfectionSeedingProcess)

   # InfectionProcess: drives daily S→E→I→R transitions using stochastic ABM rules.
   model.add_component(InfectionProcess)

   # StateTracker without params → global (summed-across-all-patches) tracker.
   # Access results via tracker.I (1-D array of length num_ticks).
   model.add_component(StateTracker)

   # ── 5. Run ───────────────────────────────────────────────────────────────────
   model.run()

   # ── 6. Retrieve results ──────────────────────────────────────────────────────
   # get_instance("StateTracker") returns a list of all StateTracker instances
   # in the order they were added.  [0] is the first (and here only) one.
   tracker = model.get_instance("StateTracker")[0]

   # tracker.I is a 1-D NumPy array: infectious count at each tick (day).
   # Cast to Python int before printing or building Polars DataFrames.
   peak_I   = int(tracker.I.max())
   peak_day = int(tracker.I.argmax())
   print(f"Peak infectious: {peak_I} on day {peak_day}")


Example 2 — Biweekly: five-patch endemic run with per-patch StateTracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Five communities, births/deaths, importation, 5 years. Uses
``BiweeklyModel`` (26 ticks per year) and a per-patch ``StateTracker``
(``aggregation_level=0``) to read the infectious time series per community.

.. code-block:: python

   import numpy as np
   import polars as pl
   from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
   from laser.measles.biweekly import InitializeEquilibriumStatesProcess, ImportationPressureProcess
   from laser.measles.biweekly import InfectionProcess, VitalDynamicsProcess, StateTracker
   from laser.measles.abm import StateTrackerParams   # not in biweekly — import from abm
   from laser.measles import create_component

   # ── 1. Scenario ─────────────────────────────────────────────────────────────
   # Build a 5-patch scenario manually.
   # IMPORTANT: lat and lon MUST be Float64.  list(range(5)) produces Int64
   # and will fail schema validation.  Use float literals or np.linspace/np.zeros.
   scenario = pl.DataFrame({
       "id":   [f"patch_{i}" for i in range(5)],
       "lat":  [0.0] * 5,                          # Float64 ✓
       "lon":  [float(i) for i in range(5)],        # Float64 ✓  (not list(range(5)))
       "pop":  [50_000, 80_000, 120_000, 200_000, 150_000],
       "mcv1": [0.90, 0.85, 0.80, 0.75, 0.70],
   })

   # ── 2. Params ────────────────────────────────────────────────────────────────
   # BiweeklyModel uses 14-day ticks: 26 ticks = 1 year, 130 ticks = 5 years.
   # There is no BiweeklyModel(scenario, num_ticks=130) — num_ticks goes in params.
   params = BiweeklyParams(num_ticks=130, seed=42, start_time="2000-01")

   # ── 3. Model construction ────────────────────────────────────────────────────
   # The ONLY valid signature is BiweeklyModel(scenario, params).
   model = BiweeklyModel(scenario, params)

   # ── 4. Components ────────────────────────────────────────────────────────────
   # InitializeEquilibriumStatesProcess: set initial S/I/R near endemic equilibrium.
   model.add_component(InitializeEquilibriumStatesProcess)

   # ImportationPressureProcess: steady background importation that sustains
   # endemic transmission.  Required when starting near equilibrium.
   model.add_component(ImportationPressureProcess)

   # InfectionProcess: biweekly transmission (SIR, no explicit E compartment).
   model.add_component(InfectionProcess)

   # VitalDynamicsProcess: births and deaths using the scenario's mcv1 coverage
   # to vaccinate newborns.
   # NOTE: in BiweeklyModel, VitalDynamicsProcess can appear after InfectionProcess.
   # (The "VitalDynamics must be first" rule applies to ABMModel only.)
   model.add_component(VitalDynamicsProcess)

   # StateTracker with aggregation_level=0 → per-patch tracker.
   # Results are in tracker.I with shape (num_ticks, n_patches).
   # IMPORTANT: StateTrackerParams is not in biweekly — imported from laser.measles.abm above.
   model.add_component(
       create_component(
           StateTracker,
           params=StateTrackerParams(aggregation_level=0),
       )
   )

   # ── 5. Run ───────────────────────────────────────────────────────────────────
   model.run()

   # ── 6. Retrieve results ──────────────────────────────────────────────────────
   tracker = model.get_instance("StateTracker")[0]

   # tracker.I has shape (num_ticks, n_patches) when aggregation_level=0.
   # Axis 0 = time (ticks), axis 1 = patch index.
   I = tracker.I   # shape: (130, 5)

   print("Mean infectious in each community (last 26 ticks = final year):")
   for p, patch_id in enumerate(scenario["id"]):
       mean_I = float(I[-26:, p].mean())   # last year only
       print(f"  {patch_id}: {mean_I:.1f}")


Example 3 — Compartmental: R0 sweep with InfectionParams
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single population, three different R0 values, 2-year runs. Shows how
to scale ``beta`` from the default to reach a target R0, using
``CompartmentalModel`` and a per-patch ``StateTracker``.

.. code-block:: python

   import numpy as np
   import polars as pl
   from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
   from laser.measles.compartmental import InitializeEquilibriumStatesProcess, InfectionSeedingProcess
   from laser.measles.compartmental import InfectionProcess, InfectionParams, StateTracker, StateTrackerParams
   from laser.measles.scenarios import single_patch_scenario
   from laser.measles import create_component

   # Default beta (R0 ≈ 8 with default measles parameters).
   # Scale it linearly to reach any other R0.
   R0_DEFAULT   = 8.0
   BETA_DEFAULT = 0.5714285714285714   # default beta shipped with InfectionParams

   for target_r0 in [4.0, 8.0, 16.0]:

       # ── 1. Scenario ──────────────────────────────────────────────────────────
       scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.0)

       # ── 2. Params ────────────────────────────────────────────────────────────
       # CompartmentalModel uses daily ticks: 730 ticks = 2 years.
       # There is no CompartmentalModel(scenario, num_ticks=730) shortcut.
       params = CompartmentalParams(num_ticks=730, seed=42, start_time="2000-01")

       # ── 3. Model construction ────────────────────────────────────────────────
       # The ONLY valid signature is CompartmentalModel(scenario, params).
       model = CompartmentalModel(scenario, params)

       # ── 4. Components ────────────────────────────────────────────────────────
       model.add_component(InitializeEquilibriumStatesProcess)
       model.add_component(InfectionSeedingProcess)

       # Scale beta to reach the desired R0.
       # InfectionParams accepts 'beta' directly — there is no 'beta_scale' field.
       scaled_beta = target_r0 * (BETA_DEFAULT / R0_DEFAULT)
       model.add_component(
           create_component(
               InfectionProcess,
               params=InfectionParams(beta=scaled_beta),
           )
       )

       model.add_component(
           create_component(
               StateTracker,
               params=StateTrackerParams(aggregation_level=0),
           )
       )

       # ── 5. Run ───────────────────────────────────────────────────────────────
       model.run()

       # ── 6. Retrieve results ──────────────────────────────────────────────────
       tracker = model.get_instance("StateTracker")[0]

       # tracker.I shape: (num_ticks, n_patches).
       # State index order in state_tracker: S=0, E=1, I=2, R=3.
       I = tracker.I[:, 0]   # single patch → 1-D array of length num_ticks
       print(f"R0={target_r0:.0f}: peak I = {int(I.max()):,} on day {int(I.argmax())}")

----------

.. _gotchas:

Gotchas & FAQ
-------------

This section documents common pitfalls when writing ``laser-measles`` models.
If you encounter unexpected ``ImportError``, tracker shape mismatches, or
component configuration errors, check the items below first.

These issues occur frequently when users are learning the component system
or adapting code between the ABM, biweekly, and compartmental models.

1. Where does ``create_component`` come from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``create_component`` is available from both the top-level
``laser.measles`` namespace and the shared ``laser.measles.components``
package, regardless of which model type you are using.

It lives in the shared components package because it works with **all model
types** (ABM, biweekly, and compartmental), and is re-exported at the
top level for convenience.

.. code-block:: python

   # PREFERRED (flattened public API)
   from laser.measles import create_component

   # ALSO SUPPORTED (direct components package)
   from laser.measles.components import create_component

   # WRONG — ImportError or inconsistent with the public API
   from laser.measles.abm import create_component
   from laser.measles.biweekly import create_component
   from laser.measles.compartmental import create_component


2. How do I access component classes and their parameter classes?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Import component classes and their parameter classes directly from the
subpackage. Each subpackage's ``__init__`` re-exports everything from its
``components`` module, so all concrete components are available at the
top level.

.. code-block:: python

   # PREFERRED — import directly from the subpackage
   from laser.measles.abm import ABMModel, ABMParams
   from laser.measles.abm import NoBirthsProcess, InfectionSeedingProcess, InfectionSeedingParams
   from laser.measles.abm import InfectionProcess, StateTracker, StateTrackerParams
   from laser.measles import create_component

   model.components = [
       NoBirthsProcess,

       create_component(
           InfectionSeedingProcess,
           params=InfectionSeedingParams(target_patches=["patch_0"])
       ),

       InfectionProcess,

       create_component(
           StateTracker,
           params=StateTrackerParams(aggregation_level=0)
       ),
   ]

The same pattern applies to biweekly and compartmental — import directly from
``laser.measles.biweekly`` or ``laser.measles.compartmental``.


3. ``model.components`` is assigned *after* construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The model constructors only accept ``scenario`` and ``params``.

Components must be attached by assigning to ``model.components`` **after**
the model object is created.

.. code-block:: python

   # CORRECT
   model = BiweeklyModel(scenario=scenario, params=params)

   model.components = [
       InitializeEquilibriumStatesProcess,
       ImportationPressureProcess,
       InfectionProcess,
       VitalDynamicsProcess,
       StateTracker,
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
   from laser.measles.abm import ABMModel, ABMParams


5. ``StateTracker`` output shape depends on ``aggregation_level``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``StateTracker`` component stores time-series data differently depending
on how it is configured.

Default behavior (global aggregation, ``aggregation_level=-1``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default ``aggregation_level=-1`` sums across all patches.

Arrays are **1-D** with shape::

   (num_ticks,)

.. code-block:: python

   tracker = model.get_instance("StateTracker")[0]

   peak_I = int(tracker.I.max())


Patch-level tracking
^^^^^^^^^^^^^^^^^^^^

If ``aggregation_level=0`` is used, the tracker stores values **per patch**
(for flat patch IDs with no ``":"`` hierarchy).

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Components should be passed as **classes**, not instantiated objects.

The model constructs the component instances internally.

.. code-block:: python

   # CORRECT
   model.components = [
       InfectionProcess
   ]

   # WRONG
   model.components = [
       InfectionProcess()
   ]


If parameters are needed, use ``create_component``:

.. code-block:: python

   model.components = [
       create_component(
           InfectionProcess,
           params=InfectionParams(beta=0.8)
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


9. Use ``laser.measles.scenarios.synthetic`` for test scenarios
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``synthetic`` module provides ready-made scenario DataFrames for
testing and development. It is available via several import paths:

.. code-block:: python

   # Functions re-exported at the scenarios package level
   from laser.measles.scenarios import single_patch_scenario, two_patch_scenario
   from laser.measles.scenarios import two_cluster_scenario, satellites_scenario

   # Access via the synthetic submodule
   from laser.measles.scenarios import synthetic
   scenario = synthetic.single_patch_scenario(population=50_000, mcv1_coverage=0.85)

   # synthetic is also re-exported at the top level
   from laser.measles import synthetic

   # WRONG — laser_measles (underscore) does not exist
   from laser_measles.scenarios import synthetic

Each function returns a :class:`polars.DataFrame` with all required columns
(``id``, ``lat``, ``lon``, ``pop``, ``mcv1``) already populated. Pass it
directly to any model constructor:

.. code-block:: python

   from laser.measles.abm import ABMModel, ABMParams
   from laser.measles.scenarios import single_patch_scenario

   scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
   params = ABMParams(num_ticks=365, seed=42)
   model = ABMModel(scenario, params)

Available helpers: ``single_patch_scenario``, ``two_patch_scenario``,
``two_cluster_scenario``, ``satellites_scenario``. See the
:ref:`Scenarios API <api/index:Scenarios Package>` for full parameter details.

10. Retrieving results from ``StateTracker``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``StateTracker`` component does **not** expose a ``.data``, ``.results``,
or ``.to_polars()`` attribute. These names do not exist.

After ``model.run()``, retrieve the tracker instance with
``model.get_instance("StateTracker")[0]`` and access the time-series arrays
directly as properties.

**Global tracker** (default, ``aggregation_level=-1``):

.. code-block:: python

   # CORRECT — add the class, retrieve via get_instance, access .I
   model.add_component(StateTracker)
   model.run()

   tracker = model.get_instance("StateTracker")[0]
   peak_I = int(tracker.I.max())          # global infectious peak
   peak_day = int(tracker.I.argmax())     # day of peak

**Per-patch tracker** (``aggregation_level=0``):

``StateTrackerParams`` always lives in ``laser.measles.abm.components``,
regardless of model type (ABM, biweekly, or compartmental).

.. code-block:: python

   from laser.measles import create_component
   from laser.measles.abm import StateTracker, StateTrackerParams

   model.add_component(
       create_component(
           StateTracker,
           params=StateTrackerParams(aggregation_level=0),
       )
   )
   model.run()

   tracker = model.get_instance("StateTracker")[0]
   st = tracker.state_tracker   # shape: (n_states, n_ticks, n_patches)
   # State index order: S=0, E=1, I=2, R=3
   peak_I_patch0 = int(st[2, :, 0].max())   # patch 0 infectious peak

**Global + per-patch together** (add both, retrieve by index):

.. code-block:: python

   from laser.measles.abm import StateTracker, StateTrackerParams

   model.add_component(StateTracker)           # index [0] — global
   model.add_component(
       create_component(
           StateTracker,
           params=StateTrackerParams(aggregation_level=0),
       )
   )                                                      # index [1] — per-patch
   model.run()

   global_tracker = model.get_instance("StateTracker")[0]
   patch_tracker  = model.get_instance("StateTracker")[1]

.. code-block:: python

   # WRONG — these attributes do not exist
   tracker.data
   tracker.results
   tracker.to_polars()
   tracker.df


11. ``VitalDynamicsProcess`` must be the first component
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When using vital dynamics (births and deaths), ``VitalDynamicsProcess`` must
be the **first** component added to the model.

This is because ``VitalDynamicsProcess`` calls ``calculate_capacity`` to
pre-allocate the ``LaserFrame`` with enough headroom for the births that will
occur over the simulation. If any other component is added first, the
``LaserFrame`` is already initialized at the wrong size, which causes a crash.

.. code-block:: python

   # CORRECT
   model.add_component(VitalDynamicsProcess)        # FIRST
   model.add_component(InitializeEquilibriumStatesProcess)
   model.add_component(ImportationPressureProcess)
   model.add_component(InfectionProcess)
   model.add_component(StateTracker)

.. code-block:: python

   # WRONG — VitalDynamicsProcess is not first; LaserFrame is already
   # initialized at the wrong capacity and will crash at runtime
   model.add_component(InitializeEquilibriumStatesProcess)
   model.add_component(VitalDynamicsProcess)   # too late


12. ``lat`` and ``lon`` columns must be ``Float64``, not ``Int64``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The scenario schema requires ``lat`` and ``lon`` to be floating-point.
Using Python's ``range()`` or integer literals produces ``Int64`` columns,
which fail Polars schema validation when the model is constructed.

.. code-block:: python

   # WRONG — list(range(N)) produces Int64; schema validation will fail
   scenario = pl.DataFrame({
       "id":   [f"patch_{i}" for i in range(5)],
       "pop":  [10_000] * 5,
       "lat":  [0] * 5,            # Int64
       "lon":  list(range(5)),     # Int64
       "mcv1": [0.0] * 5,
   })

   # CORRECT — explicit float literals
   scenario = pl.DataFrame({
       "id":   [f"patch_{i}" for i in range(5)],
       "pop":  [10_000] * 5,
       "lat":  [0.0] * 5,
       "lon":  [float(i) for i in range(5)],
       "mcv1": [0.0] * 5,
   })


13. Tick granularity: daily vs biweekly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ABMModel`` and ``CompartmentalModel`` use **daily** ticks (1 tick = 1 day).
``BiweeklyModel`` uses **14-day** ticks (1 tick = 2 weeks, 26 ticks = 1 year).

Quick reference:
