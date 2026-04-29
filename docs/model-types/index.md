# Model types

laser-measles provides three complementary modeling approaches for simulating measles transmission dynamics. Each approach represents the same underlying epidemiology — susceptible individuals become exposed, then infectious, then recovered — but differs in how it tracks populations, how finely it resolves time, and how much computation it requires.

The three model types share a common interface: all accept a scenario DataFrame and a params object, use the same component system, and produce compatible output arrays. This means you can start with the fastest model for exploratory work and switch to a more detailed model for final analysis without rewriting your pipeline.

## How the three models differ

### ABM (agent-based model)

The ABM represents every person as a discrete agent with individual properties — age, location, disease state, vaccination history. Transmission, recovery, and demographic events (births, deaths, aging) happen to individual agents via stochastic draws at each daily timestep.

This level of detail makes the ABM the right choice when individual heterogeneity matters: when you need to track age-specific immunity profiles, model individual vaccination records, or capture stochastic fadeout in small populations. The cost is computation — simulating millions of individual agents is orders of magnitude slower than compartmental arithmetic.

**Key properties:**

- **Timestep**: 1 day
- **Disease states**: SEIR (Susceptible → Exposed → Infectious → Recovered)
- **Population representation**: Individual agents with properties (age, patch, state, vaccination date)
- **Stochasticity**: Individual-level probabilistic events
- **Snapshotting**: Supported (save/resume long runs)

### Biweekly model

The biweekly model tracks population *counts* in each compartment rather than individual agents. It uses 14-day timesteps and an SIR (not SEIR) structure — the exposed compartment is omitted because the 14-day timestep is comparable to measles' incubation period (~10–14 days), making the distinction between exposed and infectious negligible at this resolution.

This model is the fastest of the three and is designed for parameter exploration, scenario comparison, and policy analysis where you need to run hundreds or thousands of parameter combinations. Binomial sampling provides realistic stochastic variability without the overhead of tracking individuals.

**Key properties:**

- **Timestep**: 14 days (26 ticks per year)
- **Disease states**: SIR (Susceptible → Infectious → Recovered)
- **Population representation**: Compartment counts per patch (Polars DataFrames)
- **Stochasticity**: Binomial sampling at compartment level
- **Snapshotting**: Not currently supported

### Compartmental model

The compartmental model also tracks population counts rather than individuals, but uses daily timesteps and a full SEIR structure. This gives it finer temporal resolution than the biweekly model while remaining faster than the ABM.

This model is well suited for fitting to surveillance data (where daily or weekly case counts are available), detailed outbreak analysis, and situations where the exposed-to-infectious transition timing matters. Like the biweekly model, it uses efficient array arithmetic; unlike the biweekly model, it captures the incubation period explicitly.

**Key properties:**

- **Timestep**: 1 day (365 ticks per year)
- **Disease states**: SEIR (Susceptible → Exposed → Infectious → Recovered)
- **Population representation**: Compartment counts per patch
- **Stochasticity**: Optional stochastic elements over a deterministic core
- **Snapshotting**: Supported (save/resume long runs)

---

## Trade-offs at a glance

| | ABM | Biweekly | Compartmental |
|---|---|---|---|
| **Resolution** | Individual agents | Compartment counts | Compartment counts |
| **Timestep** | 1 day | 14 days | 1 day |
| **Disease model** | SEIR | SIR | SEIR |
| **Speed** | Slowest | Fastest | Middle |
| **Memory** | Highest (one record per agent) | Lowest | Low |
| **Individual tracking** | Yes (age, vaccination, location) | No | No |
| **Stochastic fadeout** | Naturally captured | Approximated | Approximated |
| **Parameter sweeps** | Expensive | Cheap | Moderate |
| **Snapshotting** | ✅ | ❌ | ✅ |

---

## Shared interface

All three model types follow the same construction and execution pattern:

```python
# 1. Import the model type and its params class
from laser.measles.abm import ABMModel, ABMParams
# or: from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
# or: from laser.measles.compartmental import CompartmentalModel, CompartmentalParams

# 2. Create parameters
params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")

# 3. Construct the model with scenario data and params
model = ABMModel(scenario_data, params)

# 4. Add components
model.add_component(SomeProcess)
model.add_component(AnotherProcess)

# 5. Run
model.run()
```

All three constructors require both `scenario` and `params` — omitting `params` raises `TypeError`.

The scenario DataFrame must include these columns regardless of model type:

| Column | Type | Description |
|---|---|---|
| `id` | str | Patch identifier |
| `pop` | int | Population count |
| `lat` | Float64 | Latitude (degrees) |
| `lon` | Float64 | Longitude (degrees) |
| `mcv1` | Float64 | MCV1 vaccination coverage (0–1) |

---

## See also

- [Choosing a model type](choosing-a-model.md) — decision guide for selecting the right model
- [Spatial mixing](spatial-mixing.md) — how inter-patch transmission works across all model types
- [Demographics](demographics.md) — preparing geographic scenario data
- [Snapshotting](../snapshotting/index.md) — save and resume long ABM or compartmental runs
- [Components](../components/index.md) — component architecture shared across all model types
- [Tutorials](../tutorials/index.md) — hands-on learning with each model type
- [Worked examples](../components/worked-examples.md) — runnable scripts for all three models
- [API reference](../reference/laser/measles/index.md) — full parameter and class details
