# Standard results output

`model.write_results()` writes a canonical JSON summary of a simulation to disk after `model.run()`. Use it as the contract that downstream tooling — validators, plotting scripts, model-comparison reports — reads from, instead of parsing simulation stdout or pulling fields off trackers ad-hoc.

## Why use it?

- **Stable schema across model variants.** ABM, compartmental, and biweekly models all produce the same top-level keys, so the same downstream code works for any of them.
- **One method instead of many.** No need to remember which tracker exposes peak infectious vs attack rate vs final state — all the common quantities land in one file with predictable names.
- **Decouples stdout from automation.** Progress bars, warnings, and debug prints stay in stdout for humans; numeric results stay in `results.json` for code.

---

## Basic usage

```python
import laser.measles as lm
from laser.measles.abm.components import StateTracker
from laser.measles.components import BaseStateTrackerParams, create_component

params = lm.ABMParams(num_ticks=365, seed=42, start_time="2000-01")
model = lm.ABMModel(scenario, params)
model.add_component(lm.NoBirthsProcess)
model.add_component(lm.InfectionProcess)

# IMPORTANT: aggregation_level=0 keeps per-patch arrays. Without it,
# write_results() can only emit global aggregates (attack_rate_per_patch=None).
model.add_component(create_component(StateTracker,
                                     params=BaseStateTrackerParams(aggregation_level=0)))

model.run()
model.write_results("results.json")  # defaults to "results.json" in cwd
```

The method returns the dict that was written, so you can also inspect it in-process without re-reading the file.

---

## Requirements

- A `StateTracker` component must be attached before `model.run()`. Otherwise `write_results()` raises a clear `RuntimeError` telling you to add one.
- For per-patch breakdowns (attack rate per community, peak per patch, final S/E/I/R per patch), the tracker's `aggregation_level` must be `>= 0`. The default (`-1`) sums over all patches and produces global aggregates only.
- `"I"` must be in `model.params.states` — required for peak-infectious and time-series fields.

---

## Output schema

```json
{
  "model_type": "ABMModel",
  "num_ticks": 365,
  "num_patches": 8,
  "patch_ids": ["patch_0", "patch_1", "patch_2", "..."],
  "states": ["S", "E", "I", "R"],
  "summary": {
    "peak_infectious_global": 51925,
    "peak_day": 48,
    "attack_rate_global": 0.882,
    "attack_rate_per_patch": [0.879, 0.890, 0.890, "..."],
    "peak_infectious_per_patch": [25933, 41727, 61569, "..."],
    "final_state_per_patch": {
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
| `num_patches` | int | Number of patches/groups represented in the per-patch arrays. Equals `len(patch_ids)` when per-patch tracking is on; `1` for global-only. |
| `patch_ids` | array of strings | Patch identifiers in the same order as the per-patch arrays. `["all_patches"]` for global-only output. |
| `states` | array of strings | The disease states tracked, in order — `["S", "E", "I", "R"]` for SEIR; `["S", "I", "R"]` for SIR. |
| `summary.peak_infectious_global` | int | Maximum total infectious count summed across all patches over the run. |
| `summary.peak_day` | int | Tick index at which `peak_infectious_global` occurred. |
| `summary.attack_rate_global` | float | `final R / initial population` summed across all patches. `null` if `R` isn't in `states`. |
| `summary.attack_rate_per_patch` | array of floats or null | Per-patch attack rate; `null` when only global tracking is available. |
| `summary.peak_infectious_per_patch` | array of ints or null | Per-patch peak; `null` when only global tracking is available. |
| `summary.final_state_per_patch` | object or null | Final count of each state per patch. Keys are the state names present in `states`. `null` when only global tracking is available. |

---

## Reading the results back

```python
import json
results = json.loads(open("results.json").read())

print(f"Peak infectious: {results['summary']['peak_infectious_global']} on day {results['summary']['peak_day']}")
print(f"Overall attack rate: {results['summary']['attack_rate_global']:.1%}")

for patch_id, rate in zip(results["patch_ids"], results["summary"]["attack_rate_per_patch"]):
    print(f"  {patch_id}: {rate:.1%}")
```

---

## Comparing models

Because all three model variants emit the same schema, a cross-model comparison is just three reads:

```python
results = {name: json.load(open(f"results_{name}.json")) for name in ("abm", "compartmental", "biweekly")}
for name, r in results.items():
    print(f"{name}: peak={r['summary']['peak_infectious_global']} on day {r['summary']['peak_day']}")
```
