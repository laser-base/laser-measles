# %% [markdown]
# # Model Structure
#
# This tutorial goes over how a laser-measles models run.
# It compares the structure of compartmental and agent-based models,
# focusing on their LaserFrame data structures and how they operate.

# ## Overview
# Laser-measles takes a stochastic, distrete-time approach that is
# focused on incorporating spatial structure and data to model measles transmission.
#
# laser-measles provides two primary modeling approaches:
# - **Compartmental/state-transision approach**: Population-level SEIR dynamics using aggregated patch data
# - **Agent-based approach**: Individual-level simulation with stochastic agents
#
# The comprtmental approach is taken by the *compartmental* and *biweekly* models while the
# agent-based is taken by the *abm* model. The key difference lies in their
# data organization and LaserFrame structures.
# You can choose which model (*abm*, *compartmental*, or *biweekly*) to import by importing
# the submodule directly from laser-measles:
# %%
# Importing all three models
from laser.measles.abm import ABMModel, ABMParams
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
# or use the Model alias to allow for code that can be easily carried between models:
from laser.measles.abm import Model

# %% [markdown]
# ## The BaseLaserModel and components
#
# ### BaseLaserModel
#
# All three models inherit from the `BaseLaserModel`. This class is composed of a few main steps/methods:
# - `.__init__`: This method is called when the model is instantiated and sets up the model's random seed (for reproducibility),
# model clock (`start_time` and `current_date`), and performance metrics (`metrics`).
# - `.run`: This method executes the model, running the model in discrete time steps (`num_ticks`)
#
# ### Components and phases
#
# Each time step the model loops over the components that define what will happen in the simulation. Laser-measles
# diffentiates between a `BaseComponent` and a `BasePhase`. Most components will be a `BasePhase` which is called
# every time step. A `BaseComponent` will be called at the beginning of the simulation but not necessarily every
# time step (e.g., useful for initialization).
#
# A `Phase` (e.g. `InfectionProcess` or `StateTracker`) executes every time step the `__call__` method
# defined in the class. Both a `Phase` and a `Component` has an `__init__` method that executes on initialization
# as well as an `_initialize` method that run at the beginning of the simulation (`model.run()`). These are
# particularly important for the abm model.
#
# To see/access all components available for a model you use the associated `components` sub-module.
# %%
from laser.measles.abm import components as abm_components
print("Available Process components:")
for c in sorted([c for c in dir(abm_components) if 'Process' in c]):
    print(f"  - {c}")
# %% [markdown]
# ## Patches
#
# Patches represent a spatial unit (e.g., administraive unit) and
# exist for both the compartmental and ABM models. They track the spatial
# data and aggregates in the model.
# The `patches` use a `BasePatchLaserFrame` (or child class) for population-level aggregates.
# %%
import polars as pl

from laser.measles import create_component
from laser.measles.compartmental import CompartmentalModel
from laser.measles.compartmental.components import CaseSurveillanceParams
from laser.measles.compartmental.components import CaseSurveillanceTracker
from laser.measles.compartmental.params import CompartmentalParams

# Create a simple scenario
scenario = pl.DataFrame(
    {"id": ["1", "2", "3"], "pop": [1000, 2000, 1500], "lat": [40.0, 41.0, 42.0], "lon": [-74.0, -73.0, -72.0], "mcv1": [0.0, 0.0, 0.0]}
)

# Initialize compartmental model
params = CompartmentalParams(num_ticks=100)
comp_model = CompartmentalModel(scenario, params)

# Examine the patch structure
print("Compartmental model patches:")
print(f"Shape: {comp_model.patches.states.shape}")
print(f"State names: {comp_model.patches.states.state_names}")
print(f"Initial S compartment: {comp_model.patches.states.S}")
print(f"Total population: {comp_model.patches.states.S.sum()}")

# You can also print the model to get some info:
print("Compartmental model 'out of the box':")
print(comp_model)

# Create a CaseSurveillanceTracker to monitor infections
case_tracker = create_component(
    CaseSurveillanceTracker,
    CaseSurveillanceParams(detection_rate=1.0),  # 100% detection for accurate infection counting
)

