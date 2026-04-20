"""
Snapshot save/load for the laser-measles ABM.

Snapshots capture the full population and patch state at a given point in time
and allow the simulation to be resumed exactly from that point.

Typical usage::

    import laser.measles as lm

    # --- Segment 1 ---
    model1 = lm.ABMModel(scenario, params1)
    model1.components = [lm.VitalDynamicsProcess, lm.InfectionProcess]
    model1.run()
    lm.save_snapshot(model1, "checkpoint.h5")

    # --- Segment 2 ---
    params2 = lm.ABMParams(start_time="2001-01", num_ticks=365)
    model2 = lm.load_snapshot("checkpoint.h5", params2,
                               components=[lm.VitalDynamicsProcess, lm.InfectionProcess])
    model2.run()

Notes:
    - ``save_snapshot`` **modifies** the model in place: R agents are squashed and
      vaccination dates are normalized.  Do not continue using the model after saving.
    - The caller is responsible for setting ``params.start_time`` in the resumed
      segment to match the snapshot date (printed by ``load_snapshot``).
    - ``WPPVitalDynamicsProcess`` is supported with the same guard mechanism.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import h5py
import numpy as np
import polars as pl

if TYPE_CHECKING:
    from laser.measles.abm.model import ABMModel
    from laser.measles.abm.params import ABMParams

__all__ = ["load_snapshot", "save_snapshot"]

# Null sentinel used by VitalDynamicsProcess / WPPVitalDynamicsProcess for
# unscheduled dates.  Must match the value used in those components.
_DATE_NULL = int(np.iinfo(np.int32).max)  # 2_147_483_647


def save_snapshot(
    model: ABMModel,
    path: str | Path,
    squash_recovered: bool = True,
    verbose: bool = True,
) -> None:
    """
    Save ABM state to an HDF5 snapshot file.

    .. warning::
        This function **mutates** ``model``: recovered agents are squashed (if
        ``squash_recovered=True``) and future vaccination dates are normalized.
        Do not continue running the model after calling this function.

    Args:
        model: A fully-run (or mid-run) :class:`ABMModel` instance.
        path: Destination HDF5 file path (created or overwritten).
        squash_recovered: If ``True`` (default), remove recovered agents before
            saving.  This dramatically reduces file size for long measles runs.
        verbose: Print a progress summary.
    """
    path = Path(path)

    # Elapsed ticks = elapsed calendar days (ABM time_step_days == 1)
    t_snap = int((model.current_date - model.start_time).days)
    snap_date = model.current_date.strftime("%Y-%m-%d")

    # ── Capture patch states BEFORE any squashing ─────────────────────────────
    state_names = model.params.states  # ["S", "E", "I", "R"]
    patch_states = np.stack(
        [np.array(getattr(model.patches.states, s), dtype=np.int32) for s in state_names]
    )  # shape (n_states, n_patches)

    # ── Normalize future vaccination dates so they are relative to t_snap ─────
    # Only applicable when VitalDynamicsProcess (or WPP variant) is in use.
    if hasattr(model.people, "date_of_vaccination"):
        _normalize_vaccination_dates(model.people, t_snap)

    # ── Optionally squash recovered agents ────────────────────────────────────
    if squash_recovered:
        r_idx = np.uint8(model.params.states.index("R"))
        keep = model.people.state[: model.people.count] != r_idx
        n_squash = int((~keep).sum())
        if verbose:
            print(f"Squashing {n_squash:,} recovered agents")
        model.people.squash(keep)

    # ── results_r: per-node R count, shape (1, n_patches) ────────────────────
    # Used by LaserFrame.load_snapshot to correctly size capacity when CBR is
    # provided (it adds back squashed R agents to the per-node population).
    r_idx_int = model.params.states.index("R")
    results_r = patch_states[r_idx_int].reshape(1, -1).astype(np.int32)

    # ── Save people LaserFrame + ABMParams via laser-core API ─────────────────
    model.people.save_snapshot(path, results_r=results_r, pars=model.params.model_dump())

    # ── Find CBR from any vital-dynamics component ────────────────────────────
    # Only look at pydantic model_fields, not @property overrides (e.g. NoBirthsParams).
    cbr_per_1000: float | None = None
    for inst in getattr(model, "instances", []):
        p = getattr(inst, "params", None)
        if p is not None and hasattr(p, "crude_birth_rate"):
            val = p.crude_birth_rate
            if isinstance(val, (int, float)) and float(val) > 0:
                cbr_per_1000 = float(val)
                break

    # ── Append extra datasets ─────────────────────────────────────────────────
    with h5py.File(path, "a") as f:
        f.create_dataset("t_snap", data=np.int32(t_snap))
        f.create_dataset("snap_date", data=snap_date)
        f.create_dataset("patch_states", data=patch_states)
        if cbr_per_1000 is not None:
            f.create_dataset("cbr_per_1000", data=float(cbr_per_1000))

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
        print(f"Snapshot saved → {path}")
        print(f"  t_snap={t_snap}  snap_date={snap_date}  people.count={model.people.count:,}")
        if cbr_per_1000 is not None:
            print(f"  cbr_per_1000={cbr_per_1000}")
        print(f"  Resume with: params.start_time='{snap_date[:7]}'")


def load_snapshot(
    path: str | Path,
    params: ABMParams,
    components: list | None = None,
    verbose: bool = True,
) -> ABMModel:
    """
    Load an ABM from an HDF5 snapshot file and return it ready to run.

    Args:
        path: Path to the HDF5 snapshot file written by :func:`save_snapshot`.
        params: :class:`ABMParams` for the resumed segment.  Set
            ``start_time`` to the snapshot date (printed by ``save_snapshot``
            or ``load_snapshot``) and ``num_ticks`` to the remaining duration.
        components: Ordered list of component *classes* to attach — same list
            as used when building the original model.  Components that modify
            the people frame (e.g. ``VitalDynamicsProcess``) detect the
            snapshot context via ``model._from_snapshot`` and skip frame setup.
        verbose: Print a loading summary.

    Returns:
        A configured :class:`ABMModel` instance.  Call ``model.run()`` to
        continue the simulation.
    """
    from laser.measles.abm.base import PeopleLaserFrame  # noqa: PLC0415
    from laser.measles.abm.model import ABMModel  # noqa: PLC0415

    path = Path(path)
    components = components or []

    # ── Load metadata ─────────────────────────────────────────────────────────
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

    # ── Reconstruct scenario DataFrame ───────────────────────────────────────
    scenario_df = pl.DataFrame(scen_data)
    # Ensure BaseABMScenario-required dtypes regardless of HDF5 round-trip
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

    # ── Load people LaserFrame ────────────────────────────────────────────────
    # Always use cbr=None so laser-core doesn't require a 'node_id' property
    # (laser-measles uses 'patch_id').  Capacity for projected births is handled
    # by VitalDynamicsProcess.__init__ in snapshot mode when it detects
    # model._from_snapshot and calls initialize_people_capacity itself.
    people, _, _ = PeopleLaserFrame.load_snapshot(path, cbr=None, nt=None)

    if verbose:
        print(f"Loaded snapshot from {path}")
        print(f"  snap_date={snap_date}  t_snap={t_snap}")
        print(f"  people.count={people.count:,}  capacity={people.capacity:,}")
        print(f"  params.start_time={params.start_time}  num_ticks={params.num_ticks}")

    # ── Build model (setup_patches / setup_people run, then we replace) ───────
    model = ABMModel(scenario=scenario_df, params=params)

    # Mark as snapshot-loaded BEFORE adding components so that each component's
    # __init__ (and _initialize) can detect and skip frame-modifying operations.
    model._from_snapshot = True
    model._t_snap = t_snap

    # Replace the placeholder people frame with the loaded one
    model.people = people

    # Restore patch state counters
    for i, state_name in enumerate(params.states):
        getattr(model.patches.states, state_name)[:] = patch_states[i]

    # ── Add components ────────────────────────────────────────────────────────
    for comp_class in components:
        model.add_component(comp_class)

    # ── Restore implemented_sias into any SIACalendarProcess instances ────────
    if implemented_sias:
        for inst in model.instances:
            if hasattr(inst, "implemented_sias"):
                inst.implemented_sias.update(implemented_sias)

    return model


# ── Internal helpers ──────────────────────────────────────────────────────────


def _normalize_vaccination_dates(people, t_snap: int) -> None:
    """
    Subtract *t_snap* from all future (non-null) vaccination dates so they are
    relative to the start of the resumed segment (tick 0).

    Agents with ``date_of_vaccination == _DATE_NULL`` (never scheduled) or
    ``<= t_snap`` (already vaccinated / will be squashed) are not touched.
    """
    dov = people.date_of_vaccination[: people.count]
    # Cast to int64 to avoid uint32 comparison pitfalls
    dov_i64 = dov.astype(np.int64)
    future_mask = (dov_i64 < _DATE_NULL) & (dov_i64 > t_snap)
    if future_mask.any():
        dov[future_mask] = (dov_i64[future_mask] - t_snap).astype(dov.dtype)
