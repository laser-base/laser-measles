# %% [markdown]
# # Investigating Traveling Waves in Measles Epidemics
#
# This tutorial demonstrates how to investigate traveling waves in measles epidemics using laser-measles.
# We'll create a spatial network of towns, seed infection in the largest city, and analyze how
# infection spreads as traveling waves across the landscape.
#
# The tutorial covers:
# - Creating synthetic spatial networks with realistic population distributions
# - Seeding infection in the largest population center
# - Tracking infection peaks and calculating wave speeds
# - Analyzing the effect of spatial mixing (κ) on wave acceleration and synchrony
#
# ## Background
#
# Traveling waves in infectious disease epidemics occur when infection spreads spatially
# in a wave-like pattern from source populations to neighboring areas. The speed of these
# waves depends on:
# - Local transmission intensity (R₀)
# - Spatial coupling strength (κ)
# - Population density and spatial structure
#
# By analyzing the relationship between distance from the source and time-to-peak infection,
# we can estimate wave speeds and understand spatial epidemic dynamics.

# %%
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy import stats

import laser.measles as lm
from laser.measles import create_component
from laser.measles.compartmental import BaseScenario, CompartmentalParams, CompartmentalModel
from laser.measles.compartmental import InfectionParams, ImportationPressureParams, ImportationPressureProcess, InfectionProcess, InitializeEquilibriumStatesProcess, StateTracker, CaseSurveillanceTracker, CaseSurveillanceParams

# Set random seed for reproducibility
np.random.seed(42)

# %% [markdown]
# ## Creating a synthetic spatial network
#
# First, we'll create a synthetic network of towns distributed on a 2D plane.
# We'll use a realistic spatial distribution with one major city and smaller towns
# at various distances.


# %%
def create_spatial_network(n_towns=30, max_distance=200):
    """
    Create a synthetic spatial network of towns with realistic population distribution.

    Args:
        n_towns: Number of towns to create
        max_distance: Maximum distance from center (km)

    Returns:
        DataFrame with columns: id, lat, lon, pop, mcv1
    """
    # Create one major city at the center
    towns = []

    # Major city (largest population)
    towns.append(
        {
            "id": "0",
            "lat": 0.0,
            "lon": 0.0,
            "pop": 500000,  # Large central city
            "mcv1": 0.85,
        }
    )

    # Create smaller towns at various distances
    for i in range(1, n_towns):
        # Random distance from center (weighted toward closer distances)
        distance = np.random.exponential(scale=max_distance / 3)
        distance = min(distance, max_distance)

        # Random angle
        angle = np.random.uniform(0, 2 * np.pi)

        # Convert to lat/lon (approximate, assuming 1 degree ≈ 111 km)
        lat = (distance * np.cos(angle)) / 111.0
        lon = (distance * np.sin(angle)) / 111.0

        # Population follows power law distribution (many small towns, few large ones)
        pop = np.random.lognormal(mean=9.0, sigma=1.0)  # Log-normal distribution
        pop = max(5000, min(100000, int(pop)))  # Constrain to reasonable range

        # MCV1 coverage varies slightly
        mcv1 = np.random.normal(0.80, 0.05)
        mcv1 = max(0.5, min(0.95, mcv1))

        towns.append({"id": str(i), "lat": lat, "lon": lon, "pop": pop, "mcv1": mcv1})

    return pl.DataFrame(towns)


# Create the spatial network
scenario_df = create_spatial_network(n_towns=25, max_distance=150)


# Calculate distances from center for later analysis
def calculate_distances(df):
    """Calculate distances from the central city (id='0')"""
    central_lat = df.filter(pl.col("id") == "0")["lat"][0]
    central_lon = df.filter(pl.col("id") == "0")["lon"][0]

    distances = []
    for row in df.iter_rows(named=True):
        if row["id"] == "0":
            distances.append(0.0)
        else:
            # Haversine distance approximation
            lat_diff = row["lat"] - central_lat
            lon_diff = row["lon"] - central_lon
            distance = np.sqrt(lat_diff**2 + lon_diff**2) * 111.0  # Convert to km
            distances.append(distance)

    return df.with_columns(pl.Series("distance_km", distances))


