# %% [markdown]
# # ABM model introduction
#
# This tutorial serves as an introduction to the ABM model in laser-measles.
#
# As introduced in the "model structure" tutorial, the ABM model keeps track of
# individual agents located in the `people` LaserFrame. In order to improve
# performance, laser-measles stores agent attributes in a single LaserFrame with an
# array associated with each attribute (rather than a single array of pointers to an
# agent class structure).
#
# This tutorial covers important details on model initialization and setup.
# When we first setup the model you'll note that the capacity and count of the
# LaserFrame is 1 even though the scenario has an initial population of 150k.
#
# %%
from laser.measles.abm.model import ABMModel
from laser.measles.scenarios.synthetic import two_patch_scenario
from laser.measles.abm.model import ABMParams
scenario = two_patch_scenario()
params = ABMParams(seed=20250314, start_time="2000-01", num_ticks=365)
model = ABMModel(scenario=scenario, params=params)
print("Initial scenario:")
print(scenario.head())
print("Initial people LaserFrame:")
print(model.people)

# %% [markdown]
# The reason for this is that initialization of the agents (for example, age distribution and susceptibility)
# is dealt with by the components you add. However, to be able to maintain the cross-over with the
# compartmental models we assume no vital dynamics unless otherwise provided. For example, if we
# initialize with the rough equilibrium distribution between S and R the LaserFrame is
# initialized appropriately with 150k agents.
# %%
from laser.measles.abm.components import ConstantPopProcess
model = ABMModel(scenario=scenario, params=params)
model.add_component(ConstantPopProcess)
print(model.people)
# %% [markdown]
# If, we run the model without adding a component that sets the vital dynamics, then
# the `NoBirthsProcess` is added by default:
# %%
from laser.measles.abm.components import InfectionProcess, InfectionSeedingProcess
def make_model():
    model = ABMModel(scenario=scenario, params=params)
    model.components = [InfectionSeedingProcess, InfectionProcess]
    model.run()
    return model
model = make_model()
print("People LaserFrame:")
print(model.people)
print("Model components:")
print(model.components)
# %% [markdown]
# One of the reasons the abm model waits to initialize the LaserFrame until
# a component with vital dynamics is added is because the *capacity* (or size)
# of the LaserFrame/arrays needs to be determined based on how the population
# is expected to grow over the course of the simulation. In order to manage this,
# a component that sets the vital dynamics has a 'calculate_capacity` method that
# returns the requires array size based on the duration of the simulation.
#
# For example, the `ConstantPopProcess` recycles entries in the arrays so that
# the array sizes can remain the same
# %%
model = make_model()
vd = ConstantPopProcess(model)
print(f"Capacity for a constant population size: {vd.calculate_capacity(model)}")
#
# %% [markdown]
# In the case the population will grow in size then the capacity of the LaserFrame
# also grows. The LaserFrame has some special methods that differentiate between the
# size of the array holding agents that have entered the simulation and what is the
# full size of the arrays in memory.
#
# The `VitalDynamicsProcess` is a constant birth / mortality rate with no
# enforced age structure.
#  %%
from laser.measles.abm.components import VitalDynamicsProcess
model = make_model()
vd = VitalDynamicsProcess(model)
print(f"Capacity for the {model.params.num_ticks} tick simulation: {vd.calculate_capacity(model)}")
print(f"len(model.people): {len(model.people)} at the start of the simulation")
# %% [markdown]
# During the instantiation of the component, the `calculate_capacity` method
# is utilized to re-initialize the LaserFrame with the correct capacity. The
# `ABMModel` contains a method, `initialize_people_capacity` that goes through the existing
# LaserFrame attributes (for example, susceptibility, etimer, itimer) and constructs the
# arrays with the correct size.
# %%
help(model.initialize_people_capacity)
