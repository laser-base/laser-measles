# %% [markdown]
# # Spatial Mixing Models Tutorial
#
# This tutorial demonstrates how to choose and configure different spatial mixing models
# in the laser-measles framework and shows how they affect disease transmission patterns.
#
# ## Key pattern: mixer goes inside InfectionParams
#
# We are using a compartmental model where the mixer is wired in through `InfectionParams` (note the ABM uses a different approach):
#
# ```python
# mixer = GravityMixing(params=GravityParams(a=1.0, b=1.0, c=2.0, k=0.01))
# infection_params = InfectionParams(beta=0.8, mixer=mixer)
# ```
#
# You do **not** need to pass `scenario=` to the mixer at construction — the model
# sets it automatically before the first tick.
#
# This tutorial uses the **compartmental** model. For an ABM spatial mixing example,
# see the *Quick Start: Spatial ABM "Hello World"* in the documentation.
#
# ## What are Spatial Mixing Models?
#
# Spatial mixing models determine how infectious individuals in one location can infect
# susceptible individuals in other locations. They create a **mixing matrix** that quantifies
# the probability of contact between people from different patches (spatial locations).
#
# The tutorial covers:
# - Overview of available mixing models (gravity, radiation, competing destinations, stouffer)
# - Configuring models with different mixing patterns
# - Comparing spatial disease spread patterns
# - Understanding how mixing matrices affect transmission dynamics
#
# ## Available Mixing Models
#
# laser-measles provides four spatial mixing models:
#
# 1. **Gravity Model**: Based on gravitational attraction, depends on population sizes and distance
#    - Formula: $$M_{i,j} = k \cdot p_i^{a-1} \cdot p_j^b \cdot d_{i,j}^{-c}$$
#    - Good for modeling general mobility patterns
#
# 2. **Radiation Model**: Based on radiation theory of human mobility
#    - Less dependent on specific parameter tuning
#    - Often performs well for real-world mobility data
#
# 3. **Competing Destinations**: Extension of gravity model with destination competition and synergistic attraction
#    - Formula: $$M_{i,j} = k \frac{p_i^{a-1} p_j^b}{d_{i,j}^c} \left(\sum_{k \ne i,j} \frac{p_k^b}{d_{ik}^c}\right)^\delta$$
#    - Includes delta parameter for destination selection
#
# 4. **Stouffer Model**: Based on intervening opportunities theory
#    - Considers intermediate locations between origin and destination

# %% [markdown]
# ## Setting up the scenario
#
# We'll create a scenario with multiple spatial nodes to demonstrate the effects
# of different mixing models on disease transmission patterns.

# %%
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import seaborn as sns

from laser.measles.scenarios import synthetic
from laser.measles.compartmental import CompartmentalParams, Model
from laser.measles.compartmental import InfectionParams, InitializeEquilibriumStatesProcess, ImportationPressureProcess, InfectionProcess, VitalDynamicsProcess, StateTracker
from laser.measles.components import create_component
from laser.measles.mixing.gravity import GravityMixing, GravityParams
from laser.measles.mixing.radiation import RadiationMixing, RadiationParams

# Set up matplotlib for better plots
plt.style.use('default')
sns.set_palette("husl")

# Create two different scenarios to showcase model differences
# 1. Two-cluster scenario (default)
cluster_scenario = synthetic.two_cluster_scenario(
    n_nodes_per_cluster=20,  # Smaller for clearer visualization
    cluster_size_std=2.0,    # More spread out clusters
    seed=42
)

