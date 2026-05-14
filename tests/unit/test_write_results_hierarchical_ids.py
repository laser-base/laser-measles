"""Tests for BaseLaserModel.write_results() — hierarchical-ID edge cases.

These tests were written because p16 in the laser-mcp prompt suite kept
failing with broadcast errors like ``(2,) vs (100,)``. The root cause
was a contract gap between ``write_results()`` and ``StateTracker``:

  - ``two_cluster_scenario`` produces hierarchical IDs of the form
    ``"cluster_1:node_42"``.
  - With ``StateTracker(aggregation_level=0)`` the tracker groups by the
    first segment and yields ``len(group_ids) == 2`` (the two cluster
    names), not ``n_patches == 100``.
  - The old schema emitted these length-2 arrays under the misleading
    name ``summary.attack_rate_per_patch``, while ``num_patches: 100``
    at the top-level lied about the grouping.

Fix: rename ``_per_patch → _per_group`` (also ``num_patches → num_groups``
and ``patch_ids → group_ids``) and add ``group_aggregation_level`` so
consumers can branch on it without re-deriving from the scenario.
Also ``peak_day → peak_tick`` so the tick index isn't confused with
calendar days.

These tests pin the new schema.
"""

from __future__ import annotations

import polars as pl
import pytest

from laser.measles.abm import ABMModel
from laser.measles.abm import ABMParams
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import NoBirthsProcess
from laser.measles.abm.components import StateTracker
from laser.measles.biweekly import BiweeklyModel
from laser.measles.biweekly import BiweeklyParams
from laser.measles.biweekly.components import InfectionProcess as BWInfection
from laser.measles.biweekly.components import InitializeEquilibriumStatesProcess
from laser.measles.components import BaseStateTrackerParams
from laser.measles.components import ResultsWriter
from laser.measles.components import create_component

N_PER_CLUSTER = 4
TICKS = 60


def _hierarchical_scenario(n_per_cluster: int = N_PER_CLUSTER) -> pl.DataFrame:
    """Two-cluster scenario with ``cluster_X:node_Y``-style hierarchical IDs.

    Mirrors the shape of ``laser.measles.scenarios.two_cluster_scenario``
    but is built inline so the test stays self-contained.
    """
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


def _build_model(state_tracker_params) -> ABMModel:
    params = ABMParams(num_ticks=TICKS, seed=42, start_time="2000-01", verbose=False, show_progress=False)
    model = ABMModel(_hierarchical_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=20)))
    model.add_component(InfectionProcess)
    model.add_component(create_component(StateTracker, params=state_tracker_params))
    return model


def test_aggregation_level_0_with_hierarchical_ids_rolls_up_to_clusters(tmp_path):
    """With ``aggregation_level=0`` and hierarchical IDs (``cluster_1:node_1``),
    the tracker rolls nodes up to one row per top-level segment.
    ``write_results()`` then emits length-2 arrays — but under the
    correctly-named ``_per_group`` keys, with ``num_groups=2`` and
    ``group_aggregation_level=0`` so the consumer knows what they're
    holding.
    """
    n_clusters = 2
    model = _build_model(BaseStateTrackerParams(aggregation_level=0))
    model.run()

    out = model.write_results(str(tmp_path / "results.json"))
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
    tracker yields one row per scenario patch and ``write_results()``
    must produce per-group arrays of that exact length — which IS
    per-patch in this case.
    """
    n_patches = 2 * N_PER_CLUSTER
    model = _build_model(BaseStateTrackerParams(aggregation_level=1))
    model.run()

    out = model.write_results(str(tmp_path / "results.json"))
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
    The top-level ``group_aggregation_level`` field carries that
    contract so readers can branch without re-deriving from the
    scenario.
    """
    model = _build_model(BaseStateTrackerParams(aggregation_level=0))
    model.run()
    out = model.write_results(str(tmp_path / "results.json"))
    assert "group_aggregation_level" in out
    assert isinstance(out["group_aggregation_level"], int)
    assert out["group_aggregation_level"] == 0


def test_peak_tick_is_tick_index_in_biweekly_model(tmp_path):
    """``summary.peak_tick`` is named for what it is — the tick index
    of the global infectious peak — so consumers don't accidentally
    treat a biweekly tick (14 days) as a calendar day.
    """
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
    ]
    model.run()
    out = model.write_results(str(tmp_path / "results.json"))
    summary = out["summary"]

    assert "peak_tick" in summary
    assert "peak_day" not in summary, "peak_day was renamed to peak_tick to avoid implying calendar days."
    assert 0 <= summary["peak_tick"] < params.num_ticks


def test_results_writer_path_is_relative_to_cwd(tmp_path, monkeypatch):
    """Audit: ``ResultsWriter`` passes its ``path`` straight to
    ``model.write_results(path)``. Verify a relative path is resolved
    against the current working directory (so per-attempt cwds in the
    laser-mcp parallel test runner isolate writes properly).

    This is the contract the runner relies on — if someone changes
    ResultsWriter to resolve relative paths against the model's home or
    a package-relative location, concurrent prompts will overwrite each
    other's results.json.
    """
    monkeypatch.chdir(tmp_path)

    model = _build_model(BaseStateTrackerParams(aggregation_level=1))
    model.add_component(ResultsWriter)
    model.run()

    target = tmp_path / "results.json"
    assert target.exists(), f"ResultsWriter should write its default path 'results.json' relative to cwd ({tmp_path}); found nothing there."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
