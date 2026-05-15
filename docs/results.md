# Standard results output

The `ResultsWriter` component writes a canonical JSON summary of a simulation to disk at end of run. Use it as the contract that downstream tooling — validators, plotting scripts, model-comparison reports — reads from, instead of parsing simulation stdout or pulling fields off trackers ad-hoc.

## Why use it?

- **Stable schema across model variants.** ABM, compartmental, and biweekly models all produce the same top-level keys, so the same downstream code works for any of them.
- **One component instead of many.** No need to remember which tracker exposes peak infectious vs attack rate vs final state — all the common quantities land in one file with predictable names.
- **Decouples stdout from automation.** Progress bars, warnings, and debug prints stay in stdout for humans; numeric results stay in `results.json` for code.
- **Opt-in.** A calibration loop that only wants final stats (no per-trial JSON files) simply omits `ResultsWriter` from `model.components`.

---

## Basic usage — add `ResultsWriter` as a component

Adding `ResultsWriter` to `model.components` causes the JSON dump to happen automatically at end of run, alongside any other end-of-run work declared by other components.

```python
import laser.measles as lm
from laser.measles.abm.components import StateTracker
from laser.measles.components import (
    BaseStateTrackerParams,
    ResultsWriter,
    create_component,
)

params = lm.ABMParams(num_ticks=365, seed=42, start_time="2000-01")
model = lm.ABMModel(scenario, params)
model.add_component(lm.NoBirthsProcess)
model.add_component(lm.InfectionProcess)

# IMPORTANT: aggregation_level controls per-group output. For flat patch
# IDs, aggregation_level=0 gives per-patch arrays. For hierarchical IDs
# ("region:district"), use aggregation_level=depth-1 to reach leaf rows.
# The default (-1) sums over all patches and emits global aggregates only.
model.add_component(create_component(StateTracker,
                                     params=BaseStateTrackerParams(aggregation_level=0)))
model.add_component(ResultsWriter)            # writes results.json at end of run

model.run()
# results.json is now sitting in cwd.
```

For a custom path:

```python
from laser.measles.components import ResultsWriterParams, create_component
model.add_component(
    create_component(ResultsWriter, params=ResultsWriterParams(path="run_42.json"))
)
```

### Skipping the writer for calibration

A calibration loop that runs the model thousands of times typically doesn't want a `results.json` per trial. Just omit `ResultsWriter` from the components list — the model itself writes nothing. Read the metrics you care about off the tracker (or any other component) in-process instead.

```python
# Calibration sweep: no ResultsWriter, no disk writes per trial
for trial in range(100):
    model = build_model(trial_params[trial])
    model.run()                                # no ResultsWriter component
    metric = compute_loss(model)               # read trackers in-process
```

---

## Requirements

- A `StateTracker` component must already be attached before you add or instantiate `ResultsWriter` (for example via `add_component(ResultsWriter)` or when building the components list). If no tracker is present, `ResultsWriter.__init__` raises a clear `RuntimeError` during component wiring, before `model.run()`.
- For per-group breakdowns (attack rate per community, peak per patch, final S/E/I/R per patch), the tracker's `aggregation_level` must be `>= 0`. The default (`-1`) sums over all patches and produces global aggregates only.
- `"I"` must be in `model.params.states` — required for peak-infectious metrics and `final_state_per_group["I"]` in the written summary.

---

## Output schema

```json
{
  "model_type": "ABMModel",
  "num_ticks": 365,
  "num_groups": 8,
  "group_ids": ["patch_0", "patch_1", "patch_2", "..."],
  "group_aggregation_level": 0,
  "states": ["S", "E", "I", "R"],
  "summary": {
    "peak_infectious_global": 51925,
    "peak_tick": 48,
    "attack_rate_global": 0.882,
    "final_state_global": {"S": 67, "E": 0, "I": 0, "R": 249933},
    "attack_rate_per_group": [0.879, 0.890, 0.890, "..."],
    "peak_infectious_per_group": [25933, 41727, 61569, "..."],
    "final_state_per_group": {
      "S": [42, 17, 8,  "..."],
      "E": [0,  0,  0,  "..."],
      "I": [0,  0,  0,  "..."],
      "R": [49958, 79983, 119992, "..."]
    }
  }
}
```

