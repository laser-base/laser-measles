# Troubleshooting

This page documents common pitfalls when writing `laser-measles` models.
If you encounter unexpected `ImportError`, tracker shape mismatches, or
component configuration errors, check the items below first.

These issues occur frequently when users are learning the component system
or adapting code between the ABM, biweekly, and compartmental models.

---

## Imports and namespaces

### Where does `create_component` come from?

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

### How do I access component classes and their parameter classes?

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

    Do not import `InfectionParams` from `laser.measles.components` or from
    `laser.measles` directly — those paths raise `ImportError`. Always import
    model-specific classes from the correct model subpackage
    (`laser.measles.abm`, `laser.measles.biweekly`, or
    `laser.measles.compartmental`).

    Do not import scenario helpers (`single_patch_scenario`,
    `two_patch_scenario`, `two_cluster_scenario`) from `laser.measles.abm`
    or any model subpackage — they are not there. Import them from
    `laser.measles` or `laser.measles.scenarios`:

    ```python
    # CORRECT — import each class from its own model subpackage
    from laser.measles.abm import InfectionParams            # ABM variant
    from laser.measles.biweekly import InfectionParams       # Biweekly variant
    from laser.measles.compartmental import InfectionParams  # Compartmental variant

    # Scenario helpers live at the top level or laser.measles.scenarios:
    from laser.measles import single_patch_scenario, two_patch_scenario, two_cluster_scenario
    # or equivalently:
    from laser.measles.scenarios import single_patch_scenario
    ```

    `NoBirthsProcess` and `SIACalendarProcess` exist in the ABM subpackage only —
    there is no equivalent in the biweekly or compartmental subpackages.

### There is no `lm` object in `laser.measles`

The top-level `laser.measles` package does **not** export a convenience
object such as `lm`.

Some tutorials or AI-generated examples use this alias, but it is not part
of the package API.

Do not try `from laser.measles import lm` — it raises `ImportError`.
Import the specific model class directly:

```python
# CORRECT
from laser.measles.abm import ABMModel, ABMParams
```

### Scenario helpers are in `laser.measles` or `laser.measles.scenarios`, not in subpackages

Scenario generators (`single_patch_scenario`, `two_patch_scenario`,
`two_cluster_scenario`, etc.) are exported from `laser.measles` and
`laser.measles.scenarios`. They are **not** available from the model-specific
subpackages (`laser.measles.abm`, `laser.measles.biweekly`, etc.).

Do not import scenario helpers from `laser.measles.abm`,
`laser.measles.biweekly`, or `laser.measles.compartmental` — they are
not defined there and will raise `ImportError`. Always import them from
`laser.measles` or `laser.measles.scenarios`:

```python
# CORRECT
from laser.measles import single_patch_scenario
# or
from laser.measles.scenarios import single_patch_scenario
```

---

## Model construction

### `model.components` is assigned *after* construction

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

Do not pass `components` as a constructor argument — it raises
`TypeError: unexpected keyword argument "components"`. Always assign
`model.components` as a separate statement after construction.

This applies to all three model types:

- `ABMModel`
- `BiweeklyModel`
- `CompartmentalModel`

### Components are classes, not instances

Components should be passed as **classes**, not instantiated objects.

The model constructs the component instances internally.

```python
# CORRECT — pass the class, not an instance
model.components = [
    InfectionProcess
]
```

Do not instantiate components before adding them. Neither
`model.components = [InfectionProcess()]` nor
`model.add_component(InfectionProcess())` works — the model
constructs component instances internally. Passing an already-created
instance causes `TypeError: 'InfectionProcess' object is not callable`.

If parameters are needed, use `create_component`:

```python
model.components = [
    create_component(
        InfectionProcess,
        params=InfectionParams(beta=0.8)
    )
]
```

### `VitalDynamicsProcess` must be the first component

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

Do not add `InitializeEquilibriumStatesProcess` or any other component
before `VitalDynamicsProcess`. If `VitalDynamicsProcess` is not first,
the `LaserFrame` is already initialized at the wrong capacity and will
crash at runtime.

### Do NOT add `TransmissionProcess` separately when using `InfectionProcess` (ABM)

`InfectionProcess` already instantiates `TransmissionProcess` internally and
registers the `etimer` property on the population. Adding `TransmissionProcess`
as a separate component causes a `ValueError: Property 'etimer' already exists`.

