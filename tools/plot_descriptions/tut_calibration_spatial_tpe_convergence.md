### Reading the TPE convergence plot

A `1 × 1` plot tracking optimisation progress over the 30-trial live Stage-1 (CMP cold-start) TPE run. X-axis is trial number; y-axis is loss (log scale).

Two series:

- **Light gray circles connected by lines (`trial loss`):** the loss value at each individual trial. Early trials are noisy/high; later trials should cluster lower as TPE concentrates around the basin.
- **Red running-best line (`running best`):** monotone-decreasing trace of the best loss seen so far. The shape of this trace is the proper convergence diagnostic — flat sections are stalls, sudden drops are when TPE found a better region.

What a healthy run looks like: the running-best should drop substantially in the first ~10 trials (TPE has located the basin), then refine slowly afterward. If the running-best is still falling steeply at trial 30, the optimisation hasn't converged and you'd want more trials or a different prior.

This figure exists to show convergence behavior on a small live run; the full-precision 100-trial result loaded next for downstream analysis is what calibration decisions are actually based on.
