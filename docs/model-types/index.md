# Model types

laser-measles provides three complementary modeling approaches for simulating measles transmission dynamics, each optimized for different use cases:

1. **ABM (Agent-Based Model)**: Individual-level simulation with stochastic agents
2. **Biweekly Compartmental Model**: Population-level SIR dynamics with 2-week timesteps
3. **Compartmental Model**: Population-level SEIR dynamics with daily timesteps

Each model type offers different trade-offs between computational efficiency, temporal resolution, and modeling detail.

---

## ABM (agent-based model)

The ABM model provides individual-level simulation with stochastic agents, allowing for detailed tracking of disease dynamics at the person level.

**Key characteristics:**

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

## Biweekly model

The biweekly model is a compartmental model optimized for fast simulation and parameter exploration with 2-week timesteps.

**Key characteristics:**

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

## Compartmental model

The compartmental model provides population-level SEIR dynamics with daily timesteps, optimized for parameter estimation and detailed outbreak modeling.

**Key characteristics:**

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

    Do not pass only `scenario` to the constructor — omitting `params`
    raises `TypeError: missing 1 required positional argument: 'params'`.

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

## See also

- [Tutorials](../tutorials/index.md) — hands-on learning with each model type
- [Worked examples](../components/worked-examples.md) — copy-paste runnable scripts for all three models
- [Demographics](demographics.md) — geographic data handling for spatial scenarios
- [API reference](../reference/laser/measles/index.md) — full parameter and class details
