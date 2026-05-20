# How to create a custom component

This guide walks through creating a custom component for laser-measles. Components are modular pieces that execute once per timestep to modify model state or record metrics.

## Decide what your component does

Components fall into two categories:

- **Process components** modify model state — they move people between compartments, apply interventions, or update demographics. Inherit from `BasePhase`.
- **Tracker components** record metrics without modifying state — they log compartment counts, case counts, or other outputs. Inherit from `BaseComponent`.

## Create a process component

A process component needs three things: an `__init__` method, an `_initialize` method (called once before the simulation loop), and a `__call__` method (called every timestep).

Here is a minimal example — a component that applies a one-time pulse vaccination campaign at a specified tick:

```python
from laser.measles.base import BaseLaserModel, BasePhase

class PulseVaccinationProcess(BasePhase):
    """Vaccinates a fixed fraction of susceptibles at a specified tick."""

    def __init__(self, model, verbose=False, coverage=0.5, target_tick=100):
        super().__init__(model, verbose)
        self.coverage = coverage
        self.target_tick = target_tick

    def _initialize(self, model: BaseLaserModel) -> None:
        # Called once before model.run() starts the simulation loop.
        # Use this for setup that depends on other components being present.
        pass

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        # Called every timestep. This is where the work happens.
        if tick != self.target_tick:
            return

        states = model.patches.states
        vaccinated = (states.S * self.coverage).astype(states.dtype)
        states.S -= vaccinated
        states.R += vaccinated

        if self.verbose:
            print(f"Tick {tick}: vaccinated {vaccinated.sum()} individuals")
```

## Create a tracker component

Tracker components record data but do not modify model state. They inherit from `BaseComponent` and implement `__call__` to collect data at each timestep.

```python
import numpy as np
from laser.measles.base import BaseLaserModel, BasePhase

class IncidenceTracker(BasePhase):
    """Records new infections per patch at each timestep."""

    def __init__(self, model, verbose=False):
        super().__init__(model, verbose)
        self.incidence = []
        self._prev_I = None

    def _initialize(self, model: BaseLaserModel) -> None:
        self._prev_I = model.patches.states.I.copy()

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        current_I = model.patches.states.I
        new_infections = np.maximum(current_I - self._prev_I, 0)
        self.incidence.append(new_infections.copy())
        self._prev_I = current_I.copy()
```

## Add your component to a model

Add custom components the same way as built-in components — either in the component list or with `add_component`:

```python
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
from laser.measles.biweekly.components import InfectionSeedingProcess, InfectionProcess

params = BiweeklyParams(num_ticks=260, seed=42, start_time="2000-01")
model = BiweeklyModel(scenario, params)

# Add built-in components first
model.add_component(InfectionSeedingProcess)
model.add_component(InfectionProcess)

# Add your custom component
model.add_component(PulseVaccinationProcess)

model.run()
```

Or set all components at once:

```python
model.components = [
    InfectionSeedingProcess,
    InfectionProcess,
    PulseVaccinationProcess,
    IncidenceTracker,
]
```

## Use Pydantic for component parameters

For components with multiple configurable parameters, use a Pydantic model for validation:

```python
from pydantic import BaseModel, Field
from laser.measles.base import BaseLaserModel, BasePhase

class PulseVaccinationParams(BaseModel):
    coverage: float = Field(default=0.5, ge=0.0, le=1.0, description="Fraction of susceptibles to vaccinate")
    target_tick: int = Field(default=100, ge=0, description="Tick at which to apply vaccination")

class PulseVaccinationProcess(BasePhase):
    """Vaccinates a fixed fraction of susceptibles at a specified tick."""

    def __init__(self, model, verbose=False, params=None):
        super().__init__(model, verbose)
        self.params = params if params is not None else PulseVaccinationParams()

    def _initialize(self, model: BaseLaserModel) -> None:
        pass

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        if tick != self.params.target_tick:
            return

        states = model.patches.states
        vaccinated = (states.S * self.params.coverage).astype(states.dtype)
        states.S -= vaccinated
        states.R += vaccinated
```

## Access other components

If your component needs to read state from another component (e.g., checking whether an infection component exists), use `model.get_instance()`:

```python
def _initialize(self, model: BaseLaserModel) -> None:
    trackers = model.get_instance(StateTracker)
    if trackers[0] is not None:
        self.state_tracker = trackers[0]
```

## Component ordering considerations

Place your component in the list based on what it needs:

- If it reads compartment counts that other components modify, place it **after** those components.
- If it modifies state that downstream components use, place it **before** them.
- Trackers generally go last so they record the final state for each timestep.

## See also

- [Components](index.md) — explanation of the component architecture and base class hierarchy
- [Worked examples](worked-examples.md) — complete runnable scripts showing component wiring
- [Troubleshooting](../troubleshooting.md) — common pitfalls
- [Tutorial: Creating a component](../../tutorials/tut_creating_component.py) — hands-on tutorial for component creation
- [Tutorial: Pydantic component parameters](../../tutorials/tut_pydantic_component_parameters.py) — validated configuration with Pydantic
- [API reference](../../reference/laser/measles/index.md) — full class and parameter details
