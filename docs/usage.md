# Usage

## Overview

laser-measles is a spatial epidemiological modeling toolkit for measles transmission dynamics, built on the [LASER framework](https://github.com/InstituteforDiseaseModeling/laser).
It provides a flexible, component-based architecture for disease simulation with support for multiple geographic scales and demographic configurations.

Key features include:

- **Spatial modeling**: Support for geographic regions with administrative boundaries and population distributions
- **Multiple model types**: ABM, Biweekly, and Compartmental models for different use cases
- **Component-based architecture**: Interchangeable disease dynamics components
- **High-performance computing**: Optimized data structures and Numba JIT compilation
- **Type-safe parameters**: Pydantic-based configuration management

## Installation and Setup

Install laser-measles using pip (requires Python 3.10+):

```bash
pip install laser-measles
```

For development installation with all dependencies (recommended: use `uv` for faster package management):

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"
# or for full installation including examples
uv pip install -e ".[full]"

# Alternative: using pip
pip install -e ".[dev]"
```

**Major Dependencies:**

- `laser-core>=1.0.0`: Core LASER framework
- `pydantic>=2.11.5`: Parameter validation and serialization
- `polars>=1.30.0`: High-performance data manipulation
- `alive-progress>=3.2.0`: Progress bars and status indicators
- `rastertoolkit>=0.3.11`: Raster data processing utilities
- `patito>=0.8.3`: Polars DataFrame validation

---

## Model Types

laser-measles provides three complementary modeling approaches, each optimized for different use cases:

1. **ABM (Agent-Based Model)**: Individual-level simulation with stochastic agents
2. **Biweekly Compartmental Model**: Population-level SIR dynamics with 2-week timesteps
3. **Compartmental Model**: Population-level SEIR dynamics with daily timesteps

Each model type offers different trade-offs between computational efficiency, temporal resolution, and modeling detail.

---

### ABM (Agent-Based Model)

The ABM model provides individual-level simulation with stochastic agents, allowing for detailed tracking of disease dynamics at the person level.

**Key Characteristics:**

- **Individual agents**: Each person is represented as a discrete agent with properties like age, location, and disease state
- **Daily timesteps**: Fine-grained temporal resolution for precise modeling
- **Stochastic processes**: Individual-level probabilistic events for realistic variability
- **Spatial heterogeneity**: Agents can move between patches and have location-specific interactions
- **Flexible demographics**: Full support for births, deaths, aging, and migration

**Example usage:**

```python
from laser.measles.abm import ABMModel, ABMParams

# Configure model parameters
params = ABMParams(
    num_ticks=7300,  # 20 years of daily timesteps
    seed=12345
)

# Initialize and run model
model = ABMModel(scenario_data, params)
model.run()
```

---

### Biweekly Model

The Biweekly Model is a compartmental model optimized for fast simulation and parameter exploration with 2-week timesteps.

**Key Characteristics:**

- **Compartmental approach**: SIR (Susceptible-Infected-Recovered) structure.
  The exposed (E) compartment is omitted because the 14-day timestep is
  comparable to measles' typical incubation period (~10-14 days), making
  the distinction between exposed and infectious states negligible at this
  temporal resolution. For detailed SEIR dynamics with explicit incubation
  periods, use the Compartmental Model with daily timesteps.
- **Time resolution**: 14-day fixed time steps (26 ticks per year)
- **High performance**: Uses Polars DataFrames for efficient data manipulation
- **Stochastic sampling**: Binomial sampling for realistic variability
- **Policy analysis**: Recommended for scenario building and intervention assessment

**Example usage:**

```python
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams

# Configure model parameters
params = BiweeklyParams(
    num_ticks=520,  # 20 years of bi-weekly time steps
    seed=12345
)

# Initialize and run model
model = BiweeklyModel(scenario_data, params)
model.run()
```

---

### Compartmental Model

The Compartmental Model provides population-level SEIR dynamics with daily timesteps, optimized for parameter estimation and detailed outbreak modeling.

**Key Characteristics:**

- **Daily timesteps**: Fine-grained temporal resolution (365 ticks per year)
- **SEIR dynamics**: Detailed compartmental structure with exposed compartment
- **Parameter estimation**: Recommended for fitting to surveillance data
- **Outbreak modeling**: Ideal for detailed temporal analysis of disease dynamics
- **Deterministic core**: Efficient ODE-based dynamics with optional stochastic elements

**Example usage:**

```python
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams

# Configure model parameters
params = CompartmentalParams(
    num_ticks=7300,  # 20 years of daily time steps
    seed=12345
)

# Initialize and run model
model = CompartmentalModel(scenario_data, params)
model.run()
```

!!! warning

    **All three model constructors require both** `scenario` **and** `params`.
    There is no default — omitting `params` raises `TypeError` immediately:

    ```python
    # WRONG — raises TypeError: missing 1 required positional argument: 'params'
    model = ABMModel(scenario=scenario)
    model = BiweeklyModel(scenario=scenario)
    model = CompartmentalModel(scenario=scenario)
    ```

    Always create the `*Params` object first, then pass both to the constructor:

    ```python
    # CORRECT — both arguments are required
    params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
    model  = ABMModel(scenario=scenario, params=params)

    params = BiweeklyParams(num_ticks=130, seed=42, start_time="2000-01")
    model  = BiweeklyModel(scenario=scenario, params=params)

    params = CompartmentalParams(num_ticks=730, seed=42, start_time="2000-01")
    model  = CompartmentalModel(scenario=scenario, params=params)
    ```

    Components are added **after** construction via `model.add_component()`.
    `params` configures duration, seed, and start date — not components.

---

## Demographics Package

The demographics package provides comprehensive geographic data handling capabilities for spatial epidemiological modeling.

**Core Features:**

- **GADM Integration**: `GADMShapefile` class for administrative boundary management
- **Raster Processing**: `RasterPatchGenerator` for population distribution handling
- **Shapefile Utilities**: Functions for geographic data visualization and analysis
- **Flexible Geographic Scales**: Support from national to sub-district administrative levels

**Key Classes:**

- `GADMShapefile`: Manages administrative boundaries from GADM database
- `RasterPatchParams`: Configuration for raster-based population patches
- `RasterPatchGenerator`: Creates population patches from raster data
- `get_shapefile_dataframe`: Utility for shapefile data manipulation
- `plot_shapefile_dataframe`: Visualization functions for geographic data

**Example usage:**

```python
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
```

## Technical Features

### Pydantic Integration

laser-measles uses Pydantic for type-safe parameter management, providing automatic validation and documentation.

**Parameter Classes:**

- `ABMParams`: Configuration for agent-based models with individual-level parameters
- `BiweeklyParams`: Configuration for biweekly models with epidemiological parameters
- `CompartmentalParams`: Configuration for compartmental models with daily dynamics

**Component Classes:**
Components come in "process" and "tracker" categories and each component has a corresponding parameter class.
Each model (ABM, Biweekly, or Compartmental) has its own set of components. See the API reference section for more details.

**Benefits:**

- **Type safety**: Automatic validation of parameter types and ranges
- **Documentation**: Built-in parameter descriptions and constraints
- **Serialization**: JSON export/import of model configurations
- **IDE support**: Enhanced autocomplete and error detection

**Example:**

```python
from laser.measles.biweekly import BiweeklyParams

params = BiweeklyParams(
    num_ticks=520,  # Validated as positive integer
    seed=12345      # Random seed for reproducibility
)

# Export configuration
config_json = params.model_dump_json()
```

### High-Performance Computing

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

### Component System

The component system provides a uniform interface for disease dynamics with interchangeable modules built on a hierarchical base class architecture.

**Base Architecture:**

- **BaseLaserModel**: Abstract base class for all model types with common functionality
- **BaseComponent**: Base class for all components with standardized interface
- **BasePhase**: Components that execute every tick (inherit from BaseComponent)
- **Inheritance-based design**: Base components define shared functionality and abstract interfaces

**Base Component Classes:**

- `base_transmission.py`: Base transmission/infection logic
- `base_vital_dynamics.py`: Base births/deaths logic
- `base_importation.py`: Base importation pressure logic
- `base_tracker.py`: Base tracking/metrics logic
- `base_infection.py`: Base infection state transitions
- `base_tracker_state.py`: Base state tracking functionality

**Component Naming Convention:**

- **Process components**: `process_*.py` - Modify model state (births, deaths, infection, transmission)
- **Tracker components**: `tracker_*.py` - Record metrics and state over time

**Component Creation Patterns:**

```python
# Component with parameters using Pydantic
from laser.measles.components.base_infection import BaseInfectionProcess

class MyInfectionProcess(BaseInfectionProcess):
    def __init__(self, model, verbose=False, **params):
        super().__init__(model, verbose)
        # Initialize with validated parameters

# Add to model
model.components = [MyInfectionProcess]
```

---

## Complete Worked Examples {: #complete-examples }

These end-to-end scripts are copy-paste runnable. Each one shows the
**full** pattern — imports, scenario, params, model construction, component
wiring, running, and result retrieval — with detailed inline comments on
every line that commonly causes errors.

### The three non-negotiable constructor facts

!!! warning

    **Read this before writing any model code.**

    These three facts are the source of the most common runtime failures.
    They apply to every model type without exception.

**Fact 1 — The only three model classes are** `ABMModel`, `BiweeklyModel`, `CompartmentalModel`

Import them from their respective subpackages:

```python
from laser.measles.abm           import ABMModel,           ABMParams
from laser.measles.biweekly      import BiweeklyModel,      BiweeklyParams
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
```

!!! warning

    The following names **do not exist** in the package and will raise
    `AttributeError` or `ImportError`:

    ```python
    lm.abm.Model          # ← does not exist
    lm.abm.ABM            # ← does not exist
    lm.abm.LaserABM       # ← does not exist
    lm.Model              # ← does not exist
    lm.BiweeklyModel      # ← does not exist
    lm.CompartmentalModel # ← does not exist
    lm.create_model(...)  # ← does not exist
    ```

    There is no convenience shortcut. Always import from the subpackage.

**Fact 2 — The constructor signature is always** `Model(scenario, params)`

```python
params = ABMParams(num_ticks=365, seed=42)      # ALL settings go here
model  = ABMModel(scenario, params)              # then params goes here
```

!!! warning

    **params is not optional.** Calling the constructor with only a scenario
    raises `TypeError` immediately, before the simulation runs:

    ```python
    ABMModel(scenario=scenario)                   # TypeError: missing 1 required positional argument: 'params'
    BiweeklyModel(scenario=scenario)              # TypeError: missing 1 required positional argument: 'params'
    CompartmentalModel(scenario=scenario)         # TypeError: missing 1 required positional argument: 'params'
    ```

    The `*Params` object is always the **second positional argument**.
    It is mandatory — there is no default and no shortcut.

    Passing simulation settings directly as keyword arguments also fails:

    ```python
    ABMModel(scenario, num_ticks=365)             # TypeError
    ABMModel(scenario, n_ticks=365)               # TypeError
    ABMModel(scenario, seed=42)                   # TypeError
    ABMModel(scenario, params, components=[...])  # TypeError
    BiweeklyModel(scenario, n_ticks=26)           # TypeError
    CompartmentalModel(scenario, num_ticks=730)   # TypeError
    ```

    Every simulation setting — duration, seed, start date, verbosity —
    goes into the `*Params` object. Then the populated `*Params`
    object is the second argument to the model constructor.

**Fact 3 —** `start_time` **must be** `"YYYY-MM"`, **never** `"YYYY-MM-DD"`

```python
# CORRECT — "YYYY-MM" format
params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
```

!!! warning

    Passing a full date string raises a Pydantic `ValidationError` at
    construction time, before the simulation runs:

    ```python
    # WRONG — raises ValidationError: start_time must be in 'YYYY-MM' format
    params = ABMParams(num_ticks=365, seed=42, start_time="2000-01-01")
    ```

### Example 1 — ABM: single-patch outbreak with StateTracker

One population of 100,000 people, no births, outbreak seeded from
`InfectionSeedingProcess`, peak infectious tracked with `StateTracker`.
This is the minimal correct ABM script.

```python
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
```

### Example 2 — Biweekly: five-patch endemic run with per-patch StateTracker

Five communities, births/deaths, importation, 5 years. Uses
`BiweeklyModel` (26 ticks per year) and a per-patch `StateTracker`
(`aggregation_level=0`) to read the infectious time series per community.

```python
import numpy as np
import polars as pl
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
from laser.measles.biweekly import InitializeEquilibriumStatesProcess, ImportationPressureProcess
from laser.measles.biweekly import InfectionProcess, VitalDynamicsProcess, StateTracker, StateTrackerParams
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
```

### Example 3 — Compartmental: R0 sweep with InfectionParams

Single population, three different R0 values, 2-year runs. Shows how
to scale `beta` from the default to reach a target R0, using
`CompartmentalModel` and a per-patch `StateTracker`.

```python
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
```

---

## Gotchas & FAQ {: #gotchas }

This section documents common pitfalls when writing `laser-measles` models.
If you encounter unexpected `ImportError`, tracker shape mismatches, or
component configuration errors, check the items below first.

These issues occur frequently when users are learning the component system
or adapting code between the ABM, biweekly, and compartmental models.

### 1. Where does `create_component` come from?

`create_component` is available from both the top-level
`laser.measles` namespace and the shared `laser.measles.components`
package, regardless of which model type you are using.

It lives in the shared components package because it works with **all model
types** (ABM, biweekly, and compartmental), and is re-exported at the
top level for convenience.

```python
# PREFERRED (flattened public API)
from laser.measles import create_component

# ALSO SUPPORTED — re-exported from each model subpackage and shared components:
from laser.measles.abm import create_component
from laser.measles.biweekly import create_component
from laser.measles.compartmental import create_component
from laser.measles.components import create_component
```

### 2. How do I access component classes and their parameter classes?

Import component classes and their parameter classes directly from the
subpackage. Each subpackage's `__init__` re-exports everything from its
`components` module, so all concrete components are available at the
top level.

```python
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
```

The same pattern applies to biweekly and compartmental — import directly from
`laser.measles.biweekly` or `laser.measles.compartmental`.

!!! warning

    **Component and param classes are model-specific.** `InfectionParams`,
    `SIACalendarParams`, `NoBirthsProcess`, and similar classes have different
    fields per model type and live in their respective subpackage. Do not import
    them from the shared `laser.measles.components` package or from the wrong
    model subpackage:

    ```python
    # WRONG — ImportError or wrong class
    from laser.measles.components import InfectionParams     # ImportError
    from laser.measles import InfectionParams                # ImportError
    from laser.measles.components import SIACalendarProcess  # ImportError
    from laser.measles.abm import single_patch_scenario      # ImportError

    # CORRECT — import each class from its own model subpackage
    from laser.measles.abm import InfectionParams            # ABM variant
    from laser.measles.biweekly import InfectionParams       # Biweekly variant
    from laser.measles.compartmental import InfectionParams  # Compartmental variant

    # Scenario helpers live at the top level only:
    from laser.measles import single_patch_scenario, two_patch_scenario, two_cluster_scenario
    ```

    `NoBirthsProcess` and `SIACalendarProcess` exist in the ABM subpackage only —
    there is no equivalent in the biweekly or compartmental subpackages.

### 3. `model.components` is assigned *after* construction

The model constructors only accept `scenario` and `params`.

Components must be attached by assigning to `model.components` **after**
the model object is created.

```python
# CORRECT
model = BiweeklyModel(scenario=scenario, params=params)

model.components = [
    InitializeEquilibriumStatesProcess,
    ImportationPressureProcess,
    InfectionProcess,
    VitalDynamicsProcess,
    StateTracker,
]
```

The model internally instantiates the component classes when the list is
assigned.

```python
# WRONG — TypeError: unexpected keyword argument "components"
model = BiweeklyModel(
    scenario=scenario,
    params=params,
    components=[...]
)
```

This applies to all three model types:

- `ABMModel`
- `BiweeklyModel`
- `CompartmentalModel`

### 4. There is no `lm` object in `laser.measles`

The top-level `laser.measles` package does **not** export a convenience
object such as `lm`.

Some tutorials or AI-generated examples use this alias, but it is not part
of the package API.

```python
# WRONG — ImportError
from laser.measles import lm

# CORRECT
from laser.measles.abm import ABMModel, ABMParams
```

### 5. `StateTracker` output shape depends on `aggregation_level`

The `StateTracker` component stores time-series data differently depending
on how it is configured.

#### Default behavior (global aggregation)

Adding `StateTracker` **without any params** (or with `aggregation_level=-1`) sums
across all patches. **Do not pass `aggregation_level=0` or `aggregation_level=1`
when you want global results** — those activate per-patch or per-region tracking
and will produce multi-dimensional arrays.

Arrays are **1-D** with shape:

    (num_ticks,)

```python
tracker = model.get_instance("StateTracker")[0]

peak_I = int(tracker.I.max())
```

#### Patch-level tracking

If `aggregation_level=0` is used, the tracker stores values **per patch**
(for flat patch IDs with no `":"` hierarchy).

Arrays become **2-D** with shape:

    (num_ticks, n_patches)

```python
tracker = model.get_instance("StateTracker")[0]

peak_patch_0 = int(tracker.I[:, 0].max())
```

Retrieve the tracker instance after `model.run()`:

```python
tracker = model.get_instance("StateTracker")[0]
```

### 6. Cast NumPy scalars before building a Polars DataFrame

Tracker arrays are NumPy arrays, so operations like `.max()` return
NumPy scalar types (`np.int64`, `np.float64`).

Polars expects **Python primitive types** when constructing row-oriented
DataFrames. Passing NumPy scalars can trigger `TypeError` or
`DataOrientationWarning`.

```python
# WRONG
rows.append([patch_id, tracker.I[:, p].max()])

# CORRECT
rows.append([patch_id, int(tracker.I[:, p].max())])
```

An alternative is to use `.item()`:

```python
rows.append([patch_id, tracker.I[:, p].max().item()])
```

### 7. Components are classes, not instances

Components should be passed as **classes**, not instantiated objects.

The model constructs the component instances internally.

```python
# CORRECT
model.components = [
    InfectionProcess
]

# WRONG
model.components = [
    InfectionProcess()
]
```

If parameters are needed, use `create_component`:

```python
model.components = [
    create_component(
        InfectionProcess,
        params=InfectionParams(beta=0.8)
    )
]
```

### 8. Scenario DataFrame must contain required columns

All models expect the scenario DataFrame to contain at least the following
columns:

- `id` — patch identifier
- `lat` — latitude
- `lon` — longitude
- `pop` — population size
- `mcv1` — routine vaccination coverage

Missing columns will trigger a validation error when constructing the model.

```python
scenario = pl.DataFrame({
    "id": ["patch_0"],
    "lat": [0.0],
    "lon": [0.0],
    "pop": [50000],
    "mcv1": [0.8],
})
```

### 9. Use `laser.measles.scenarios.synthetic` for test scenarios

The `synthetic` module provides ready-made scenario DataFrames for
testing and development. It is available via several import paths:

```python
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
```

Each function returns a `polars.DataFrame` with all required columns
(`id`, `lat`, `lon`, `pop`, `mcv1`) already populated. Pass it
directly to any model constructor:

```python
from laser.measles.abm import ABMModel, ABMParams
from laser.measles.scenarios import single_patch_scenario

scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
params = ABMParams(num_ticks=365, seed=42)
model = ABMModel(scenario, params)
```

!!! warning

    **The patch IDs returned by the helper functions are 1-indexed**, not 0-indexed:

    - `single_patch_scenario()` → `id = "patch_1"` (not `"patch_0"`)
    - `two_patch_scenario()` → `id = ["patch_1", "patch_2"]`

    If you pass `target_patches=["patch_0"]` to `InfectionSeedingParams` when
    using a helper-built scenario, the model will raise:

    ```
    ValueError: Target patches not found in model: ['patch_0']
    ```

    The safest approach is to **omit `target_patches`** entirely — it defaults
    to seeding all patches, which is correct for single-patch scenarios:

    ```python
    # PREFERRED — omit target_patches to seed all patches
    model.add_component(InfectionSeedingProcess)

    # If you need to specify a patch explicitly, read the ID from the scenario:
    patch_id = scenario["id"][0]   # "patch_1" for single_patch_scenario
    from laser.measles.abm import InfectionSeedingParams
    from laser.measles import create_component
    model.add_component(
        create_component(InfectionSeedingProcess,
                         params=InfectionSeedingParams(target_patches=[patch_id]))
    )
    ```

Available helpers: `single_patch_scenario`, `two_patch_scenario`,
`two_cluster_scenario`, `satellites_scenario`. See the
API reference for full parameter details.

### 10. Retrieving results from `StateTracker`

The `StateTracker` component does **not** expose a `.data`, `.results`,
or `.to_polars()` attribute. These names do not exist.

After `model.run()`, retrieve the tracker instance with
`model.get_instance("StateTracker")[0]` and access the time-series arrays
directly as properties.

**Global tracker** (default, `aggregation_level=-1`):

```python
# CORRECT — add the class, retrieve via get_instance, access .I
model.add_component(StateTracker)
model.run()

tracker = model.get_instance("StateTracker")[0]
peak_I = int(tracker.I.max())          # global infectious peak
peak_day = int(tracker.I.argmax())     # day of peak
```

**Per-patch tracker** (`aggregation_level=0`):

`StateTrackerParams` is available from all model subpackages:

```python
from laser.measles import create_component
from laser.measles.abm import StateTracker, StateTrackerParams          # ABM
# or: from laser.measles.biweekly import StateTracker, StateTrackerParams
# or: from laser.measles.compartmental import StateTracker, StateTrackerParams

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
```

**Global + per-patch together** (add both, retrieve by index):

```python
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
```

```python
# WRONG — these attributes do not exist
tracker.data
tracker.results
tracker.to_polars()
tracker.df
```

### 11. `VitalDynamicsProcess` must be the first component

When using vital dynamics (births and deaths), `VitalDynamicsProcess` must
be the **first** component added to the model.

This is because `VitalDynamicsProcess` calls `calculate_capacity` to
pre-allocate the `LaserFrame` with enough headroom for the births that will
occur over the simulation. If any other component is added first, the
`LaserFrame` is already initialized at the wrong size, which causes a crash.

```python
# CORRECT
model.add_component(VitalDynamicsProcess)        # FIRST
model.add_component(InitializeEquilibriumStatesProcess)
model.add_component(ImportationPressureProcess)
model.add_component(InfectionProcess)
model.add_component(StateTracker)
```

```python
# WRONG — VitalDynamicsProcess is not first; LaserFrame is already
# initialized at the wrong capacity and will crash at runtime
model.add_component(InitializeEquilibriumStatesProcess)
model.add_component(VitalDynamicsProcess)   # too late
```

### 12. `lat` and `lon` columns must be `Float64`, not `Int64`

The scenario schema requires `lat` and `lon` to be floating-point.
Using Python's `range()` or integer literals produces `Int64` columns,
which fail Polars schema validation when the model is constructed.

```python
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
```

### 13. Tick granularity: daily vs biweekly

`ABMModel` and `CompartmentalModel` use **daily** ticks (1 tick = 1 day).
`BiweeklyModel` uses **14-day** ticks (1 tick = 2 weeks, 26 ticks = 1 year).

Scale `num_ticks` accordingly:

```python
# 5 years
ABMParams(num_ticks=5 * 365)          # 1825 daily ticks
BiweeklyParams(num_ticks=5 * 26)      # 130 biweekly ticks
CompartmentalParams(num_ticks=5 * 365) # 1825 daily ticks
```

### 14. Scenario `id` must be a string; `pop` must be `Int32`

Two dtype requirements that produce cryptic errors if violated:

**`id` must be a string (`str` / `Utf8`), not an integer.**
Python list comprehensions like `[0, 1, 2]` produce `Int64`, which fails
schema validation. Use string patch IDs:

```python
# WRONG — Int64 id raises: Polars dtype Int64 does not match model field type
scenario = pl.DataFrame({"id": [0, 1, 2], ...})

# CORRECT — string id
scenario = pl.DataFrame({"id": ["patch_0", "patch_1", "patch_2"], ...})
```

**`pop` (and all integer columns) must be `Int32`, not the default `Int64`.**
Python integer lists and `np.array(...)` without a dtype both produce `Int64`:

```python
import numpy as np, polars as pl

# WRONG — Int64 pop raises: Polars dtype Int64 does not match model field type
scenario = pl.DataFrame({"pop": [100_000, 80_000, 60_000], ...})

# CORRECT — explicit Int32 via numpy
scenario = pl.DataFrame({
    "pop": np.array([100_000, 80_000, 60_000], dtype=np.int32),
    ...
})

# ALSO CORRECT — build with defaults then cast
scenario = pl.DataFrame({"pop": [100_000, 80_000, 60_000], ...}).with_columns(
    pl.col("pop").cast(pl.Int32)
)
```

The scenario helper functions (`single_patch_scenario`, `two_patch_scenario`, etc.)
handle these dtypes correctly and are the safest way to build test scenarios.

### 15. Do NOT add `TransmissionProcess` separately when using `InfectionProcess` (ABM)

`InfectionProcess` already instantiates `TransmissionProcess` internally and
registers the `etimer` property on the population. Adding `TransmissionProcess`
as a separate component causes a `ValueError: Property 'etimer' already exists`.

```python
# WRONG — TransmissionProcess is already created inside InfectionProcess
model.add_component(TransmissionProcess)   # registers etimer
model.add_component(InfectionProcess)      # tries to register etimer again → crash

# CORRECT — InfectionProcess is self-contained; add it alone
model.add_component(InfectionProcess)
```

The same applies to any component that is a sub-component of another: check the
docs to see which components are stand-alone vs. internally managed.

### 16. `StateTracker` values are `StateArray` objects, not plain Python scalars

When you index into a tracker's `.S`, `.I`, `.R` (etc.) arrays you get a
`StateArray`, not a `float`. Passing a `StateArray` to an f-string format spec
(e.g. `f"{val:.4f}"`) raises `TypeError: unsupported format string`.

Always extract a Python scalar first:

```python
# WRONG — StateArray does not support format specs
frac = tracker.I[tick]
print(f"infected fraction: {frac:.4f}")   # TypeError

# CORRECT — call .item() to get a plain Python float
frac = float(tracker.I[tick])              # or tracker.I[tick].item()
print(f"infected fraction: {frac:.4f}")
```

For per-patch trackers (`aggregation_level=0`) the shape is
`(n_states, n_ticks, n_patches)` — index with `[state_idx, tick, patch_idx]`
and wrap with `int()` or `float()` before arithmetic or formatting.

### 17. SIA schedule date column must use `datetime.date` values, not strings

`SIACalendarProcess` filters the schedule by comparing a polars date column
to the current simulation date. If the column contains Python `str` values
(e.g. `"2024-06-01"`) rather than `datetime.date` objects, polars raises:

```
InvalidOperationError: cannot compare 'date/datetime/time' to a string value
```

Build the schedule with `datetime.date` objects (or cast the column):

```python
import datetime, polars as pl

# WRONG — string dates cause a polars comparison error at runtime
sia_df = pl.DataFrame({
    "date": ["2024-06-01", "2025-06-01"],
    ...
})

# CORRECT — use datetime.date objects
sia_df = pl.DataFrame({
    "date": [datetime.date(2024, 6, 1), datetime.date(2025, 6, 1)],
    ...
})
# OR cast after construction
sia_df = sia_df.with_columns(pl.col("date").str.to_date())
```

### 18. `AgePyramidTracker` — reading the age distribution data

`AgePyramidTracker` stores snapshots in its `.age_pyramid` dict, keyed by
date string (`"YYYY-MM-DD"`), with numpy histogram arrays as values.
There is no `.counts` attribute.

```python
from laser.measles.abm import AgePyramidTracker, AgePyramidTrackerParams

model.add_component(AgePyramidTracker)   # default: yearly snapshots

model.run()

# Retrieve the tracker instance
apt = model.get_instance(AgePyramidTracker)[0]

# Iterate over snapshots  {date_str: np.ndarray of counts per age bin}
for date_str, counts in apt.age_pyramid.items():
    print(f"{date_str}: total tracked = {counts.sum()}, bins = {counts}")

# Compare start vs end
dates = sorted(apt.age_pyramid.keys())
start_counts = apt.age_pyramid[dates[0]]
end_counts   = apt.age_pyramid[dates[-1]]
change = end_counts.astype(float) - start_counts.astype(float)
```

The bin edges are set by `AgePyramidTrackerParams.age_bins` (in days).
Default bins come from `pyvd.constants.MORT_XVAL[::2]`.

### 19. Per-patch attack rates from `StateTracker` (multi-patch models)

When using a per-patch tracker (`aggregation_level=0`), the raw array has
shape `(n_states, n_ticks, n_patches)`. To compute attack rates per patch
at the end of a run:

```python
import numpy as np
from laser.measles.abm import StateTracker, StateTrackerParams

# Add per-patch tracker
model.add_component(StateTracker,
                    params=StateTrackerParams(aggregation_level=0))

model.run()

st = model.get_instance(StateTracker)[1]   # index 1 = per-patch tracker
# state_tracker shape: (n_states, n_ticks, n_patches)
arr = st.state_tracker   # e.g. shape (5, 365, 10) for 10 patches

# State indices (check StateTracker docs for your model)
S_IDX, I_IDX, R_IDX = 0, 2, 3   # typical ABM order: S E I R D

initial_S = arr[S_IDX, 0, :]    # shape (n_patches,)
final_R   = arr[R_IDX, -1, :]   # shape (n_patches,)
pop       = initial_S            # approx total population per patch at t=0

attack_rate = final_R / pop      # shape (n_patches,) — fraction ever infected

# Pop must come from the scenario, NOT from tracker, for the denominator:
pop_from_scenario = scenario["pop"].to_numpy()   # Int32 array, shape (n_patches,)
attack_rate = final_R / pop_from_scenario.astype(float)
```

**Key rule**: the number of patches in the scenario must equal `n_patches`
in the tracker array. Do not mix a 100-patch scenario with a tracker
configured for 2 patches, or vice versa.

### 20. `two_cluster_scenario` returns 100 patches by default (2 × 50)

`two_cluster_scenario(n_nodes_per_cluster=50)` creates **100 patches** (2
clusters × 50 nodes each). A per-patch StateTracker will have shape
`(n_states, n_ticks, 100)`. Using a global tracker and indexing `[-1]`
gives shape `(n_states,)` which cannot be divided by a 100-element pop array.

```python
from laser.measles.scenarios import two_cluster_scenario
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
from laser.measles.biweekly import StateTracker, StateTrackerParams

scenario = two_cluster_scenario()   # 100 patches

params = BiweeklyParams(...)
model  = BiweeklyModel(scenario, params)

# Add per-patch tracker
model.add_component(StateTracker,
                    params=StateTrackerParams(aggregation_level=0))
model.run()

st = model.get_instance(StateTracker)[0]
arr = st.state_tracker                     # (n_states, n_ticks, 100)

# Attack rate per patch (biweekly model state order: S=0, I=1, R=2)
initial_S = arr[0,  0, :].astype(float)   # shape (100,)
final_R   = arr[2, -1, :].astype(float)   # shape (100,)
pop       = scenario["pop"].to_numpy().astype(float)   # shape (100,)
attack_rate = (initial_S - arr[0, -1, :]) / pop        # fraction ever infected
```

For a smaller scenario pass `n_nodes_per_cluster`:
```python
scenario = two_cluster_scenario(n_nodes_per_cluster=5)  # 10 patches
```

### 21. Multiprocessing workers must be defined at module level

Python's `multiprocessing` module uses pickle to transfer functions to worker
processes. Functions defined inside another function (closures / nested defs)
cannot be pickled and will raise:

```
AttributeError: Can't pickle local object 'run_all_models.<locals>.worker'
```

Define worker functions at the **top level** of the module, not inside
another function:

```python
# WRONG — nested function cannot be pickled
def run_all_models():
    def worker(model_type):
        ...
    with Pool() as p:
        results = p.map(worker, model_types)   # AttributeError

# CORRECT — top-level function is picklable
def _worker(model_type):
    ...

def run_all_models():
    with Pool() as p:
        results = p.map(_worker, model_types)  # works
```

Alternatively, use `concurrent.futures.ProcessPoolExecutor` with
`functools.partial` if you need to pass extra arguments.

### 22. Scenario helpers are in `laser.measles` or `laser.measles.scenarios`, not in subpackages

Scenario generators (`single_patch_scenario`, `two_patch_scenario`,
`two_cluster_scenario`, etc.) are exported from `laser.measles` and
`laser.measles.scenarios`. They are **not** available from the model-specific
subpackages (`laser.measles.abm`, `laser.measles.biweekly`, etc.).

```python
# WRONG — raises ImportError
from laser.measles.abm import single_patch_scenario

# CORRECT
from laser.measles import single_patch_scenario
# or
from laser.measles.scenarios import single_patch_scenario
```

### 23. `SIACalendarParams.aggregation_level` must be ≥ 1

`SIACalendarParams` validates that `aggregation_level >= 1`. Passing 0 raises:

```
ValueError: aggregation_level must be at least 1
```

Use `aggregation_level=1` for flat (single-level) hierarchies:

```python
from laser.measles.abm.components import SIACalendarParams
params = SIACalendarParams(aggregation_level=1, sia_schedule=schedule_df, ...)
```

For hierarchical IDs like `"country:state:lga"`, use `aggregation_level=3`.

### 24. Custom components added via `add_component` must accept `verbose`

`ABMModel.add_component(ComponentClass)` instantiates the class as
`ComponentClass(model, verbose=False)`. Any custom component class must
accept `verbose` as a keyword argument or the framework raises:

```
TypeError: MyTracker.__init__() got an unexpected keyword argument 'verbose'
```

Always include `verbose=False` in custom component `__init__`:

```python
class MyTracker:
    def __init__(self, model, verbose: bool = False):
        self.model = model
        # ...
```

### 25. `model.people` has `date_of_birth`, not `age`

The ABM people LaserFrame stores `date_of_birth` (in ticks), not an `age`
column. Accessing `model.people.age` raises `AttributeError`. To get age
in years at a given tick:

```python
# WRONG
age_years = model.people.age

# CORRECT — date_of_birth is stored in ticks
dob = model.people.date_of_birth[model.people.active.view(bool)]
current_tick = model.params.num_ticks - 1
age_ticks = current_tick - dob
age_years  = age_ticks / 365.0
```

Available people properties: `state`, `susceptibility`, `patch_id`,
`active`, `date_of_birth`, `date_of_vaccination`.

### 26. Scenario `pop` column must be integer (`Int32`), not float

The scenario DataFrame validator requires `pop` to be an integer type.
Passing a float column raises:

```
ValueError: DataFrame validation error: Column 'pop' must be integer type
```

Cast `pop` to `Int32` when building a scenario:

```python
import polars as pl

scenario = pl.DataFrame({
    "id":   ["patch_0", "patch_1"],
    "lat":  [0.0, 1.0],
    "lon":  [0.0, 1.0],
    "pop":  pl.Series([100_000, 50_000], dtype=pl.Int32),
    "mcv1": [0.8, 0.7],
})
# or cast after the fact:
scenario = scenario.with_columns(pl.col("pop").cast(pl.Int32))
```

### 27. polars `with_column` (singular) was removed — use `with_columns`

Older polars had `DataFrame.with_column(expr)` (singular). Current polars only
has `with_columns(*exprs)` (plural). Using the singular form raises:

```
AttributeError: 'DataFrame' object has no attribute 'with_column'.
Did you mean: 'with_columns'?
```

Always use the plural form:

```python
# WRONG
df = df.with_column(pl.col("pop").cast(pl.Int32))

# CORRECT
df = df.with_columns(pl.col("pop").cast(pl.Int32))
```

### 28. `get_mixing_matrix()` takes no arguments — pass `scenario` at construction

All mixing models (GravityMixing, RadiationMixing, etc.) accept the scenario
at construction time, not at `get_mixing_matrix()` call time. Calling
`mixer.get_mixing_matrix(scenario)` raises:

```
TypeError: BaseMixing.get_mixing_matrix() takes 1 positional argument but 2 were given
```

Correct pattern:

```python
from laser.measles import RadiationMixing, RadiationParams

mixer = RadiationMixing(scenario=scenario, params=RadiationParams())
mixing_matrix = mixer.get_mixing_matrix()   # no arguments
```

### 29. `lookup_state_idx` does not exist — use `params.states.index()`

There is no `lookup_state_idx` function exported from `laser.measles`. To find
state indices, use the `states` list on the model params:

```python
params = BiweeklyParams(...)   # or ABMParams, CompartmentalParams
S_IDX = params.states.index('S')
I_IDX = params.states.index('I')
R_IDX = params.states.index('R')
```

For the biweekly model the default order is `['S', 'I', 'R']` (indices 0, 1, 2).

### 30. `AgePyramidTracker.age_pyramid` is a dict keyed by date strings — not an array

`AgePyramidTracker.age_pyramid` returns a `dict[str, np.ndarray]` where the
keys are date strings (e.g. `"2000-01-01"`). Indexing with an integer raises
`KeyError`:

```python
# WRONG — age_pyramid is not a list or array
start_pyramid = tracker.age_pyramid[0]    # KeyError: 0
end_pyramid   = tracker.age_pyramid[-1]   # KeyError: -1
```

Use dict access:

```python
keys = list(tracker.age_pyramid.keys())   # sorted date strings
start_pyramid = tracker.age_pyramid[keys[0]]   # first recorded date
end_pyramid   = tracker.age_pyramid[keys[-1]]  # last recorded date
```

Or iterate:

```python
first_array = next(iter(tracker.age_pyramid.values()))
```

### 31. `numpy` has no `cummax` — use `np.maximum.accumulate`

`np.cummax` does not exist in NumPy. The equivalent is `np.maximum.accumulate`:

```python
# WRONG
result = np.cummax(arr)          # AttributeError: module 'numpy' has no attribute 'cummax'

# CORRECT
result = np.maximum.accumulate(arr)
```

### 32. `AgePyramidTracker.age_pyramid` key format — do not hardcode date strings

The keys of `age_pyramid` are date strings generated internally and may not
match the format you expect (e.g. `'2005-01-01'` vs `'2005-1-1'`). Always
retrieve keys dynamically:

```python
keys = sorted(tracker.age_pyramid.keys())
start_pyramid = tracker.age_pyramid[keys[0]]   # first snapshot
end_pyramid   = tracker.age_pyramid[keys[-1]]  # last snapshot
```

Never do `tracker.age_pyramid['2005-01-01']` — use `keys[-1]` instead.
