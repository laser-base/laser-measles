### Reading the allowed/forbidden routes mask

A `20 × 20` binary heatmap. Source patch on the y-axis, destination patch on the x-axis. Red cells mark allowed migration routes; blue cells mark forbidden routes. White rectangles overlay cluster boundaries with `c0`-`c3` labels.

What you should see:

- **Block structure.** Four `5 × 5` diagonal blocks (within-cluster routes — c0→c0, c1→c1, ..., minus the diagonal) and immediately-off-diagonal blocks (adjacent-cluster routes — c0↔c1, c1↔c2, c2↔c3). All red.
- **Forbidden regions.** Everything else is blue: c0↔c2, c0↔c3, c1↔c3. Non-adjacent clusters cannot exchange at all under the chain topology.
- **Blue diagonal.** A patch cannot migrate to itself; self-loops are deliberately blocked in the migration matrix (self-mixing happens elsewhere in the SEIR pipeline).

This is the topology of the chain mixer, separated from the gravity weights. The defining feature is the off-diagonal-only coupling — transmission can only propagate through the chain, never skip a cluster, which is what makes B_far a stochastic bottleneck in the calibration tutorial.
