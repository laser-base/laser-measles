"""Tests for the ResultsWriter component.

Coverage is grouped into sections below — keep new tests next to the
existing one that covers the closest concern rather than scattering
them across files.

  1. Basic end-to-end: writing, custom path, default path, opt-out.
  2. Per-tick dispatch contract: ResultsWriter must NOT land in
     ``model.phases`` even though it's a component.
  3. StateTracker discovery: explicit BaseStateTracker dependency,
     fail-fast at __init__, most-granular selection when multiple
     trackers are present.
  4. JSON schema: full per-group schema, global-only fallback,
     missing-state error path.
  5. Hierarchical IDs: ``aggregation_level=0`` vs ``=1`` semantics,
     top-level metadata for disambiguation, peak_tick naming.
  6. Robustness: attack rate stays in [0, 1] even when patches.states
     underflows (laser-measles #117), group_ids matches axis order for
     unsorted scenarios.
  7. finalize() hook coverage: the BaseLaserModel.run() hook that
     ResultsWriter depends on — kept here because ResultsWriter is its
     most prominent user.
"""

from __future__ import annotations

import json
from typing import ClassVar

import numpy as np
import polars as pl
import pytest

from laser.measles.abm import ABMModel
from laser.measles.abm import ABMParams
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import NoBirthsProcess
from laser.measles.abm.components import StateTracker
from laser.measles.base import BaseComponent
from laser.measles.biweekly import BiweeklyModel
from laser.measles.biweekly import BiweeklyParams
from laser.measles.biweekly.components import InfectionProcess as BWInfection
from laser.measles.biweekly.components import InitializeEquilibriumStatesProcess
from laser.measles.components import BaseStateTrackerParams
from laser.measles.components import ResultsWriter
from laser.measles.components import ResultsWriterParams
from laser.measles.components import create_component

# ── shared fixtures / helpers ────────────────────────────────────────────────

N_PATCHES = 5
TICKS = 90
N_PER_CLUSTER = 4
HIER_TICKS = 60


def _flat_scenario():
    """5 patches with flat IDs (patch_0..patch_4). Used by most tests."""
    return pl.DataFrame(
        {
            "id": [f"patch_{i}" for i in range(N_PATCHES)],
            "pop": [50_000, 80_000, 120_000, 60_000, 40_000],
            "lat": [0.0, 0.1, 0.2, 0.3, 0.4],
            "lon": [0.0, 0.0, 0.0, 0.0, 0.0],
            "mcv1": [0.0, 0.2, 0.4, 0.6, 0.8],
        }
    )


def _hierarchical_scenario(n_per_cluster: int = N_PER_CLUSTER) -> pl.DataFrame:
    """Two-cluster scenario with ``cluster_X:node_Y``-style hierarchical IDs."""
    ids: list[str] = []
    lats: list[float] = []
    lons: list[float] = []
    pops: list[int] = []
    for cluster_idx in range(2):
        for i in range(n_per_cluster):
            ids.append(f"cluster_{cluster_idx + 1}:node_{i + 1}")
            lats.append(40.0 + cluster_idx * 5.0 + i * 0.01)
            lons.append(5.0 + cluster_idx * 5.0 + i * 0.01)
            pops.append(50_000 + 1_000 * i)
    return pl.DataFrame(
        {
            "id": ids,
            "pop": pops,
            "lat": lats,
            "lon": lons,
            "mcv1": [0.0] * len(ids),
        }
    )


def _make_model(state_tracker_params=None, results_writer_params=None, add_writer=True):
    """Build a small ABM with seeding + infection, optionally a StateTracker,
    optionally a ResultsWriter. Use ``state_tracker_params=None`` to omit
    the tracker entirely (for the missing-tracker error-path test).
    """
    params = ABMParams(num_ticks=TICKS, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_flat_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    if state_tracker_params is not None:
        model.add_component(create_component(StateTracker, params=state_tracker_params))
    if add_writer:
        if results_writer_params is not None:
            model.add_component(create_component(ResultsWriter, params=results_writer_params))
        else:
            model.add_component(ResultsWriter)
    return model


def _run_hierarchical(state_tracker_params, out_path) -> dict:
    """Run a small ABM on the two-cluster hierarchical scenario with the
    given tracker config + ResultsWriter; return the parsed JSON."""
    params = ABMParams(num_ticks=HIER_TICKS, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_hierarchical_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=state_tracker_params))
    model.add_component(create_component(ResultsWriter, params=ResultsWriterParams(path=str(out_path))))
    model.run()
    return json.loads(out_path.read_text())


