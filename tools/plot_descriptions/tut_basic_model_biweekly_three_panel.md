### Reading the biweekly-model results

Three panels for a 20-year run (520 biweekly ticks) of the biweekly compartmental model:

- **Left (Susceptible Fraction Over Time):** Fraction of the population in the S compartment, summed across all 100 patches and divided by total population. Healthy measles dynamics drop S during epidemic waves and recover between waves as births replenish susceptibles. With `seasonality=0.3` in `InfectionParams`, you should see periodic structure rather than a single peak.
- **Center (Spatial Attack Rate Distribution):** End-of-run map. Each marker is a patch sized by initial population, colored by attack rate = `(R + I at final tick) / initial population`, using the Reds colormap. A uniform deep-red map indicates the epidemic reached every patch; a salt-and-pepper map indicates spatial heterogeneity.
- **Right (Epidemic Curve):** Total infectious count summed across patches at each tick. Confirms the periodicity from the S panel and shows magnitude — peak infectious on the order of a few thousand on a few-hundred-thousand-person population is typical for measles with this configuration.

Together the three panels validate measles-like dynamics: recurring outbreaks, attack rates above zero across patches, and seasonality-driven periodicity.
