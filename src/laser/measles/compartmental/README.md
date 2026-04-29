# Compartmental model

Compartmental SEIR model using daily timesteps. This model implements stochastic disease transmission dynamics with four compartments: Susceptible, Exposed, Infected, and Recovered.

## Model overview

The compartmental model uses:
- **Daily timesteps** (1-day intervals) for fine-grained temporal resolution
- **SEIR compartments**: S → E → I → R disease progression
- **Stochastic transitions** using binomial sampling for realistic variability
- **Spatial mixing** via gravity diffusion based on population and distance
- **Seasonal transmission** with configurable amplitude and timing

## Key features

### SEIR dynamics
- **S → E**: Susceptible individuals become exposed based on force of infection
- **E → I**: Exposed individuals become infectious at rate σ (1/incubation_period)
- **I → R**: Infectious individuals recover at rate γ (1/infectious_period)
- **Basic reproduction number**: R₀ = β/γ

### Parameters
- **β (beta)**: Transmission rate per day
- **σ (sigma)**: Progression rate from exposed to infectious (1/incubation_period)
- **γ (gamma)**: Recovery rate from infection (1/infectious_period)
- **Seasonality**: Optional seasonal variation in transmission
- **Spatial mixing**: Gravity model with configurable distance decay

## Example

```python
import polars as pl
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
from laser.measles.compartmental import InitializeEquilibriumStatesProcess
from laser.measles.compartmental import InfectionSeedingProcess, InfectionProcess, StateTracker

scenario = pl.DataFrame({
    "id": ["patch_0", "patch_1", "patch_2"],
    "lat": [11.0, 12.0, 13.0],
    "lon": [8.0, 9.0, 10.0],
    "pop": [10_000, 15_000, 12_000],
    "mcv1": [0.8, 0.75, 0.85],
})

params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
model = CompartmentalModel(scenario, params)

model.add_component(InitializeEquilibriumStatesProcess)
model.add_component(InfectionSeedingProcess)
model.add_component(InfectionProcess)
model.add_component(StateTracker)

model.run()

tracker = model.get_instance("StateTracker")[0]
print(f"Peak infections: {int(tracker.I.max())}")
```

## Recommended for

- **Parameter estimation**: Calibrate epidemiological parameters against surveillance data
- **Outbreak modeling**: Track disease spread with realistic incubation dynamics
- **Scenario planning**: Compare different control strategies and timing