# ── 1. Basic end-to-end ──────────────────────────────────────────────────────


def test_writes_results_json_at_end_of_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model(state_tracker_params=BaseStateTrackerParams(aggregation_level=0))
    model.run()

    out = tmp_path / "results.json"
    assert out.exists(), "ResultsWriter should have written results.json in cwd"
    data = json.loads(out.read_text())
    assert data["model_type"] == "ABMModel"
    assert data["num_ticks"] == TICKS
    assert "summary" in data
    assert "peak_infectious_global" in data["summary"]


def test_honors_custom_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(aggregation_level=0),
        results_writer_params=ResultsWriterParams(path="custom_run.json"),
    )
    model.run()
    assert (tmp_path / "custom_run.json").exists()
    assert not (tmp_path / "results.json").exists(), "should NOT have written the default path when custom path is set"


def test_default_path_is_results_json_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model(state_tracker_params=BaseStateTrackerParams(aggregation_level=0))
    model.run()
    assert (tmp_path / "results.json").exists(), "default path 'results.json' should land in cwd"


def test_no_writer_means_no_results_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(aggregation_level=0),
        add_writer=False,
    )
    model.run()
    assert not (tmp_path / "results.json").exists(), "without ResultsWriter, no results.json should be written"


def test_path_resolves_relative_to_cwd(tmp_path, monkeypatch):
    """The laser-mcp parallel test runner relies on the writer resolving
    relative paths against cwd — per-attempt cwds isolate concurrent
    writes. If this ever starts resolving against model home or a
    package-relative location, concurrent prompts would clobber each
    other's results.json.
    """
    monkeypatch.chdir(tmp_path)

    params = ABMParams(num_ticks=HIER_TICKS, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_hierarchical_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=1)))
    model.add_component(ResultsWriter)  # default path = "results.json"
    model.run()

    target = tmp_path / "results.json"
    assert target.exists(), f"ResultsWriter should write its default path 'results.json' relative to cwd ({tmp_path})"


# ── 2. Per-tick dispatch contract ────────────────────────────────────────────


def test_not_in_per_tick_phases(tmp_path, monkeypatch):
    """ResultsWriter must NOT define __call__ — BaseLaserModel adds any
    component that has __call__ to ``self.phases``, which is the per-tick
    dispatch loop. A no-op __call__ would still get invoked every tick.
    Pin: in ``self.instances`` (so finalize() finds it) but stays out of
    ``self.phases``.
    """
    monkeypatch.chdir(tmp_path)
    model = _make_model(state_tracker_params=BaseStateTrackerParams(aggregation_level=0))

    in_instances = any(isinstance(i, ResultsWriter) for i in model.instances)
    in_phases = any(isinstance(p, ResultsWriter) for p in model.phases)

    assert in_instances, "ResultsWriter should be in model.instances for finalize() to reach it"
    assert not in_phases, "ResultsWriter must NOT be in model.phases — that's the per-tick loop"


# ── 3. StateTracker discovery ────────────────────────────────────────────────


def test_missing_state_tracker_raises_at_add_component_time(tmp_path):
    """ResultsWriter added with no StateTracker → fail fast at construction,
    NOT after a full run() completes."""
    with pytest.raises(RuntimeError, match="StateTracker"):
        _make_model(
            state_tracker_params=None,
            results_writer_params=ResultsWriterParams(path=str(tmp_path / "results.json")),
        )


def test_picks_most_granular_state_tracker(tmp_path, monkeypatch):
    """Hello-world pattern: a default global StateTracker plus a per-patch
    one. ResultsWriter must prefer the per-patch (highest aggregation_level)
    so the per_group arrays are populated instead of being silently null.
    """
    monkeypatch.chdir(tmp_path)
    params = ABMParams(num_ticks=TICKS, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_flat_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    model.add_component(StateTracker)  # default: aggregation_level=-1 (global)
    model.add_component(create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=0)))
    model.add_component(ResultsWriter)
    model.run()

    data = json.loads((tmp_path / "results.json").read_text())
    assert data["group_aggregation_level"] == 0, (
        "ResultsWriter should have picked the per-patch tracker (aggregation_level=0), "
        f"not the global one. Got group_aggregation_level={data['group_aggregation_level']}."
    )
    assert data["num_groups"] == N_PATCHES, f"expected per-patch ({N_PATCHES} groups), got {data['num_groups']}"
    assert data["summary"]["attack_rate_per_group"] is not None
    assert len(data["summary"]["attack_rate_per_group"]) == N_PATCHES


# ── 4. JSON schema ───────────────────────────────────────────────────────────


