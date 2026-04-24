# Simulation snapshot user guide

You can save a snapshot of a fully running simulation to disk and resume it later, picking up exactly where it left off. laser-measles supports snapshots for compartmental and ABM models. See [lm.abm.snapshot][laser.measles.abm.snapshot] and [lm.compartmental.snapshot][laser.measles.compartmental.snapshot] for full reference information.

## Why snapshot?

Long epidemic simulations are expensive to re-run from scratch. A snapshot captures the complete model state at a chosen point so that subsequent work (parameter sweeps, post-peak analysis, intervention studies) can start from a known, pre-computed baseline without repeating the warm-up period.

Common use cases:

- **Warm-start parameter sweeps**: Run a shared 10-year spin-up once, save a snapshot, then branch into dozens of scenario variants.
- **Long runs in segments**: Split a 30-year run into shorter jobs that fit within a compute-cluster time limit.
- **Reproducible checkpoints**: Share a snapshot file with collaborators so they can reproduce results from a fixed starting condition.

## Key concepts

### Align start_time with the snapshot date

A snapshot divides a run into two **segments**: one before the snapshot and the 
second after the snapshot. Each segment is a fully independent `ABMModel` (or 
`CompartmentalModel`) instance with its own `params` object.

The most important rule: **set `params.start_time` for segment 2 to the snapshot
date**. Both `save_snapshot` and `load_snapshot` print this value — look for the
`Resume with:` line in the `save_snapshot` output, or the `snap_date` in the
`load_snapshot` output.

```python
# save_snapshot prints: "Resume with: params.start_time='2009-12'"
params2 = lm.ABMParams(start_time="2009-12", ...)  # ← must match snap_date month
```

If `start_time` is wrong, `model.current_date` will be wrong and any
date-dependent components (SIA calendars, importation schedules) will fire at
incorrect times.

### Do not re-seed the infection in segment 2

Do not include `InfectionSeedingProcess` in the segment 2 component list. 
Infections are already encoded in the restored patch states and agent states; 
re-seeding would add spurious infections on top of an already active epidemic.

```python
# Segment 1 — seeding needed to start the epidemic
model1.components = [InfectionSeedingProcess, InfectionProcess]

# Segment 2 — epidemic is already running; seeding not needed
model2 = lm.load_snapshot(snap, params2, components=[InfectionProcess])
```

### Do not re-initialize the population equilibrium in segment 2
    
Do not include `InitializeEquilibriumStatesProcess` in the segment 2 component
list. It re-initializes the population to equilibrium values and would
overwrite the loaded state.

### SIA calendars can exist across the snapshot boundary 

When `SIACalendarProcess` is in the component list, the snapshot saves the set of
campaign IDs that were already applied before the save point
(`implemented_sias`).  On load, this set is restored into the new
`SIACalendarProcess` instance. Campaigns already executed in segment 1 will
**not** fire again in segment 2 — only campaigns with dates after the snapshot
boundary remain eligible.

## ABM-specific notes

### Recovered agents are squashed

`save_snapshot` **modifies the model in place**: Recovered (R) agents are removed
from the people frame before writing to disk. This *squashing* dramatically reduces 
the file size for long measles runs where the majority of agents
have recovered.

The patch-level R counts in `patch_states` are preserved — they reflect the true
epidemic state at save time. The in-memory model after saving is therefore no
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
people frame to accommodate projected births during segment 2. The capacity
printed by `load_snapshot` will be larger than `people.count` for this reason.

### Vaccination queue

If `VitalDynamicsProcess` was active, each agent's scheduled vaccination date is
saved relative to the snapshot boundary (tick 0 of segment 2 = the snapshot
date). The vaccination queue is rebuilt automatically on load.
