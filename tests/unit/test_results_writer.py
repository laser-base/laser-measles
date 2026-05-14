"""Tests for the ResultsWriter component + the finalize() hook in BaseLaserModel.run().

Coverage:
- Adding ResultsWriter to a model's components causes results.json to be
  written at end of run, with the canonical schema (model_type,
  num_groups, group_ids, group_aggregation_level, summary.*).
- Custom path via ResultsWriterParams is honored.
- A model run *without* ResultsWriter does NOT create results.json
  (calibration loops opt out by simply not including the component).
- The finalize() hook itself: a custom component that defines finalize()
  is invoked exactly once after the tick loop, in component-list order;
  components that don't define finalize() are skipped without error.
"""

import json
from typing import ClassVar

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
from laser.measles.components import BaseStateTrackerParams
from laser.measles.components import ResultsWriter
from laser.measles.components import ResultsWriterParams
from laser.measles.components import create_component


def _scenario():
    return pl.DataFrame(
        {
            "id": ["patch_0", "patch_1", "patch_2"],
            "pop": [40_000, 30_000, 30_000],
            "lat": [0.0, 0.1, 0.2],
            "lon": [0.0, 0.0, 0.0],
            "mcv1": [0.0, 0.2, 0.4],
        }
    )


def _make_model_with(extra_components):
    params = ABMParams(num_ticks=60, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=15)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=0)))
    for c in extra_components:
        model.add_component(c)
    return model


def test_results_writer_writes_results_json_at_end_of_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model_with([ResultsWriter])
    model.run()

    out = tmp_path / "results.json"
    assert out.exists(), "ResultsWriter should have written results.json in cwd"
    data = json.loads(out.read_text())
    assert data["model_type"] == "ABMModel"
    assert data["num_ticks"] == 60
    assert "summary" in data
    assert "peak_infectious_global" in data["summary"]


def test_results_writer_honors_custom_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model_with([create_component(ResultsWriter, params=ResultsWriterParams(path="custom_run.json"))])
    model.run()

    assert (tmp_path / "custom_run.json").exists()
    assert not (tmp_path / "results.json").exists(), "should NOT have written the default path when custom path is set"


def test_no_results_writer_means_no_results_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = _make_model_with([])  # no ResultsWriter
    model.run()
    assert not (tmp_path / "results.json").exists(), "without ResultsWriter, no results.json should be written"


def test_results_writer_picks_most_granular_state_tracker(tmp_path, monkeypatch):
    """Hello-world pattern: a default global StateTracker plus a per-patch
    one. ResultsWriter must prefer the per-patch (highest aggregation_level)
    so the per_group arrays are populated instead of being silently null.
    """
    monkeypatch.chdir(tmp_path)
    # Build the model manually — _make_model_with already adds the per-patch
    # tracker, but here we want to add a global one FIRST and the per-patch
    # one SECOND, so first-match-by-name would pick the wrong one.
    params = ABMParams(num_ticks=60, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=15)))
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
    assert data["num_groups"] == 3, f"expected per-patch (3 groups), got {data['num_groups']}"
    assert data["summary"]["attack_rate_per_group"] is not None
    assert len(data["summary"]["attack_rate_per_group"]) == 3


# ── finalize() hook coverage ─────────────────────────────────────────────────


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


def test_finalize_hook_called_once_for_components_that_define_it():
    _RecordsFinalize.calls = []
    model = _make_model_with([_NoFinalize, _RecordsFinalize])
    model.run()
    assert _RecordsFinalize.calls == ["finalize"], f"expected exactly one finalize() call, got {_RecordsFinalize.calls}"


def test_finalize_hook_skips_components_without_finalize():
    # Just runs to completion; the assertion is "no exception raised".
    model = _make_model_with([_NoFinalize])
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

    model = _make_model_with([_BoomFinalize])
    with pytest.raises(RuntimeError, match="intentional finalize failure"):
        model.run()
