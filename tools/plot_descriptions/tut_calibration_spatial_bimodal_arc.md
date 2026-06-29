### Reading the bimodal-AR_C histogram

A histogram of final cluster-C attack rate (`AR_C = R_C(T) / N_C`) across the 20 reference simulations at TRUE parameters. X-axis is `AR_C` in [0, 1] with 20 bins; y-axis is count of simulations.

What to see: **a clean bimodal distribution** with one peak near `AR_C ≈ 0` and another near `AR_C ≈ 1`. Almost no simulations end up in the middle — either the chain transmission gets through B_far and produces a near-full C epidemic, or it doesn't and C stays near-zero.

This is the tutorial's defining methodological point. The mean of this distribution (~0.45) is unphysical — it's the average of an outcome that's actually either 0 or 1, never 0.45. The **standard deviation** (~0.50), on the other hand, is the bimodality fingerprint: only a stochastic ensemble can reproduce that spread. A deterministic ODE model with the same mean would have std = 0, no matter how well it matched any other metric. That's why the calibration loss function uses `std(AR_C)` as a target instead of `mean(AR_C)`.
