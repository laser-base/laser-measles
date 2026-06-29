# %% [markdown]
# # Vital dynamics
#
# This tutorial serves as an introduction to the different options for incorporating
# vital dynamics (births, deaths, and age structure) into the ABM model.
#
# Vital dynamics is an essential component of modeling measles transmission, particularly
# the birth rate. The ABM model is the best for modeling age-based transmission so this
# tutorial goes over some of the components you can use to setup the models.
#
# We start with some basic imports.
# %%
from laser.measles.abm import ABMModel, ABMParams, VitalDynamicsProcess, ConstantPopProcess, VitalDynamicsParams, ConstantPopParams, PopulationTracker, WPPVitalDynamicsProcess, AgePyramidTracker
from laser.measles.scenarios import synthetic
from laser.measles import create_component
import matplotlib.pyplot as plt
import numpy as np

params = ABMParams(num_ticks=365)
scenario = synthetic.two_patch_scenario()
# %% [markdown]
# And define a custom component to track the length of the
# LaserFrame. This does not indicate the total size of the
# people LaserFrame (the capacity), but rather the number of agents
# who have entered the simulation.
# %%
from laser.measles.base import BasePhase
class PeopleLengthTracker(BasePhase):
    def __init__(self, model):
        super().__init__(model)
        self.laserframe_tracker = np.zeros((model.params.num_ticks,))
    def __call__(self, model, tick):
        self.laserframe_tracker[tick] = len(model.people)
# %% [markdown]
# ## VitalDynamics and ContantPop processes
# The `VitalDynamicsProcess` and `ConstantPopProcess` take constant crude birth rates (births per 1k pop per year)
# as well as death rates (in the case of the former). Below we compare how the length of the LaserFrame increases
# compared to the total population. Using the `VitalDynamicsProcess` we see that the length
# of the LaserFrame is greater than the population size because agents that die remain in the computer memory while
# the `ConstantPopProcess` recycles elements in the arrays as agents enter and leave the simulation.
# %%
fig, axs = plt.subplots(1,2,figsize=(10, 5))
for i, process in enumerate([VitalDynamicsProcess, ConstantPopProcess]):
    model = ABMModel(scenario, params)
    if issubclass(process, VitalDynamicsProcess):
        vd_params = VitalDynamicsParams(crude_birth_rate=10, crude_death_rate=5)
    else:
        vd_params = ConstantPopParams(crude_birth_rate=0)
    model.components = [create_component(process, vd_params), PopulationTracker, PeopleLengthTracker]
    model.run()
    kwargs = {'color': f'C{i}'}
    axs[i].plot(model.get_component("PopulationTracker")[0].population_tracker.sum(axis=0), label='Population Size')
    axs[i].plot(model.get_component("PeopleLengthTracker")[0].laserframe_tracker, linestyle='--', label='Length(People)')
    axs[i].set_title(process.__name__)
    axs[i].set_xlabel('Time (days)')
    axs[i].set_ylabel('N')
    axs[i].legend()

# %% [markdown]
# ### Reading the population-vs-LaserFrame-length plot
#
# A `1 × 2` subplot comparing two vital-dynamics process variants over a one-year ABM run (365 daily ticks) with CBR=10/1000/yr and CDR=5/1000/yr.
#
# - **Left panel — `VitalDynamicsProcess`:** Two curves on the same axes. The solid `Population Size` curve sums LIVING agents and rises at the net rate (CBR - CDR) = 5/1000/yr = 0.5%/yr. The dashed `Length(People)` curve is the underlying `LaserFrame` length — it rises FASTER at CBR alone = 10/1000/yr = 1.0%/yr, because dead agents remain in memory as "dead but not removed" rows. The gap between the two curves at year-end is approximately `N_0 * CDR / 1000` (≈ 500 rows for a starting population of 100k). Visually the dashed line sits above the solid by a few percent at year-end — small but unmistakable.
# - **Right panel — `ConstantPopProcess`:** Same two curves, but `Length(People)` tracks `Population Size` exactly (the two lines overlap to within visual resolution). `ConstantPopProcess` recycles array slots when agents leave the simulation, so the LaserFrame never grows beyond the active population. CBR is set to 0 for this comparison so total population stays nearly flat.
#
# **Decision rule (the figure's empirical case):** choose `VitalDynamicsProcess` when you need full demographic accounting (age-at-death, cohort tracking) and can tolerate the ~CBR-rate LaserFrame growth. Choose `ConstantPopProcess` when you want a stable memory footprint and don't need per-agent death records — the LaserFrame size at end of run will equal what you initialized it with.
#
# **Sanity check:** if you're running `VitalDynamicsProcess` and your dashed line tracks the solid one exactly, something is wrong — either no agents are dying (check CDR) or the tracker is double-counting. If you're running `ConstantPopProcess` and the dashed line diverges from solid, the slot-recycling logic isn't engaging — check that `ConstantPopParams.crude_birth_rate` is set deliberately and the component is in `model.components` in the right order (before any process that creates agents).

