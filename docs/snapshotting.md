# Snapshotting

Snapshotting lets you save a fully-running simulation to disk and resume it later — picking up exactly where it left off.

## Why snapshot?

Long epidemic simulations are expensive to re-run from scratch.  A snapshot captures the complete model state at a chosen point in time so that subsequent work (parameter sweeps, post-peak analysis, intervention studies) can start from a known, pre-computed baseline without repeating the warm-up period.

Common use cases:

- **Warm-start parameter sweeps** — run a shared 10-year spin-up once, save a snapshot, then branch into dozens of scenario variants.
- **Long runs in segments** — split a 30-year run into shorter jobs that fit within a compute-cluster time limit.
- **Reproducible checkpoints** — share a snapshot file with collaborators so they can reproduce results from a fixed starting condition.

---

## Supported model types

Both model types in laser-measles support snapshotting:

| Model | Save function | Load function | Classmethod alias |
|---|---|---|---|
| ABM (`ABMModel`) | `lm.save_snapshot` | `lm.load_snapshot` | `ABMModel.from_snapshot` |
| Compartmental (`CompartmentalModel`) | `lm.save_snapshot` | `lm.load_snapshot` | `CompartmentalModel.from_snapshot` |

Both functions are importable directly from the top-level `laser.measles` namespace.

---

## ABM snapshotting

### Saving

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

### Loading and resuming

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

### Classmethod alias

```python
model2 = lm.ABMModel.from_snapshot("checkpoint.h5", params2,
                                    components=[lm.VitalDynamicsProcess, lm.InfectionProcess])
```

---

## Compartmental snapshotting

### Saving

```python
import laser.measles as lm
from laser.measles.compartmental.components import InfectionSeedingProcess, InfectionProcess

params1 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
model1 = lm.CompartmentalModel(scenario, params1)
model1.components = [InfectionSeedingProcess, InfectionProcess]
model1.run()

lm.save_snapshot(model1, "checkpoint.h5")
```

### Loading and resuming

```python
params2 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2001-01")
model2 = lm.load_snapshot("checkpoint.h5", params2, components=[InfectionProcess])
model2.run()
```

### Classmethod alias

```python
model2 = lm.CompartmentalModel.from_snapshot("checkpoint.h5", params2,
                                              components=[InfectionProcess])
```

---

## What is stored in the snapshot file

Snapshots are standard [HDF5](https://www.hdfgroup.org/solutions/hdf5/) files (`.h5`), readable by any HDF5-compatible tool.

### ABM snapshot contents

| Dataset | Description |
|---|---|
| `people/*` | All agent properties (patch_id, state, age, date_of_vaccination, …) |
| `patch_states` | SEIR counts per patch, shape `(n_states, n_patches)` |
| `scenario/*` | Scenario DataFrame columns (id, pop, lat, lon, mcv1, …) |
| `t_snap` | Elapsed ticks at save time |
| `snap_date` | Calendar date at save time (YYYY-MM-DD) |
| `cbr_per_1000` | Crude birth rate (present when `VitalDynamicsProcess` was active) |
| `implemented_sias` | SIA campaign IDs already applied (present when `SIACalendarProcess` was active) |

### Compartmental snapshot contents

| Dataset | Description |
|---|---|
| `patch_states` | SEIR counts per patch, shape `(n_states, n_patches)` |
| `scenario/*` | Scenario DataFrame columns |
| `t_snap` | Elapsed ticks at save time |
| `snap_date` | Calendar date at save time (YYYY-MM-DD) |
| `implemented_sias` | SIA campaign IDs already applied (present when `SIACalendarProcess` was active) |

---

## Key concepts

### Segments and start_time alignment

A snapshot divides a run into **segments**.  Each segment is a fully independent
`ABMModel` (or `CompartmentalModel`) instance with its own `params` object.

The most important rule: **set `params.start_time` for segment 2 to the snapshot
date**.  Both `save_snapshot` and `load_snapshot` print this value — look for the
`Resume with:` line in the `save_snapshot` output, or the `snap_date` in the
`load_snapshot` output.

```python
# save_snapshot prints: "Resume with: params.start_time='2009-12'"
params2 = lm.ABMParams(start_time="2009-12", ...)  # ← must match snap_date month
```

If `start_time` is wrong, `model.current_date` will be wrong and any
date-dependent components (SIA calendars, importation schedules) will fire at
incorrect times.

### The component list for the resumed segment

Pass the **same component list** you used in segment 1 — with one exception for
the ABM and compartmental models:

**Do not include `InfectionSeedingProcess` in segment 2.**  Infections are already
encoded in the restored patch states and agent states; re-seeding would add
spurious infections on top of an already-active epidemic.

```python
# Segment 1 — seeding needed to start the epidemic
model1.components = [InfectionSeedingProcess, InfectionProcess]

# Segment 2 — epidemic is already running; seeding not needed
model2 = lm.load_snapshot(snap, params2, components=[InfectionProcess])
```

### SIA calendars across the boundary

When `SIACalendarProcess` is in the component list, the snapshot saves the set of
campaign IDs that were already applied before the save point
(`implemented_sias`).  On load, this set is restored into the new
`SIACalendarProcess` instance.  Campaigns already executed in segment 1 will
**not** fire again in segment 2 — only campaigns with dates after the snapshot
boundary remain eligible.

---

## ABM-specific notes

### R-agent squashing

`save_snapshot` **modifies the model in place**: recovered (R) agents are removed
from the people frame before writing to disk.  This is called *squashing* and
dramatically reduces file size for long measles runs where the majority of agents
have recovered.

The patch-level R counts in `patch_states` are preserved — they reflect the true
epidemic state at save time.  The in-memory model after saving is therefore no
longer consistent for continued simulation; **do not call `model.run()` after
`save_snapshot`**.

```python
model1.run()
lm.save_snapshot(model1, "checkpoint.h5")
# ← do not use model1 after this point
```

### Population capacity for future births

When `VitalDynamicsProcess` is in the component list, `load_snapshot` restores
the current population from disk and then lets `VitalDynamicsProcess` expand the
people frame to accommodate projected births during segment 2.  The capacity
printed by `load_snapshot` will be larger than `people.count` for this reason.

### Vaccination queue

If `VitalDynamicsProcess` was active, each agent's scheduled vaccination date is
saved relative to the snapshot boundary (tick 0 of segment 2 = the snapshot
date).  The vaccination queue is rebuilt automatically on load.

---

## Caveats and warnings

!!! warning "Do not use the model after saving"
    `save_snapshot` mutates the ABM model (squashes R agents, normalises
    vaccination dates).  Treat it as a terminal operation on `model1`.

!!! warning "start_time must match the snapshot date"
    Setting the wrong `start_time` in segment 2 parameters causes date-dependent
    components (SIA calendars, importation, age-based vaccination) to fire at
    incorrect calendar times.

!!! note "InitializeEquilibriumStatesProcess"
    Do not include `InitializeEquilibriumStatesProcess` in the segment 2 component
    list.  It re-initialises the population to equilibrium values and would
    overwrite the loaded state.

!!! note "InfectionSeedingProcess"
    Do not include `InfectionSeedingProcess` in the segment 2 component list (see
    [The component list for the resumed segment](#the-component-list-for-the-resumed-segment)).

---

## Inspecting a snapshot file

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