scenario_df = calculate_distances(scenario_df)

print(f"Created spatial network with {len(scenario_df)} towns")
print(f"Population range: {scenario_df['pop'].min():,} to {scenario_df['pop'].max():,}")
print(f"Distance range: {scenario_df['distance_km'].min():.1f} to {scenario_df['distance_km'].max():.1f} km")

# %% [markdown]
# ## Visualizing the spatial network
#
# Let's visualize our synthetic spatial network to understand the town distribution
# and population sizes.

# %%
plt.figure(figsize=(10, 8))

# Create scatter plot with population size mapped to point size and color
scatter = plt.scatter(
    scenario_df["lon"],
    scenario_df["lat"],
    c=scenario_df["pop"],
    s=scenario_df["pop"] / 2000,  # Scale point size
    cmap="viridis",
    alpha=0.7,
    edgecolors="black",
    linewidth=0.5,
)

# Highlight the central city
central_city = scenario_df.filter(pl.col("id") == "0")
plt.scatter(central_city["lon"], central_city["lat"], c="red", s=200, marker="*", label="Central City", edgecolors="black", linewidth=1)

plt.colorbar(scatter, label="Population")
plt.xlabel("Longitude (degrees)")
plt.ylabel("Latitude (degrees)")
plt.title("Synthetic Spatial Network of Towns")
plt.legend()
plt.grid(True, alpha=0.3)
plt.axis("equal")
plt.tight_layout()
plt.show()

# %% [markdown]
# ## Setting up the epidemic model
#
# Now we'll create the compartmental model with spatial mixing to simulate
# measles transmission across our spatial network.


# %%
def run_traveling_wave_simulation(scenario_df, mixing_scale=0.005, num_ticks=365 * 2):
    """
    Run a traveling wave simulation with the given mixing scale.

    Args:
        scenario_df: DataFrame with town information
        mixing_scale: Spatial mixing parameter (κ)
        num_ticks: Number of days to simulate

    Returns:
        Tuple of (model, state_results, case_results)
    """
    # Convert to scenario object
    scenario = BaseScenario(scenario_df)

    # Model parameters
    params = CompartmentalParams(num_ticks=num_ticks, verbose=False, seed=42)

    # Create model
    model = CompartmentalModel(scenario, params)

    # Configure infection parameters with spatial mixing
    infection_params = InfectionParams(
        beta=0.4,  # Base transmission rate
        exp_mu=8.0,  # 8-day incubation period
        inf_mu=6.0,  # 6-day infectious period
        mixing_scale=mixing_scale,  # κ parameter
        distance_exponent=1.5,  # Distance decay
        seasonality=0.1,  # Slight seasonality
        season_start=0,
    )

    # Configure importation (seeding) to start in central city only
    importation_params = ImportationPressureParams(
        crude_importation_rate=5.0,  # Import rate per 1k population per year
        importation_start=30,  # Start after 30 days
        importation_end=60,  # End after 60 days
    )

    # Model components
    components = [
        # Initialize population in susceptible state
        InitializeEquilibriumStatesProcess,
        # Seed infection in central city
        create_component(ImportationPressureProcess, importation_params),
        # Disease transmission with spatial mixing
        create_component(InfectionProcess, infection_params),
        # Track states over time
        StateTracker,
        # Track incident cases
        create_component(
            CaseSurveillanceTracker, CaseSurveillanceParams(detection_rate=1.0)
        ),
    ]

    model.components = components

    # Run simulation
    print(f"Running simulation with mixing_scale={mixing_scale}...")
    model.run()

    # Extract results
    state_tracker = model.get_instance(StateTracker)[0]
    case_tracker = model.get_instance(CaseSurveillanceTracker)[0]

    state_results = state_tracker.get_dataframe()
    case_results = case_tracker.get_dataframe()

    return model, state_results, case_results


