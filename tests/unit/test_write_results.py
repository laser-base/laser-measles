"""Tests for BaseLaserModel.write_results() — the standard JSON output.

Coverage:
- Per-patch tracker (aggregation_level=0): full schema with non-null per-patch
  arrays in the right shape, correct patch_ids order, summary scalars sane.
- Global-only tracker (default aggregation_level=-1): per-patch arrays are
  None; global aggregates still populated.
- No StateTracker attached: write_results() raises a clear RuntimeError.
- Return value matches what's written to disk.
"""

import json

import polars as pl
import pytest

import laser.measles as lm
from laser.measles.abm import ABMModel, ABMParams
from laser.measles.abm.components import (
    InfectionProcess,
    InfectionSeedingParams,
    InfectionSeedingProcess,
    NoBirthsProcess,
    StateTracker,
)
from laser.measles.components import BaseStateTrackerParams, create_component


N_PATCHES = 5
TICKS = 90


def _scenario():
    return pl.DataFrame({
        "id": [f"patch_{i}" for i in range(N_PATCHES)],
        "pop": [50_000, 80_000, 120_000, 60_000, 40_000],
        "lat": [0.0, 0.1, 0.2, 0.3, 0.4],
        "lon": [0.0, 0.0, 0.0, 0.0, 0.0],
        "mcv1": [0.0, 0.2, 0.4, 0.6, 0.8],
    })


def _make_model(state_tracker_params=None):
    params = ABMParams(num_ticks=TICKS, seed=42, start_time="2000-01",
                       verbose=False, show_progress=False)
    model = ABMModel(_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess,
                                         params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    if state_tracker_params is not None:
        model.add_component(create_component(StateTracker, params=state_tracker_params))
    return model


def test_per_patch_output_has_full_schema(tmp_path):
    model = _make_model(BaseStateTrackerParams(aggregation_level=0))
    model.run()

    out_path = tmp_path / "results.json"
    returned = model.write_results(str(out_path))

    assert out_path.exists(), "write_results() did not write the file"
    on_disk = json.loads(out_path.read_text())
    assert on_disk == returned, "return value must match what's written"

    # Top-level keys
    for key in ("model_type", "num_ticks", "num_patches", "patch_ids", "states", "summary"):
        assert key in on_disk, f"missing top-level key {key!r}"

    assert on_disk["model_type"] == "ABMModel"
    assert on_disk["num_ticks"] == TICKS
    assert on_disk["num_patches"] == N_PATCHES
    assert on_disk["patch_ids"] == [f"patch_{i}" for i in range(N_PATCHES)]
    assert set(("S", "I", "R")).issubset(set(on_disk["states"]))

    summary = on_disk["summary"]

    # Global scalars
    assert isinstance(summary["peak_infectious_global"], int)
    assert summary["peak_infectious_global"] > 0
    assert 0 <= summary["peak_day"] < TICKS
    assert 0.0 <= summary["attack_rate_global"] <= 1.0

    # Per-patch arrays present and correctly sized
    assert summary["attack_rate_per_patch"] is not None
    assert len(summary["attack_rate_per_patch"]) == N_PATCHES
    assert all(0.0 <= r <= 1.0 for r in summary["attack_rate_per_patch"])

    assert summary["peak_infectious_per_patch"] is not None
    assert len(summary["peak_infectious_per_patch"]) == N_PATCHES
    assert all(p >= 0 for p in summary["peak_infectious_per_patch"])

    # final_state_per_patch is a dict of state -> N_PATCHES counts
    final = summary["final_state_per_patch"]
    assert final is not None
    for state in ("S", "I", "R"):
        assert state in final, f"missing final state {state!r}"
        assert len(final[state]) == N_PATCHES


def test_global_only_tracker_emits_null_per_patch_arrays(tmp_path):
    # Default aggregation_level=-1 → tracker sums over all patches → per-patch
    # arrays in the JSON should be None.
    model = _make_model(BaseStateTrackerParams())  # default
    model.run()

    out = model.write_results(str(tmp_path / "results.json"))
    summary = out["summary"]

    # Global aggregates still produced
    assert isinstance(summary["peak_infectious_global"], int)
    assert summary["peak_infectious_global"] > 0
    assert summary["attack_rate_global"] is not None

    # Per-patch arrays explicitly null
    assert summary["attack_rate_per_patch"] is None
    assert summary["peak_infectious_per_patch"] is None
    assert summary["final_state_per_patch"] is None

    # patch_ids reflects the single aggregated group
    assert out["patch_ids"] == ["all_patches"]


def test_missing_state_tracker_raises(tmp_path):
    model = _make_model(state_tracker_params=None)  # no tracker
    model.run()

    with pytest.raises(RuntimeError, match="StateTracker"):
        model.write_results(str(tmp_path / "results.json"))


def test_default_path_is_results_json_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model(BaseStateTrackerParams(aggregation_level=0))
    model.run()
    model.write_results()  # no path arg

    default_path = tmp_path / "results.json"
    assert default_path.exists(), "default path 'results.json' should land in cwd"
