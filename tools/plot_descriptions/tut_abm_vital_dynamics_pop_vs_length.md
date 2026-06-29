### Reading the population-vs-LaserFrame-length plot

A `1 × 2` subplot comparing two vital-dynamics process variants over a one-year ABM run:

- **Left panel — `VitalDynamicsProcess`:** Two curves on the same axes. The solid `Population Size` curve sums living agents over time and rises slowly (births at CBR=10/1000/yr exceed deaths at CDR=5/1000/yr). The dashed `Length(People)` curve is the underlying `LaserFrame` length — it rises FASTER than population because agents that die stay in memory as "dead but not removed" rows. The gap between the two curves at any tick is the cumulative death count.
- **Right panel — `ConstantPopProcess`:** Same two curves, but `Length(People)` tracks `Population Size` exactly. `ConstantPopProcess` recycles array slots when agents leave the simulation, so the LaserFrame never grows beyond the current population.

The figure exists to make the memory-handling difference concrete. Choose `VitalDynamicsProcess` when you need full demographic accounting (births and deaths tracked separately, ageing). Choose `ConstantPopProcess` when total population should stay flat and memory pressure matters.
