### Reading the age-pyramid plot

A bar chart comparing the simulated age distribution produced by `WPPVitalDynamicsProcess` (laser-measles) against the corresponding World Population Prospects (WPP) reference data for Nigeria, after 5 years of simulation. Both distributions are normalised to fractions and plotted on the same age-bin grid.

- **Solid bars:** laser-measles age pyramid at simulation year 2005, taken from the `AgePyramidTracker`.
- **Hatched outlined bars:** WPP estimates for Nigeria 2005, the validation target. Note the trailing WPP bar extends beyond the laser-measles bins because WPP includes an open-ended `100+` category.

A well-functioning age-structured simulation produces solid bars that closely match the hatched outlines: a high-base pyramid characteristic of high-fertility / high-mortality populations like Nigeria, with the largest cohort being children under 5 and a steady decline thereafter. Systematic deviations — too few young agents (under-fertility) or too many old agents (under-mortality) — would indicate the WPP rate-tables aren't being applied correctly, or the simulation hasn't run long enough to reach the equilibrium age structure.
