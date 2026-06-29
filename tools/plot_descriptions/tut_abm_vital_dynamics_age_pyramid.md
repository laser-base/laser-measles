### Reading the age-pyramid plot

A bar chart comparing the simulated age distribution from `WPPVitalDynamicsProcess` (laser-measles) against the corresponding World Population Prospects (WPP) reference for Nigeria after 5 years of simulation. Both distributions are normalized to fractions and plotted on the same age-bin grid.

- **Solid bars:** laser-measles age pyramid at simulated year 2005, drawn from the `AgePyramidTracker`.
- **Hatched outlined bars:** WPP Nigeria 2005 reference. Note the trailing WPP bar extends past the laser-measles bins because WPP includes a `100+` open-ended category that laser-measles does not.

**What a well-functioning simulation looks like:** solid bars within roughly 5-10% relative error of the hatched outlines across the bin range. The expected shape is a high-base pyramid (Nigeria is high-fertility / high-mortality): the under-5 cohort is the largest (typically ~15-18% of population), the curve steps down through working-age, and the elderly tail is thin (single-digit percentages).

**Failure modes to recognize:**

- **Inverted pyramid** (oldest cohort larger than youngest): WPP fertility rates aren't being applied. Births aren't entering the simulation at the expected rate. Check that `WPPVitalDynamicsProcess` is in `model.components` and that no other vital-dynamics process is shadowing it.
- **Squashed pyramid** (no working-age, no elderly): WPP mortality is over-killing or `num_ticks` is too small to reach equilibrium. The Nigerian age structure takes roughly one mortality timescale (~60-80 years simulated) to fully equilibrate from arbitrary initial conditions; a 5-year window relies on the model's initialization being already close to equilibrium.
- **Mid-range bumps or gaps** (cohort spike or hole at one age band): birth-rate discontinuity or cohort-processing error. Check the WPP `birth_rates` time series for unexpected jumps.
- **WPP overshoot in the rightmost bin only** (laser-measles falls short of WPP's `100+`): expected, not a bug. The WPP open-ended category bundles all centenarians while laser-measles bins by definite ranges; correct comparison requires aggregating laser-measles' top bins or ignoring the rightmost WPP bar.

**For programmatic use:** the histogram values are read from `model.get_component("AgePyramidTracker")[0].age_pyramid[f'{year}-01-01']` — a NumPy array of length `len(age_bins) - 1`, indexed by age bin in years. Bin edges live on `tracker.params.age_bins` (in days). Compare against `pyvd.make_pop_dat('NGA')` for Nigeria-specific WPP data; for other countries replace the ISO-3 code accordingly.

The figure validates that `WPPVitalDynamicsProcess` is correctly applying age-structured WPP rate tables. A well-matched pyramid is the empirical evidence the rate-table integration is working as intended.
