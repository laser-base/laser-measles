# %% [markdown]
# # State Arrays
#
# This tutorial covers StateArray, a key data structure in laser-measles that provides
# convenient access to epidemiological state compartments.

# %% [markdown]
# ## Section 1: StateArray fundamentals

# %% [markdown]
# ### What is a StateArray?
#
# `StateArray` is a numpy array wrapper that extends `np.ndarray` to provide attribute-based
# access to epidemiological state compartments. Instead of remembering that `states[0]` is
# Susceptible and `states[1]` is Infectious, you can use intuitive names like `states.S`
# and `states.I`.

# %%
import numpy as np

from laser.measles.utils import StateArray

# %% [markdown]
# ### Construction
#
# `StateArray` is constructed with two parameters:
# - `input_array`: A numpy array (typically 2D with shape `(num_states, num_patches)`)
# - `state_names`: A list of state compartment names

# %%
# Example: Create a StateArray for a 3-patch SIR model
num_patches = 3
num_states = 3

# Create underlying numpy array
data = np.array(
    [
        [1000, 800, 1200],  # Susceptible population in each patch
        [10, 20, 5],  # Infectious population in each patch
        [0, 0, 0],  # Recovered population in each patch
    ]
)

# Wrap with StateArray
states = StateArray(data, state_names=["S", "I", "R"])
print("StateArray shape:", states.shape)
print("State names:", states._state_names)

# %% [markdown]
# ### Data storage
#
# `StateArray` uses standard numpy array storage with additional metadata:
# - The underlying data is stored as a regular numpy array
# - `_state_names` stores the list of state compartment names
# - `_state_indices` provides a mapping from names to array indices

# %%
print("Underlying data type:", type(states.view(np.ndarray)))
print("State indices mapping:", states._state_indices)

# %% [markdown]
# ### Access patterns
#
# `StateArray` supports both traditional numeric indexing and intuitive attribute access:

# %%
# Numeric access (backward compatible)
print("Susceptible (numeric):", states[0])
print("Infectious (numeric):", states[1])

# Attribute access (intuitive)
print("Susceptible (attribute):", states.S)
print("Infectious (attribute):", states.I)

# Both approaches access the same data
print("Same data?", np.array_equal(states[0], states.S))

# %% [markdown]
# ## Section 2: StateArray in practice

# %% [markdown]
# ### Usage in patches LaserFrame
#
# In laser-measles models, `StateArray` is used as the `states` property of the patches
# `LaserFrame`. This provides a convenient interface for accessing and modifying
# epidemiological compartments across spatial patches.

# %%
# Example showing how models initialize `StateArray`
# (This mimics what happens in actual model initialization)

# Simulate patch populations
patch_pops = np.array([1000, 800, 1200])
num_patches = len(patch_pops)

# Create states array for SEIR model
seir_states = np.zeros((4, num_patches))
seir_states[0] = patch_pops  # Initialize all as Susceptible

# Wrap with StateArray
patch_states = StateArray(seir_states, state_names=["S", "E", "I", "R"])

print("Initial populations:")
print(f"Susceptible: {patch_states.S}")
print(f"Exposed: {patch_states.E}")
print(f"Infectious: {patch_states.I}")
print(f"Recovered: {patch_states.R}")

# %% [markdown]
# ### Practical examples
#
# `StateArray` supports all numpy operations while maintaining readable code:

# %%
# Example 1: Calculate prevalence
total_pop = patch_states.sum(axis=0)
prevalence = patch_states.I / total_pop
print("Prevalence per patch:", prevalence)

# Example 2: Simulate some infections
new_infections = np.array([5, 3, 8])
patch_states.S -= new_infections
patch_states.E += new_infections

print("After infections:")
print(f"Susceptible: {patch_states.S}")
print(f"Exposed: {patch_states.E}")

# Example 3: Slicing operations work as expected
print("Total infectious across all patches:", patch_states.I.sum())
print("States in first patch:", patch_states[:, 0])

# %% [markdown]
# ### Benefits
#
# `StateArray` provides several key advantages:
#
# 1. **Readable Code**: `states.S` is more intuitive than `states[0]`
# 2. **Maintainability**: Adding/removing states doesn't break numeric indices
# 3. **Backward Compatibility**: Existing code using numeric indexing still works
# 4. **Full NumPy Support**: All numpy operations work seamlessly
# 5. **Error Prevention**: Typos in state names raise `AttributeError` immediately
# 6. **Flexibility**: Works with different model types (SIR, SEIR, etc.)

# %%
# Example: Error handling for invalid state names
try:
    invalid_state = patch_states.X  # X is not a valid state
except AttributeError as e:
    print(f"Error caught: {e}")

# Example: Different state configurations
sir_states = StateArray(np.zeros((3, 2)), state_names=["S", "I", "R"])
seirs_states = StateArray(np.zeros((5, 2)), state_names=["S", "E", "I", "R", "S2"])

print("SIR state names:", sir_states._state_names)
print("SEIRS state names:", seirs_states._state_names)

# %% [markdown]
# ## Summary
#
# `StateArray` is a wrapper that makes epidemiological modeling code more readable
# and maintainable. It provides intuitive access to disease compartments while preserving
# all the performance and functionality of numpy arrays. In laser-measles, it
# is used for the patches `LaserFrame`.