### Field reference

| Key | Type | Notes |
|---|---|---|
| `model_type` | string | Class name of the model (`"ABMModel"`, `"CompartmentalModel"`, `"BiweeklyModel"`). |
| `num_ticks` | int | Total simulation length in ticks (days for ABM/compartmental, 14-day units for biweekly). |
| `num_groups` | int | Number of tracker groups represented in the per-group arrays. Equals `len(group_ids)`; `1` for global-only output. |
| `group_ids` | array of strings | Tracker group identifiers in the same order as the per-group arrays. `["all_patches"]` for global-only output. May be leaf scenario IDs at full aggregation depth, or higher-level keys like `"cluster_1"` when the tracker rolls up. |
| `group_aggregation_level` | int | The tracker's `aggregation_level`: `-1` means global, `0+` means grouped at that hierarchy depth. Use this to know whether the `_per_group` arrays are leaf-level (true per-patch) or aggregated above. |
| `states` | array of strings | The disease states tracked, in order — `["S", "E", "I", "R"]` for SEIR; `["S", "I", "R"]` for SIR. |
| `summary.peak_infectious_global` | int | Maximum total infectious count summed across all groups over the run. |
| `summary.peak_tick` | int | Tick index at which `peak_infectious_global` occurred. Convert to calendar time using the model's tick→day mapping (1 day for ABM/compartmental, 14 days for biweekly). |
| `summary.attack_rate_global` | float or null | Fraction of initial susceptibles globally that ever left the `S` compartment, i.e. `(S[0] - S[-1]).sum() / S[0].sum()`, clamped to `[0, 1]`. `null` if `S` isn't in `states`. Defined this way so the value stays well-defined under spatial migration (where an `R[-1] / initial_pop` formulation would exceed 1.0) and is robust to per-patch state-counter underflow ([laser-measles #117](https://github.com/laser-base/laser-measles/issues/117)). |
| `summary.final_state_global` | object | Final count of each state summed across all groups. Keys are the state names present in `states`. Always emitted (works with both per-group and global-only trackers). |
| `summary.attack_rate_per_group` | array of floats or null | Per-group version of `attack_rate_global` (same formula, applied per tracker group). Each entry is in `[0, 1]`. `null` when only global tracking is available. |
| `summary.peak_infectious_per_group` | array of ints or null | Per-group peak; `null` when only global tracking is available. |
| `summary.final_state_per_group` | object or null | Final count of each state per group. Keys are the state names present in `states`. `null` when only global tracking is available. |

---

## Reading the results back

```python
import json
results = json.loads(open("results.json").read())

print(f"Peak infectious: {results['summary']['peak_infectious_global']} at tick {results['summary']['peak_tick']}")

attack_rate_global = results["summary"]["attack_rate_global"]
if attack_rate_global is not None:
    print(f"Overall attack rate: {attack_rate_global:.1%}")
else:
    print("Overall attack rate: unavailable")

attack_rate_per_group = results["summary"]["attack_rate_per_group"]
if attack_rate_per_group is not None:
    for group_id, rate in zip(results["group_ids"], attack_rate_per_group):
        print(f"  {group_id}: {rate:.1%}")
else:
    print("Per-group attack rates: unavailable")
```

---

## Comparing models

Because all three model variants emit the same schema, a cross-model comparison is just three reads:

```python
results = {name: json.load(open(f"results_{name}.json")) for name in ("abm", "compartmental", "biweekly")}
for name, r in results.items():
    print(f"{name}: peak={r['summary']['peak_infectious_global']} at tick {r['summary']['peak_tick']}")
```