# 2. Create a linear chain scenario for better demonstration of intervening opportunities
def create_linear_chain_scenario(n_nodes=30, seed=42):
    """Create a linear chain of nodes to highlight radiation vs gravity differences"""
    np.random.seed(seed)

    # Create nodes in a line with some random variation
    x_coords = np.linspace(0, 10, n_nodes) + np.random.normal(0, 0.1, n_nodes)
    y_coords = np.random.normal(0, 0.2, n_nodes)  # Small y variation

    # Create population gradient - larger populations at the ends
    base_pop = 1000
    pop_multiplier = 1 + 3 * (np.abs(np.linspace(-1, 1, n_nodes)))  # U-shaped
    populations = (base_pop * pop_multiplier).astype(int)

    # Create vaccination coverage (uniform for simplicity)
    mcv1_coverage = np.full(n_nodes, 0.85)

    return pl.DataFrame({
        'id': [f"node_{i}" for i in range(n_nodes)],
        'lat': y_coords,
        'lon': x_coords,
        'pop': populations,
        'mcv1': mcv1_coverage
    })

linear_scenario = create_linear_chain_scenario(seed=42)

# Choose which scenario to use for main comparison
scenario = linear_scenario  # Use linear for dramatic differences
print(f"Using linear chain scenario with {len(scenario)} patches")
print(f"Total population: {scenario['pop'].sum():,}")

# Visualize both scenarios
fig, axes = plt.subplots(1, 2, figsize=(15, 6))

# Plot cluster scenario
axes[0].scatter(cluster_scenario["lon"], cluster_scenario["lat"],
               c=cluster_scenario["pop"], s=cluster_scenario["pop"]/10,
               cmap="viridis", alpha=0.7, edgecolors="black")
axes[0].set_xlabel("Longitude")
axes[0].set_ylabel("Latitude")
axes[0].set_title("Two-Cluster Scenario")
axes[0].grid(True, alpha=0.3)

# Plot linear scenario
scatter = axes[1].scatter(scenario["lon"], scenario["lat"],
                         c=scenario["pop"], s=scenario["pop"]/8,
                         cmap="viridis", alpha=0.7, edgecolors="black")
axes[1].set_xlabel("Longitude")
axes[1].set_ylabel("Latitude")
axes[1].set_title("Linear Chain Scenario (Used for Analysis)")
axes[1].grid(True, alpha=0.3)

plt.colorbar(scatter, ax=axes[1], label="Population")
plt.tight_layout()
plt.show()

print(f"Population range: {scenario['pop'].min():,} - {scenario['pop'].max():,}")
print(f"Spatial extent: lon=[{scenario['lon'].min():.1f}, {scenario['lon'].max():.1f}], lat=[{scenario['lat'].min():.1f}, {scenario['lat'].max():.1f}]")

# %% [markdown]
# ## How Mixing Matrices Work in Disease Transmission
#
# Before we compare models, let's understand how the mixing matrix is used in the infection process.
# In the compartmental model's infection component (`process_infection.py:114`), the force of infection
# is calculated as:
#
# ```python
# lambda_i = (beta * seasonal_factor * prevalence) @ mixer.mixing_matrix
# ```
#
# This matrix multiplication means:
# - `prevalence` is a vector of infectious individuals per patch
# - `mixing_matrix[i,j]` is the probability that someone from patch i mixes with patch j
# - The result `lambda_i[i]` is the total infectious pressure on patch i from all patches
#
# Key insight: **The mixing matrix determines which patches can "seed" infections in other patches**

# %% [markdown]
# ## Model 1: Gravity Mixing
#
# The gravity model assumes that mixing between patches follows a gravitational law:
# stronger attraction between larger populations, weaker with greater distance.

# %%
# Configure model parameters
years = 5
num_ticks = years * 365  # Daily timesteps

params = CompartmentalParams(
    num_ticks=num_ticks,
    seed=42,
    verbose=False,  # Set to True to see timing information
    start_time="2000-01"
)

# Create gravity mixing with extreme parameters to show clear differences
gravity_params = GravityParams(
    a=1.0,    # Source population exponent
    b=2.0,    # Target population exponent - higher to favor large populations
    c=1.0,    # Distance decay exponent - lower for long-range connections
    k=0.01    # Overall mixing scale - higher for more mixing
)
gravity_mixer = GravityMixing(params=gravity_params)