Do not add `TransmissionProcess` separately — `InfectionProcess` already
creates it internally. Adding `TransmissionProcess` before or alongside
`InfectionProcess` causes `ValueError: Property 'etimer' already exists`.

```python
# CORRECT — InfectionProcess is self-contained; add it alone
model.add_component(InfectionProcess)
```

The same applies to any component that is a sub-component of another: check the
docs to see which components are stand-alone vs. internally managed.

### Custom components added via `add_component` must accept `verbose`

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

---

## Scenario DataFrames

### Scenario DataFrame must contain required columns

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

### `lat` and `lon` columns must be `Float64`, not `Int64`

The scenario schema requires `lat` and `lon` to be floating-point.
Using Python's `range()` or integer literals produces `Int64` columns,
which fail Polars schema validation when the model is constructed.

Do not use `[0] * N` or `list(range(N))` for `lat`/`lon` columns —
Python integer lists produce `Int64` which fails schema validation.
Always use float literals:

```python
# CORRECT — explicit float literals
scenario = pl.DataFrame({
    "id":   [f"patch_{i}" for i in range(5)],
    "pop":  [10_000] * 5,
    "lat":  [0.0] * 5,
    "lon":  [float(i) for i in range(5)],
    "mcv1": [0.0] * 5,
})
```

### Scenario `id` must be a string; `pop` must be `Int32`

Two dtype requirements that produce cryptic errors if violated:

**`id` must be a string (`str` / `Utf8`), not an integer.**
Python list comprehensions like `[0, 1, 2]` produce `Int64`, which fails
schema validation. Use string patch IDs:

Do not use integer lists for `id` — `[0, 1, 2]` produces `Int64` which
fails schema validation. Always use string patch IDs:

```python
# CORRECT — string id
scenario = pl.DataFrame({"id": ["patch_0", "patch_1", "patch_2"], ...})
```

**`pop` (and all integer columns) must be `Int32`, not the default `Int64`.**
Python integer lists and `np.array(...)` without a dtype both produce `Int64`:

Do not use plain Python integer lists for `pop` — `[100_000, ...]`
produces `Int64` which fails schema validation. Use `np.array(..., dtype=np.int32)`:

