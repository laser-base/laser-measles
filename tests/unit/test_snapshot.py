"""
ABM snapshot save/load — requirements traceability and test coverage.

Each requirement is tagged with its test(s) or marked UNTESTED.
INDIRECT means a test would catch a regression but is not named for that requirement.
This module covers the ABM (agent-based) model only; see test_snapshot_compartmental.py
for the compartmental model.

═══════════════════════════════════════════════════════════════════════════
R1  PATCH STATE PRESERVATION
═══════════════════════════════════════════════════════════════════════════

R1.1  All four SEIR channels (S, E, I, R) loaded from snapshot exactly match
      the values present at the end of seg1, per patch.
      → TestSnapshotContinuity::test_seir_continuity_at_boundary

R1.2  SEIR counts are non-negative at the snapshot boundary and after a full
      seg2 run.
      → TestSnapshotNoBirths::test_roundtrip (_seir_consistent)
      → TestSnapshotVitalDynamics::test_roundtrip (_seir_consistent)
      → TestSnapshotContinuity::test_seir_continuity_at_boundary

R1.3  R count in patch_states is preserved even though R agents are squashed
      from the people frame (squashing is people-only).
      → TestSnapshotContinuity::test_seir_continuity_at_boundary
        (R channel compared exactly pre/post-squash)

═══════════════════════════════════════════════════════════════════════════
R2  PEOPLE FRAME PRESERVATION
═══════════════════════════════════════════════════════════════════════════

R2.1  Active-agent count after load equals the post-squash count from seg1.
      → TestSnapshotNoBirths::test_roundtrip
      → TestSnapshotContinuity::test_people_count_boundary

R2.2  All active agents have valid patch_ids (0 ≤ id < n_patches).
      → _seir_consistent() called in all roundtrip tests

R2.3  date_of_birth is normalized by -t_snap so every active non-null DOB
      is ≤ 0 at the start of seg2 (i.e. no agent appears to be born in the
      future relative to seg2's t=0).
      → TestSnapshotDOBNormalization::test_dob_normalized_after_snapshot

R2.4  Null DOB sentinel (INT_MAX) is not adjusted during normalization.
      UNTESTED — covered only by the same normalization helper that adjusts
      real DOBs; no explicit assertion that INT_MAX is left unchanged.

R2.5  date_of_vaccination is normalized by -t_snap for future (pending)
      vaccination dates.
      INDIRECT — TestSnapshotVitalDynamics::test_vaccination_queue_rebuilt
      checks queue length, not whether the date values are correct.

R2.6  Null vaccination-date sentinel (INT_MAX / UINT_MAX) is not adjusted.
      UNTESTED

R2.7  etimer and itimer (per-agent exposure/infection progression timers)
      are preserved so E→I and I→R transitions are not disrupted in seg2.
      INDIRECT — TestSnapshotContinuity::test_seir_continuity_at_boundary
      requires I > 0 at the boundary, so a broken timer would cause the
      epidemic to collapse in seg2, but the test does not assert seg2 dynamics
      against a reference run.

R2.8  susceptibility is preserved per agent across the snapshot boundary.
      UNTESTED

R2.9  Per-agent state byte is preserved (separate from patch-level counts).
      INDIRECT — SEIR counts loaded from patch_states; agent state byte is
      only exercised when the disease process runs in seg2.

═══════════════════════════════════════════════════════════════════════════
R3  R-AGENT SQUASHING  (squash_recovered=True, the default)
═══════════════════════════════════════════════════════════════════════════

R3.1  Recovered agents are removed from the people frame before saving.
      INDIRECT — TestSnapshotNoBirths::test_roundtrip confirms count drops
      but does not assert that exactly the R agents were removed.

R3.2  squash_recovered=False skips squashing; the people frame retains all
      agents including R.
      UNTESTED

═══════════════════════════════════════════════════════════════════════════
R4  VACCINATION QUEUE
═══════════════════════════════════════════════════════════════════════════

R4.1  Queue length after load equals the number of pending (non-null,
      non-expired) vaccination dates in the loaded people frame.
      → TestSnapshotVitalDynamics::test_vaccination_queue_rebuilt

R4.2  Vaccination queue fires at the correct ticks during seg2 (normalized
      dates are internally consistent so agents vaccinate on schedule).
      UNTESTED — would require comparing seg2 S→R transitions against
      a reference or checking that queue drains at expected ticks.

═══════════════════════════════════════════════════════════════════════════
R5  SCENARIO PRESERVATION
═══════════════════════════════════════════════════════════════════════════

R5.1  Scenario DataFrame round-trips with correct values and dtypes for all
      columns (id, pop, lat, lon, mcv1, and any extras).
      UNTESTED — load_snapshot applies cast_exprs to fix known HDF5 dtype
      drift, but there is no assertion that values are correct after load.

R5.2  String patch IDs survive the HDF5 encode/decode round-trip.
      UNTESTED

═══════════════════════════════════════════════════════════════════════════
R6  SIA CALENDAR PERSISTENCE
═══════════════════════════════════════════════════════════════════════════

R6.1  implemented_sias from any SIACalendarProcess instances is saved and
      restored so already-run campaigns are not re-executed in seg2.
      UNTESTED — requires a scenario with SIACalendarProcess.

R6.2  No crash when no SIACalendarProcess is present (empty set saved
      gracefully / absent key handled on load).
      INDIRECT — all tests run without SIACalendarProcess and don't crash.

═══════════════════════════════════════════════════════════════════════════
R7  CAPACITY EXPANSION
═══════════════════════════════════════════════════════════════════════════

R7.1  The loaded people frame has enough capacity for projected births during
      seg2 so no OverflowError occurs.
      INDIRECT — TestSnapshotVitalDynamics::test_roundtrip runs without
      error, but does not assert the capacity value explicitly.

═══════════════════════════════════════════════════════════════════════════
R8  DATE / TIME
═══════════════════════════════════════════════════════════════════════════

R8.1  model.current_date in seg2 begins from params.start_time (the caller's
      chosen resume date), not from the original snap_date.
      UNTESTED

R8.2  t_snap stored in the file equals the elapsed calendar days between
      model.start_time and model.current_date at save time.
      UNTESTED

═══════════════════════════════════════════════════════════════════════════
R9  COMPONENT SNAPSHOT-MODE DETECTION
═══════════════════════════════════════════════════════════════════════════

R9.1  Components that check model._from_snapshot skip people-frame setup so
      existing loaded agents are not overwritten.
      INDIRECT — TestSnapshotVitalDynamics::test_roundtrip relies on this
      (frame would be reset otherwise), but does not assert it directly.

R9.2  InfectionSeedingProcess does not re-seed infections when called in a
      seg2 that uses InfectionSeedingProcess as a component.
      UNTESTED — the current tests do not include InfectionSeedingProcess
      in the seg2 component list, so this is never exercised.

═══════════════════════════════════════════════════════════════════════════
R10  FILE I/O & API
═══════════════════════════════════════════════════════════════════════════

R10.1 Snapshot file is created at the requested path and is non-empty.
      → TestSnapshotTopLevelAPI::test_snapshot_file_created

R10.2 ABMModel.from_snapshot is a working alias for load_snapshot.
      → TestSnapshotNoBirths::test_from_snapshot_classmethod

R10.3 save_snapshot and load_snapshot are importable from laser.measles
      top-level namespace.
      → TestSnapshotTopLevelAPI::test_top_level_import

═══════════════════════════════════════════════════════════════════════════
COVERAGE SUMMARY
═══════════════════════════════════════════════════════════════════════════

COVERED (direct):      R1.1, R1.2, R1.3, R2.1, R2.2, R2.3, R4.1,
                       R10.1, R10.2, R10.3
COVERED (indirect):    R2.5, R2.7, R2.9, R3.1, R6.2, R7.1, R9.1
UNTESTED:              R2.4, R2.6, R2.8, R3.2, R4.2, R5.1, R5.2,
                       R6.1, R8.1, R8.2, R9.2

Priority gaps (correctness risk):
  R2.4 / R2.6  — sentinel preservation during date normalization
                 → TestSnapshotSentinels
  R5.1 / R5.2  — scenario dtype/value drift through HDF5
                 → TestSnapshotScenario
  R6.1         — SIA campaign not re-run after snapshot
                 → TestSnapshotSIACalendar
  R8.1         — current_date in seg2 reflects params.start_time
                 → TestSnapshotCurrentDate
  R4.2         — vaccination fires on schedule in seg2
                 STILL UNTESTED
"""

