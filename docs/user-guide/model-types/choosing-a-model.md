# How to choose a model type

laser-measles provides three model types that represent the same measles epidemiology at different levels of detail. Use this guide to select the right model for your analysis.

## Decision guide

Start with the question that best matches your situation:

**Do you need to track individual people** (age-specific immunity, individual vaccination records, person-level migration)?

- **Yes** → Use the **ABM**. It is the only model type that represents individual agents.
- **No** → Continue below.

**Do you need daily temporal resolution** (fitting to weekly/daily surveillance data, capturing the exposed-to-infectious transition)?

- **Yes** → Use the **Compartmental model**. It runs daily SEIR dynamics at compartment level.
- **No** → Continue below.

**Do you need to run many scenarios quickly** (parameter sweeps, sensitivity analysis, intervention comparisons)?

- **Yes** → Use the **Biweekly model**. It is the fastest model and is designed for large-scale exploration.
- **No** → Either the biweekly or compartmental model will work. Start with whichever is simpler for your use case.

## Common scenarios

### "I want to compare vaccination strategies across dozens of coverage levels"

Use the **biweekly model**. Its speed makes it practical to run hundreds of parameter combinations. Each run completes in seconds for moderate-sized countries, so you can sweep coverage from 50% to 95% in 1% increments without waiting hours.

### "I need to fit model parameters to weekly case reports"

Use the **compartmental model**. Its daily timesteps align well with weekly reporting intervals, and its SEIR structure captures the incubation delay that matters when fitting outbreak curves. The compartmental model is fast enough for iterative fitting while maintaining temporal fidelity.

### "I want to model age-targeted supplementary immunization activities (SIAs)"

Use the **ABM**. SIAs target specific age groups, and only the ABM tracks individual ages and vaccination histories. The ABM can determine which agents are eligible for a campaign based on their age and prior vaccination status.

### "I want to understand stochastic fadeout in small island populations"

Use the **ABM**. Stochastic fadeout — where an epidemic dies out because the last few infectious individuals happen to recover before transmitting — is an individual-level phenomenon. Compartmental models can approximate this with stochastic draws, but the ABM captures it naturally because it tracks each person.

### "I want a quick first look at measles dynamics in a new country"

Use the **biweekly model**. Set up your scenario data, run a few exploratory simulations to check that the dynamics are reasonable, then switch to a more detailed model if needed. The shared interface means your scenario data and component choices transfer directly.

### "I have limited compute resources and need to model a large country"

Start with the **biweekly model**. Its low computational cost means you can model a country with hundreds of administrative units on a standard laptop in seconds. If you need finer temporal resolution later, the **compartmental model** is the next step — it runs daily dynamics at population level without the memory overhead of the ABM. Reserve the ABM for situations where individual-level detail is essential, and consider [snapshotting](../snapshotting/index.md) to split long ABM runs into manageable segments.

## Switching between models

Because all three models share the same scenario format and component system, switching is straightforward. The main changes are:

1. **Import the different model and params classes** — e.g., change `ABMModel, ABMParams` to `BiweeklyModel, BiweeklyParams`.
2. **Adjust `num_ticks`** — the biweekly model uses 14-day ticks (26 per year), while the ABM and compartmental model use daily ticks (365 per year).
3. **Use model-specific components** — each model type has its own component implementations under `laser.measles.abm.components`, `laser.measles.biweekly.components`, or `laser.measles.compartmental.components`.

```python
# Biweekly: 10 years = 260 ticks
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
params = BiweeklyParams(num_ticks=260, seed=42, start_time="2000-01")
model = BiweeklyModel(scenario, params)

# Compartmental: 10 years = 3650 ticks
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
params = CompartmentalParams(num_ticks=3650, seed=42, start_time="2000-01")
model = CompartmentalModel(scenario, params)

# ABM: 10 years = 3650 ticks
from laser.measles.abm import ABMModel, ABMParams
params = ABMParams(num_ticks=3650, seed=42, start_time="2000-01")
model = ABMModel(scenario, params)
```

## See also

- [Model types](index.md) — detailed explanation of each model's properties and trade-offs
- [Worked examples](../components/worked-examples.md) — complete runnable scripts for all three models
- [Configuring spatial mixing](configuring-spatial-mixing.md) — how to set up disease spread between patches
- [Snapshotting](../snapshotting/index.md) — save and resume long simulations in segments
- [Tutorials](../../tutorials/index.md) — hands-on walkthroughs starting with the [Quick start](../../tutorials/tut_quickstart_hello_world.py)
