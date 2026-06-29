### Reading the synthetic-chain-scenario layout plot

A `1 × 1` scatter showing the 20-patch / 4-cluster synthetic scenario. Longitude on the x-axis, latitude on the y-axis. Marker color encodes cluster membership (viridis colormap, c0 darkest through c3 brightest); marker size is proportional to patch population (`pops / 300`).

Four cluster centers are spaced 300 km apart along the longitude axis at latitude 40, with `cluster_spread_km=30` of within-cluster jitter — so each cluster reads as a tight blob, and the four blobs form a horizontal chain. Population sizes are drawn uniformly from 20k-80k so marker sizes vary substantially within each cluster.

This is the spatial substrate the chain-mixer operates on. The clustering matters for everything that follows: the migration matrix only allows exchange between patches in the same or adjacent clusters, so the geographic chain visible here translates directly into the chain-topology structure visible in the next two figures.
