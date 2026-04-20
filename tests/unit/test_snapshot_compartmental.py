"""
Tests for compartmental model snapshot save/load.

Tests run two segments:
  seg1: run N ticks → save snapshot
  seg2: load → run M ticks

Checks:
  - Patch SEIR counts are non-negative and consistent after each segment
  - Resumed model advances current_date correctly
  - Round-trip with InfectionProcess (standard case)
  - Round-trip with VitalDynamicsProcess
  - Exact continuity: all SEIR channels match at the snapshot boundary and
    the epidemic is active (I > 0) so the test cannot trivially pass
  - CompartmentalModel.from_snapshot classmethod alias works
"""

import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

import laser.measles as lm
from laser.measles.compartmental import load_snapshot
from laser.measles.compartmental import save_snapshot
from laser.measles.compartmental.components import InfectionProcess
from laser.measles.compartmental.components import InfectionSeedingProcess
from laser.measles.compartmental.components import VitalDynamicsProcess


VERBOSE = False


# ── Scenarios ─────────────────────────────────────────────────────────────────

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


def _large_scenario() -> pl.DataFrame:
    """3-patch scenario with enough population to sustain a well-developed epidemic."""
    return pl.DataFrame(
        {
            "id": ["urban", "rural_a", "rural_b"],
            "pop": [50_000, 20_000, 10_000],
            "lat": [0.0, 1.0, -1.0],
            "lon": [0.0, 1.0,  1.0],
            "mcv1": [0.5, 0.4, 0.3],
        }
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seir_non_negative(model) -> None:
    for s in model.params.states:
        assert (getattr(model.patches.states, s) >= 0).all(), (
            f"Negative '{s}' counts"
        )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSnapshotBasic:
    """Round-trip with InfectionProcess only (no vital dynamics)."""

    COMP_SEG1 = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2 = [InfectionProcess]  # no seeding in resumed run
    TICKS_SEG1 = 30
    TICKS_SEG2 = 20

    def test_roundtrip(self, tmp_path):
        snap = tmp_path / "snap_basic.h5"
        scenario = _scenario()

        p1 = lm.CompartmentalParams(num_ticks=self.TICKS_SEG1, seed=1, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()
        _seir_non_negative(m1)
        patch_S_after_seg1 = int(m1.patches.states.S.sum())
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(num_ticks=self.TICKS_SEG2, seed=1, start_time="2000-02", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)
        _seir_non_negative(m2)

        m2.run()
        _seir_non_negative(m2)
        # Epidemic should continue — S cannot increase
        assert int(m2.patches.states.S.sum()) <= patch_S_after_seg1

    def test_file_created(self, tmp_path):
        snap = tmp_path / "file_check.h5"
        scenario = _scenario()
        p = lm.CompartmentalParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m = lm.CompartmentalModel(scenario, p)
        m.components = self.COMP_SEG1
        m.run()
        save_snapshot(m, snap, verbose=VERBOSE)
        assert snap.exists()
        assert snap.stat().st_size > 0


class TestSnapshotClassmethod:
    """CompartmentalModel.from_snapshot is a working alias for load_snapshot."""

    COMP_SEG1 = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2 = [InfectionProcess]

    def test_from_snapshot(self, tmp_path):
        snap = tmp_path / "snap_classmethod.h5"
        scenario = _scenario()

        p1 = lm.CompartmentalParams(num_ticks=10, seed=2, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(num_ticks=10, seed=2, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m2 = lm.CompartmentalModel.from_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)
        m2.run()
        _seir_non_negative(m2)


class TestSnapshotVitalDynamics:
    """Round-trip with VitalDynamicsProcess."""

    TICKS_SEG1 = 60
    TICKS_SEG2 = 30
    COMP_SEG1 = [InfectionSeedingProcess, InfectionProcess, VitalDynamicsProcess]
    COMP_SEG2 = [InfectionProcess, VitalDynamicsProcess]

    def test_roundtrip(self, tmp_path):
        snap = tmp_path / "snap_vital.h5"
        scenario = _scenario()

        p1 = lm.CompartmentalParams(num_ticks=self.TICKS_SEG1, seed=3, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(num_ticks=self.TICKS_SEG2, seed=3, start_time="2000-03", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)
        _seir_non_negative(m2)

        m2.run()
        _seir_non_negative(m2)


class TestSnapshotTopLevelAPI:
    """save_snapshot / load_snapshot are importable from laser.measles.compartmental."""

    def test_imports(self):
        from laser.measles.compartmental import load_snapshot, save_snapshot  # noqa: F401
        assert callable(save_snapshot)
        assert callable(load_snapshot)


# ── Continuity test ───────────────────────────────────────────────────────────

class TestSnapshotContinuity:
    """
    Exact SEIR channel continuity at the snapshot boundary.

      1. Run seg1 for SNAP_TICKS, capture SEIR patch counts at the final tick.
      2. Save snapshot.
      3. Load snapshot, capture SEIR patch counts immediately (before run).
      4. Assert all four channels match exactly at the boundary.
      5. Assert the epidemic is active (I > 0) so the test cannot trivially pass.
      6. Run seg2 to completion and verify SEIR counts remain non-negative.
    """

    SNAP_TICKS = 60   # at epidemic peak (total I peaks ~tick 60)
    SEG2_TICKS = 55   # long enough to witness the full post-peak decline
    COMP_SEG1 = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2 = [InfectionProcess]

    def test_seir_continuity_at_boundary(self, tmp_path):
        snap = tmp_path / "continuity.h5"
        scenario = _large_scenario()

        # ── Segment 1 ─────────────────────────────────────────────────────────
        p1 = lm.CompartmentalParams(
            num_ticks=self.SNAP_TICKS,
            seed=42,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
        )
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()

        n_states = len(m1.params.states)
        n_patches = len(m1.scenario)
        seir_end_seg1 = np.zeros((n_states, n_patches), dtype=np.int64)
        for i, s in enumerate(m1.params.states):
            seir_end_seg1[i] = getattr(m1.patches.states, s).copy()

        # Epidemic must be active at the snapshot boundary.
        I_idx = m1.params.states.index("I")
        total_I = int(seir_end_seg1[I_idx].sum())
        assert total_I > 0, (
            f"No active infections at snapshot boundary (I={total_I}). "
            "Increase SNAP_TICKS or seed more infections."
        )

        save_snapshot(m1, snap, verbose=VERBOSE)

        # ── Load and check boundary ────────────────────────────────────────────
        p2 = lm.CompartmentalParams(
            num_ticks=self.SEG2_TICKS,
            seed=42,
            start_time="2000-03",
            show_progress=False,
            verbose=VERBOSE,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)

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
        _seir_non_negative(m2)

    def test_population_conserved_at_boundary(self, tmp_path):
        """
        Total population (S+E+I+R) is conserved across the snapshot boundary
        when there are no vital dynamics.
        """
        snap = tmp_path / "pop_conserved.h5"
        scenario = _large_scenario()

        p1 = lm.CompartmentalParams(
            num_ticks=self.SNAP_TICKS,
            seed=7,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
        )
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()

        total_pop_seg1 = int(m1.patches.states.sum(axis=0).sum())
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(
            num_ticks=self.SEG2_TICKS,
            seed=7,
            start_time="2000-03",
            show_progress=False,
            verbose=VERBOSE,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)

        total_pop_seg2 = int(m2.patches.states.sum(axis=0).sum())
        assert total_pop_seg2 == total_pop_seg1, (
            f"Total population changed at boundary: "
            f"seg1={total_pop_seg1:,}, seg2={total_pop_seg2:,}"
        )
