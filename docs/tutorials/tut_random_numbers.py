# %% [markdown]
# # Random Numbers and Reproducibility
#
# This tutorial covers how random numbers are handled in laser-measles models to ensure reproducibility.
# Understanding this is crucial for debugging, testing, and scientific reproducibility.

# %% [markdown]
# ## Core concepts
#
# ### Model Seeding
#
# All laser-measles models automatically seed their random number generator from the `seed` parameter.
# If no seed is provided, the model uses the current microsecond timestamp.

# %%
from laser.measles.compartmental.model import CompartmentalModel
from laser.measles.compartmental.params import CompartmentalParams
from laser.measles.scenarios.synthetic import single_patch_scenario

# Create scenario and parameters
scenario = single_patch_scenario(population=10000)
params = CompartmentalParams(seed=42, num_ticks=100)

# Model automatically seeds from params.seed
model = CompartmentalModel(scenario, params)
print(f"Model PRNG seeded with: {params.seed}")

# %% [markdown]
# ### How laser.core Handles Seeding
#
# Behind the scenes, laser-measles uses `laser.core.random.seed()` to create the random number generator.
# This function does two important things:
#
# 1. **Creates a NumPy Generator**: Returns a `numpy.random.Generator` object seeded with the given value
# 2. **Seeds global random state**: Also seeds `numpy.random` and numba's random number generator
#
# This ensures both `model.prng` and `np.random` operations are reproducible.

# %%
from laser.core.random import seed as seed_prng

# This is what happens inside `BaseLaserModel.__init__`:
prng = seed_prng(42)
print(f"PRNG type: {type(prng)}")
print(f"Available methods: {len([m for m in dir(prng) if not m.startswith('_')])} methods")

# Some key methods available
print("Key methods:", ["random", "binomial", "poisson", "normal", "exponential", "lognormal"])

# %% [markdown]
# ### Reproducible Random Numbers
#
# The `model.prng` object provides access to the seeded random number generator.
# This ensures all random operations are reproducible when using the same seed.

# %%
import numpy as np

# Same seed produces identical results
model1 = CompartmentalModel(scenario, CompartmentalParams(seed=123, num_ticks=10))
model2 = CompartmentalModel(scenario, CompartmentalParams(seed=123, num_ticks=10))

# Draw random numbers from each model
random1 = model1.prng.random(5)
random2 = model2.prng.random(5)

print("Model 1 random numbers:", random1)
print("Model 2 random numbers:", random2)
print("Are they identical?", np.allclose(random1, random2))

# %% [markdown]
# ## Usage patterns
#
# ### Using model.prng in Components
#
# Components should use `model.prng` for random number generation to maintain reproducibility.
# This is how the biweekly infection process samples new infections:


# %%
# Example from biweekly infection process
def simulate_infections(model, susceptible_count, infection_probability):
    """Simulate new infections using model's PRNG"""
    # Use model.prng.binomial for stochastic sampling
    new_infections = model.prng.binomial(susceptible_count, infection_probability)
    return new_infections


# Demonstrate with our model
S = np.array([5000, 3000, 2000])  # Susceptible counts
prob = np.array([0.01, 0.02, 0.015])  # Infection probabilities

new_infections = simulate_infections(model, S, prob)
print("New infections by patch:", new_infections)

# %% [markdown]
# ### NumPy Random Functions
#
# For performance-critical code, especially with Numba, use `np.random` functions directly.
# This is common in ABM transmission processes for sampling exposure times:

# %%
import numba as nb

@nb.njit
def sample_exposure_times(count, mu, sigma):
    """Sample exposure times using lognormal distribution"""
    # Use np.random directly in numba functions
    return np.maximum(1, np.round(np.random.lognormal(mu, sigma, count)))

# Example parameters from ABM transmission
exp_mu = 6.0  # Mean exposure time
exp_sigma = 2.0  # Standard deviation

# Convert to lognormal parameters
mu_underlying = np.log(exp_mu**2 / np.sqrt(exp_mu**2 + exp_sigma**2))
sigma_underlying = np.sqrt(np.log(1 + (exp_sigma / exp_mu) ** 2))

# Set numpy seed for reproducibility
np.random.seed(42)
exposure_times = sample_exposure_times(10, mu_underlying, sigma_underlying)
print("Exposure times (days):", exposure_times)

# %% [markdown]
# ### Mixed Usage Example
#
# Real components often combine both approaches. Here's how the ABM transmission process works:

# %%
def transmission_example(model, forces, susceptible_agents):
    """Example showing mixed random number usage"""

    # Use model.prng for high-level decisions
    seasonal_factor = 1 + 0.1 * np.sin(2 * np.pi * model.time_elapsed() / 365)

    # Simulate infections using model.prng
    infected_mask = model.prng.random(len(susceptible_agents)) < forces[susceptible_agents]
    newly_infected = susceptible_agents[infected_mask]

    # Use np.random for detailed parameters (compatible with numba)
    if len(newly_infected) > 0:
        exposure_times = sample_exposure_times(len(newly_infected), mu_underlying, sigma_underlying)
        print(f"Infected {len(newly_infected)} agents with exposure times: {exposure_times}")

    return newly_infected


# Simulate with dummy data
susceptible_agents = np.array([0, 1, 2, 3, 4])
forces = np.array([0.1, 0.05, 0.15, 0.08, 0.12])

infected = transmission_example(model, forces, susceptible_agents)
print("Newly infected agents:", infected)

# %% [markdown]
# ## Best practices
#
# ### When to Use Each Approach
#
# **Use `model.prng`:**
# - For high-level stochastic processes (infections, births, deaths)
# - When you need reproducibility across model runs
# - For sampling from standard distributions (binomial, poisson, normal)
#
# **Use `np.random`:**
# - Inside `@nb.njit` compiled functions
# - For performance-critical loops
# - When working with specialized distributions

# %% [markdown]
# ### Testing Reproducibility
#
# Always test that your models produce identical results with the same seed:


# %%
def test_reproducibility():
    """Test that models with same seed produce identical results"""

    # Run same model twice with same seed
    results1 = []
    results2 = []

    for seed in [42, 123, 456]:
        model_a = CompartmentalModel(scenario, CompartmentalParams(seed=seed, num_ticks=10))
        model_b = CompartmentalModel(scenario, CompartmentalParams(seed=seed, num_ticks=10))

        # Sample some random numbers
        result_a = model_a.prng.random(5)
        result_b = model_b.prng.random(5)

        results1.append(result_a)
        results2.append(result_b)

    # Check all results are identical
    for i, (r1, r2) in enumerate(zip(results1, results2, strict=False)):
        print(f"Seed test {i + 1}: {'PASS' if np.allclose(r1, r2) else 'FAIL'}")


test_reproducibility()

# %% [markdown]
# ### Numba Compatibility
#
# When using numba, set numpy's global seed before calling compiled functions:


# %%
@nb.njit
def numba_random_example(n):
    """Example numba function using random numbers"""
    return np.random.exponential(2.0, n)


# Set seed before calling numba function
np.random.seed(789)
result1 = numba_random_example(5)

np.random.seed(789)  # Reset seed
result2 = numba_random_example(5)

print("Numba result 1:", result1)
print("Numba result 2:", result2)
print("Numba reproducible:", np.allclose(result1, result2))

# %% [markdown]
# ## Summary
#
# Key points for random numbers in laser-measles:
#
# 1. Set `seed` in model parameters for reproducibility
# 2. Use `model.prng` for component-level random operations
# 3. Use `np.random`  numba-compiled functions
#
# This ensures your models are reproducible and scientifically sound.
