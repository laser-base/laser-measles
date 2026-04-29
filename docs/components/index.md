# Components

laser-measles uses a component-based architecture where disease dynamics are built from interchangeable, modular pieces. This page explains the component system design, how components interact, and the technical infrastructure that supports them.

## Component system

The component system provides a uniform interface for disease dynamics with interchangeable modules built on a hierarchical base class architecture.

**Base architecture:**

- **BaseLaserModel**: Abstract base class for all model types with common functionality
- **BaseComponent**: Base class for all components with standardized interface
- **BasePhase**: Components that execute every tick (inherit from BaseComponent)
- **Inheritance-based design**: Base components define shared functionality and abstract interfaces

**Base component classes:**

- `base_transmission.py`: Base transmission/infection logic
- `base_vital_dynamics.py`: Base births/deaths logic
- `base_importation.py`: Base importation pressure logic
- `base_tracker.py`: Base tracking/metrics logic
- `base_infection.py`: Base infection state transitions
- `base_tracker_state.py`: Base state tracking functionality

**Component naming convention:**

- **Process components**: `process_*.py` — modify model state (births, deaths, infection, transmission)
- **Tracker components**: `tracker_*.py` — record metrics and state over time

**Component creation pattern:**

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

## Pydantic integration

laser-measles uses Pydantic for type-safe parameter management, providing automatic validation and documentation.

**Parameter classes:**

- `ABMParams`: Configuration for agent-based models with individual-level parameters
- `BiweeklyParams`: Configuration for biweekly models with epidemiological parameters
- `CompartmentalParams`: Configuration for compartmental models with daily dynamics

**Component classes:**
Components come in "process" and "tracker" categories and each component has a corresponding parameter class.
Each model (ABM, Biweekly, or Compartmental) has its own set of components. See the [API reference](../reference/laser/measles/index.md) for more details.

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

---

## High-performance computing

laser-measles is optimized for performance through several technical approaches:

**LaserFrame architecture:**
High-performance array-based structure for agent populations, built on the LASER framework.

**numba JIT compilation:**
Performance-critical operations implemented in numba for maximum speed.

**Polars DataFrames:**
Efficient data manipulation using Polars for biweekly model operations with Arrow backend.

**Component modularity:**
Modular architecture allows for selective component usage and optimization.

**Progress tracking:**
Integrated progress bars using alive-progress for long-running simulations.

**Python 3.10+ support:**
Optimized for modern Python features and performance improvements.

---

## See also

- [Model types](../model-types/index.md) — overview of the three model types
- [Worked examples](worked-examples.md) — copy-paste runnable scripts showing component wiring
- [Troubleshooting](troubleshooting.md) — common pitfalls with components and parameters
- [API reference](../reference/laser/measles/index.md) — full class and parameter details
