### Reading the compartmental-model results

Same three-panel layout as the biweekly figure but for the daily-timestep compartmental (SEIR) model (20 years = 7300 ticks). Key differences when comparing the two:

- **Left panel:** The Susceptible-fraction curve is much smoother than the biweekly version because daily ticks resolve the seasonal forcing finer than 26-step-per-year sampling can. Mean level and trough depth should be similar; the noise floor is lower.
- **Center panel:** Spatial attack-rate distribution should resemble the biweekly map qualitatively — same scenario, same seasonality, same migration assumptions — but small per-patch differences are expected because the two models discretize state-update timing differently.
- **Right panel:** The epidemic curve has visibly more inter-tick noise (per-day infectious count, not per-biweek) but the envelope of peaks tracks the biweekly figure.

The takeaway is that the compartmental and biweekly variants are intended to be interchangeable at this level of detail — choose biweekly when you need speed (~26× fewer ticks), compartmental when you need daily resolution for parameter estimation or short-timescale interventions.