# Create infection parameters with gravity mixing
infection_params = InfectionParams(
    beta=0.8,           # Transmission rate
    seasonality=0.2,    # Seasonal variation
    mixer=gravity_mixer
)

# Create patch-level state tracking parameters
from laser.measles.abm import StateTrackerParams
patch_tracker_params = StateTrackerParams(aggregation_level=0)  # Track by patch

# Create and configure the model
gravity_model = Model(scenario, params, name="gravity_mixing_demo")
gravity_model.components = [
    InitializeEquilibriumStatesProcess,
    ImportationPressureProcess,
    create_component(InfectionProcess, params=infection_params),
    VitalDynamicsProcess,
    StateTracker,  # Overall tracker
    create_component(StateTracker, params=patch_tracker_params)  # Patch-level tracker
]

print("Running gravity model simulation...")
gravity_model.run()
print("Gravity model completed!")

# Get results
gravity_tracker = gravity_model.get_instance("StateTracker")[0]  # Overall tracker
gravity_patch_tracker = gravity_model.get_instance("StateTracker")[1]  # Patch-level tracker
gravity_final_R = gravity_model.patches.states.R.copy()
gravity_mixing_matrix = gravity_mixer.mixing_matrix.copy()

# %% [markdown]
# ## Model 2: Radiation Mixing
#
# The radiation model is based on a different theory of human mobility.
# It tends to be less parameter-dependent and often captures real mobility patterns well.

# %%
# Create radiation mixing
radiation_params = RadiationParams(
    k=0.01,           # Same overall mixing scale as gravity
    include_home=True # Include self-mixing (staying home)
)
radiation_mixer = RadiationMixing(params=radiation_params)

# Create infection parameters with radiation mixing
infection_params_rad = InfectionParams(
    beta=0.8,              # Same transmission rate
    seasonality=0.2,       # Same seasonal variation
    mixer=radiation_mixer
)

# Create new model instance for radiation
radiation_model = Model(scenario, params, name="radiation_mixing_demo")
radiation_model.components = [
    InitializeEquilibriumStatesProcess,
    ImportationPressureProcess,
    create_component(InfectionProcess, params=infection_params_rad),
    VitalDynamicsProcess,
    StateTracker,  # Overall tracker
    create_component(StateTracker, params=patch_tracker_params)  # Patch-level tracker
]

print("Running radiation model simulation...")
radiation_model.run()
print("Radiation model completed!")

# Get results
radiation_tracker = radiation_model.get_instance("StateTracker")[0]  # Overall tracker
radiation_patch_tracker = radiation_model.get_instance("StateTracker")[1]  # Patch-level tracker
radiation_final_R = radiation_model.patches.states.R.copy()
radiation_mixing_matrix = radiation_mixer.mixing_matrix.copy()

# %% [markdown]
# ## Analyzing Spatial Mixing Patterns
#
# Let's perform detailed analysis of how the two models structure spatial interactions differently.

# %%
# Calculate distances between all patches for analysis
def calculate_mixing_distances(scenario, mixing_matrix):
    """Calculate weighted average mixing distance for each patch"""
    coords = scenario[['lat', 'lon']].to_numpy()
    n_patches = len(coords)

    # Calculate distance matrix
    distances = np.zeros((n_patches, n_patches))
    for i in range(n_patches):
        for j in range(n_patches):
            distances[i, j] = np.sqrt((coords[i, 0] - coords[j, 0])**2 +
                                    (coords[i, 1] - coords[j, 1])**2)

    # Calculate weighted average mixing distance for each patch
    mixing_distances = np.zeros(n_patches)
    for i in range(n_patches):
        weights = mixing_matrix[i, :]
        if weights.sum() > 0:
            mixing_distances[i] = np.average(distances[i, :], weights=weights)

    return mixing_distances, distances

