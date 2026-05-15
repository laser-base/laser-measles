# How to snapshot and resume a simulation

This guide shows how to save a simulation checkpoint and resume from it in a new segment. For background on why snapshotting works this way and what is preserved, see [Snapshotting](index.md).

## Save an ABM snapshot

Run the first segment to completion, then save:

```python
import laser.measles as lm

params1 = lm.ABMParams(num_ticks=3650, seed=42, start_time="2000-01")
model1 = lm.ABMModel(scenario, params1)
model1.components = [lm.VitalDynamicsProcess, lm.InfectionProcess]
model1.run()

lm.save_snapshot(model1, "checkpoint.h5")
```

`save_snapshot` prints a summary:

```
Squashing 12,483 recovered agents
Snapshot saved → checkpoint.h5
  t_snap=3650  snap_date=2009-12-28  people.count=486,712
  cbr_per_1000=32.0
  Resume with: params.start_time='2009-12'
```

Note the `Resume with:` line — you need this value for the next step.

!!! warning "Do not use the model after saving"
    `save_snapshot` mutates the ABM model (squashes R agents, normalizes
    vaccination dates). Treat it as a terminal operation on `model1`.

## Resume an ABM from a snapshot

Create new params with `start_time` matching the snapshot date, then load:

```python
params2 = lm.ABMParams(num_ticks=1825, seed=42, start_time="2009-12")
model2 = lm.load_snapshot("checkpoint.h5", params2,
                           components=[lm.VitalDynamicsProcess, lm.InfectionProcess])
model2.run()
```

You can also use the classmethod alias:

```python
model2 = lm.ABMModel.from_snapshot("checkpoint.h5", params2,
                                    components=[lm.VitalDynamicsProcess, lm.InfectionProcess])
```

!!! warning "start_time must match the snapshot date"
    Setting the wrong `start_time` causes date-dependent components (SIA
    calendars, importation, age-based vaccination) to fire at incorrect
    calendar times.

## Save and resume a compartmental model

The procedure is the same, using compartmental classes:

```python
import laser.measles as lm
from laser.measles.compartmental.components import InfectionSeedingProcess, InfectionProcess

# Segment 1
params1 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
model1 = lm.CompartmentalModel(scenario, params1)
model1.components = [InfectionSeedingProcess, InfectionProcess]
model1.run()

lm.save_snapshot(model1, "checkpoint.h5")
```

```python
# Segment 2
params2 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2001-01")
model2 = lm.load_snapshot("checkpoint.h5", params2, components=[InfectionProcess])
model2.run()
```

Or using the classmethod alias:

```python
model2 = lm.CompartmentalModel.from_snapshot("checkpoint.h5", params2,
                                              components=[InfectionProcess])
```

## Exclude seeding from the second segment

Pass the same component list you used in segment 1 — **except** for `InfectionSeedingProcess`. Infections are already present in the restored state; re-seeding would create spurious infections.

```python
# Segment 1 — seeding needed to start the epidemic
model1.components = [InfectionSeedingProcess, InfectionProcess]

# Segment 2 — epidemic is already running; seeding not needed
model2 = lm.load_snapshot(snap, params2, components=[InfectionProcess])
```

Similarly, do not include `InitializeEquilibriumStatesProcess` in the second segment — it would overwrite the loaded state.

## Inspect a snapshot file

Snapshots are standard HDF5 files, readable with any HDF5-compatible tool:

```python
import h5py

with h5py.File("checkpoint.h5", "r") as f:
    print("snap_date:", f["snap_date"][()].decode())
    print("t_snap:   ", int(f["t_snap"][()]))
    print("people.count:", int(f["people/count"][()]))
    print("patch_states shape:", f["patch_states"].shape)
    print("keys:", list(f.keys()))
```

Or from the command line:

```bash
h5ls -r checkpoint.h5
```

## See also

- [Snapshotting](index.md) — concepts, what is preserved, and ABM-specific behavior
- [Worked examples](../components/worked-examples.md) — complete runnable scripts for all model types
- [Troubleshooting](../components/troubleshooting.md) — common pitfalls and error resolution
