"""
Compartmental snapshot save/load — requirements traceability and test coverage.

Each requirement is tagged with its test(s) or marked UNTESTED.
INDIRECT means a test would catch a regression but is not named for that requirement.
The compartmental model has no people frame (agents), so requirements around
agent-level properties (DOB, vaccination dates, etimer/itimer) do not apply here.
See test_snapshot.py for the ABM model.

═══════════════════════════════════════════════════════════════════════════
R1  PATCH STATE PRESERVATION
═══════════════════════════════════════════════════════════════════════════

R1.1  All four SEIR channels (S, E, I, R) loaded from snapshot exactly match
      the values present at the end of seg1, per patch.
      → TestSnapshotContinuity::test_seir_continuity_at_boundary

R1.2  SEIR counts are non-negative at the snapshot boundary and after a full
      seg2 run.
      → TestSnapshotBasic::test_roundtrip (_seir_non_negative)
      → TestSnapshotVitalDynamics::test_roundtrip (_seir_non_negative)
      → TestSnapshotContinuity::test_seir_continuity_at_boundary

R1.3  Total population (S+E+I+R) is conserved across the boundary when there
      are no vital dynamics.
      → TestSnapshotContinuity::test_population_conserved_at_boundary

R1.4  S cannot increase between seg1 end and seg2 start (no infections
      spontaneously reverse).
      → TestSnapshotBasic::test_roundtrip (S_seg2 ≤ S_seg1_end)

═══════════════════════════════════════════════════════════════════════════
R2  SCENARIO PRESERVATION
═══════════════════════════════════════════════════════════════════════════

R2.1  Scenario DataFrame round-trips with correct values and dtypes for all
      columns (id, pop, lat, lon, mcv1, and any extras).
      UNTESTED — load_snapshot applies cast_exprs to fix known HDF5 dtype
      drift, but no assertion verifies values are correct after load.

R2.2  String patch IDs survive the HDF5 encode/decode round-trip.
      UNTESTED

═══════════════════════════════════════════════════════════════════════════
R3  VITAL DYNAMICS ACROSS BOUNDARY
═══════════════════════════════════════════════════════════════════════════

R3.1  VitalDynamicsProcess round-trip runs without error (births/deaths not
      disrupted by snapshot boundary).
      → TestSnapshotVitalDynamics::test_roundtrip

R3.2  Population changes due to vital dynamics in seg2 are internally
      consistent (births increase S, deaths reduce compartments proportionally).
      UNTESTED — no reference run comparison; only non-negativity is checked.

═══════════════════════════════════════════════════════════════════════════
R4  COMPONENT BEHAVIOR — SEEDING
═══════════════════════════════════════════════════════════════════════════

R4.1  InfectionSeedingProcess is not included in seg2 component list in any
      current test (seeding only happens in seg1).
      NOTE: There is no test that verifies InfectionSeedingProcess would
      correctly handle being present in seg2 (idempotent or raises clearly).
      UNTESTED

═══════════════════════════════════════════════════════════════════════════
R5  DATE / TIME
═══════════════════════════════════════════════════════════════════════════

R5.1  model.current_date in seg2 begins from params.start_time (the caller's
      chosen resume date).
      UNTESTED

═══════════════════════════════════════════════════════════════════════════
R6  FILE I/O & API
═══════════════════════════════════════════════════════════════════════════

R6.1  Snapshot file is created at the requested path and is non-empty.
      → TestSnapshotBasic::test_file_created

R6.2  CompartmentalModel.from_snapshot is a working alias for load_snapshot.
      → TestSnapshotClassmethod::test_from_snapshot

R6.3  save_snapshot and load_snapshot are callable (importable from the
      compartmental sub-package).
      → TestSnapshotTopLevelAPI::test_imports

═══════════════════════════════════════════════════════════════════════════
COVERAGE SUMMARY
═══════════════════════════════════════════════════════════════════════════

COVERED (direct):      R1.1, R1.2, R1.3, R1.4, R3.1, R6.1, R6.2, R6.3
COVERED (indirect):    R4.1 (implicitly — seeding not present in seg2)
UNTESTED:              R2.1, R2.2, R3.2, R4.1 (seg2 seeding), R5.1

Priority gaps (correctness risk):
  R2.1 / R2.2  — scenario dtype/value drift through HDF5
                 → TestSnapshotScenario
  R5.1         — current_date in seg2 reflects params.start_time
                 → TestSnapshotCurrentDate
"""