```python
import numpy as np, polars as pl

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

### Scenario `pop` column must be integer (`Int32`), not float

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

### Use `laser.measles.scenarios.synthetic` for test scenarios

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

### `two_cluster_scenario` returns 100 patches by default (2 × 50)

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

---

## StateTracker

### `StateTracker` output shape depends on `aggregation_level`

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

### Retrieval of results from `StateTracker`

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

The following attributes do not exist on any tracker and will raise
`AttributeError`: `tracker.data`, `tracker.results`, `tracker.to_polars()`,
`tracker.df`. Use `get_dataframe()` for global trackers or `.state_tracker`
for per-patch trackers.

### `StateTracker` values are `StateArray` objects, not plain Python scalars

When you index into a tracker's `.S`, `.I`, `.R` (etc.) arrays you get a
`StateArray`, not a `float`. Passing a `StateArray` to an f-string format spec
(e.g. `f"{val:.4f}"`) raises `TypeError: unsupported format string`.

Always extract a Python scalar first:

Do not use `tracker.I[tick]` directly in f-string format specs like
`f"{frac:.4f}"` — `StateArray` does not support format specs and raises
`TypeError`.

```python
# CORRECT — call float() or .item() to get a plain Python float
frac = float(tracker.I[tick])              # or tracker.I[tick].item()
print(f"infected fraction: {frac:.4f}")
```

For per-patch trackers (`aggregation_level=0`) the shape is
`(n_states, n_ticks, n_patches)` — index with `[state_idx, tick, patch_idx]`
and wrap with `int()` or `float()` before arithmetic or formatting.

### Cast NumPy scalars before building a Polars DataFrame

Tracker arrays are NumPy arrays, so operations like `.max()` return
NumPy scalar types (`np.int64`, `np.float64`).

Polars expects **Python primitive types** when constructing row-oriented
DataFrames. Passing NumPy scalars can trigger `TypeError` or
`DataOrientationWarning`.

Do not pass NumPy scalar results (e.g. `tracker.I[:, p].max()`) directly
to Polars DataFrame constructors — wrap with `int()` or call `.item()`:

```python
# CORRECT
rows.append([patch_id, int(tracker.I[:, p].max())])
```

An alternative is to use `.item()`:

```python
rows.append([patch_id, tracker.I[:, p].max().item()])
```

### Per-patch attack rates from `StateTracker` (multi-patch models)

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

### `lookup_state_idx` does not exist — use `params.states.index()`

There is no `lookup_state_idx` function exported from `laser.measles`. To find
state indices, use the `states` list on the model params:

```python
params = BiweeklyParams(...)   # or ABMParams, CompartmentalParams
S_IDX = params.states.index('S')
I_IDX = params.states.index('I')
R_IDX = params.states.index('R')
```

For the biweekly model the default order is `['S', 'I', 'R']` (indices 0, 1, 2).

---

## Tick granularity and time

### Tick granularity: Daily vs. biweekly

`ABMModel` and `CompartmentalModel` use **daily** ticks (1 tick = 1 day).
`BiweeklyModel` uses **14-day** ticks (1 tick = 2 weeks, 26 ticks = 1 year).

Scale `num_ticks` accordingly:

```python
# 5 years
ABMParams(num_ticks=5 * 365)          # 1825 daily ticks
BiweeklyParams(num_ticks=5 * 26)      # 130 biweekly ticks
CompartmentalParams(num_ticks=5 * 365) # 1825 daily ticks
```

### SIA schedule date column must use `datetime.date` values, not strings

`SIACalendarProcess` filters the schedule by comparing a polars date column
to the current simulation date. If the column contains Python `str` values
(e.g. `"2024-06-01"`) rather than `datetime.date` objects, polars raises:

```
InvalidOperationError: cannot compare 'date/datetime/time' to a string value
```

Build the schedule with `datetime.date` objects (or cast the column):

Do not use string literals like `"2024-06-01"` for the `date` column —
polars raises `InvalidOperationError` when comparing a string column to
a date. Always use `datetime.date` objects:

```python
import datetime, polars as pl

# CORRECT — use datetime.date objects
sia_df = pl.DataFrame({
    "date": [datetime.date(2024, 6, 1), datetime.date(2025, 6, 1)],
    ...
})
# OR cast after construction
sia_df = sia_df.with_columns(pl.col("date").str.to_date())
```

### `SIACalendarParams.aggregation_level` must be ≥ 1

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

---

## ABM-specific issues

### `model.people` has `date_of_birth`, not `age`

The ABM people LaserFrame stores `date_of_birth` (in ticks), not an `age`
column. Accessing `model.people.age` raises `AttributeError`. To get age
in years at a given tick:

Do not access `model.people.age` — that attribute does not exist and raises
`AttributeError`. Use `date_of_birth` (stored in ticks) instead:

```python
# CORRECT — date_of_birth is stored in ticks
dob = model.people.date_of_birth[model.people.active.view(bool)]
current_tick = model.params.num_ticks - 1
age_ticks = current_tick - dob
age_years  = age_ticks / 365.0
```

Available people properties: `state`, `susceptibility`, `patch_id`,
`active`, `date_of_birth`, `date_of_vaccination`.

### Read the age distribution data from `AgePyramidTracker`

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

### `AgePyramidTracker.age_pyramid` is a dict keyed by date strings — not an array

`AgePyramidTracker.age_pyramid` returns a `dict[str, np.ndarray]` where the
keys are date strings (e.g. `"2000-01-01"`). Indexing with an integer raises
`KeyError`:

Do not index `age_pyramid` with integers — it is a dict, not a list.
`tracker.age_pyramid[0]` raises `KeyError: 0`. Use dict access:

```python
keys = list(tracker.age_pyramid.keys())   # sorted date strings
start_pyramid = tracker.age_pyramid[keys[0]]   # first recorded date
end_pyramid   = tracker.age_pyramid[keys[-1]]  # last recorded date
```

Or iterate:

```python
first_array = next(iter(tracker.age_pyramid.values()))
```

### `AgePyramidTracker.age_pyramid` key format — do not hard code date strings

The keys of `age_pyramid` are date strings generated internally and may not
match the format you expect (e.g. `'2005-01-01'` vs `'2005-1-1'`). Always
retrieve keys dynamically:

```python
keys = sorted(tracker.age_pyramid.keys())
start_pyramid = tracker.age_pyramid[keys[0]]   # first snapshot
end_pyramid   = tracker.age_pyramid[keys[-1]]  # last snapshot
```

Never do `tracker.age_pyramid['2005-01-01']` — use `keys[-1]` instead.

---

## Parameters and data types

### Never pass a plain dict as `params` to `create_component` or model constructors

All params objects (`ABMParams`, `BiweeklyParams`, `InfectionParams`, etc.)
are **Pydantic models**, not plain dicts. Passing a dict raises
`AttributeError` immediately at model construction — `BaseLaserModel.__init__`
accesses `params.verbose` and `params.start_time` before any component runs.

Always instantiate the typed params class:

```python
# CORRECT — use the typed Pydantic class
from laser.measles.abm import InfectionProcess, InfectionParams
from laser.measles.abm import InfectionSeedingProcess, InfectionSeedingParams
from laser.measles import create_component

