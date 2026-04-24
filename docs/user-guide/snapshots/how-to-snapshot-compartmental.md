# How to snapshot a compartmental model

This topic describes how to save, load, resume, and inspect a saved snapshot of a compartmental model simulation.
See [lm.compartmental.snapshot][laser.measles.compartmental.snapshot] for full reference information.

## Save a snapshot

```python
import laser.measles as lm
from laser.measles.compartmental.components import InfectionSeedingProcess, InfectionProcess

params1 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
model1 = lm.CompartmentalModel(scenario, params1)
model1.components = [InfectionSeedingProcess, InfectionProcess]
model1.run()

lm.save_snapshot(model1, "checkpoint.h5")
```

## Load and resume a snapshot

```python
params2 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2001-01")
model2 = lm.load_snapshot("checkpoint.h5", params2, components=[InfectionProcess])
model2.run()
```

## Use the classmethod alias

```python
model2 = lm.CompartmentalModel.from_snapshot("checkpoint.h5", params2,
                                              components=[InfectionProcess])
```

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
