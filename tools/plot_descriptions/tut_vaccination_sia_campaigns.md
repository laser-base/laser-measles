### Reading the SIA-campaigns plot

A `1 × 2` subplot from a 5-year compartmental run with two scheduled SIA (Supplementary Immunization Activity) campaigns at 2001-06-15 (year 1.5) and 2003-06-15 (year 3.5). `sia_efficacy=0.9` — each campaign vaccinates 90% of the currently-susceptible population in the targeted patch.

- **Left (Epidemic Curve with SIA Campaigns):** Infectious count over time (red), with green dashed vertical lines marking the two campaign dates. You should see a recurring outbreak pattern (driven by `seasonality=0.15`) where each post-SIA wave is visibly suppressed compared to a no-SIA counterfactual; the second SIA further dampens the next 1-2 wave cycles before susceptible buildup from births allows new outbreaks.
- **Right (Susceptible Fraction with SIA Campaigns):** Susceptible fraction (S / total) in blue, with the same green vertical lines. The most prominent visual feature is two near-vertical drops in the curve at the SIA dates — the campaigns remove 90% of susceptibles in a single tick, which looks like a step function on the year-scale x-axis.

The takeaway: SIAs are the right tool when you need IMMEDIATE population-level immunity changes at specific dates. They complement `mcv1` (slow, ongoing) and `InitializeEquilibriumStatesProcess` (historical, t=0).