gravity_mix_dist, distance_matrix = calculate_mixing_distances(scenario, gravity_mixing_matrix)
radiation_mix_dist, _ = calculate_mixing_distances(scenario, radiation_mixing_matrix)

# Create comprehensive mixing analysis
fig, axes = plt.subplots(2, 3, figsize=(18, 12))

# Plot 1: Mixing matrices
im1 = axes[0, 0].imshow(gravity_mixing_matrix, cmap='Blues', aspect='auto')
axes[0, 0].set_title('Gravity Mixing Matrix')
axes[0, 0].set_xlabel('Destination Patch')
axes[0, 0].set_ylabel('Source Patch')
plt.colorbar(im1, ax=axes[0, 0], label='Mixing Probability')

im2 = axes[0, 1].imshow(radiation_mixing_matrix, cmap='Reds', aspect='auto')
axes[0, 1].set_title('Radiation Mixing Matrix')
axes[0, 1].set_xlabel('Destination Patch')
axes[0, 1].set_ylabel('Source Patch')
plt.colorbar(im2, ax=axes[0, 1], label='Mixing Probability')

# Plot difference
diff_matrix = gravity_mixing_matrix - radiation_mixing_matrix
im3 = axes[0, 2].imshow(diff_matrix, cmap='RdBu_r', aspect='auto',
                       vmin=-np.max(np.abs(diff_matrix)),
                       vmax=np.max(np.abs(diff_matrix)))
axes[0, 2].set_title('Difference (Gravity - Radiation)')
axes[0, 2].set_xlabel('Destination Patch')
axes[0, 2].set_ylabel('Source Patch')
plt.colorbar(im3, ax=axes[0, 2], label='Probability Difference')

# Plot 2: Mixing distance profiles
patch_positions = scenario['lon'].to_numpy()  # Use longitude as position along chain
axes[1, 0].plot(patch_positions, gravity_mix_dist, 'b-o', label='Gravity', linewidth=2, markersize=4)
axes[1, 0].plot(patch_positions, radiation_mix_dist, 'r-s', label='Radiation', linewidth=2, markersize=4)
axes[1, 0].set_xlabel('Patch Position (Longitude)')
axes[1, 0].set_ylabel('Average Mixing Distance')
axes[1, 0].set_title('Mixing Distance Profiles')
# axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.3)

# Plot 3: Population vs mixing distance
pop_sizes = scenario['pop'].to_numpy()
axes[1, 1].scatter(pop_sizes, gravity_mix_dist, c='blue', alpha=0.7, s=50, label='Gravity')
axes[1, 1].scatter(pop_sizes, radiation_mix_dist, c='red', alpha=0.7, s=50, label='Radiation')
axes[1, 1].set_xlabel('Population Size')
axes[1, 1].set_ylabel('Average Mixing Distance')
axes[1, 1].set_title('Population Size vs Mixing Distance')
# axes[1, 1].legend()
axes[1, 1].grid(True, alpha=0.3)

# Plot 4: Mixing strength vs distance for representative patches
# Choose patches at positions 5, 15, 25 (left, center, right)
representative_patches = [5, 15, 25]
colors = ['green', 'orange', 'purple']

for idx, patch_i in enumerate(representative_patches):
    distances_from_patch = distance_matrix[patch_i, :]
    gravity_mixing_from_patch = gravity_mixing_matrix[patch_i, :]
    radiation_mixing_from_patch = radiation_mixing_matrix[patch_i, :]

    # Sort by distance for cleaner plotting
    sort_idx = np.argsort(distances_from_patch)
    sorted_distances = distances_from_patch[sort_idx]
    sorted_gravity = gravity_mixing_from_patch[sort_idx]
    sorted_radiation = radiation_mixing_from_patch[sort_idx]

    axes[1, 2].plot(sorted_distances, sorted_gravity, '-',
                   color=colors[idx], alpha=0.7, linewidth=2,
                   label=f'Gravity (Patch {patch_i})')
    axes[1, 2].plot(sorted_distances, sorted_radiation, '--',
                   color=colors[idx], alpha=0.7, linewidth=2,
                   label=f'Radiation (Patch {patch_i})')