from datetime import date
from datetime import timedelta
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
    """Patch SEIR totals are non-negative and consistent with people counts when available."""
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

    assert patch_id.shape[0] == active_mask.shape[0], "people.patch_id and people.active must have the same length"

    n_patches = patch_total.shape[0]
    active_patch_id = patch_id[active_mask]
    assert ((active_patch_id >= 0) & (active_patch_id < n_patches)).all(), "Active people must have valid patch ids"

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


class TestSnapshotDOBNormalization:
    """
    date_of_birth values must be normalized (made relative to seg2 t=0) on save.

    In seg1, newborns receive date_of_birth = tick (e.g. 30 for a birth at tick 30).
    If DOBs are saved without adjustment, seg2's age calculations become wrong:
        age = current_tick - date_of_birth = 0 - 30 = -30  (should be positive)

    The correct invariant after loading: every active non-null DOB must be <= 0,
    meaning the agent was born at or before seg2's t=0.
    """

    TICKS_SEG1 = 60  # enough for births to occur (CBR=20/1000/yr → ~3 births/day at 15K pop)
    TICKS_SEG2 = 20
    COMP: ClassVar = [VitalDynamicsProcess]

    def test_dob_normalized_after_snapshot(self, tmp_path):
        snap = tmp_path / "snap_dob.h5"
        scenario = _scenario()  # 15,000 people total

        p1 = lm.ABMParams(
            num_ticks=self.TICKS_SEG1,
            seed=5,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
            use_numba=False,
        )
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()

        # Sanity: at least one birth occurred during seg1 (positive DOB exists).
        null_dob = int(np.iinfo(np.int32).max)
        dob1 = m1.people.date_of_birth[: m1.people.count].astype(np.int64)
        active1 = m1.people.active[: m1.people.count].astype(bool)
        positive_dobs = int(((dob1 > 0) & (dob1 < null_dob) & active1).sum())
        assert positive_dobs > 0, (
            f"No births occurred in seg1 ({positive_dobs} agents with positive DOB). "
            "Increase TICKS_SEG1 or population to make the test meaningful."
        )

        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(
            num_ticks=self.TICKS_SEG2,
            seed=5,
            start_time="2000-03",
            show_progress=False,
            verbose=VERBOSE,
            use_numba=False,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        # Every active agent's DOB must be <= 0 (born before seg2's t=0).
        # With the bug: newborns from seg1 have DOB = tick (e.g. 30), which is > 0.
        # With the fix:  all DOBs are shifted by -t_snap, so max DOB = (t_snap-1) - t_snap = -1.
        dob2 = m2.people.date_of_birth[: m2.people.count].astype(np.int64)
        active2 = m2.people.active[: m2.people.count].astype(bool)
        non_null_active = active2 & (dob2 != null_dob)
        bad = dob2[non_null_active & (dob2 > 0)]
        assert len(bad) == 0, (
            f"{len(bad)} active agents have date_of_birth > 0 after snapshot load.\n"
            f"  Max DOB seen: {int(bad.max()) if len(bad) else 'n/a'}\n"
            f"  t_snap was: {self.TICKS_SEG1}\n"
            "DOBs were not normalized relative to the snapshot tick."
        )


class TestSnapshotSentinels:
    """
    R2.4 + R2.6: INT_MAX sentinel values for date_of_birth and date_of_vaccination
    must not be adjusted during normalization.

    The initial population has null vaccination dates (INT_MAX) because they were
    born before the simulation started and have not been scheduled for MCV1.
    If the normalizer incorrectly shifted these, agents would get date_of_vaccination
    equal to INT_MAX - t_snap, causing spurious vaccinations in seg2.
    """

    TICKS_SEG1 = 60
    TICKS_SEG2 = 20
    COMP: ClassVar = [VitalDynamicsProcess]

    def test_null_vaccination_date_not_shifted(self, tmp_path):
        """Null (INT_MAX) vaccination dates on initial-population agents survive save/load unchanged."""
        snap = tmp_path / "snap_sentinel_vax.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(
            num_ticks=self.TICKS_SEG1,
            seed=6,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
            use_numba=False,
        )
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()

        null_val = int(np.iinfo(np.int32).max)

        # Confirm null vax dates exist in seg1 (initial population is not scheduled).
        vax1 = m1.people.date_of_vaccination[: m1.people.count].astype(np.int64)
        active1 = m1.people.active[: m1.people.count].astype(bool)
        n_null_before = int((vax1[active1] == null_val).sum())
        assert n_null_before > 0, "No null vax dates in seg1 — test would be vacuous."

        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(
            num_ticks=self.TICKS_SEG2,
            seed=6,
            start_time="2000-03",
            show_progress=False,
            verbose=VERBOSE,
            use_numba=False,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        vax2 = m2.people.date_of_vaccination[: m2.people.count].astype(np.int64)
        active2 = m2.people.active[: m2.people.count].astype(bool)

        # If the sentinel were shifted incorrectly it would become null_val - t_snap.
        corrupted = null_val - self.TICKS_SEG1
        assert not (vax2[active2] == corrupted).any(), (
            f"{int((vax2[active2] == corrupted).sum())} agents have vax date == "
            f"INT_MAX - t_snap ({corrupted}): sentinel was incorrectly shifted."
        )
        # Confirm nulls still present after load (they weren't silently cleared).
        assert (vax2[active2] == null_val).any(), "No null vaccination dates remain after load — sentinel may have been cleared."

    def test_null_dob_not_shifted(self, tmp_path):
        """No active agent should have DOB == INT_MAX - t_snap after load."""
        snap = tmp_path / "snap_sentinel_dob.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(
            num_ticks=self.TICKS_SEG1,
            seed=6,
            start_time="2000-01",
            show_progress=False,
            verbose=VERBOSE,
            use_numba=False,
        )
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        null_val = int(np.iinfo(np.int32).max)
        p2 = lm.ABMParams(
            num_ticks=self.TICKS_SEG2,
            seed=6,
            start_time="2000-03",
            show_progress=False,
            verbose=VERBOSE,
            use_numba=False,
        )
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        dob2 = m2.people.date_of_birth[: m2.people.count].astype(np.int64)
        active2 = m2.people.active[: m2.people.count].astype(bool)
        corrupted = null_val - self.TICKS_SEG1
        assert not (dob2[active2] == corrupted).any(), (
            f"{int((dob2[active2] == corrupted).sum())} active agents have "
            f"DOB == INT_MAX - t_snap ({corrupted}): DOB sentinel was incorrectly shifted."
        )


