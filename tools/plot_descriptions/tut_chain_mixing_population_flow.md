### Reading the population-flow stackplot

A `stackplot` over 6000 ticks showing how an initial seeded population spreads through the chain. Y-axis = share of total seeded population in each cluster; x-axis = tick; each band is a cluster colored with the same viridis palette used for cluster identity throughout the tutorial.

The seed: all population starts in cluster 0 (the leftmost cluster); the other three clusters start at zero. Then `pop_{t+1} = pop_t - k*pop_t + pop_t @ M` is iterated, which is the migration matrix acting as an operator without births, deaths, or transmission.

What to read:

- **At tick 0**, the entire colored area is cluster 0 (blue) — the seeded state.
- **Cluster 1 fills in first** as population leaks across the c0/c1 boundary.
- **Cluster 2 fills in only after cluster 1**, because population can reach c2 only via c1 (chain topology forbids c0→c2 directly).
- **Cluster 3 fills in last**, requiring the full c0→c1→c2→c3 chain traversal.

The strict ordering — no shortcuts, propagation only along the chain — is the defining dynamical signature of the chain mixer. This same propagation pattern, with the SEIR machinery layered on top, is what creates the stochastic bottleneck at B_far in the calibration tutorial: a single subcritical cluster mid-chain can sever transmission to the downstream clusters.
