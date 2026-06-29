### Reading the migration-matrix heatmap

The same `20 × 20` grid as the allowed-mask figure, but now showing actual migration weights from `chain_migration_matrix(scenario, cluster_indices, k=0.01, c=1.5)`. Color scale is log-scaled `viridis` (purple→yellow as weights go from `~1e-7` to `~1e-3`); zero entries are blank/NaN.

What to read off:

- **Same block sparsity pattern as the mask.** Weights only appear in the allowed regions (within-cluster + adjacent-cluster); the forbidden cells are exactly zero.
- **Within-cluster weights dominate.** Patches inside a cluster are close in distance and similar in population, so the gravity kernel `pop_j / d^c` favors them. These cells are the brightest yellow.
- **Cross-cluster (adjacent) weights are visible but smaller.** A faint but populated off-diagonal band — this is what couples adjacent clusters together, making the chain a chain rather than a set of isolated cliques.
- **Each row sums to k=0.01.** Within a row, more probability mass is concentrated in within-cluster destinations than spread across the adjacent-cluster band.

The two-tier intensity (bright diagonal blocks, dim adjacent-block fringe) is the chain mixer's signature on a population's daily movements.