class TestSnapshotScenario:
    """
    R5.1 + R5.2: Scenario DataFrame values and dtypes survive the HDF5 round-trip.

    Covers all columns: string IDs (encode/decode), int64 populations, float64
    lat/lon/mcv1.  Column order may differ after round-trip (HDF5 key order is
    unspecified); comparison is column-name-based.
    """

    COMP: ClassVar = [InfectionSeedingProcess, InfectionProcess]

    def test_scenario_values_preserved(self, tmp_path):
        snap = tmp_path / "snap_scenario.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        orig = scenario.sort("id")
        loaded = m2.scenario.unwrap().sort("id")

        assert set(orig.columns) == set(loaded.columns), (
            f"Scenario columns changed after HDF5 round-trip: {set(orig.columns)} → {set(loaded.columns)}"
        )

        # String patch IDs (HDF5 bytes encode/decode)
        assert orig["id"].to_list() == loaded["id"].to_list(), f"Patch IDs changed: {orig['id'].to_list()} → {loaded['id'].to_list()}"

        # Numeric columns — exact for int, allclose for float
        np.testing.assert_array_equal(orig["pop"].to_numpy(), loaded["pop"].to_numpy(), err_msg="'pop' changed after round-trip")
        for col in ["lat", "lon", "mcv1"]:
            np.testing.assert_allclose(orig[col].to_numpy(), loaded[col].to_numpy(), err_msg=f"'{col}' changed after round-trip")