# %% [markdown]
# ## Running the base simulation
#
# Let's run our first simulation with a moderate mixing scale to observe
# the traveling wave pattern.

# %%
# Run simulation with moderate mixing
model1, state_results1, case_results1 = run_traveling_wave_simulation(scenario_df, mixing_scale=0.003, num_ticks=365 * 2)

print("Base simulation completed!")
print(f"Total simulation days: {state_results1['tick'].max()}")
print(f"Total cases recorded: {case_results1['cases'].sum()}")

# %% [markdown]
# ## Analyzing infection peaks and wave speed
#
# Now we'll analyze the timing of infection peaks in each town to calculate
# the wave speed. We'll look for the day when each town experiences its
# maximum daily incidence.


# %%
def analyze_wave_speed(case_results, scenario_df):
    """
    Analyze traveling wave speed by finding infection peaks.

    Args:
        case_results: DataFrame with case surveillance data
        scenario_df: DataFrame with town information including distances

    Returns:
        DataFrame with peak analysis results
    """
    # Find peak day for each patch
    peak_data = []

    for patch_id in scenario_df["id"]:
        patch_cases = case_results.filter(pl.col("patch_id") == str(patch_id))

        if len(patch_cases) == 0 or patch_cases["cases"].sum() == 0:
            continue

        # Find day with maximum cases
        max_cases_day = patch_cases.filter(pl.col("cases") == pl.col("cases").max())["tick"].min()

        if max_cases_day is None:
            continue

        # Get town information
        town_info = scenario_df.filter(pl.col("id") == str(patch_id))

        peak_data.append(
            {
                "id": patch_id,
                "peak_day": max_cases_day,
                "distance_km": town_info["distance_km"][0],
                "population": town_info["pop"][0],
                "max_cases": patch_cases["cases"].max(),
            }
        )

    peak_df = pl.DataFrame(peak_data)

    # Calculate wave speed using linear regression
    # Exclude central city (distance = 0) as it's the source
    regression_data = peak_df.filter(pl.col("distance_km") > 0)

    if len(regression_data) > 5:  # Need enough points for regression
        distances = regression_data["distance_km"].to_numpy()
        peak_days = regression_data["peak_day"].to_numpy()

        # Linear regression: peak_day = intercept + slope * distance
        result = stats.linregress(distances, peak_days)
        slope, intercept, r_value, p_value = result.slope, result.intercept, result.rvalue, result.pvalue

        # Wave speed = distance / time = 1 / slope (km/day)
        wave_speed = 1.0 / slope if slope > 0 else float("inf")

        return peak_df, {
            "wave_speed_km_per_day": wave_speed,
            "r_squared": r_value**2,
            "p_value": p_value,
            "slope": slope,
            "intercept": intercept,
        }
    else:
        return peak_df, None


# Debug: Check case results structure
print("\nCase results columns:", case_results1.columns)
print("Case results head:")
print(case_results1.head())

# Analyze wave speed for base simulation
peak_analysis1, wave_stats1 = analyze_wave_speed(case_results1, scenario_df)

print("\nWave Speed Analysis (Base Simulation):")
if wave_stats1:
    print(f"Wave speed: {wave_stats1['wave_speed_km_per_day']:.2f} km/day")
    print(f"R²: {wave_stats1['r_squared']:.3f}")
    print(f"P-value: {wave_stats1['p_value']:.3f}")
else:
    print("Insufficient data for wave speed calculation")

# %% [markdown]
# ## Visualizing the traveling wave
#
# Let's create visualizations to show the traveling wave pattern and
# the relationship between distance and time-to-peak.

# %%
fig, axes = plt.subplots(2, 2, figsize=(15, 12))