# Add transmission and surveillance to the model
from laser.measles.compartmental.components import InfectionProcess, InfectionSeedingProcess

comp_model.add_component(InfectionSeedingProcess)
comp_model.add_component(InfectionProcess)
comp_model.add_component(case_tracker)

print("\nCompartmental model with surveillance:")
print(comp_model)

# Run the simulation
comp_model.run()

# Access infection data
case_tracker_instance = comp_model.get_instance(CaseSurveillanceTracker)[0]
comp_infections_df = case_tracker_instance.get_dataframe()
print(f"\nCompartmental model total infections: {comp_infections_df['cases'].sum()}")

# %% [markdown]
# ### Key Features of patches (e.g., BasePatchLaserFrame):
# - `states` **property**: StateArray with shape `(num_states, num_patches)`
# - **Attribute access**: `states.S`, `states.E`, `states.I`, `states.R`
# - **Population aggregates**: Each patch contains total counts by disease state
# - **Spatial organization**: Patches represent geographic locations

# %% [markdown]
# ## People
#
# In addition to a `patch`, the ABM uses `people` (e.g., `BasePeopleLaserFrame`) for individual agents:

# %%
import laser.measles as lm
from laser.measles.abm import ABMModel
from laser.measles.abm import InfectionProcess, InfectionSeedingProcess, CaseSurveillanceTracker, CaseSurveillanceParams
from laser.measles.abm.params import ABMParams

# Initialize ABM model
abm_params = ABMParams(num_ticks=100)
abm_model = ABMModel(scenario, abm_params)

# Examine the model
print("ABM model 'out of the box':")
print(abm_model)

# Now what if we add a transmission?
abm_model.add_component(InfectionSeedingProcess)
abm_model.add_component(InfectionProcess)
print("ABM model after adding infection:")
print(abm_model)

# Add CaseSurveillanceTracker to ABM model
abm_case_tracker = create_component(
    CaseSurveillanceTracker, CaseSurveillanceParams(detection_rate=1.0)
)
abm_model.add_component(abm_case_tracker)

print("\nABM model with surveillance:")
print(abm_model)

# Run the simulation
abm_model.run()

# Access infection data
abm_case_tracker_instance = abm_model.get_instance(CaseSurveillanceTracker)[0]
abm_infections_df = abm_case_tracker_instance.get_dataframe()
print(f"\nABM model total infections: {abm_infections_df['cases'].sum()}")


# %% [markdown]
# ### Key Features of BasePeopleLaserFrame:
# - **Individual agents**: Each row represents one person
# - **Agent properties**: `patch_id`, `state`, `susceptibility`, `active`
# - **Dynamic capacity**: Can grow/shrink as agents are born/die
# - **Stochastic processes**: Each agent processed individually

# %% [markdown]
# ## Key differences
#
# | Aspect | Compartmental | ABM |
# |--------|---------------|-----|
# | **Data Structure** | `BasePatchLaserFrame` | `BasePeopleLaserFrame` |
# | **Population Storage** | Aggregated counts by patch | Individual agents |
# | **State Representation** | `states.S[patch_id]` | `people.state[agent_id]` |
# | **Spatial Organization** | Patch-level mixing matrix | Agent patch assignment |
# | **Transitions** | Binomial sampling | Individual stochastic events |
# | **Performance** | Faster (fewer calculations) | Slower (more detailed) |
# | **Memory Usage** | Lower (aggregates) | Higher (individual records) |

# %% [markdown]
# ## When to use each model
#
# **Use a Patches model only (e.g., Compartmental Model) when:**
# - Analyzing population-level dynamics
# - Running many scenarios quickly
# - Interested in aggregate outcomes
# - Working with large populations
#
# **Use a Patches+People Model (e.g., ABM Model) when:**
# - Modeling individual heterogeneity
# - Studying contact networks
# - Tracking individual histories
# - Need detailed stochastic processes
#
# Both models share the same component architecture and can use similar
# initialization and analysis tools, making it easy to switch between approaches.
