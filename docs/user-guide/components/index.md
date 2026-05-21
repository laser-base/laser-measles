# Components

laser-measles uses a component-based architecture where disease dynamics are built from interchangeable, modular pieces. Rather than embedding all epidemiological logic in a single monolithic model, each process — transmission, recovery, births, deaths, vaccination, case tracking — is implemented as a separate component that can be added, removed, or replaced independently.

This page explains why the component system exists, how components interact, and the design decisions behind the architecture.

## Why components?

Measles models need to answer different questions for different audiences. A rapid scenario comparison might need only transmission and recovery. A detailed country analysis might add vital dynamics, vaccination campaigns, importation pressure, and multiple trackers. A methods paper might replace the transmission kernel entirely.

The component system makes this possible without forking the codebase. You assemble exactly the processes you need for your analysis:

```python
# Minimal model: just transmission
model.components = [InfectionSeedingProcess, InfectionProcess]

# Full model: transmission + demographics + vaccination + tracking
model.components = [
    InitializeEquilibriumStatesProcess,
    VitalDynamicsProcess,
    InfectionProcess,
    SIACalendarProcess,
    ImportationPressureProcess,
    StateTracker,
    PopulationTracker,
    CaseSurveillanceTracker,
]
```

## Component types

Components fall into two categories, distinguished by naming convention:

**Process components** (`process_*.py`) modify model state at each timestep. They move individuals between compartments, add or remove agents, and apply interventions. Examples:

- `InfectionProcess` — computes transmission and moves susceptibles to exposed/infectious
- `VitalDynamicsProcess` — handles births, deaths, and aging
- `SIACalendarProcess` — applies supplementary immunization activities on scheduled dates
- `ImportationPressureProcess` — introduces external infections from outside the model

**Tracker components** (`tracker_*.py`) record metrics and state over time without modifying the simulation. They are used for output and analysis. Examples:

- `StateTracker` — records SEIR compartment counts at each timestep
- `PopulationTracker` — records total population per patch
- `CaseSurveillanceTracker` — records new cases for comparison with surveillance data
- `FadeoutTracker` — detects when infection dies out in a patch

## Component execution order

Components execute in the order they appear in the component list, once per timestep. Order matters when components depend on each other's output:

1. **Initialization components** (e.g., `InitializeEquilibriumStatesProcess`) should come first — they set the initial SEIR distribution before the simulation loop begins.
2. **Vital dynamics** (births, deaths) typically come before transmission — new susceptible births should be available for infection in the same timestep.
3. **Infection/transmission** components use the current population state to compute new infections.
4. **Intervention components** (SIA campaigns, importation) modify state after transmission.
5. **Trackers** should come last — they record the state after all processes have run for the timestep.

## The base class hierarchy

All components inherit from a common base class hierarchy defined in `laser.measles.base`:

- **`BaseComponent`** — provides the standard interface: `__init__(model, verbose)`, an `_initialize(model)` hook, and a `plot()` method.
- **`BasePhase`** — extends `BaseComponent` with a `__call__(model, tick)` method. Components that execute every timestep inherit from this class.

Each model type (ABM, biweekly, compartmental) has its own component implementations that inherit from shared base classes in `laser.measles.components`. For example, the infection logic in `laser.measles.components.base_infection` defines the shared algorithm, and `laser.measles.abm.components.process_infection` adapts it for individual agents while `laser.measles.compartmental.components.process_infection` adapts it for compartment counts.

This means the same epidemiological logic is shared across model types — only the population representation differs.

## Pydantic parameter validation

Model parameters and component parameters use [Pydantic](https://docs.pydantic.dev/) for type-safe validation. Each model type has a params class (`ABMParams`, `BiweeklyParams`, `CompartmentalParams`) that validates configuration at construction time:

- **Type checking**: passing a string where an integer is expected raises an error immediately, not during simulation.
- **Range validation**: parameters with physical constraints (e.g., probabilities between 0 and 1) are enforced.
- **Extra field protection**: misspelled parameter names are caught (`extra="forbid"` in the model config).
- **Serialization**: parameters can be exported to JSON for reproducibility and logging.

```python
from laser.measles.biweekly import BiweeklyParams

params = BiweeklyParams(
    num_ticks=520,      # Validated as positive integer
    seed=12345,         # Random seed for reproducibility
    start_time="2000-01"  # Validated as YYYY-MM format
)

# Export configuration for reproducibility
config = params.model_dump_json()
```

## Performance infrastructure

Several performance features are built into the component system:

- **Numba JIT compilation**: Performance-critical inner loops (transmission kernels, state updates) have both pure-NumPy and Numba-accelerated implementations. Components use `select_function()` to choose the right one based on the `use_numba` parameter.
- **LaserFrame arrays**: Agent populations (in the ABM) use the LASER framework's `LaserFrame` structure for cache-friendly, contiguous memory layout.
- **Polars DataFrames**: The biweekly model uses Polars with its Arrow backend for efficient column-oriented operations.
- **Progress tracking**: Long simulations display progress bars via `alive-progress`.

## See also

- [How to create a custom component](custom-component.md) — step-by-step guide to writing your own component
- [Worked examples](worked-examples.md) — runnable scripts showing component wiring for all three models
- [Troubleshooting](../troubleshooting.md) — common pitfalls with components and parameters
- [Tutorial: Creating a component](../../tutorials/tut_creating_component.py) — hands-on tutorial for component creation
- [Tutorial: Pydantic component parameters](../../tutorials/tut_pydantic_component_parameters.py) — validated configuration with Pydantic
- [Model types](../model-types/index.md) — overview of the three model types
- [Snapshotting](../snapshotting/index.md) — save and resume simulations with their component state
- [API reference](../../reference/laser/measles/index.md) — full class and parameter details