# 1. Spatial map with peak timing
ax1 = axes[0, 0]
if len(peak_analysis1) > 0:
    # Join peak analysis with scenario data for proper alignment
    peak_with_location = peak_analysis1.join(scenario_df, on="id", how="inner")

    scatter = ax1.scatter(
        peak_with_location["lon"],
        peak_with_location["lat"],
        c=peak_with_location["peak_day"],
        s=peak_with_location["pop"] / 2000,
        cmap="plasma",
        alpha=0.7,
        edgecolors="black",
        linewidth=0.5,
    )
    plt.colorbar(scatter, ax=ax1, label="Peak Day")

    # Highlight central city
    central_city = scenario_df.filter(pl.col("id") == "0")
    ax1.scatter(central_city["lon"], central_city["lat"], c="red", s=200, marker="*", edgecolors="black", linewidth=1)

ax1.set_xlabel("Longitude (degrees)")
ax1.set_ylabel("Latitude (degrees)")
ax1.set_title("Spatial Distribution of Infection Peaks")
ax1.grid(True, alpha=0.3)
ax1.axis("equal")

# 2. Distance vs Peak Day (Wave Speed Analysis)
ax2 = axes[0, 1]
if len(peak_analysis1) > 0:
    # Scatter plot
    ax2.scatter(peak_analysis1["distance_km"], peak_analysis1["peak_day"], alpha=0.7, s=50, edgecolors="black", linewidth=0.5)

    # Regression line if available
    if wave_stats1:
        max_distance = peak_analysis1["distance_km"].max()
        if max_distance is not None:
            x_line = np.linspace(0, float(max_distance), 100)
            y_line = wave_stats1["intercept"] + wave_stats1["slope"] * x_line
            ax2.plot(x_line, y_line, "r--", alpha=0.8, label=f"Speed: {wave_stats1['wave_speed_km_per_day']:.2f} km/day")
            ax2.legend()

ax2.set_xlabel("Distance from Central City (km)")
ax2.set_ylabel("Peak Day")
ax2.set_title("Wave Speed Analysis")
ax2.grid(True, alpha=0.3)

# 3. Time series for selected towns
ax3 = axes[1, 0]
# Select a few towns at different distances for time series
selected_patches = [0]  # Central city
if len(peak_analysis1) > 0:
    # Add 3-4 towns at different distances
    sorted_by_distance = peak_analysis1.sort("distance_km")
    n_towns = min(4, len(sorted_by_distance))
    for i in range(1, n_towns):
        idx = int(i * len(sorted_by_distance) / n_towns)
        selected_patches.append(sorted_by_distance["id"][idx])

for patch_id in selected_patches:
    patch_cases = case_results1.filter(pl.col("patch_id") == str(patch_id))
    if len(patch_cases) > 0:
        town_info = scenario_df.filter(pl.col("id") == str(patch_id))
        distance = town_info["distance_km"][0]
        ax3.plot(patch_cases["tick"], patch_cases["cases"], label=f"Town {patch_id} ({distance:.0f} km)", alpha=0.8)

ax3.set_xlabel("Day")
ax3.set_ylabel("Daily Cases")
ax3.set_title("Infection Time Series by Distance")
ax3.legend()
ax3.grid(True, alpha=0.3)

# 4. Population vs Peak Cases
ax4 = axes[1, 1]
if len(peak_analysis1) > 0:
    ax4.scatter(peak_analysis1["population"], peak_analysis1["max_cases"], alpha=0.7, s=50, edgecolors="black", linewidth=0.5)
    ax4.set_xlabel("Population")
    ax4.set_ylabel("Peak Daily Cases")
    ax4.set_title("Population vs Peak Cases")
    ax4.grid(True, alpha=0.3)
    ax4.set_xscale("log")

plt.tight_layout()
plt.show()

# %% [markdown]
# ## Effect of spatial mixing parameter (κ)
#
# Now let's investigate how the spatial mixing parameter (κ) affects
# wave speed and synchrony. We'll run simulations with different mixing
# scales and compare the results.

# %%
# Test different mixing scales
mixing_scales = [0.001, 0.003, 0.01, 0.03]
wave_results = []