def test_per_patch_output_has_full_schema(tmp_path):
    out_path = tmp_path / "results.json"
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(aggregation_level=0),
        results_writer_params=ResultsWriterParams(path=str(out_path)),
    )
    model.run()
    on_disk = json.loads(out_path.read_text())

    for key in (
        "model_type",
        "num_ticks",
        "num_groups",
        "group_ids",
        "group_aggregation_level",
        "states",
        "summary",
    ):
        assert key in on_disk, f"missing top-level key {key!r}"

    assert on_disk["model_type"] == "ABMModel"
    assert on_disk["num_ticks"] == TICKS
    assert on_disk["num_groups"] == N_PATCHES
    assert on_disk["group_ids"] == [f"patch_{i}" for i in range(N_PATCHES)]
    assert on_disk["group_aggregation_level"] == 0
    assert {"S", "I", "R"}.issubset(set(on_disk["states"]))

    summary = on_disk["summary"]

    # Global scalars
    assert isinstance(summary["peak_infectious_global"], int)
    assert summary["peak_infectious_global"] > 0
    assert 0 <= summary["peak_tick"] < TICKS
    assert 0.0 <= summary["attack_rate_global"] <= 1.0

    # Per-group arrays
    assert summary["attack_rate_per_group"] is not None
    assert len(summary["attack_rate_per_group"]) == N_PATCHES
    assert all(0.0 <= r <= 1.0 for r in summary["attack_rate_per_group"])

    assert summary["peak_infectious_per_group"] is not None
    assert len(summary["peak_infectious_per_group"]) == N_PATCHES
    assert all(p >= 0 for p in summary["peak_infectious_per_group"])

    final = summary["final_state_per_group"]
    assert final is not None
    for state in ("S", "I", "R"):
        assert state in final, f"missing final state {state!r}"
        assert len(final[state]) == N_PATCHES

    final_global = summary["final_state_global"]
    assert final_global is not None
    for state in ("S", "I", "R"):
        assert state in final_global, f"missing global final state {state!r}"
        assert isinstance(final_global[state], int)
        assert final_global[state] == sum(final[state]), f"global {state}={final_global[state]} != sum(per-patch)={sum(final[state])}"


def test_global_only_tracker_emits_null_per_group_arrays(tmp_path):
    """Default aggregation_level=-1 → tracker sums over all patches → per-group
    arrays in the JSON are null, but global aggregates still populated."""
    out_path = tmp_path / "results.json"
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(),  # default
        results_writer_params=ResultsWriterParams(path=str(out_path)),
    )
    model.run()
    on_disk = json.loads(out_path.read_text())
    summary = on_disk["summary"]

    # Global aggregates still produced
    assert isinstance(summary["peak_infectious_global"], int)
    assert summary["peak_infectious_global"] > 0
    assert summary["attack_rate_global"] is not None

    final_global = summary["final_state_global"]
    assert final_global is not None
    for state in ("S", "I", "R"):
        assert state in final_global
        assert isinstance(final_global[state], int)
        assert final_global[state] >= 0

    # Per-group arrays explicitly null
    assert summary["attack_rate_per_group"] is None
    assert summary["peak_infectious_per_group"] is None
    assert summary["final_state_per_group"] is None

    # group_ids reflects the single aggregated group
    assert on_disk["group_ids"] == ["all_patches"]
    assert on_disk["group_aggregation_level"] == -1


# ── 5. Hierarchical IDs ──────────────────────────────────────────────────────


def test_aggregation_level_0_with_hierarchical_ids_rolls_up_to_clusters(tmp_path):
    """With ``aggregation_level=0`` and hierarchical IDs (``cluster_1:node_1``),
    the tracker rolls nodes up to one row per top-level segment.
    ResultsWriter then emits length-2 arrays under the correctly-named
    ``_per_group`` keys, with ``num_groups=2`` and
    ``group_aggregation_level=0`` so the consumer knows what they're
    holding.
    """
    n_clusters = 2
    out = _run_hierarchical(BaseStateTrackerParams(aggregation_level=0), tmp_path / "results.json")
    summary = out["summary"]

    assert out["num_groups"] == n_clusters
    assert out["group_aggregation_level"] == 0
    assert sorted(out["group_ids"]) == ["cluster_1", "cluster_2"]

    assert summary["attack_rate_per_group"] is not None
    assert len(summary["attack_rate_per_group"]) == n_clusters
    assert summary["peak_infectious_per_group"] is not None
    assert len(summary["peak_infectious_per_group"]) == n_clusters
    for state, vec in summary["final_state_per_group"].items():
        assert len(vec) == n_clusters, f"final_state_per_group[{state!r}] wrong length"