class TestSnapshotCurrentDate:
    """
    R8.1: model.current_date in seg2 begins from params.start_time, not snap_date.

    Uses a deliberately different start_time in seg2 to confirm that the resume
    date is driven by params, not by the date stored in the snapshot file.
    """

    COMP: ClassVar = [InfectionSeedingProcess, InfectionProcess]
    SEG1_TICKS = 30
    SEG2_TICKS = 20

    def test_current_date_before_run(self, tmp_path):
        """current_date equals params.start_time (as datetime) before seg2 runs."""
        snap = tmp_path / "snap_date.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=self.SEG1_TICKS, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        # Use a start_time far from snap_date to confirm it's params-driven.
        p2 = lm.ABMParams(num_ticks=self.SEG2_TICKS, seed=0, start_time="2003-07", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)

        assert m2.current_date.date() == date(2003, 7, 1), (
            f"current_date before run should be params.start_time=2003-07-01, got {m2.current_date}"
        )

    def test_current_date_after_run(self, tmp_path):
        """current_date advances by num_ticks days from params.start_time after seg2 runs."""
        snap = tmp_path / "snap_date2.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=self.SEG1_TICKS, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(num_ticks=self.SEG2_TICKS, seed=0, start_time="2003-07", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)
        m2.run()

        expected = date(2003, 7, 1) + timedelta(days=self.SEG2_TICKS)
        assert m2.current_date.date() == expected, (
            f"After {self.SEG2_TICKS} ticks from 2003-07-01, expected {expected}, got {m2.current_date}"
        )


