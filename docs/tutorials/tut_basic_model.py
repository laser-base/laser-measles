# %% [markdown]
# # Creating And Running Models
#
# This tutorial demonstrates how to initialize and run a model using
# the laser-measles framework.
#
# The tutorial covers:
# - Setting up scenario data with multiple spatial nodes
# - Configuring model parameters including transmission and vital dynamics
# - Adding components for disease transmission and state tracking
# - Running the simulation and visualizing results

# %% [markdown]
# ## Setting up the scenario
#
# First we'll load a scenario with two clusters of 50 spatial nodes each,
# representing different communities around two major population centers.
# Each node has population, geographic coordinates, and MCV1 vaccination coverage.
# The nodes are distributed around each center using a Gaussian distribution
# for radial distance, creating realistic spatial clustering patterns.
# We will also divide the nodes into clusters using colon convention: (cluster_i:node_j).
# This is useful for doing spatial aggregation of e.g., case counts.
#
# laser-measles comes with a few simple scenarios which you can access
# from the `scenarios` module (e.g. `from laser.measles import scenarios`).
# For this demo we will use one of the `synthetic` scenarios.

# %%
import matplotlib.pyplot as plt
import numpy as np

from laser.measles.scenarios import synthetic

scenario = synthetic.two_cluster_scenario(cluster_size_std=1.0)
plt.figure(figsize=(6, 5))
plt.scatter(scenario["lon"], scenario["lat"], c=scenario["pop"], cmap="viridis")
plt.colorbar(label="Population")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title("Population Distribution")
plt.show()

# %% [markdown]

# The scenario data is a polars dataframe with the following columns:
# - `lat`: latitude
# - `lon`: longitude
# - `pop`: population
# - `mcv1`: MCV1 coverage
# Each row represents a spatial patch in the model.

# %%

scenario.head(n=3)

# %% [markdown]
# ## Model selection
# The main models (biweekly, compartmental, and abm) are meant - for the simplest instantiations - to be interchangeable.
# This can be done at the import level. For example, we'll start with the fastest model, the biweekly one.

# %%
from laser.measles.biweekly import BaseScenario
from laser.measles.biweekly import BiweeklyParams
from laser.measles.biweekly import Model
from laser.measles.biweekly import InfectionParams, InitializeEquilibriumStatesProcess, ImportationPressureProcess, InfectionProcess, VitalDynamicsProcess, StateTracker
from laser.measles.components import create_component

# %% [markdown]
# ## Create a scenario and parameter validation
# The scenario sets the initial condition for the simulation and is a collection of patches,
# each with a population, geographic coordinates, and MCV1 vaccination coverage.
# The BaseScenario class will validate the dataframe to make sure it is in the right format.
# If you simply pass the dataframe the Scenario is constructed during initialization.
#
# This is a pattern that you will see across laser-measles.
# %%

# Try to create BaseScenario object missing the lat column
try:
    scenario = BaseScenario(scenario.drop("lat"))
except ValueError:
    import traceback

    print("Error creating BaseScenario object missing the 'lat' column:")
    traceback.print_exc()

# %% [markdown]
# ## Initialize model parameters and components
# The Model is passed parameters that set the overall behavior of the simulation.
# For example, the duration of the simulation (`num_ticks`) and the random seed for
# reproducibility (`seed`). However, the processes included in the simulation (e.g.,
# transmission, vital dynamics, immunization campaigns) will be determined by **selecting
# and including the relevant components**. Each component has its own associated parameters.

# %%
# Calculate number of time steps (bi-weekly for 5 years)
years = 20
num_ticks = years * 26  # 26 bi-weekly periods per year

# Create model parameters
params = BiweeklyParams(
    num_ticks=num_ticks,
    seed=42,
    verbose=True,
    start_time="2000-01",  # YYYY-MM format
)

print(f"Model configured for {num_ticks} time steps ({years} years)")
print(f"Parameters: {params}")

# Create the biweekly model
biweekly_model = Model(scenario, params, name="biweekly_tutorial")

# Currently the model has no components
print(f"Model has {len(biweekly_model.components)} components:\n{biweekly_model.components}")

# Create infection parameters with seasonal transmission
infection_params = InfectionParams(
    seasonality=0.3,  # seasonal variation
)

# Create model components
model_components = [
    InitializeEquilibriumStatesProcess,  # Initialize the states
    ImportationPressureProcess,  # Infection seeding
    create_component(InfectionProcess, params=infection_params),  # Infections
    VitalDynamicsProcess,  # Births/deaths
]
biweekly_model.components = model_components
print(f"Model has {len(biweekly_model.components)} components:\n{biweekly_model.components}")

# You can also add components using the `add_component` method
biweekly_model.add_component(StateTracker)
print(f"Model has {len(biweekly_model.components)} components:\n{biweekly_model.components}")

