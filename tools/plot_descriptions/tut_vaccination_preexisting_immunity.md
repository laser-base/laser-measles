### Reading the pre-existing-immunity comparison

A `1 × 2` subplot comparing four immunity levels (set via the effective `R0` parameter of `InitializeEquilibriumStatesProcess`). Each panel overlays four curves — R0 = 1, 4, 8, 16 — corresponding to initial susceptible fractions of 100%, 25%, 12.5%, and 6.25% respectively. 3-year compartmental simulation, single 500k-person patch, `seasonality=0.15`.

- **Left (Epidemic Curve by Pre-existing Immunity Level):** Infectious count over time, one curve per R0 level. The R0=1 line should produce a clear large-amplitude epidemic peak (typically tens of thousands infectious at peak — a population-wide outbreak). The R0=16 line stays orders of magnitude lower and contains quickly — initial 6% susceptibility is below the herd-immunity threshold for most realistic transmission parameters.
- **Right (Susceptible Population Over Time):** Same four runs, susceptible-count time series. The R0=1 trace plummets as the wave passes; the R0=16 trace is nearly flat near its already-low initial value.

The takeaway: `R0` in `InitializeEquilibriumStatesProcess` is the lever for "what fraction of the population is already immune at t=0". Use it for outbreak scenario analysis when historical vaccination context matters but you don't want to simulate decades of routine immunization first.
