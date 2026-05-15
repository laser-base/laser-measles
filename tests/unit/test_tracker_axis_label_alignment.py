"""Regression tests for the axis-vs-label contract in BaseStateTracker and
BaseCaseSurveillance.

Both base classes store per-tick data in an array whose last axis is filled
in the insertion order of ``self.node_mapping.items()`` (dict insertion
order). Previously both also set ``self.group_ids = sorted(node_mapping.keys())``,
which silently misaligned the label list with the storage axis whenever the
scenario IDs weren't already in sorted order. Consumers that read both
together — including ``BaseStateTracker.get_dataframe()``,
``BaseCaseSurveillance.get_dataframe()``, and ``ResultsWriter._build()`` —
would attribute counts to the wrong patch.

These tests use scenarios whose ID order differs from the alphabetically-
sorted order, so they fail on the pre-fix code (sorted group_ids) and
pass with the fix (group_ids = insertion order). The pop is deliberately
imbalanced so we can detect misalignment by comparing reported counts to
the patch's known initial population.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from laser.measles.abm import ABMModel
from laser.measles.abm import ABMParams
from laser.measles.abm.components import CaseSurveillanceParams
from laser.measles.abm.components import CaseSurveillanceTracker
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import NoBirthsProcess
from laser.measles.abm.components import StateTracker
from laser.measles.components import BaseStateTrackerParams
from laser.measles.components import create_component


def _unsorted_scenario() -> pl.DataFrame:
    """IDs chosen so insertion order (banana, apple, cherry) differs
    from sorted order (apple, banana, cherry). Pops are imbalanced so
    that a label-axis mismatch produces an unambiguous wrong answer.
    """
    return pl.DataFrame(
        {
            "id": ["banana", "apple", "cherry"],
            "pop": [200_000, 50_000, 80_000],
            "lat": [0.0, 0.1, 0.2],
            "lon": [0.0, 0.0, 0.0],
            "mcv1": [0.0, 0.0, 0.0],
        }
    )


def _build_and_run(tracker_params):
    params = ABMParams(num_ticks=30, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_unsorted_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=tracker_params))
    model.run()
    return model


def test_state_tracker_group_ids_match_node_mapping_insertion_order():
    """``StateTracker.group_ids`` must follow the insertion order of
    ``node_mapping`` so ``state_tracker[..., i]`` always corresponds to
    ``group_ids[i]``. Pre-fix this returned sorted order.
    """
    model = _build_and_run(BaseStateTrackerParams(aggregation_level=0))
    tracker = model.get_instance("StateTracker")[0]

    insertion = list(tracker.node_mapping.keys())
    assert tracker.group_ids == insertion, (
        f"group_ids should equal node_mapping insertion order; got {tracker.group_ids!r} vs insertion {insertion!r}"
    )


def test_state_tracker_initial_count_matches_scenario_pop_at_correct_index():
    """For a scenario with imbalanced pops, the patch labeled 'banana'
    (pop=200K) must have the largest initial S count, and that count
    must appear at the array index that ``group_ids`` says is 'banana'.

    Pre-fix: group_ids[0] == 'apple' (sorted), but state_tracker[:, 0, 0]
    sums the BANANA nodes (insertion order). So index 0 would have
    pop=200K but the label would say 'apple'.
    """
    model = _build_and_run(BaseStateTrackerParams(aggregation_level=0))
    tracker = model.get_instance("StateTracker")[0]

    state_names = list(model.params.states)
    s_idx = state_names.index("S")

    # Initial S count for each axis slot at tick 0
    initial_S_by_axis = np.asarray(tracker.state_tracker[s_idx, 0, :])

    # Pre-fix sorted order would have put apple (50K) at index 0; with the
    # fix, banana (200K) is at index 0. Expected pops by axis position when
    # aligned with insertion order: banana=200K, apple=50K, cherry=80K —
    # minus the seeded infections distributed across patches by infectious
    # weighting, so we check the LABEL match rather than exact counts.
    banana_idx = tracker.group_ids.index("banana")
    apple_idx = tracker.group_ids.index("apple")
    cherry_idx = tracker.group_ids.index("cherry")

    assert initial_S_by_axis[banana_idx] > initial_S_by_axis[cherry_idx] > initial_S_by_axis[apple_idx], (
        f"axis-vs-label mismatch: "
        f"banana@{banana_idx}={initial_S_by_axis[banana_idx]}, "
        f"cherry@{cherry_idx}={initial_S_by_axis[cherry_idx]}, "
        f"apple@{apple_idx}={initial_S_by_axis[apple_idx]} — "
        f"expected pop-ordered descending (200K, 80K, 50K)."
    )


def test_state_tracker_get_dataframe_assigns_counts_to_correct_patch():
    """``BaseStateTracker.get_dataframe()`` iterates ``self.group_ids``
    while indexing ``state_tracker[..., group_idx]`` by the same index.
    For an unsorted scenario, pre-fix this attributes patch X's counts
    to patch Y's label. Verify with an imbalanced pop: the 'banana'
    patch must have the largest tick-0 S row in the DataFrame.
    """
    model = _build_and_run(BaseStateTrackerParams(aggregation_level=0))
    tracker = model.get_instance("StateTracker")[0]

    df = tracker.get_dataframe()
    s_at_t0 = df.filter((pl.col("tick") == 0) & (pl.col("state") == "S"))
    counts_by_patch = {row["patch_id"]: row["count"] for row in s_at_t0.iter_rows(named=True)}

    assert counts_by_patch["banana"] > counts_by_patch["cherry"] > counts_by_patch["apple"], (
        f"get_dataframe attributed counts to wrong patches: {counts_by_patch} — "
        f"expected banana > cherry > apple (matching pops 200K, 80K, 50K)."
    )


def test_case_surveillance_group_ids_match_node_mapping_insertion_order():
    """Same axis-vs-label contract as BaseStateTracker, but for
    BaseCaseSurveillance. We don't need a full surveillance run — just
    verify that after init, group_ids order matches node_mapping
    insertion order.
    """
    params = ABMParams(num_ticks=10, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_unsorted_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(CaseSurveillanceTracker, params=CaseSurveillanceParams(aggregation_level=0)))
    # Don't need to run — init populates node_mapping and group_ids.

    surv = model.get_instance("CaseSurveillanceTracker")[0]
    insertion = list(surv.node_mapping.keys())
    assert surv.group_ids == insertion, (
        f"CaseSurveillance.group_ids should equal node_mapping insertion order; got {surv.group_ids!r} vs insertion {insertion!r}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
