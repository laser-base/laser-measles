# How to snapshot an ABM

This topic describes how to save, load, resume, and inspect a saved snapshot of an ABM model simulation.
See [lm.abm.snapshot][laser.measles.abm.snapshot] for full reference information.

### Save a snapshot

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

### Load and resume a snapshot

```python
params2 = lm.ABMParams(num_ticks=1825, seed=42, start_time="2009-12")
model2 = lm.load_snapshot("checkpoint.h5", params2,
                           components=[lm.VitalDynamicsProcess, lm.InfectionProcess])
model2.run()
```

`load_snapshot` prints a complementary summary:

```
Loaded snapshot from checkpoint.h5
  snap_date=2009-12-28  t_snap=3650
  people.count=486,712  capacity=537,040
  params.start_time=2009-12  num_ticks=1825
```

### Use the classmethod alias

```python
model2 = lm.ABMModel.from_snapshot("checkpoint.h5", params2,
                                    components=[lm.VitalDynamicsProcess, lm.InfectionProcess])
```

---

## Inspect a snapshot file

Snapshots are standard [HDF5](https://www.hdfgroup.org/solutions/hdf5/) files
(`.h5`), readable by any HDF5-compatible tool.
Because snapshots are plain HDF5, you can inspect them with standard tools:

```python
import h5py

with h5py.File("checkpoint.h5", "r") as f:
    print("snap_date:", f["snap_date"][()].decode())
    print("t_snap:   ", int(f["t_snap"][()]))
    print("people.count:", int(f["people/count"][()]))
    print("patch_states shape:", f["patch_states"].shape)
    print("keys:", list(f.keys()))
```

Or from the shell:

```bash
h5ls -r checkpoint.h5
```