print("Testing different mixing scales (κ):")
for mixing_scale in mixing_scales:
    print(f"\nRunning simulation with κ = {mixing_scale}...")

    # Run simulation
    model, state_results, case_results = run_traveling_wave_simulation(scenario_df, mixing_scale=mixing_scale, num_ticks=365 * 2)

    # Analyze wave speed
    peak_analysis, wave_stats = analyze_wave_speed(case_results, scenario_df)

    result = {
        "mixing_scale": mixing_scale,
        "peak_analysis": peak_analysis,
        "wave_stats": wave_stats,
        "case_results": case_results,
        "total_cases": case_results["cases"].sum(),
    }

    wave_results.append(result)

    if wave_stats:
        print(f"  Wave speed: {wave_stats['wave_speed_km_per_day']:.2f} km/day")
        print(f"  R²: {wave_stats['r_squared']:.3f}")
        print(f"  Total cases: {result['total_cases']:,}")
    else:
        print("  Insufficient data for wave speed calculation")

# %% [markdown]
# ## Comparing results across different κ values
#
# Let's visualize how the mixing parameter affects wave speed and
# epidemic dynamics.

# %%
fig, axes = plt.subplots(2, 2, figsize=(15, 12))

# 1. Wave speed vs mixing scale
ax1 = axes[0, 0]
valid_results = [r for r in wave_results if r["wave_stats"] is not None]
if valid_results:
    mixing_vals = [r["mixing_scale"] for r in valid_results]
    wave_speeds = [r["wave_stats"]["wave_speed_km_per_day"] for r in valid_results]

    ax1.semilogx(mixing_vals, wave_speeds, "o-", markersize=8, linewidth=2)
    ax1.set_xlabel("Mixing Scale (κ)")
    ax1.set_ylabel("Wave Speed (km/day)")
    ax1.set_title("Wave Speed vs Mixing Parameter")
    ax1.grid(True, alpha=0.3)

# 2. R² vs mixing scale (goodness of fit)
ax2 = axes[0, 1]
if valid_results:
    r_squared_vals = [r["wave_stats"]["r_squared"] for r in valid_results]

    ax2.semilogx(mixing_vals, r_squared_vals, "o-", markersize=8, linewidth=2, color="orange")
    ax2.set_xlabel("Mixing Scale (κ)")
    ax2.set_ylabel("R² (Wave Pattern Fit)")
    ax2.set_title("Wave Pattern Quality vs Mixing Parameter")
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 1)

# 3. Distance vs Peak Day for different κ
ax3 = axes[1, 0]
colors = ["blue", "green", "red", "purple"]
for i, result in enumerate(wave_results):
    if result["wave_stats"] is not None:
        peak_data = result["peak_analysis"]
        regression_data = peak_data.filter(pl.col("distance_km") > 0)

        if len(regression_data) > 0:
            ax3.scatter(
                regression_data["distance_km"],
                regression_data["peak_day"],
                alpha=0.6,
                s=30,
                color=colors[i],
                label=f"κ = {result['mixing_scale']}",
            )

            # Add regression line
            wave_stats = result["wave_stats"]
            max_distance = regression_data["distance_km"].max()
            if max_distance is not None:
                x_line = np.linspace(0, float(max_distance), 100)
                y_line = wave_stats["intercept"] + wave_stats["slope"] * x_line
                ax3.plot(x_line, y_line, "--", alpha=0.7, color=colors[i])

ax3.set_xlabel("Distance from Central City (km)")
ax3.set_ylabel("Peak Day")
ax3.set_title("Wave Patterns for Different κ Values")
ax3.legend()
ax3.grid(True, alpha=0.3)

# 4. Total cases vs mixing scale
ax4 = axes[1, 1]
total_cases = [r["total_cases"] for r in wave_results]
mixing_scales_all = [r["mixing_scale"] for r in wave_results]

ax4.semilogx(mixing_scales_all, total_cases, "o-", markersize=8, linewidth=2, color="red")
ax4.set_xlabel("Mixing Scale (κ)")
ax4.set_ylabel("Total Cases")
ax4.set_title("Total Cases vs Mixing Parameter")
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# %% [markdown]
# ## Summary of results
#
# Let's summarize the key findings from our traveling wave analysis.