axes[1, 2].set_xlabel('Distance')
axes[1, 2].set_ylabel('Mixing Probability')
axes[1, 2].set_title('Mixing vs Distance (Representative Patches)')
# axes[1, 2].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
axes[1, 2].grid(True, alpha=0.3)
axes[1, 2].set_yscale('log')

plt.tight_layout()
plt.show()

# Print quantitative comparison
print("=== QUANTITATIVE MIXING ANALYSIS ===")
print(f"Gravity model - Mean mixing distance: {gravity_mix_dist.mean():.3f} ± {gravity_mix_dist.std():.3f}")
print(f"Radiation model - Mean mixing distance: {radiation_mix_dist.mean():.3f} ± {radiation_mix_dist.std():.3f}")

# Calculate spatial coupling metrics
gravity_off_diag = gravity_mixing_matrix.copy()
np.fill_diagonal(gravity_off_diag, 0)
radiation_off_diag = radiation_mixing_matrix.copy()
np.fill_diagonal(radiation_off_diag, 0)

print(f"\nGravity model - Off-diagonal mixing (total spatial coupling): {gravity_off_diag.sum():.3f}")
print(f"Radiation model - Off-diagonal mixing (total spatial coupling): {radiation_off_diag.sum():.3f}")

# Calculate mixing inequality (how evenly distributed is mixing)
def mixing_inequality(mixing_matrix):
    """Calculate Gini coefficient of mixing probabilities (excluding diagonal)"""
    off_diag = mixing_matrix.copy()
    np.fill_diagonal(off_diag, 0)
    probs = off_diag.flatten()
    probs = probs[probs > 0]  # Only consider non-zero probabilities
    if len(probs) == 0:
        return 0
    probs = np.sort(probs)
    n = len(probs)
    cumsum = np.cumsum(probs)
    return (2 * np.sum((np.arange(1, n+1) * probs))) / (n * cumsum[-1]) - (n + 1) / n

gravity_gini = mixing_inequality(gravity_mixing_matrix)
radiation_gini = mixing_inequality(radiation_mixing_matrix)

print(f"\nGravity model - Mixing inequality (Gini): {gravity_gini:.3f}")
print(f"Radiation model - Mixing inequality (Gini): {radiation_gini:.3f}")
print("(Higher Gini = more unequal mixing, more concentrated on specific connections)")

# %% [markdown]
# ## Key Insights and Summary
#
# This tutorial demonstrated dramatic differences between gravity and radiation mixing models
# using a linear chain scenario and extreme parameter settings. Here are the key findings:
#
# ### Technical Configuration
#
# To create dramatic model differences in your analysis:
#
# ```python
# # Extreme gravity parameters for demonstration
# gravity_params = GravityParams(
#     a=1.0,  # Source population exponent
#     b=2.0,  # High target population attraction
#     c=1.0,  # Low distance decay for long-range connections
#     k=0.01  # Overall mixing scale
# )
#
# # Radiation parameters
# radiation_params = RadiationParams(
#     k=0.01,           # Same mixing scale for fair comparison
#     include_home=True # Include self-mixing
# )
#
# # Use linear or chain-like scenarios to highlight intervening opportunities
# ```
#
# ### Key Takeaway
# **The choice of spatial mixing model can dramatically affect both the spatial patterns
# and temporal dynamics of epidemic spread.** Always compare multiple models and use
# quantitative metrics (mixing distances, spatial coupling, epidemic velocity) to
# understand how your choice affects results.
#
# Different mixing models represent different theories of human mobility and contact patterns.
# The "best" model depends on your research question, available data, and the geographic
# context of your study.
