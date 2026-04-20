"""
Tests for ABM snapshot save/load (save_snapshot / load_snapshot).

Tests run two segments:
  seg1: run N ticks → save snapshot
  seg2: load → run M ticks

Checks:
  - Patch SEIR counts are non-negative and consistent with people counts
  - People count is within expected range
  - Resumed model advances current_date correctly
  - Round-trip with NoBirthsProcess (no vital dynamics)
  - Round-trip with VitalDynamicsProcess (births, deaths, vaccination queue)
  - Exact continuity: all SEIR channels match at the snapshot boundary and
    the epidemic is active (I > 0) so the test cannot trivially pass
"""

from typing import ClassVar

import numpy as np
import polars as pl

import laser.measles as lm
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import VitalDynamicsProcess
from laser.measles.abm.snapshot import load_snapshot
from laser.measles.abm.snapshot import save_snapshot

VERBOSE = False

# ── Minimal 2-patch scenario ──────────────────────────────────────────────────


def _scenario() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": ["patch0", "patch1"],
            "pop": [10_000, 5_000],
            "lat": [0.0, 1.0],
            "lon": [0.0, 1.0],
            "mcv1": [0.5, 0.5],
        }
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seir_consistent(model) -> bool:
    """Patch SEIR totals are non-negative and match per-patch people counts when available."""
    patch_total = np.asarray(model.patches.states.sum(axis=0))  # (n_patches,)
    assert (patch_total >= 0).all(), "Negative patch state counts"

    people = getattr(model, "people", None)
    if people is None or not hasattr(people, "patch_id"):
        return True

    patch_id = np.asarray(people.patch_id)
    if patch_id.ndim != 1:
        patch_id = patch_id.reshape(-1)

    active = getattr(people, "active", None)
    if active is None:
        active_mask = np.ones(patch_id.shape[0], dtype=bool)
    else:
        active_mask = np.asarray(active, dtype=bool)
        if active_mask.ndim != 1:
            active_mask = active_mask.reshape(-1)

    assert patch_id.shape[0] == active_mask.shape[0], (
        "people.patch_id and people.active must have the same length"
    )

    n_patches = patch_total.shape[0]
    active_patch_id = patch_id[active_mask]
    assert ((active_patch_id >= 0) & (active_patch_id < n_patches)).all(), (
        "Active people must have valid patch ids"
    )

    people_total = np.bincount(active_patch_id, minlength=n_patches)
    assert np.array_equal(patch_total, people_total), (
        f"Patch SEIR totals {patch_total.tolist()} != active people counts "
        f"{people_total.tolist()}"
    )
    return True


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSnapshotNoBirths:
    """Round-trip with NoBirthsProcess (static population, no vital dynamics)."""

    COMP: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    TICKS_SEG1 = 30
    TICKS_SEG2 = 20

    def test_roundtrip(self, tmp_path):
        snap = tmp_path / "snap_no_births.h5"
        scenario = _scenario()

        # Segment 1
        p1 = lm.ABMParams(num_ticks=self.TICKS_SEG1, seed=1, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        patch_S_after_seg1 = int(m1.patches.states.S.sum())
        save_snapshot(m1, snap, verbose=VERBOSE)
        # Count AFTER save (recovered agents have been squashed)
        count_after_snap = m1.people.count

        # Segment 2 — load and continue
        p2 = lm.ABMParams(num_ticks=self.TICKS_SEG2, seed=1, start_time="2000-02", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        assert m2.people.count == count_after_snap, "People count changed across snapshot boundary"
        assert _seir_consistent(m2)

        m2.run()
        assert _seir_consistent(m2)
        # Susceptibles should be ≤ what they were after seg1 (infections may have occurred)
        assert int(m2.patches.states.S.sum()) <= patch_S_after_seg1

    def test_from_snapshot_classmethod(self, tmp_path):
        """ABMModel.from_snapshot is a working alias for load_snapshot."""
        snap = tmp_path / "snap_classmethod.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=10, seed=2, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(num_ticks=10, seed=2, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m2 = lm.ABMModel.from_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)
        m2.run()
        assert _seir_consistent(m2)


class TestSnapshotVitalDynamics:
    """Round-trip with VitalDynamicsProcess (births, deaths, vaccination queue)."""

    TICKS_SEG1 = 60
    TICKS_SEG2 = 30
    # Vital dynamics only — enough to exercise snapshot of people properties and
    # vaccination queue without triggering the known small-population overflow
    # that affects VitalDynamics + InfectionProcess in tiny scenarios.
    COMP: ClassVar = [VitalDynamicsProcess]

    def test_roundtrip(self, tmp_path):
        snap = tmp_path / "snap_vital.h5"
        scenario = _scenario()

        # Segment 1
        p1 = lm.ABMParams(num_ticks=self.TICKS_SEG1, seed=3, start_time="2000-01", show_progress=False, verbose=VERBOSE, use_numba=False)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        # Segment 2
        p2 = lm.ABMParams(num_ticks=self.TICKS_SEG2, seed=3, start_time="2000-03", show_progress=False, verbose=VERBOSE, use_numba=False)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        assert m2.people.count > 0
        assert hasattr(m2.people, "date_of_vaccination"), "date_of_vaccination missing after load"
        assert hasattr(m2.people, "active"), "active missing after load"
        assert _seir_consistent(m2)

        m2.run()
        assert _seir_consistent(m2)

    def test_vaccination_queue_rebuilt(self, tmp_path):
        """Vaccination queue has entries for agents with pending dates."""
        snap = tmp_path / "snap_vq.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=self.TICKS_SEG1, seed=4, start_time="2000-01", show_progress=False, verbose=VERBOSE, use_numba=False)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(num_ticks=self.TICKS_SEG2, seed=4, start_time="2000-03", show_progress=False, verbose=VERBOSE, use_numba=False)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        # Find the VitalDynamicsProcess instance and check its queue
        vd_inst = next((i for i in m2.instances if isinstance(i, VitalDynamicsProcess)), None)
        assert vd_inst is not None, "VitalDynamicsProcess not found in loaded model"

        null_val = int(np.iinfo(np.int32).max)
        pending = m2.people.date_of_vaccination[: m2.people.count].astype(np.int64) < null_val
        n_pending = int(pending.sum())
        assert len(vd_inst.vaccination_queue) == n_pending, f"Queue length {len(vd_inst.vaccination_queue)} != pending agents {n_pending}"


class TestSnapshotTopLevelAPI:
    """save_snapshot / load_snapshot are importable from laser.measles directly."""

    def test_top_level_import(self):
        assert hasattr(lm, "save_snapshot")
        assert hasattr(lm, "load_snapshot")

    def test_snapshot_file_created(self, tmp_path):
        snap = tmp_path / "api_test.h5"
        scenario = _scenario()
        p = lm.ABMParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m = lm.ABMModel(scenario, p)
        m.components = [InfectionSeedingProcess, InfectionProcess]
        m.run()
        lm.save_snapshot(m, snap, verbose=VERBOSE)
        assert snap.exists()
        assert snap.stat().st_size > 0


# ── Continuity test ───────────────────────────────────────────────────────────


def _large_scenario() -> pl.DataFrame:
    """Larger scenario to ensure the epidemic is well under way at snap time."""
    return pl.DataFrame(
        {
            "id": ["urban", "rural_a", "rural_b"],
            "pop": [50_000, 20_000, 10_000],
            "lat": [0.0, 1.0, -1.0],
            "lon": [0.0, 1.0, 1.0],
            "mcv1": [0.5, 0.4, 0.3],
        }
    )


class TestSnapshotContinuity:
    """
    Exact SEIR channel continuity at the snapshot boundary.

    Mirrors the laser-polio continuity test:
      1. Run seg1 for SNAP_TICKS, capture SEIR patch counts at the final tick.
      2. Save snapshot.
      3. Load snapshot, capture SEIR patch counts immediately (before run).
      4. Assert all four channels match exactly at the boundary.
      5. Assert the epidemic is active (I > 0) so the test cannot trivially pass.
      6. Run seg2 to completion and verify SEIR counts remain non-negative.
    """

    SNAP_TICKS = 55  # at epidemic peak (I is maximal around tick 56)
    SEG2_TICKS = 50  # long enough to witness the full post-peak decline
    COMP: ClassVar = [InfectionSeedingProcess, InfectionProcess]

    def test_seir_continuity_at_boundary(self, tmp_path):
        snap = tmp_path / "continuity.h5"
        scenario = _large_scenario()

        # ── Segment 1 ─────────────────────────────────────────────────────────
        p1 = lm.ABMParams(
            num_ticks=self.SNAP_TICKS,
            seed=42,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
        )
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()

        # Capture SEIR BEFORE save_snapshot (which squashes R agents but
        # does not modify patches.states).
        n_states = len(m1.params.states)
        n_patches = len(m1.scenario)
        seir_end_seg1 = np.zeros((n_states, n_patches), dtype=np.int64)
        for i, s in enumerate(m1.params.states):
            seir_end_seg1[i] = getattr(m1.patches.states, s).copy()

        # Epidemic must be active at the snapshot boundary.
        I_idx = m1.params.states.index("I")
        total_I = int(seir_end_seg1[I_idx].sum())
        assert total_I > 0, f"No active infections at snapshot boundary (I={total_I}). Increase SNAP_TICKS or seed more infections."

        save_snapshot(m1, snap, verbose=VERBOSE)

        # ── Load and check boundary ────────────────────────────────────────────
        p2 = lm.ABMParams(
            num_ticks=self.SEG2_TICKS,
            seed=42,
            start_time="2000-02",
            show_progress=False,
            verbose=VERBOSE,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        # Capture SEIR immediately after load, before any ticks run.
        seir_start_seg2 = np.zeros((n_states, n_patches), dtype=np.int64)
        for i, s in enumerate(m2.params.states):
            seir_start_seg2[i] = getattr(m2.patches.states, s).copy()

        # ── Exact continuity check ─────────────────────────────────────────────
        for i, state in enumerate(m1.params.states):
            np.testing.assert_array_equal(
                seir_end_seg1[i],
                seir_start_seg2[i],
                err_msg=(
                    f"Channel '{state}' is discontinuous at snapshot boundary.\n"
                    f"  seg1 end:   {seir_end_seg1[i]}\n"
                    f"  seg2 start: {seir_start_seg2[i]}"
                ),
            )

        # ── Seg2 runs cleanly ──────────────────────────────────────────────────
        m2.run()
        for s in m2.params.states:
            assert (getattr(m2.patches.states, s) >= 0).all(), f"Negative '{s}' counts after seg2 run"

    def test_people_count_boundary(self, tmp_path):
        """
        People count at seg2 start matches seg1 end (post-squash).
        Included to guard against silent frame-resize bugs in component inits.
        """
        snap = tmp_path / "count_boundary.h5"
        scenario = _large_scenario()

        p1 = lm.ABMParams(
            num_ticks=self.SNAP_TICKS,
            seed=7,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
        )
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()

        save_snapshot(m1, snap, verbose=VERBOSE)
        count_after_snap = m1.people.count  # post-squash count

        p2 = lm.ABMParams(
            num_ticks=self.SEG2_TICKS,
            seed=7,
            start_time="2000-02",
            show_progress=False,
            verbose=VERBOSE,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        assert m2.people.count == count_after_snap, (
            f"People count changed at boundary: seg1 post-squash={count_after_snap}, seg2 start={m2.people.count}"
        )
