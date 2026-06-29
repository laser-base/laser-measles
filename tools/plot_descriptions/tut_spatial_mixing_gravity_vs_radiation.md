### Reading the gravity-vs-radiation mixing analysis

A `2 × 3` multi-panel figure dissecting how the gravity and radiation mixing models differ on the same linear-chain scenario.

**Top row — the matrices themselves:**

- **Top-left (Gravity Mixing Matrix):** Heatmap, Blues colormap. Source patch on y-axis, destination patch on x-axis. Should show a smooth gradient with a bright diagonal and a steady falloff away from it; gravity models are continuous in distance.
- **Top-center (Radiation Mixing Matrix):** Same axes, Reds colormap. The radiation model is non-parametric and tends to look more block-structured — sharper transitions, with mixing strength conditioned on the population between source and destination.
- **Top-right (Difference (Gravity - Radiation)):** Diverging `RdBu_r` heatmap, symmetric color limits. Red cells indicate gravity assigns more weight than radiation; blue cells the reverse. The diff panel makes the structural differences between the two models concrete: gravity over-couples some pairs that radiation under-couples and vice versa.

**Bottom row — derived metrics:**

- **Bottom-left (Mixing Distance Profiles):** Average mixing distance per patch (population-weighted average over destinations), one line per model, x-axis is patch position along the chain. Gravity (blue circles) and radiation (red squares) trace different profiles — particularly at the chain ends where boundary effects matter.
- **Bottom-center (Population Size vs Mixing Distance):** Scatter of per-patch population vs that patch's average mixing distance, two colors for the two models. Highlights whether bigger patches mix at longer ranges (yes for gravity; less so for radiation).
- **Bottom-right (Mixing vs Distance (Representative Patches)):** For three representative patches (positions 5, 15, 25 — left, center, right of chain), plot mixing probability vs distance from that source. Y-axis is log scale. Gravity (solid) and radiation (dashed) overlay; you should see gravity's smooth power-law-like decay vs radiation's flatter step-like decay.

Together the six panels are the canonical visual for "gravity vs radiation mixing have different functional forms; choose based on what your data supports."