def test_aggregation_level_1_with_hierarchical_ids_is_true_per_patch(tmp_path):
    """When ``aggregation_level`` is set to the ID depth minus one, the
    tracker yields one row per scenario patch and ResultsWriter must
    produce per-group arrays of that exact length — which IS per-patch
    in this case.
    """
    n_patches = 2 * N_PER_CLUSTER
    out = _run_hierarchical(BaseStateTrackerParams(aggregation_level=1), tmp_path / "results.json")
    summary = out["summary"]

    assert out["num_groups"] == n_patches
    assert out["group_aggregation_level"] == 1
    assert sorted(out["group_ids"]) == sorted(f"cluster_{c}:node_{i + 1}" for c in (1, 2) for i in range(N_PER_CLUSTER))
    assert summary["attack_rate_per_group"] is not None
    assert len(summary["attack_rate_per_group"]) == n_patches
    assert summary["peak_infectious_per_group"] is not None
    assert len(summary["peak_infectious_per_group"]) == n_patches
    for state, vec in summary["final_state_per_group"].items():
        assert len(vec) == n_patches, f"final_state_per_group[{state!r}] wrong length"


def test_top_level_exposes_aggregation_level_for_disambiguation(tmp_path):
    """Consumers reading the JSON must be able to tell whether the
    ``_per_group`` arrays are at patch granularity or aggregated above.
    The top-level ``group_aggregation_level`` field carries that contract
    so readers can branch without re-deriving from the scenario.
    """
    out = _run_hierarchical(BaseStateTrackerParams(aggregation_level=0), tmp_path / "results.json")
    assert "group_aggregation_level" in out
    assert isinstance(out["group_aggregation_level"], int)
    assert out["group_aggregation_level"] == 0


def test_peak_tick_is_tick_index_in_biweekly_model(tmp_path):
    """``summary.peak_tick`` is named for what it is — the tick index of
    the global infectious peak — so consumers don't accidentally treat
    a biweekly tick (14 days) as a calendar day.
    """
    out_path = tmp_path / "results.json"
    scenario = pl.DataFrame(
        {
            "id": [f"patch_{i}" for i in range(3)],
            "pop": [10_000, 20_000, 15_000],
            "lat": [0.0, 0.1, 0.2],
            "lon": [0.0, 0.0, 0.0],
            "mcv1": [0.0, 0.0, 0.0],
        }
    )
    params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = BiweeklyModel(scenario, params)
    model.components = [
        InitializeEquilibriumStatesProcess,
        BWInfection,
        create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=0)),
        create_component(ResultsWriter, params=ResultsWriterParams(path=str(out_path))),
    ]
    model.run()
    out = json.loads(out_path.read_text())
    summary = out["summary"]

    assert "peak_tick" in summary
    assert "peak_day" not in summary, "peak_day was renamed to peak_tick to avoid implying calendar days."
    assert 0 <= summary["peak_tick"] < params.num_ticks


# ── 6. Robustness ────────────────────────────────────────────────────────────


def test_attack_rate_stays_in_unit_interval_even_with_corrupted_R(tmp_path):
    """Regression for laser-mcp prompt p07: when ``patches.states`` counters
    underflow (a known family of bugs; see laser-measles issue #117 —
    uint32 wraparound when any state-to-state transition decrements past
    zero without a ``min(delta, available)`` clamp), the StateTracker
    faithfully records the corrupted values and ``_per_group`` arrays end
    up with ≈ 2³² magnitude entries. ``attack_rate_per_group`` MUST still
    land in [0, 1] because the S-only formula bypasses the corrupted
    E/I/R channels and clamps the result.

    Force the corruption directly by writing pathological values into the
    tracker after the model runs — the fix lives in ``_build()``'s formula,
    not in the framework's state-conservation code, so this test pins the
    contract independently of whether #117 is resolved.
    """
    out_path = tmp_path / "results.json"
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(aggregation_level=0),
        results_writer_params=ResultsWriterParams(path=str(out_path)),
        add_writer=False,  # add it after corrupting the tracker
    )
    model.run()

    # Reach into the tracker and force-set patch 1 to look like a migration
    # casualty: R well above initial pop, E/I at uint32-overflow levels.
    state_names = list(model.params.states)
    tracker = next(i for i in model.instances if hasattr(i, "state_tracker"))
    arr = np.asarray(tracker.state_tracker)
    i_state = state_names.index("I")
    e_state = state_names.index("E") if "E" in state_names else None
    r_state = state_names.index("R")
    if e_state is not None:
        arr[e_state, -1, 1] = 4_294_966_457
    arr[i_state, -1, 1] = 4_294_967_082
    arr[r_state, -1, 1] = 51_053  # above patch 1's initial pop (50K)

    writer = ResultsWriter(model, params=ResultsWriterParams(path=str(out_path)))
    writer.finalize(model)

    on_disk = json.loads(out_path.read_text())
    rates = on_disk["summary"]["attack_rate_per_group"]
    assert rates is not None
    assert len(rates) == N_PATCHES
    for r in rates:
        assert 0.0 <= r <= 1.0, f"attack rate {r} out of [0, 1]"
    assert 0.0 <= on_disk["summary"]["attack_rate_global"] <= 1.0