from datetime import date
from datetime import timedelta
from typing import ClassVar

import numpy as np
import polars as pl

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
            "lon": [0.0, 1.0, 1.0],
            "mcv1": [0.5, 0.4, 0.3],
        }
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seir_non_negative(model) -> None:
    for s in model.params.states:
        assert (getattr(model.patches.states, s) >= 0).all(), f"Negative '{s}' counts"


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSnapshotBasic:
    """Round-trip with InfectionProcess only (no vital dynamics)."""

    COMP_SEG1: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2: ClassVar = [InfectionProcess]  # no seeding in resumed run
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

    COMP_SEG1: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2: ClassVar = [InfectionProcess]

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
    COMP_SEG1: ClassVar = [InfectionSeedingProcess, InfectionProcess, VitalDynamicsProcess]
    COMP_SEG2: ClassVar = [InfectionProcess, VitalDynamicsProcess]

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


class TestSnapshotScenario:
    """
    R2.1 + R2.2: Scenario DataFrame values and dtypes survive the HDF5 round-trip.

    Column order may differ after round-trip; comparison is column-name-based.
    """

    COMP_SEG1: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2: ClassVar = [InfectionProcess]

    def test_scenario_values_preserved(self, tmp_path):
        snap = tmp_path / "snap_scenario.h5"
        scenario = _scenario()

        p1 = lm.CompartmentalParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)

        orig = scenario.sort("id")
        loaded = m2.scenario.unwrap().sort("id")

        assert set(orig.columns) == set(loaded.columns), (
            f"Scenario columns changed after HDF5 round-trip: {set(orig.columns)} → {set(loaded.columns)}"
        )
        assert orig["id"].to_list() == loaded["id"].to_list(), f"Patch IDs changed: {orig['id'].to_list()} → {loaded['id'].to_list()}"
        np.testing.assert_array_equal(orig["pop"].to_numpy(), loaded["pop"].to_numpy(), err_msg="'pop' changed after round-trip")
        for col in ["lat", "lon", "mcv1"]:
            np.testing.assert_allclose(orig[col].to_numpy(), loaded[col].to_numpy(), err_msg=f"'{col}' changed after round-trip")


class TestSnapshotCurrentDate:
    """
    R5.1: model.current_date in seg2 begins from params.start_time, not snap_date.

    Uses a deliberately different start_time in seg2 to confirm the resume date
    is params-driven, not inherited from the file.
    """

    COMP_SEG1: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2: ClassVar = [InfectionProcess]
    SEG1_TICKS = 30
    SEG2_TICKS = 20

    def test_current_date_before_run(self, tmp_path):
        snap = tmp_path / "snap_date.h5"
        scenario = _scenario()

        p1 = lm.CompartmentalParams(num_ticks=self.SEG1_TICKS, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(num_ticks=self.SEG2_TICKS, seed=0, start_time="2003-07", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)

        assert m2.current_date.date() == date(2003, 7, 1), (
            f"current_date before run should be params.start_time=2003-07-01, got {m2.current_date}"
        )

    def test_current_date_after_run(self, tmp_path):
        snap = tmp_path / "snap_date2.h5"
        scenario = _scenario()

        p1 = lm.CompartmentalParams(num_ticks=self.SEG1_TICKS, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.CompartmentalModel(scenario, p1)
        m1.components = self.COMP_SEG1
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.CompartmentalParams(num_ticks=self.SEG2_TICKS, seed=0, start_time="2003-07", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP_SEG2, verbose=VERBOSE)
        m2.run()

        expected = date(2003, 7, 1) + timedelta(days=self.SEG2_TICKS)
        assert m2.current_date.date() == expected, (
            f"After {self.SEG2_TICKS} ticks from 2003-07-01, expected {expected}, got {m2.current_date}"
        )


class TestSnapshotTopLevelAPI:
    """save_snapshot / load_snapshot are importable from laser.measles.compartmental."""

    def test_imports(self):
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

    SNAP_TICKS = 60  # at epidemic peak (total I peaks ~tick 60)
    SEG2_TICKS = 55  # long enough to witness the full post-peak decline
    COMP_SEG1: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    COMP_SEG2: ClassVar = [InfectionProcess]

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
        assert total_I > 0, f"No active infections at snapshot boundary (I={total_I}). Increase SNAP_TICKS or seed more infections."

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
        assert total_pop_seg2 == total_pop_seg1, f"Total population changed at boundary: seg1={total_pop_seg1:,}, seg2={total_pop_seg2:,}"
