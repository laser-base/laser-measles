# How to configure spatial mixing

This guide shows how to set up a spatial mixing model and attach it to an infection component so that disease spreads between patches.

## Choose a mixing model

Select one of the four available models based on your needs:

| Model | Best for | Key advantage |
|---|---|---|
| `GravityMixing` | General use, calibration to travel data | Intuitive, tunable parameters |
| `RadiationMixing` | Minimal calibration needed | Nearly parameter-free |
| `CompetingDestinationsMixing` | Clustered urban areas | Captures destination competition |
| `StoufferMixing` | Terrain-constrained travel | Distance-independent opportunity model |

If you are unsure, start with `GravityMixing` — it is the most widely used in epidemiological modeling.

## Set up the mixer

Create the mixer with its parameter object. You do not need to pass the scenario data — the model provides it automatically before the first timestep.

```python
from laser.measles.mixing import GravityMixing, GravityParams

# Default parameters
mixer = GravityMixing(params=GravityParams())

# Custom parameters — stronger distance decay, lower mobility
mixer = GravityMixing(params=GravityParams(k=0.005, c=2.0))
```

For the radiation model:

```python
from laser.measles.mixing import RadiationMixing, RadiationParams

mixer = RadiationMixing(params=RadiationParams(k=0.01))
```

## Attach the mixer to an infection component

Pass the mixer to the infection component's parameter class. The exact parameter class depends on your model type.

```python
from laser.measles.compartmental import components

# Create infection parameters with the mixer
infection_params = components.InfectionParams(beta=0.8, mixer=mixer)

# Add the infection component to the model
model.add_component(components.InfectionProcess, infection_params)
```

The infection component reads the mixing matrix at each timestep to distribute infectious pressure across patches.

## Inspect the mixing matrix before running

If you want to examine the mixing matrix before running a simulation, pass the scenario data explicitly:

```python
from laser.measles.mixing import GravityMixing, GravityParams

mixer = GravityMixing(
    scenario=scenario_data,
    params=GravityParams(k=0.01, c=1.5)
)

# The mixing matrix is computed lazily on first access
print(mixer.mixing_matrix.shape)  # (N, N) where N = number of patches
print(mixer.mixing_matrix.sum(axis=1))  # Should be all 1.0 (row-stochastic)
```

You can also check trip volumes:

```python
# Average trips into each patch per timestep
trips_in = mixer.trips_into()

# Average trips out of each patch per timestep
trips_out = mixer.trips_out_of()
```

## Adjust the scale parameter `k`

The `k` parameter controls overall mobility. Start with the default (`k=0.01`) and adjust based on your study:

- **Increase `k`** if spatial spread is too slow compared to surveillance data.
- **Decrease `k`** if outbreaks synchronize across patches faster than observed.
- **Set `k=0`** to disable inter-patch transmission entirely (useful for debugging).

The right value depends on your timestep length, geographic scale, and study population. For a country-level simulation with admin-2 patches and daily timesteps, values between 0.001 and 0.05 are typical.

## Switch between mixing models

Because all mixers share the same `BaseMixing` interface, switching models requires only changing the import and parameter class:

```python
# Switch from gravity to radiation
from laser.measles.mixing import RadiationMixing, RadiationParams

mixer = RadiationMixing(params=RadiationParams(k=0.01))
# Then pass to infection_params as before
```

The rest of your code — infection component setup, model construction, analysis — remains unchanged.

## See also

- [Spatial mixing](spatial-mixing.md) — conceptual explanation of the four mixing models
- [Tutorial: Spatial mixing](../tutorials/tut_spatial_mixing.py) — hands-on tutorial on spatial mixing
- [Worked examples](../components/worked-examples.md) — complete runnable scripts showing component wiring
- [Troubleshooting](../components/troubleshooting.md) — common issues with mixing and components
- [API reference](../reference/laser/measles/mixing/index.md) — full parameter details
