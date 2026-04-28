"""
Snapshot save/load for the laser-measles compartmental model.

Snapshots capture the full patch SEIR state at a given point in time and
allow the simulation to be resumed exactly from that point.

Typical usage::

    import laser.measles as lm
    from laser.measles.compartmental import save_snapshot, load_snapshot
    from laser.measles.compartmental.components import InfectionProcess

    # --- Segment 1 ---
    model1 = lm.CompartmentalModel(scenario, params1)
    model1.components = [InfectionProcess]
    model1.run()
    save_snapshot(model1, "checkpoint.h5")

    # --- Segment 2 ---
    params2 = lm.CompartmentalParams(start_time="2001-01", num_ticks=365)
    model2 = load_snapshot("checkpoint.h5", params2, components=[InfectionProcess])
    model2.run()

Notes:
    - Do **not** include ``InfectionSeedingProcess`` in the ``components`` list
      for a resumed run — infections are already encoded in the restored patch
      states.
    - Snapshots persist ``SIACalendarProcess``'s ``implemented_sias`` state.
      When resumed with ``SIACalendarProcess`` in the ``components`` list,
      campaigns already applied before the snapshot will not fire again; only
      campaigns not yet implemented in the schedule remain eligible.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import h5py
import numpy as np
import polars as pl

if TYPE_CHECKING:
    from laser.measles.compartmental.model import CompartmentalModel
    from laser.measles.compartmental.params import CompartmentalParams

__all__ = ["load_snapshot", "save_snapshot"]


def save_snapshot(
    model: CompartmentalModel,
    path: str | Path,
    verbose: bool = True,
) -> None:
    """Save compartmental model patch state to an HDF5 snapshot file.

    Call this after
    [`CompartmentalModel.run()`][laser.measles.compartmental.model.CompartmentalModel]
    to persist the full patch SEIR state.  The resulting HDF5 file can be
    resumed with
    [`load_snapshot`][laser.measles.compartmental.snapshot.load_snapshot] to
    continue the simulation from exactly where it left off.

    Args:
        model: A fully-run (or mid-run)
            [`CompartmentalModel`][laser.measles.compartmental.model.CompartmentalModel]
            instance.
        path: Destination HDF5 file path (created or overwritten).
        verbose: Print a progress summary.

    **Example:**

        ```python
        import laser.measles as lm
        from laser.measles.compartmental import save_snapshot
        from laser.measles.compartmental.components import (
            InfectionSeedingProcess,
            InfectionProcess,
        )

        params = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = lm.CompartmentalModel(scenario, params)
        model.components = [InfectionSeedingProcess, InfectionProcess]
        model.run()

        save_snapshot(model, "checkpoint.h5")
        ```
    """
    path = Path(path)

    t_snap = int((model.current_date - model.start_time).days)
    snap_date = model.current_date.strftime("%Y-%m-%d")

    state_names = model.params.states
    patch_states = np.stack(
        [np.array(getattr(model.patches.states, s), dtype=np.int32) for s in state_names]
    )  # shape (n_states, n_patches)

    with h5py.File(path, "w") as f:
        f.create_dataset("t_snap", data=np.int32(t_snap))
        f.create_dataset("snap_date", data=snap_date)
        f.create_dataset("patch_states", data=patch_states)

        # ── Persist SIACalendarProcess.implemented_sias ───────────────────────
        all_sias: set[str] = set()
        for inst in getattr(model, "instances", []):
            if hasattr(inst, "implemented_sias"):
                all_sias.update(str(s) for s in inst.implemented_sias)
        if all_sias:
            f.create_dataset(
                "implemented_sias",
                data=np.array([s.encode() for s in sorted(all_sias)]),
            )

        scen_grp = f.create_group("scenario")
        scen_df = model.scenario.unwrap()
        for col in scen_df.columns:
            series = scen_df[col]
            if series.dtype == pl.String:
                scen_grp.create_dataset(col, data=np.array([s.encode() for s in series.to_list()]))
            else:
                scen_grp.create_dataset(col, data=series.to_numpy())

    if verbose:
        total_I = int(patch_states[state_names.index("I")].sum())
        print(f"Snapshot saved → {path}")
        print(f"  t_snap={t_snap}  snap_date={snap_date}  I={total_I:,}")
        print(f"  Resume with: params.start_time='{snap_date[:7]}'")


def load_snapshot(
    path: str | Path,
    params: CompartmentalParams,
    components: list | None = None,
    verbose: bool = True,
) -> CompartmentalModel:
    """Load a compartmental model from an HDF5 snapshot file and return it ready to run.

    Restores the patch SEIR state, scenario, and metadata saved by
    [`save_snapshot`][laser.measles.compartmental.snapshot.save_snapshot].
    Set ``params.start_time`` to the snapshot date printed by
    ``save_snapshot``.  Do **not** include ``InfectionSeedingProcess`` in the
    ``components`` list — infections are already encoded in the restored
    patch states.

    Args:
        path: Path to the HDF5 snapshot file written by
            [`save_snapshot`][laser.measles.compartmental.snapshot.save_snapshot].
        params:
            [`CompartmentalParams`][laser.measles.compartmental.params.CompartmentalParams]
            for the resumed segment.  Set ``start_time`` to the snapshot date
            and ``num_ticks`` to the remaining duration.
        components: Ordered list of component *classes* to attach — same list
            as used when building the original model, minus
            ``InfectionSeedingProcess``.
        verbose: Print a loading summary.

    Returns:
        A configured
            [`CompartmentalModel`][laser.measles.compartmental.model.CompartmentalModel]
            instance.  Call ``model.run()`` to continue the simulation.

    **Example:**

        ```python
        import laser.measles as lm
        from laser.measles.compartmental import load_snapshot
        from laser.measles.compartmental.components import InfectionProcess

        params2 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2001-01")
        model2 = load_snapshot(
            "checkpoint.h5", params2, components=[InfectionProcess]
        )
        model2.run()
        ```
    """
    from laser.measles.compartmental.model import CompartmentalModel  # noqa: PLC0415

    path = Path(path)
    components = components or []

    with h5py.File(path, "r") as f:
        t_snap = int(f["t_snap"][()])
        raw = f["snap_date"][()]
        snap_date = raw.decode() if isinstance(raw, bytes) else str(raw)
        patch_states = f["patch_states"][:]  # (n_states, n_patches)
        implemented_sias: set[str] = set()
        if "implemented_sias" in f:
            implemented_sias = {s.decode() if isinstance(s, bytes) else s for s in f["implemented_sias"][:]}

        scen_grp = f["scenario"]
        scen_data: dict = {}
        for col in scen_grp:
            data = scen_grp[col][:]
            if data.dtype.kind in ("S", "O"):
                scen_data[col] = [s.decode() if isinstance(s, bytes) else s for s in data]
            else:
                scen_data[col] = data

    # Reconstruct scenario DataFrame with correct dtypes
    scenario_df = pl.DataFrame(scen_data)
    cast_exprs = []
    if "pop" in scenario_df.columns:
        cast_exprs.append(pl.col("pop").cast(pl.Int64))
    if "lat" in scenario_df.columns:
        cast_exprs.append(pl.col("lat").cast(pl.Float64))
    if "lon" in scenario_df.columns:
        cast_exprs.append(pl.col("lon").cast(pl.Float64))
    if "mcv1" in scenario_df.columns:
        cast_exprs.append(pl.col("mcv1").cast(pl.Float64))
    if "id" in scenario_df.columns:
        cast_exprs.append(pl.col("id").cast(pl.String))
    if cast_exprs:
        scenario_df = scenario_df.with_columns(cast_exprs)

    expected_shape = (len(params.states), len(scenario_df))
    if patch_states.ndim != 2 or patch_states.shape != expected_shape:
        raise ValueError(
            "Snapshot patch_states shape is incompatible with the current model "
            f"configuration: expected {expected_shape} for "
            f"{len(params.states)} states and {len(scenario_df)} patches, "
            f"got {patch_states.shape}."
        )

    # Build a fresh model (initialises patches.states to S=pop, E=I=R=0)
    model = CompartmentalModel(scenario=scenario_df, params=params)

    # Restore patch state counters from snapshot
    for i, state_name in enumerate(params.states):
        getattr(model.patches.states, state_name)[:] = patch_states[i]

    # Attach components
    model.components = components

    # ── Restore implemented_sias into any SIACalendarProcess instances ────────
    if implemented_sias:
        for inst in model.instances:
            if hasattr(inst, "implemented_sias"):
                inst.implemented_sias.update(implemented_sias)

    if verbose:
        total_I = int(patch_states[params.states.index("I")].sum())
        print(f"Loaded snapshot from {path}")
        print(f"  snap_date={snap_date}  t_snap={t_snap}  I={total_I:,}")
        print(f"  params.start_time={params.start_time}  num_ticks={params.num_ticks}")

    return model