# %% [markdown]
# ## Components vs instances
#
# Note that when we setup the `model.components` we pass a reference to the component Class (e.g., `VitalDynamicsProcess`) and not instances of the Class itself
# (e.g., `VitalDynamicsProcess()`). The `Model` creates instances of the class and those are stored in the `model.instances` attribute. This is why if you want to
# pass parameters different than the defaults to the components you should use the `create_component` function.

# %%
print(biweekly_model.instances)

# %% [markdown]
# ## Run the simulation
#
# Execute the model for the specified number of time steps.
# Since we set verbose=True we will get additional timing information.

# %%
print("Starting simulation...")
biweekly_model.run()
print("Simulation completed!")

# Print final state summary
print("\nFinal state distribution:")
for state in biweekly_model.params.states:
    print(f"{state}: {getattr(biweekly_model.patches.states, state).sum():,}")

# %% [markdown]
# ## Switching models
#
# We can use the same syntax to create a compartmental (SEIR, daily time steps) model

# %%
from laser.measles.compartmental import BaseScenario
from laser.measles.compartmental import CompartmentalParams
from laser.measles.compartmental import Model
from laser.measles.compartmental import InfectionParams, InitializeEquilibriumStatesProcess, ImportationPressureProcess, InfectionProcess, VitalDynamicsProcess, StateTracker

# Create model parameters
params = CompartmentalParams(
    num_ticks=years * 365,
    seed=42,
    verbose=True,
    start_time="2000-01",  # YYYY-MM format
)

# Create the compartmental model
compartmental_model = Model(scenario, params, name="compartmental_tutorial")

# Create infection parameters with seasonal transmission
infection_params = InfectionParams(
    seasonality=0.3,
)
# Create model components
model_components = [
    InitializeEquilibriumStatesProcess,  # Initialize the states
    ImportationPressureProcess,  # Infection seeding
    create_component(InfectionProcess, params=infection_params),  # Infections
    VitalDynamicsProcess,  # Births/deaths
    StateTracker,  # State tracking
]
compartmental_model.components = model_components

# Run the simulation
print("Starting simulation...")
compartmental_model.run()
print("Simulation completed!")

# Print final state summary
print("\nFinal state distribution:")
for state in compartmental_model.params.states:
    print(f"{state}: {getattr(compartmental_model.patches.states, state).sum():,}")

# %% [markdown]
# ## Visualize results
#
# Generate plots to analyze the simulation results, including time series
# of disease states and spatial distribution of the final epidemic.

# %%
import matplotlib.pyplot as plt


def make_plot(model):
    # Get the state tracker instance from the model
    state_tracker = model.get_instance("StateTracker")[0]
    if state_tracker is None:
        raise RuntimeError("StateTracker not found in model instances")

    def lookup_state_idx(model, state):
        return model.params.states.index(state)

    # Create comprehensive visualization
    fig = plt.figure(figsize=(15, 5))

    # Population time series
    total_population = state_tracker.state_tracker.sum(axis=0).flatten()

    # Plot 1: Time series of susceptibility fraction
    ax1 = plt.subplot(1, 3, 1)
    time_steps = np.arange(model.params.num_ticks)
    ax1.plot(time_steps, state_tracker.S / total_population, "-", linewidth=2)
    ax1.set_xlabel("Time (ticks)")
    ax1.set_ylabel("Susceptible Fraction")
    ax1.set_title("Susceptible Fraction Over Time")
    ax1.grid(True, alpha=0.3)

    # Plot 2: Spatial distribution of final states
    scenario_data = model.scenario
    coordinates = scenario_data[["lat", "lon"]].to_numpy()
    final_recovered = model.patches.states[lookup_state_idx(model, "R")] + model.patches.states[lookup_state_idx(model, "I")]  # R + I
    initial_population = scenario_data["pop"].to_numpy()
    attack_rates = (final_recovered / initial_population) * 100
    ax2 = plt.subplot(1, 3, 2)
    coords_array = np.array(coordinates)
    # Size points by population, color by attack rate
    # Scale down point sizes for better visualization with many nodes
    point_sizes = np.array(scenario_data["pop"]) / 1000
    scatter = ax2.scatter(coords_array[:, 1], coords_array[:, 0], s=point_sizes, c=attack_rates, cmap="Reds", alpha=0.7, edgecolors="black")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Latitude")
    ax2.set_title("Spatial Attack Rate Distribution")
    plt.colorbar(scatter, ax=ax2, label="Attack Rate (%)")

    # Plot 3: Epidemic curve (infections per time step)
    ax3 = plt.subplot(1, 3, 3)
    ax3.plot(time_steps, state_tracker.I, "red", linewidth=1)
    ax3.set_xlabel("Time (ticks)")
    ax3.set_ylabel("Infectious")
    ax3.set_title("Epidemic Curve")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()


# %% [markdown]
# Plot the biweekly model results:

# %%
make_plot(biweekly_model)

# %% [markdown]
# Plot the compartmental model results:

# %%
make_plot(compartmental_model)
