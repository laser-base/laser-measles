"""Tests for BaseLaserModel.write_results() — hierarchical-ID edge cases.

These tests were written because p16 in the laser-mcp prompt suite kept
failing with broadcast errors like ``(2,) vs (100,)``. The root cause
turned out to be in ``write_results()`` (or more precisely the contract
between it and ``StateTracker``):

  - ``two_cluster_scenario`` produces hierarchical IDs of the form
    ``"cluster_1:node_42"``.
  - With ``StateTracker(aggregation_level=0)`` the tracker groups by the
    first segment and yields ``len(group_ids) == 2`` (the two cluster
    names), not ``n_patches == 100``.
  - ``write_results()`` then emits ``summary.attack_rate_per_patch`` as a
    length-2 list, even though the JSON top-level says
    ``num_patches: 100``.

This is a real semantic bug for downstream consumers: a field named
``_per_patch`` should either contain one value per scenario row or be
``None`` / accompanied by enough metadata to know what aggregation level
it represents.

Each test below is shaped as the **desired** post-fix behaviour, so they
fail under the current implementation. We can either:

  (a) Make ``aggregation_level=0`` with hierarchical IDs actually yield
      one group per scenario row (treat the full ID as the leaf), or
  (b) Keep current grouping semantics but rename the fields
      ``_per_patch → _per_group`` and add ``group_aggregation_level`` to
      the top-level JSON so consumers can disambiguate.

The tests assert option (b) ish — they pin the **observable shape**
``len(...) == n_patches`` whenever the tracker is configured to give
one row per scenario patch (i.e. ``aggregation_level`` = depth−1), and
they assert misleading-but-misnamed cases are caught.
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
from laser.measles.components import BaseStateTrackerParams
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


def test_aggregation_level_0_with_hierarchical_ids_must_not_be_called_per_patch(tmp_path):
    """Reproduces the p16 bug.

    With ``aggregation_level=0`` on a scenario whose IDs are hierarchical
    (``cluster_1:node_1``), the tracker rolls all nodes up to two cluster
    groups. Today, ``summary.attack_rate_per_patch`` is a length-2 list,
    while ``num_patches`` says 8 — a contract violation that crashes
    downstream code that joins back to the scenario.

    Acceptable fixes (any of):

      (1) The arrays are renamed ``_per_group`` and the JSON gains a
          ``group_aggregation_level`` field so consumers can disambiguate.
      (2) The arrays stay named ``_per_patch`` but are populated only when
          ``len(group_ids) == num_patches`` — otherwise ``None`` (with
          metadata pointing at the actual grouping).
      (3) ``aggregation_level=0`` is redefined to mean "leaf / per-patch"
          regardless of ID depth, and a separate parameter controls roll-up.

    The assertion below pins the contract: a non-null ``_per_patch`` array
    must have the same length as ``num_patches``.
    """
    n_patches = 2 * N_PER_CLUSTER
    model = _build_model(BaseStateTrackerParams(aggregation_level=0))
    model.run()

    out = model.write_results(str(tmp_path / "results.json"))
    summary = out["summary"]

    assert out["num_patches"] == n_patches, "scenario has 8 rows"
    if summary["attack_rate_per_patch"] is not None:
        assert len(summary["attack_rate_per_patch"]) == n_patches, (
            "summary.attack_rate_per_patch is mis-named — got "
            f"len={len(summary['attack_rate_per_patch'])} but num_patches={n_patches}. "
            "Either rename to _per_group + add aggregation metadata, or set to None when "
            "not actually per-patch."
        )
    if summary["peak_infectious_per_patch"] is not None:
        assert len(summary["peak_infectious_per_patch"]) == n_patches
    if summary["final_state_per_patch"] is not None:
        for state, vec in summary["final_state_per_patch"].items():
            assert len(vec) == n_patches, f"final_state_per_patch[{state!r}] wrong length"


def test_aggregation_level_1_with_hierarchical_ids_is_true_per_patch(tmp_path):
    """When ``aggregation_level`` is set to the ID depth minus one, the
    tracker yields one row per scenario patch and ``write_results()``
    must produce per-patch arrays of that exact length."""
    n_patches = 2 * N_PER_CLUSTER
    model = _build_model(BaseStateTrackerParams(aggregation_level=1))
    model.run()

    out = model.write_results(str(tmp_path / "results.json"))
    summary = out["summary"]

    assert out["num_patches"] == n_patches
    # patch_ids should now equal the scenario id column in some stable order
    assert sorted(out["patch_ids"]) == sorted(
        f"cluster_{c}:node_{i + 1}" for c in (1, 2) for i in range(N_PER_CLUSTER)
    )
    assert summary["attack_rate_per_patch"] is not None
    assert len(summary["attack_rate_per_patch"]) == n_patches
    assert summary["peak_infectious_per_patch"] is not None
    assert len(summary["peak_infectious_per_patch"]) == n_patches
    for state, vec in summary["final_state_per_patch"].items():
        assert len(vec) == n_patches, f"final_state_per_patch[{state!r}] wrong length"


def test_top_level_exposes_aggregation_level_for_disambiguation(tmp_path):
    """Consumers reading the JSON must be able to tell whether the
    ``_per_*`` arrays are at patch granularity or aggregated above. Today
    the JSON has no such field — readers have to compare
    ``len(summary.attack_rate_per_patch)`` to ``num_patches``, which is
    exactly the silent-corruption mode p16 hit.

    Asserts a top-level ``group_aggregation_level`` (int) is present so
    downstream tooling can branch cleanly.
    """
    model = _build_model(BaseStateTrackerParams(aggregation_level=0))
    model.run()
    out = model.write_results(str(tmp_path / "results.json"))
    assert "group_aggregation_level" in out, (
        "write_results() output should expose the aggregation level the "
        "summary arrays correspond to (e.g. 0, 1, -1) so consumers can "
        "branch on it without re-deriving from the scenario."
    )
    assert isinstance(out["group_aggregation_level"], int)


def test_peak_day_naming_is_tick_in_biweekly_model(tmp_path):
    """Audit: ``summary.peak_day`` is the **tick index** of the peak, not
    a real calendar day. For the biweekly model where one tick is 14
    days, calling the field ``peak_day`` is at best confusing and at
    worst silently wrong if a downstream chart treats it as days.

    Pins the contract that there is either:
      (a) a ``peak_tick`` field alongside (or instead of) ``peak_day``, or
      (b) a unit annotation in the top-level JSON (e.g. ``ticks_per_day``)
          so consumers can convert.
    """
    from laser.measles.biweekly import BiweeklyModel
    from laser.measles.biweekly import BiweeklyParams
    from laser.measles.biweekly.components import InfectionProcess as BWInfection
    from laser.measles.biweekly.components import InitializeEquilibriumStatesProcess

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

    # Either a peak_tick field is added, or ticks_per_day annotation is present.
    has_tick_field = "peak_tick" in summary
    has_unit_annotation = "ticks_per_day" in out or "tick_units" in out
    assert has_tick_field or has_unit_annotation, (
        "summary.peak_day is the tick index, not calendar days. For "
        "biweekly models (1 tick = 14 days) this is misleading. Either "
        "add peak_tick alongside peak_day or annotate the time unit at "
        "the top level."
    )


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
    from laser.measles.components import ResultsWriter

    monkeypatch.chdir(tmp_path)

    model = _build_model(BaseStateTrackerParams(aggregation_level=1))
    model.add_component(ResultsWriter)
    model.run()

    target = tmp_path / "results.json"
    assert target.exists(), (
        f"ResultsWriter should write its default path 'results.json' "
        f"relative to cwd ({tmp_path}); found nothing there."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