def test_group_ids_match_axis_order_for_unsorted_scenario(tmp_path):
    """End-to-end check that ``group_ids[i]`` corresponds to
    ``state_tracker[..., i]`` for scenarios whose IDs aren't already in
    sorted order. The BaseStateTracker contract (group_ids = insertion
    order) is what makes this work; the test pins it via the JSON.

    The patch with the highest initial pop (banana, 200K) should also
    have the largest peak_infectious_per_group entry, AND the JSON's
    group_ids should match the scenario row order.
    """
    out_path = tmp_path / "results.json"

    scenario = pl.DataFrame(
        {
            "id": ["banana", "apple", "cherry"],  # NOT sorted
            "pop": [200_000, 50_000, 80_000],
            "lat": [0.0, 0.1, 0.2],
            "lon": [0.0, 0.0, 0.0],
            "mcv1": [0.0, 0.0, 0.0],
        }
    )
    params = ABMParams(num_ticks=60, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(scenario, params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=0)))
    model.add_component(create_component(ResultsWriter, params=ResultsWriterParams(path=str(out_path))))
    model.run()

    out = json.loads(out_path.read_text())
    assert out["group_ids"] == ["banana", "apple", "cherry"], (
        f"group_ids should reflect scenario row order, not sorted; got {out['group_ids']}"
    )

    # Sanity: per-group arrays line up with group_ids. Banana (200K pop)
    # should have a strictly larger peak than apple (50K).
    peaks = out["summary"]["peak_infectious_per_group"]
    assert peaks[0] > peaks[1], (
        f"index 0 should be banana (largest pop), but peak[0]={peaks[0]} < peak[1]={peaks[1]} — labels and axis are out of sync"
    )


# ── 7. finalize() hook coverage ──────────────────────────────────────────────


class _RecordsFinalize(BaseComponent):
    """Tiny component that records calls to finalize for the hook tests."""

    calls: ClassVar[list[str]] = []

    def __init__(self, model, params=None):
        super().__init__(model)
        self.name = "RecordsFinalize"

    def __call__(self, model, tick):
        pass

    def finalize(self, model):
        _RecordsFinalize.calls.append("finalize")


class _NoFinalize(BaseComponent):
    """Component without a finalize() method — should be silently skipped."""

    def __init__(self, model, params=None):
        super().__init__(model)
        self.name = "NoFinalize"

    def __call__(self, model, tick):
        pass


def _make_hook_model(extras):
    """Model variant for finalize-hook tests: standard SEIR setup plus a
    StateTracker (so any included ResultsWriter passes its init check)
    plus whatever extra components the test wants to wire in."""
    params = ABMParams(num_ticks=60, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_flat_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=15)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=0)))
    for c in extras:
        model.add_component(c)
    return model


def test_finalize_hook_called_once_for_components_that_define_it():
    _RecordsFinalize.calls = []
    model = _make_hook_model([_NoFinalize, _RecordsFinalize])
    model.run()
    assert _RecordsFinalize.calls == ["finalize"], f"expected exactly one finalize() call, got {_RecordsFinalize.calls}"


def test_finalize_hook_skips_components_without_finalize():
    # Runs to completion; the assertion is "no exception raised".
    model = _make_hook_model([_NoFinalize])
    model.run()  # would AttributeError if the hook didn't gate on callable()


def test_finalize_hook_propagates_exceptions():
    class _BoomFinalize(BaseComponent):
        def __init__(self, model, params=None):
            super().__init__(model)
            self.name = "BoomFinalize"

        def __call__(self, model, tick):
            pass

        def finalize(self, model):
            raise RuntimeError("intentional finalize failure")

    model = _make_hook_model([_BoomFinalize])
    with pytest.raises(RuntimeError, match="intentional finalize failure"):
        model.run()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