model.components = [
    create_component(
        InfectionSeedingProcess,
        params=InfectionSeedingParams(target_patches=["patch_0"])
    ),
    create_component(
        InfectionProcess,
        params=InfectionParams(beta=1.2)
    ),
]
```

Do not write `params={"beta": 1.2}` — this will fail immediately at model
construction with `AttributeError: 'dict' object has no attribute 'verbose'`.

### Do not use try/except import blocks or dict fallbacks for params

Do not write defensive import blocks like:

```
try:
    InfectionParams = ...
except ImportError:
    InfectionParams = None
```

and then fall back to passing a dict as params. These fallback patterns
produce broken code. If an import fails, fix the import path rather than
working around it. Consult [How do I access component classes and their parameter classes?](#how-do-i-access-component-classes-and-their-parameter-classes) for correct import paths.

### Polars `with_column` (singular) was removed — use `with_columns`

Older Polars had `DataFrame.with_column(expr)` (singular). Current Polars only
has `with_columns(*exprs)` (plural). Using the singular form raises:

```
AttributeError: 'DataFrame' object has no attribute 'with_column'.
Did you mean: 'with_columns'?
```

Always use the plural form `with_columns` (not `with_column`):

```python
# CORRECT
df = df.with_columns(pl.col("pop").cast(pl.Int32))
```

### `numpy` has no `cummax` — use `np.maximum.accumulate`

`np.cummax` does not exist in NumPy. The equivalent is `np.maximum.accumulate`:

Do not use `np.cummax` — it does not exist in NumPy and raises
`AttributeError`. Use `np.maximum.accumulate` instead:

```python
# CORRECT
result = np.maximum.accumulate(arr)
```

---

## Mixing models

### `get_mixing_matrix()` takes no arguments — pass `scenario` at construction

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

---

## Multiprocessing

### Multiprocessing workers must be defined at module level

Python's `multiprocessing` module uses pickle to transfer functions to worker
processes. Functions defined inside another function (closures / nested defs)
cannot be pickled and will raise:

```
AttributeError: Can't pickle local object 'run_all_models.<locals>.worker'
```

Define worker functions at the **top level** of the module, not inside
another function:

Do not define worker functions inside another function (closures /
nested defs) — they cannot be pickled and raise
`AttributeError: Can't pickle local object`. Define the worker at the
**top level** of the module:

```python
# CORRECT — top-level function is picklable
def _worker(model_type):
    ...

def run_all_models():
    with Pool() as p:
        results = p.map(_worker, model_types)  # works
```

Alternatively, use `concurrent.futures.ProcessPoolExecutor` with
`functools.partial` if you need to pass extra arguments.

---

## See also

- [Worked examples](components/worked-examples.md) — complete runnable scripts for all three model types
- [Components](components/index.md) — component architecture and design
- [How to create a custom component](components/custom-component.md) — guide to writing your own components
- [Model types](model-types/index.md) — overview of ABM, biweekly, and compartmental models
- [Choosing a model type](model-types/choosing-a-model.md) — decision guide for selecting the right model
- [Snapshotting](snapshotting/index.md) — save and resume simulations (common source of component-list errors)
- [API reference](../reference/laser/measles/index.md) — full class and parameter details
