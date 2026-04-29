# Worked examples

These end-to-end scripts are copy-paste runnable. Each one shows the
**full** pattern — imports, scenario, params, model construction, component
wiring, running, and result retrieval — with detailed inline comments on
every line that commonly causes errors.

## The three non-negotiable constructor facts

!!! warning

    **Read this before writing any model code.**

    These three facts are the source of the most common runtime failures.
    They apply to every model type without exception.

**The only three model classes are** `ABMModel`, `BiweeklyModel`, `CompartmentalModel`

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

**The constructor signature is always** `Model(scenario, params)`

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

`start_time` **must be** `"YYYY-MM"`, **never** `"YYYY-MM-DD"`

```python
# CORRECT — "YYYY-MM" format
params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
```

!!! warning

    Passing a full date string raises a Pydantic `ValidationError` at
    construction time, before the simulation runs:

    Do not pass a full date string like `"2000-01-01"` — it raises
    `ValidationError: start_time must be in 'YYYY-MM' format`.

---

## Example 1 — ABM: Single-patch outbreak with StateTracker

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

---

## Example 2 — Biweekly: Five-patch endemic run with per-patch StateTracker

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

---

## Example 3 — Compartmental: R0 sweep with InfectionParams

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

## See also

- [Model types](../model-types/index.md) — overview of the three model types and when to use each
- [Components](index.md) — component architecture and design
- [Troubleshooting](troubleshooting.md) — common pitfalls and error resolution
- [Tutorials](../tutorials/index.md) — interactive learning with Jupyter notebooks
