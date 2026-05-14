"""Tests for the ResultsWriter component's JSON output schema.

Coverage:
- Per-group tracker (aggregation_level=0 with flat IDs → per-patch): full
  schema with non-null _per_group arrays in the right shape, correct
  group_ids order, group_aggregation_level present, summary scalars sane.
- Global-only tracker (default aggregation_level=-1): _per_group arrays
  are None; global aggregates still populated.
- No StateTracker attached: finalize() raises a clear RuntimeError.
- Default path (results.json) lands in cwd.

ResultsWriter owns both the dict-building logic and the file write. The
internal ``_build()`` helper is exercised here through the public
end-of-run path (``model.run()`` triggers ``finalize()`` which calls
``_build()`` then writes), so we read the resulting file back to assert
the schema.
"""

import json

import polars as pl
import pytest

from laser.measles.abm import ABMModel
from laser.measles.abm import ABMParams
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import NoBirthsProcess
from laser.measles.abm.components import StateTracker
from laser.measles.components import BaseStateTrackerParams
from laser.measles.components import ResultsWriter
from laser.measles.components import ResultsWriterParams
from laser.measles.components import create_component

N_PATCHES = 5
TICKS = 90


def _scenario():
    return pl.DataFrame(
        {
            "id": [f"patch_{i}" for i in range(N_PATCHES)],
            "pop": [50_000, 80_000, 120_000, 60_000, 40_000],
            "lat": [0.0, 0.1, 0.2, 0.3, 0.4],
            "lon": [0.0, 0.0, 0.0, 0.0, 0.0],
            "mcv1": [0.0, 0.2, 0.4, 0.6, 0.8],
        }
    )


def _make_model(state_tracker_params=None, results_writer_params=None, add_writer=True):
    """Build an ABM with the seeding + infection + (optional) tracker + writer.

    Set ``add_writer=False`` when a test wants to assert the
    no-writer-no-output path. Set ``state_tracker_params=None`` to omit
    the StateTracker entirely (used to verify the RuntimeError path).
    """
    params = ABMParams(num_ticks=TICKS, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_scenario(), params)
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


def test_per_patch_output_has_full_schema(tmp_path):
    out_path = tmp_path / "results.json"
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(aggregation_level=0),
        results_writer_params=ResultsWriterParams(path=str(out_path)),
    )
    model.run()

    assert out_path.exists(), "ResultsWriter did not write the file"
    on_disk = json.loads(out_path.read_text())

    # Top-level keys
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

    # Per-group arrays present and correctly sized
    assert summary["attack_rate_per_group"] is not None
    assert len(summary["attack_rate_per_group"]) == N_PATCHES
    assert all(0.0 <= r <= 1.0 for r in summary["attack_rate_per_group"])

    assert summary["peak_infectious_per_group"] is not None
    assert len(summary["peak_infectious_per_group"]) == N_PATCHES
    assert all(p >= 0 for p in summary["peak_infectious_per_group"])

    # final_state_per_group is a dict of state -> N_PATCHES counts
    final = summary["final_state_per_group"]
    assert final is not None
    for state in ("S", "I", "R"):
        assert state in final, f"missing final state {state!r}"
        assert len(final[state]) == N_PATCHES

    # final_state_global is a dict of state -> scalar int (sum across patches)
    final_global = summary["final_state_global"]
    assert final_global is not None
    for state in ("S", "I", "R"):
        assert state in final_global, f"missing global final state {state!r}"
        assert isinstance(final_global[state], int)
        # Global value equals sum of per-patch values
        assert final_global[state] == sum(final[state]), f"global {state}={final_global[state]} != sum(per-patch)={sum(final[state])}"


def test_global_only_tracker_emits_null_per_group_arrays(tmp_path):
    # Default aggregation_level=-1 → tracker sums over all patches → per-group
    # arrays in the JSON should be None.
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

    # final_state_global is present even when only global tracking is on
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


def test_missing_state_tracker_raises(tmp_path):
    # ResultsWriter present but no StateTracker → finalize() must raise.
    model = _make_model(
        state_tracker_params=None,
        results_writer_params=ResultsWriterParams(path=str(tmp_path / "results.json")),
    )
    with pytest.raises(RuntimeError, match="StateTracker"):
        model.run()


def test_default_path_is_results_json_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model(
        state_tracker_params=BaseStateTrackerParams(aggregation_level=0),
        # No results_writer_params → ResultsWriter uses its default path.
    )
    model.run()

    default_path = tmp_path / "results.json"
    assert default_path.exists(), "default path 'results.json' should land in cwd"
