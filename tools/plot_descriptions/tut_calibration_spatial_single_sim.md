### Reading the single-simulation ABM trajectory

A `1 × 1` plot of infectious-agent counts over time at the TRUE calibration parameters (`beta`, `k`, `c`, RNG seed = 42), one curve per cluster: `A` (blue), `B_far` (orange), `B_near` (deep-orange), `C` (green). X-axis is tick (days); y-axis is total infectious in that cluster summed across its patches.

What you should see depends on the RNG draw, but the canonical pattern is:

- **A peaks first** — the seed is in the three largest A patches. Clear outbreak in cluster A within ~1-3 months.
- **B_far peaks much smaller** because of its SIA — the SIA holds susceptibility low enough that B_far is barely supercritical even with arriving chain transmission. Visually, B_far's curve is a tiny bump compared to A's.
- **B_near peaks if chain transmission gets through B_far**. About half the time across seeds, the chain breaks at B_far and B_near stays near zero.
- **C peaks only if B_near peaked first.** Strict ordering; no shortcuts (chain mixer geometry).

The point of this single-simulation view is to show that a single seed produces a single trajectory — but the system is bimodal at the C level (sometimes C invades, sometimes it doesn't). That stochasticity is what motivates the ensemble-based calibration target used downstream; a single trajectory isn't a meaningful loss-function input.
