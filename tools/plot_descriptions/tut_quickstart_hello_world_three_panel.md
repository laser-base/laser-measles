### Reading the quickstart three-panel results

A single `fig, axes = plt.subplots(1, 3, figsize=(15, 4))` figure summarising the 50-day ABM run with 8 linear patches, infection seeded in `patch_7`:

- **Left (Global SEIR):** Four curves — S, E, I, R — each plotted as a fraction of total population over day. With `beta=2.0`, no births, and a 50-day window, the susceptible fraction should drop visibly (an outbreak has occurred) but not collapse to zero (this is too short for a full epidemic). E and I make low peaks under 10% each; R climbs to whatever fraction got infected.
- **Center (Spatial attack rate):** Bar chart, one bar per patch (`patch_0` through `patch_7`), height in percent. Because `distance_exponent=20` makes transmission strongly local and the seed is in `patch_7`, the bars should be tallest on the right and fall off sharply moving left — illustrating gravity-mixing geometry. The exact gradient depends on the seed-day RNG draws.
- **Right (Infection spread by patch):** Eight `I`-count curves overlaid, one per patch, vs day. The wave originates in `patch_7` (its curve rises first and highest), then neighbouring patches' curves rise with a lag proportional to their distance. The lag-and-peak pattern is the clearest visual signature of the gravity-mixing parameters.

Together the three panels show the canonical 1D gravity-mixing wavefront — a useful sanity-check pattern when reasoning about more complex spatial ABMs.