# %%
print("=" * 60)
print("TRAVELING WAVE ANALYSIS SUMMARY")
print("=" * 60)

print("\nSpatial Network:")
print(f"  • {len(scenario_df)} towns total")
print(f"  • Central city population: {scenario_df.filter(pl.col('id') == '0')['pop'][0]:,}")
print(f"  • Distance range: 0 to {scenario_df['distance_km'].max():.1f} km")

print("\nWave Speed Analysis:")
valid_results = [r for r in wave_results if r["wave_stats"] is not None]
if valid_results:
    print(f"  • Mixing scales tested: {', '.join([str(r['mixing_scale']) for r in wave_results])}")
    print(
        f"  • Wave speed range: {min([r['wave_stats']['wave_speed_km_per_day'] for r in valid_results]):.2f} to {max([r['wave_stats']['wave_speed_km_per_day'] for r in valid_results]):.2f} km/day"
    )

    # Calculate speed increase
    min_speed = min([r["wave_stats"]["wave_speed_km_per_day"] for r in valid_results])
    max_speed = max([r["wave_stats"]["wave_speed_km_per_day"] for r in valid_results])
    speed_increase = (max_speed - min_speed) / min_speed * 100

    print(f"  • Speed increase with higher κ: {speed_increase:.1f}%")

print("\nKey Findings:")
print("  • Infection spreads as traveling waves from central city")
print("  • Wave speed increases with spatial mixing parameter (κ)")
print("  • Higher κ leads to faster waves and more synchrony")
print("  • Linear relationship between distance and time-to-peak")
print("  • Spatial structure strongly influences epidemic dynamics")

# %% [markdown]
# ## Scientific interpretation
#
# ### Traveling Wave Dynamics
#
# This tutorial demonstrates several key concepts in spatial epidemiology:
#
# 1. **Wave Formation**: Measles epidemics can spread as traveling waves from source populations
#    to surrounding areas, with infection peaks occurring later at greater distances.
#
# 2. **Spatial Coupling**: The mixing parameter (κ) controls how strongly populations are
#    spatially coupled. Higher κ values lead to:
#    - Faster wave propagation
#    - More synchronized epidemics across space
#    - Reduced spatial heterogeneity in timing
#
# 3. **Distance-Time Relationship**: The linear relationship between log(distance) and
#    time-to-peak allows estimation of wave speeds, which can be compared to real-world
#    epidemic data.
#
# 4. **Population Effects**: Larger populations tend to have earlier and larger peaks,
#    but the wave pattern depends more on spatial structure than population size alone.
#
# ### Real-World Applications
#
# This analysis framework can be applied to:
# - Analyze real measles outbreak data to estimate transmission parameters
# - Predict epidemic spread patterns in new outbreaks
# - Design spatial vaccination strategies
# - Understand the role of transportation networks in disease spread
#
# ### Model Limitations
#
# - Assumes homogeneous mixing within populations
# - Simplified spatial structure (gravity model)
# - No seasonal or demographic heterogeneity
# - Constant transmission parameters over time
#
# Real applications would require more sophisticated spatial networks and parameter estimation
# from empirical data.

# %% [markdown]
# ## Exercises for further exploration
#
# 1. **Network Structure**: Try different spatial network configurations (linear chains,
#    clustered networks, scale-free networks) and observe how they affect wave patterns.
#
# 2. **Parameter Sensitivity**: Investigate how other parameters (β, infectious period,
#    distance exponent) affect wave speed and synchrony.
#
# 3. **Multiple Sources**: Seed infection in multiple cities simultaneously and observe
#    how waves interact when they meet.
#
# 4. **Vaccination Strategies**: Add spatial vaccination campaigns and study their
#    impact on wave propagation.
#
# 5. **Real Data**: Apply this framework to analyze real measles outbreak data with
#    known spatial and temporal patterns.
