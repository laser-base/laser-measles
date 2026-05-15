# Snapshotting

Snapshotting captures the complete state of a running simulation at a chosen point in time and writes it to disk. A saved snapshot can be loaded later to resume the simulation from that exact state, bypassing the need to re-run everything that came before.

This page explains why snapshotting exists, what it preserves, and the concepts you need to understand before saving and loading snapshots. For step-by-step instructions, see [How to snapshot and resume a simulation](snapshot-resume.md).

## Why snapshot?

Long epidemic simulations are expensive to re-run from scratch. A 10-year measles simulation with vital dynamics can take minutes to hours depending on the model type and population size. Without snapshotting, any work that builds on the results of a long run — parameter sweeps, post-peak analysis, intervention comparisons — must repeat the entire simulation from the beginning.

Snapshotting solves this by letting you run the expensive part once and reuse it. Three common use cases:

- **Warm-start parameter sweeps** — Run a shared 10-year spin-up once, save a snapshot, then branch into dozens of scenario variants that each start from the same pre-computed baseline. This is especially valuable when compute resources are limited, as it avoids redundant re-computation of the warm-up period.
- **Long runs in segments** — Split a 30-year run into shorter jobs that fit within a compute-cluster time limit or can be run overnight on a standard laptop.
- **Reproducible checkpoints** — Share a snapshot file with collaborators so they can reproduce results from a fixed starting condition without running the spin-up themselves.

## Segments and start_time alignment

A snapshot divides a simulation into **segments**. Each segment is a fully independent model instance with its own `params` object. The first segment runs from the beginning, and the second segment loads a snapshot and continues from where the first left off.

The most important rule when resuming a snapshot: **set `start_time` in the second segment's params to match the snapshot date.** Both `save_snapshot` and `load_snapshot` print this value — look for the `Resume with:` line in the save output.

```python
# save_snapshot prints: "Resume with: params.start_time='2009-12'"
params2 = lm.ABMParams(start_time="2009-12", ...)  # ← must match snap_date month
```

If `start_time` is wrong, `model.current_date` will be wrong and any date-dependent components (SIA calendars, importation schedules) will fire at incorrect times.

## What is preserved

Snapshots are stored as [HDF5](https://www.hdfgroup.org/solutions/hdf5/) files (`.h5`), a standard binary format readable by any HDF5-compatible tool (Python, R, MATLAB, Julia, command-line utilities). This makes snapshots portable and inspectable.

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

## Supported model types

Both the ABM and compartmental models support snapshotting. The biweekly model does not currently support it.

| Model | Save function | Load function | Classmethod alias |
|---|---|---|---|
| ABM (`ABMModel`) | `lm.save_snapshot` | `lm.load_snapshot` | `ABMModel.from_snapshot` |
| Compartmental (`CompartmentalModel`) | `lm.save_snapshot` | `lm.load_snapshot` | `CompartmentalModel.from_snapshot` |

Both functions are importable from the top-level `laser.measles` namespace.

## Component handling across the boundary

When loading a snapshot, the component list you provide determines what runs in the second segment. Two components require special treatment:

**Do not include `InfectionSeedingProcess` in the second segment.** Infections are already encoded in the restored patch states and agent states. Re-seeding would add spurious infections on top of an already-active epidemic.

**Do not include `InitializeEquilibriumStatesProcess` in the second segment.** It re-initializes the population to equilibrium values and would overwrite the loaded state.

SIA calendars work correctly across the boundary: the snapshot saves the set of campaign IDs already applied (`implemented_sias`), and on load, this set is restored so that campaigns from segment 1 do not fire again.

## ABM-specific concepts

### R-agent squashing

`save_snapshot` modifies the ABM model in place: recovered (R) agents are removed from the people frame before writing to disk. This *squashing* dramatically reduces file size for long measles runs where the majority of agents have recovered.

The patch-level R counts in `patch_states` are preserved — they reflect the true epidemic state at save time. The in-memory model after saving is no longer consistent for continued simulation; **do not call `model.run()` after `save_snapshot()`**.

### Population capacity for future births

When `VitalDynamicsProcess` is in the component list, `load_snapshot` restores the current population from disk and then lets `VitalDynamicsProcess` expand the people frame to accommodate projected births during the second segment. The capacity printed by `load_snapshot` will be larger than `people.count` for this reason.

### Vaccination queue

If `VitalDynamicsProcess` was active, each agent's scheduled vaccination date is saved relative to the snapshot boundary (tick 0 of segment 2 = the snapshot date). The vaccination queue is rebuilt automatically on load.

## See also

- [How to snapshot and resume a simulation](snapshot-resume.md) — step-by-step procedure for saving and loading snapshots
- [Model types](../model-types/index.md) — overview of the three model types and which support snapshotting
- [Components](../components/index.md) — component architecture and execution order
- [Tutorials](../tutorials/index.md) — hands-on examples for getting started
