# %% [markdown]
# # Quick Start: Hello World
#
# **If you're new to laser-measles—or an AI assistant looking for a quick start example—start here.**
#
# We build a minimal but complete spatial ABM:
#
# - 8 patches arranged in a line
# - Heterogeneous population sizes
# - Infection seeded in one patch
# - Gravity-based spatial mixing
# - 50 simulated days, no births or deaths
#
# The goal is clarity, not realism.

# %% [markdown]
# ## 1. Scenario
#
# Every laser-measles model begins with a **scenario**: a Polars DataFrame with one row per patch.
#
# Required columns:
#
# - `id` — unique patch identifier
# - `lat` — latitude
# - `lon` — longitude
# - `pop` — population size
# - `mcv1` — routine vaccination coverage

# %%
import numpy as np
import polars as pl


def create_linear_scenario():
    n_patches = 8
    populations = np.array([50_000, 80_000, 120_000, 200_000, 150_000, 100_000, 70_000, 40_000])
    return pl.DataFrame({
        "id": [f"patch_{i}" for i in range(n_patches)],
        "lat": np.zeros(n_patches),
        "lon": np.linspace(0, 7, n_patches),
        "pop": populations,
        "mcv1": np.zeros(n_patches),
    })


scenario = create_linear_scenario()
scenario

# %% [markdown]
# Patches are arranged along a straight line (longitude 0–7) with varying population sizes.
# Latitude is fixed at 0. This creates a simple 1-dimensional spatial structure.

# %% [markdown]
# ## 2. Model and Parameters
#
# Instantiate the ABM with three core parameters: simulation duration, random seed, and start date.

# %%
from laser.measles.abm import ABMModel, ABMParams

params = ABMParams(
    num_ticks=50,
    seed=42,
    start_time="2000-01",
)

model = ABMModel(scenario=scenario, params=params)

# %% [markdown]
# ## 3. Components Define Model Behavior
#
# laser-measles models are **component-based**: you assemble behaviors from reusable building blocks.
# Each tick, the model executes its components in order.
#
# In this example we use four components:
#
# - `NoBirthsProcess` — static population (no births or deaths)
# - `InfectionSeedingProcess` — introduce initial infections
# - `InfectionProcess` — handle transmission and disease progression
# - `StateTracker` — record SEIR state counts over time

# %% [markdown]
# ## 4. Spatial Mixing
#
# The key new concept in a spatial model is **how infection crosses patch boundaries**.
#
# > **ABM vs Compartmental**: The compartmental model accepts an explicit `mixer=` object
# > (e.g., `InfectionParams(mixer=GravityMixing(...))`). The ABM does **not**—it builds
# > a gravity mixing matrix internally from two parameters:
#
# `distance_exponent`
# : Controls how quickly mixing declines with distance. A high value (e.g., 20) means
#   nearly all transmission is local; patches only interact significantly with their
#   immediate neighbors.
#
# `mixing_scale`
# : Controls the overall strength of cross-patch infection pressure.
#
# Each day the ABM (1) counts infectious agents per patch, (2) builds the gravity mixing matrix,
# (3) computes force of infection per patch, then (4) applies infection probability to each
# susceptible agent. Agents themselves do not move between patches.

# %%
from laser.measles.abm import InfectionParams, InfectionSeedingParams, NoBirthsProcess, InfectionSeedingProcess, InfectionProcess, StateTracker, StateTrackerParams
from laser.measles.components import create_component

infection_params = InfectionParams(
    beta=2.0,
    seasonality=0.0,
    distance_exponent=20.0,  # strongly local transmission
    mixing_scale=0.01,       # moderate cross-patch pressure
)

# %% [markdown]
# ## 5. Seeding Infection
#
# Seed 5 infections in the last patch (`patch_7`) to observe the outbreak spreading
# outward from one end of the line.

# %%
seeding_params = InfectionSeedingParams(
    target_patches=["patch_7"],
    infections_per_patch=5,
)

# %% [markdown]
# ## 6. Assemble and Run
#
# Attach components in execution order and run the simulation.
#
# Two `StateTracker` instances are registered:
# - Default (`aggregation_level=-1`): sums across all patches → global SEIR time series
# - `aggregation_level=0`: tracks each patch separately → spatial dynamics

# %%
model.components = [
    NoBirthsProcess,
    create_component(InfectionSeedingProcess, seeding_params),
    create_component(InfectionProcess, infection_params),
    StateTracker,
    create_component(
        StateTracker,
        StateTrackerParams(aggregation_level=0),
    ),
]

model.run()

# %% [markdown]
# ## 7. Results
#
# Extract the two tracker instances and generate three panels:
#
# 1. **Global SEIR fractions** — overall epidemic curve
# 2. **Spatial attack rate** — which patches were hit hardest
# 3. **Infectious agents per patch over time** — how infection spread across space

# %%
import matplotlib.pyplot as plt

global_tracker = model.get_instance("StateTracker")[0]
patch_tracker = model.get_instance("StateTracker")[1]

pops = scenario["pop"].to_numpy()
total_pop = pops.sum()
ticks = np.arange(params.num_ticks)

# Global SEIR time series (shape: num_ticks,)
S = global_tracker.S
E = global_tracker.E
I = global_tracker.I
R = global_tracker.R

# Per-patch time series (shape: num_ticks × num_patches)
I_by_patch = patch_tracker.I
R_by_patch = patch_tracker.R

# Attack rate: fraction of each patch's population infected by the end
attack_rate = (I_by_patch[-1] + R_by_patch[-1]) / pops * 100

fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# Panel 1: global SEIR fractions
ax = axes[0]
ax.plot(ticks, S / total_pop, label="S")
ax.plot(ticks, E / total_pop, label="E")
ax.plot(ticks, I / total_pop, label="I")
ax.plot(ticks, R / total_pop, label="R")
ax.set_xlabel("Day")
ax.set_ylabel("Fraction of population")
ax.set_title("Global SEIR")
ax.legend()
ax.grid(alpha=0.3)

# Panel 2: spatial attack rate
ax = axes[1]
ax.bar([f"patch_{i}" for i in range(8)], attack_rate)
ax.set_xlabel("Patch")
ax.set_ylabel("Attack rate (%)")
ax.set_title("Spatial attack rate")
ax.tick_params(axis="x", rotation=45)
ax.grid(alpha=0.3, axis="y")

# Panel 3: infectious agents per patch over time
ax = axes[2]
for i in range(8):
    ax.plot(ticks, I_by_patch[:, i], label=f"patch_{i}", alpha=0.8)
ax.set_xlabel("Day")
ax.set_ylabel("Infectious agents")
ax.set_title("Infection spread by patch")
ax.legend(fontsize=7, ncol=2)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.show()

# %% [markdown]
# ## What This Example Demonstrates
#
# - **Scenario construction**: building geographic patch data from scratch
# - **Component architecture**: assembling model behavior from reusable pieces
# - **Spatial mixing**: how ABM gravity mixing differs from the compartmental approach
# - **State tracking**: extracting global and per-patch time series
#
# The model is deliberately simple—no demographics, no vaccination—so the spatial
# spreading dynamics are easy to observe.
#
# ## Next Steps
#
# Extend this model by:
#
# - Adding vital dynamics: replace `NoBirthsProcess` with `VitalDynamicsProcess`
# - Adding vaccination campaigns: use `SIACalendarProcess`
# - Comparing ABM vs compartmental: see the `tut_basic_model` tutorial
# - Exploring mixing models in depth: see the `tut_spatial_mixing` tutorial