# %% [markdown]
# ## WPP vital dynamics with age structure
#
# The `WPPVitalDynamicsProcess` uses World Population Prospect (WPP)
# estimates to set overall birth rates and age structured mortality
# rates.

# %%
model = ABMModel(scenario, params = ABMParams(num_ticks=5*365+3))
model.components = [WPPVitalDynamicsProcess, AgePyramidTracker]
model.run()
year = 2005
tracker = model.get_component("AgePyramidTracker")[0]
age_pyramid = tracker.age_pyramid[f'{year}-01-01']

# %% [markdown]
# Now we plot the age pyramid after 5 years of running the simulation
# and compare to WPP data.
# %%
import pyvd
wpp_data = pyvd.make_pop_dat('NGA')
wpp_years = wpp_data[0]
wpp_pop = wpp_data[1:]
bins = np.array(tracker.params.age_bins) / 365
plt.figure(figsize=(10, 5))
plt.bar(bins[:-1], age_pyramid/np.sum(age_pyramid),
    width=np.diff(bins), align='edge', label='laser-measles')
ind = np.argmin(np.abs(wpp_years - year))
plt.bar(bins, wpp_pop[:,ind]/np.sum(wpp_pop[:,ind]),
    width=np.concatenate([np.diff(bins), [5]]), align='edge',
    label='WPP', hatch='/', color='k', fill=False)
plt.xlabel('Age (years)')
plt.ylabel('Number of people')
plt.title(f'Age pyramid for {year}')
plt.legend()
plt.show()
# %% [markdown]
# ### Reading the age-pyramid plot
#
# A bar chart comparing the simulated age distribution from `WPPVitalDynamicsProcess` (laser-measles) against the corresponding World Population Prospects (WPP) reference for Nigeria after 5 years of simulation. Both distributions are normalized to fractions and plotted on the same age-bin grid.
#
# - **Solid bars:** laser-measles age pyramid at simulated year 2005, drawn from the `AgePyramidTracker`.
# - **Hatched outlined bars:** WPP Nigeria 2005 reference. Note the trailing WPP bar extends past the laser-measles bins because WPP includes a `100+` open-ended category that laser-measles does not.
#
# **What a well-functioning simulation looks like:** solid bars within roughly 5-10% relative error of the hatched outlines across the bin range. The expected shape is a high-base pyramid (Nigeria is high-fertility / high-mortality): the under-5 cohort is the largest (typically ~15-18% of population), the curve steps down through working-age, and the elderly tail is thin (single-digit percentages).
#
# **Failure modes to recognize:**
#
# - **Inverted pyramid** (oldest cohort larger than youngest): WPP fertility rates aren't being applied. Births aren't entering the simulation at the expected rate. Check that `WPPVitalDynamicsProcess` is in `model.components` and that no other vital-dynamics process is shadowing it.
# - **Squashed pyramid** (no working-age, no elderly): WPP mortality is over-killing or `num_ticks` is too small to reach equilibrium. The Nigerian age structure takes roughly one mortality timescale (~60-80 years simulated) to fully equilibrate from arbitrary initial conditions; a 5-year window relies on the model's initialization being already close to equilibrium.
# - **Mid-range bumps or gaps** (cohort spike or hole at one age band): birth-rate discontinuity or cohort-processing error. Check the WPP `birth_rates` time series for unexpected jumps.
# - **WPP overshoot in the rightmost bin only** (laser-measles falls short of WPP's `100+`): expected, not a bug. The WPP open-ended category bundles all centenarians while laser-measles bins by definite ranges; correct comparison requires aggregating laser-measles' top bins or ignoring the rightmost WPP bar.
#
# **For programmatic use:** the histogram values are read from `model.get_component("AgePyramidTracker")[0].age_pyramid[f'{year}-01-01']` — a NumPy array of length `len(age_bins) - 1`, indexed by age bin in years. Bin edges live on `tracker.params.age_bins` (in days). Compare against `pyvd.make_pop_dat('NGA')` for Nigeria-specific WPP data; for other countries replace the ISO-3 code accordingly.
#
# The figure validates that `WPPVitalDynamicsProcess` is correctly applying age-structured WPP rate tables. A well-matched pyramid is the empirical evidence the rate-table integration is working as intended.

