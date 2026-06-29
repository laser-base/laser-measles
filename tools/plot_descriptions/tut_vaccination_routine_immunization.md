### Reading the routine-immunization 20-year plot

A `1 × 2` subplot comparing `mcv1 = 0` (no routine immunization) vs `mcv1 = 0.80` (80% of newborns vaccinated through `VitalDynamicsProcess`). 20-year compartmental simulation, single 500k-person patch.

- **Left (Epidemic Curve: Routine Immunization (20 years)):** Infectious count over time, two overlaid curves. Both runs show recurring measles outbreaks driven by `seasonality=0.15`. The 80% MCV1 curve has noticeably damped peak amplitudes by the later years as vaccinated cohorts replace unvaccinated ones, but the peaks remain visible — 80% routine coverage alone is not enough to interrupt transmission in this configuration.
- **Right (Susceptible Fraction Over Time):** Susceptible fraction (S / total) for the two runs. The 0% MCV1 trace oscillates around a stable mean fraction (~6% under endemic equilibrium for R0=16-ish). The 80% MCV1 trace drifts DOWN over the 20 years as new births enter the recovered pool. The gap between the two curves widens monotonically — that's the lever's slow accumulation.

Key takeaway: `mcv1` only protects newborns, so its population-level effect is gradual. The figure exists to make the timescale concrete: meaningful difference takes a decade-plus. For short-horizon outbreak modeling, use Approach 1 (`InitializeEquilibriumStatesProcess`) or Approach 3 (SIAs) instead.
