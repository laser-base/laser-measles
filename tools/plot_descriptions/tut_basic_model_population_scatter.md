### Reading the population-distribution plot

The map shows the two-cluster synthetic scenario: longitude on the x-axis, latitude on the y-axis, one marker per spatial patch, color from the viridis colormap indicating each patch's population. The 100 patches resolve into two dense Gaussian clouds — the `cluster_size_std=1.0` parameter controls how tightly each cluster hugs its center. Brighter (yellow) markers mark the heavier-population patches near each cluster center, dimming to dark (purple) at the periphery.

This is the spatial substrate the simulation will run on: every component (transmission, vital dynamics, immunization) operates on this same 100-patch grid. The clustering matters for downstream metrics — a single epidemic seed in one cluster takes time to reach the other, and per-cluster attack rates depend on this geometry plus the model's mixing assumptions.