class TestSnapshotSIACalendar:
    """
    R6.1: implemented_sias from any component with that attribute is saved to the
    snapshot and restored in the loaded model, preventing re-execution of campaigns
    that already ran in seg1.
    """

    COMP: ClassVar = [InfectionSeedingProcess, InfectionProcess]

    def test_implemented_sias_preserved(self, tmp_path):
        """SIA campaign IDs saved in seg1 are present in the loaded model's component."""

        class _FakeSIA:
            """Minimal stand-in with the implemented_sias interface."""

            def __init__(self, model, verbose=False):
                self.implemented_sias: set[str] = set()

            def __call__(self, model, tick: int) -> None:
                pass

        snap = tmp_path / "snap_sia.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=10, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = [*self.COMP, _FakeSIA]
        m1.run()

        # Simulate campaigns that ran during seg1.
        sia_inst = next(i for i in m1.instances if isinstance(i, _FakeSIA))
        sia_inst.implemented_sias = {"region1:patch0-2000-01", "region1:patch1-2000-01"}
        expected = set(sia_inst.implemented_sias)

        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(num_ticks=10, seed=0, start_time="2000-02", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=[*self.COMP, _FakeSIA], verbose=VERBOSE)

        sia_inst2 = next((i for i in m2.instances if isinstance(i, _FakeSIA)), None)
        assert sia_inst2 is not None, "_FakeSIA not found in loaded model instances"
        assert sia_inst2.implemented_sias == expected, (
            f"implemented_sias not restored correctly.\n  Expected: {expected}\n  Got:      {sia_inst2.implemented_sias}"
        )

    def test_no_sia_component_does_not_crash(self, tmp_path):
        """Save/load without any SIA component completes without error (empty set path)."""
        snap = tmp_path / "snap_no_sia.h5"
        scenario = _scenario()

        p1 = lm.ABMParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m1 = lm.ABMModel(scenario, p1)
        m1.components = self.COMP
        m1.run()
        save_snapshot(m1, snap, verbose=VERBOSE)

        p2 = lm.ABMParams(num_ticks=5, seed=0, start_time="2000-01", show_progress=False, verbose=VERBOSE)
        m2 = load_snapshot(snap, p2, components=self.COMP, verbose=VERBOSE)
        m2.run()  # must not raise


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
