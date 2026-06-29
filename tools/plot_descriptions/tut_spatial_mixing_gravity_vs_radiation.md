### Reading the gravity-vs-radiation mixing analysis

A `2 × 3` multi-panel figure dissecting how the gravity and radiation mixing models differ on the same 30-patch linear-chain scenario. The figure is the empirical evidence for the textual claim that gravity and radiation are not interchangeable — the panels each carry distinct quantitative signatures.

**Top row — the matrices themselves (30 × 30 heatmaps, source on y, destination on x):**

- **Top-left (Gravity Mixing Matrix, Blues):** Smooth gradient with a bright diagonal that falls off continuously as you move off-diagonal. Off-diagonal weight extends visibly to ~3-5 patches in both directions. This is the power-law `pop_j / d^c` signature.
- **Top-center (Radiation Mixing Matrix, Reds):** Sharper, more block-structured. Strong on the immediate off-diagonal, falls off steeply beyond ~2 patches. Radiation's "intervening population" mechanism means once enough population sits between source and destination, the flow vanishes — visually this is a hard cutoff rather than gravity's smooth falloff.
- **Top-right (Difference (Gravity - Radiation), RdBu_r, symmetric color limits):** Red cells (gravity > radiation) and blue cells (radiation > gravity). The pattern is informative: gravity over-couples **mid-distance** pairs (red band ~2-4 patches off-diagonal) while radiation slightly over-couples **immediately-adjacent** pairs. Magnitudes are on the same order as the matrices themselves — these are not small perturbations; the two models produce quantitatively different transmission topologies.

**Bottom row — derived metrics:**

- **Bottom-left (Mixing Distance Profiles):** Average mixing distance per patch (population-weighted average over destinations) plotted against position along the chain. Gravity (blue circles) traces an **arch-shape** — patches in the middle of the chain mix farther because they have more neighbors on both sides. Radiation (red squares) traces a flatter, lower profile — its strict-cutoff behavior caps mixing distance regardless of position.
- **Bottom-center (Population Size vs Mixing Distance):** Scatter of per-patch population (x-axis) vs that patch's average mixing distance (y-axis). Gravity shows a **positive correlation** — bigger patches mix farther, because the gravity kernel's `pop_j` term favors large destinations. Radiation shows a **flat-or-negative correlation** — counter-intuitively, big patches in the middle of the chain mix LESS far because they absorb each other's outflow via the intervening-population term.
- **Bottom-right (Mixing vs Distance, log y-scale):** Mixing probability vs distance for three source patches (positions 5, 15, 25). Gravity (solid) traces a straight line on log scale — pure power-law `~1/d^c`. Radiation (dashed) shows a clear **knee around distance 2-3**, after which it drops sharply by ~2 orders of magnitude. The shape difference (power-law vs near-step-function) is the model-defining contrast that determines outbreak spread dynamics on a given scenario.

**For programmatic use** — this is the load-bearing API contrast that traps new users:

- **Compartmental model:** pass a mixer object explicitly — `InfectionParams(mixer=GravityMixing(...))` or `InfectionParams(mixer=RadiationMixing(...))`. Inspect the resulting matrix via `mixer.get_migration_matrix()`.
- **ABM:** does **not** accept a mixer object. The ABM builds a gravity mixing matrix internally from `distance_exponent` and `mixing_scale` on `InfectionParams`. Radiation mixing for the ABM requires constructing a custom matrix and exposing it through a `BaseMixing` adapter.
- **Sanity check:** if your end-of-run attack-rate map is uniformly saturated or uniformly near-zero, the mixer is misconfigured. Render the matrix as a heatmap (the panels above) to verify the dynamic range is reasonable — values should span at least 2-3 orders of magnitude with a clear off-diagonal structure.

**Takeaway:** gravity gives a smooth, tunable distance decay with two parameters (`distance_exponent`, `mixing_scale`); radiation is near-parameter-free but introduces a sharp cutoff driven by intervening population. Choose by what your data supports — for travel-survey data with a known power-law, gravity; for commuting-flow data with empirical "no traveler crosses a bigger town" structure, radiation.
