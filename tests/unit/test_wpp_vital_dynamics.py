import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pytest
import pyvd
from scipy import stats

from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import WPPVitalDynamicsProcess
from laser.measles.abm.model import ABMModel
from laser.measles.abm.model import ABMParams
from laser.measles.components import create_component
from laser.measles.scenarios.synthetic import two_patch_scenario


def is_debugger_active():
    """Check if we're running in a debugger."""
    return any(debugger in sys.modules for debugger in ["pdb", "ipdb", "pudb", "debugpy"])


def debug_plot_age_pyramid(model, age_bins, model_pyramid, wpp_pyramid):
    """Helper function to plot age pyramid for debugging."""

    plt.figure(figsize=(10, 6))
    plt.bar(
        age_bins[:-1] / 365, model_pyramid / np.sum(model_pyramid), width=np.diff(age_bins) / 365, align="edge", alpha=0.7, label="Model"
    )
    plt.bar(
        age_bins[1:-1] / 365, wpp_pyramid / np.sum(wpp_pyramid), width=np.diff(age_bins[1:]) / 365, align="edge", alpha=0.7, label="WPP"
    )
    plt.xlabel("Age (years)")
    plt.ylabel("Proportion")
    plt.title("Age Pyramid Comparison")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()


DEBUG = os.getenv("DEBUG_PLOTS", "False").lower() in ("true", "1", "yes") or is_debugger_active()


def reconstruct_from_histogram(bin_edges, counts):
    """
    Reconstruct approximate data points from histogram bins
    """
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    data_points = []

    for center, count in zip(bin_centers, counts, strict=False):
        # Add 'count' number of points at each bin center
        data_points.extend([center] * int(count))

    return np.array(data_points)


@pytest.fixture
def WPPModelZeroTicks():
    scenario = two_patch_scenario(population=10_000)
    params = ABMParams(num_ticks=0)
    model = ABMModel(scenario, params)
    model.components = [WPPVitalDynamicsProcess]
    model.run()
    return model


@pytest.fixture
def WPPModel():
    scenario = two_patch_scenario(population=100_000)
    params = ABMParams(num_ticks=5 * 365, start_time="2000-06", seed=12)
    model = ABMModel(scenario, params)
    model.components = [WPPVitalDynamicsProcess]
    model.run()
    return model


def test_initial_node_ids(WPPModelZeroTicks):
    # Check that the number of people in each patch is correct
    for i, row in enumerate(WPPModelZeroTicks.scenario.iter_rows(named=True)):
        assert np.sum(np.logical_and(WPPModelZeroTicks.people.patch_id == i, WPPModelZeroTicks.people.active)) == row["pop"]


@pytest.mark.slow
def test_initial_age_pyramid(WPPModelZeroTicks):
    age_bins = np.concatenate([[0], pyvd.constants.MORT_XVAL[::2], [pyvd.constants.MORT_XVAL[-1]]])  # in days
    idx = np.where(WPPModelZeroTicks.people.active)[0]
    model_pyramid = np.histogram(0 - WPPModelZeroTicks.people.date_of_birth[idx], bins=age_bins)[0]
    vd = WPPModelZeroTicks.get_component(WPPVitalDynamicsProcess)[0]
    wpp_pyramid = vd.wpp.get_population_pyramid(WPPModelZeroTicks.start_time.year)
    # if DEBUG:
    #     debug_plot_age_pyramid(WPPModelZeroTicks, age_bins, model_pyramid, wpp_pyramid)
    model_pyramid_samples = reconstruct_from_histogram(age_bins, model_pyramid)
    wpp_pyramid_samples = reconstruct_from_histogram(age_bins[1:], np.round(wpp_pyramid * (model_pyramid.sum() / wpp_pyramid.sum())))
    assert np.sum(model_pyramid) == len(idx)  # check that the pyramid captures everyone in the model
    _, p_value = stats.ks_2samp(model_pyramid_samples, wpp_pyramid_samples)
    assert p_value > 0.05


@pytest.mark.slow
def test_pop_agreement(WPPModel):
    # Assert population between patches and people are in agreement
    assert WPPModel.patches.states.sum() == WPPModel.people.active.sum()


@pytest.mark.slow
def test_wpp_vital_dynamics(WPPModel):
    vd = WPPModel.get_component(WPPVitalDynamicsProcess)[0]
    initial_pyramid = vd.wpp.get_population_pyramid(WPPModel.start_time.year)
    final_pyramid = vd.wpp.get_population_pyramid(WPPModel.start_time.year + WPPModel.params.num_ticks // 365)
    wpp_growth_rate = (final_pyramid.sum() - initial_pyramid.sum()) / initial_pyramid.sum()
    model_growth_rate = (WPPModel.people.active.sum() - WPPModel.scenario["pop"].sum()) / WPPModel.scenario["pop"].sum()
    assert np.isclose(model_growth_rate, wpp_growth_rate, atol=2e-2)


@pytest.mark.slow
def test_wpp_with_infection_no_state_drift():
    """Regression for laser-measles #117: WPP + InfectionProcess + DiseaseProcess
    together used to make ``patches.states`` drift below zero on uint32, wrap to
    ~2³² magnitude, and then make per-tick birth counts explode (since the
    birth lambda is ``patch_pops × birth_rate``). Symptom in the wild was
    ``frame.add() exceeds capacity`` with absurd counts.

    Two distinct bugs in WPPVitalDynamicsProcess caused this:

      1. Dead agents kept their epidemic state and E/I timers, so DiseaseProcess
         on subsequent ticks counted them as "ghost" transitions and
         decremented patches.states past zero.
      2. Recycled birth slots kept their previous owner's ``patch_id``, so a
         newborn at patch X (incremented at patches.states.S[X]) was still
         tagged at agent level with the patch_id of whichever agent died in
         patch Y. Per-patch agent vs patch-state drift compounds, eventually
         underflowing patches.states.E when transmission's effective_incidence
         clamp fires.

    The previous version of this test only checked the GLOBAL conservation
    invariant — but bug #2 conserves the global total while corrupting the
    per-patch attribution. Copilot review caught this gap. The current test
    pins the per-patch invariant: for every (state, patch) cell,
    ``patches.states[state, patch]`` must equal the count of active agents
    with that (state, patch_id) combination.
    """
    scenario = two_patch_scenario(population=20_000)
    # 45 ticks is enough for cross-patch deaths/births to produce visible
    # per-(state, patch) drift if the patch_id stamp is missing (drift
    # first appears around tick 40 in this scenario), but short enough that
    # the eventual uint32 wraparound and frame.add() crash (~tick 49) don't
    # happen — so the per-patch assertion below can fire with a clean
    # diagnostic instead of being preempted by the symptom further down
    # the chain.
    params = ABMParams(num_ticks=45, start_time="2000-01", seed=7)
    model = ABMModel(scenario, params)
    model.components = [
        WPPVitalDynamicsProcess,
        create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=50)),
        InfectionProcess,
    ]
    model.run()

    # Global conservation invariant: patches.states.sum() == active count.
    # This catches the late-stage symptom (uint32 wrap leaking into the sum).
    patch_sum = int(model.patches.states.sum())
    active_count = int(model.people.active.sum())
    assert patch_sum == active_count, (
        f"patch state drift: patches.states.sum()={patch_sum:,} "
        f"vs people.active.sum()={active_count:,} — likely uint32 underflow "
        "from ghost E/I agents (see #117)."
    )

    # Per-(state, patch) conservation invariant. This is the strict version
    # that the global check misses: bug #2 (stale patch_id on recycled
    # newborns) inflates the agent count for patch Y while
    # patches.states[X] gets the increment, with no global divergence. Build
    # the agent-level (state, patch_id) histogram and compare cell-for-cell
    # to model.patches.states.
    people = model.people
    n_states = len(model.params.states)
    n_patches = len(model.patches)
    active_mask = people.active[: people.count]
    active_state = np.asarray(people.state[: people.count])[active_mask]
    active_patch = np.asarray(people.patch_id[: people.count])[active_mask]
    # 2D bincount via flat index: state * n_patches + patch
    flat = active_state.astype(np.int64) * n_patches + active_patch.astype(np.int64)
    agent_hist = np.bincount(flat, minlength=n_states * n_patches).reshape(n_states, n_patches)
    patch_hist = np.asarray(model.patches.states).astype(np.int64)

    if not np.array_equal(agent_hist, patch_hist):
        diff = agent_hist - patch_hist
        # Locate the worst cell for the error message
        flat_idx = int(np.abs(diff).argmax())
        s_idx, p_idx = divmod(flat_idx, n_patches)
        s_name = model.params.states[s_idx]
        raise AssertionError(
            f"per-(state, patch) drift between agent-level and patches.states: "
            f"worst cell is ({s_name}, patch={p_idx}): "
            f"agent_hist={int(agent_hist[s_idx, p_idx])}, "
            f"patch_hist={int(patch_hist[s_idx, p_idx])}, "
            f"diff={int(diff[s_idx, p_idx]):+d}. "
            "Likely missing patch_id stamp on recycled newborn slots in "
            "WPPVitalDynamicsProcess (see #117)."
        )

    # And per-state, every patch's count must be a plausible non-negative number.
    # Catches the explicit underflow signature: a state showing ~2³².
    UINT32_MAX = (1 << 32) - 1
    for state_name in model.params.states:
        per_patch = np.asarray(getattr(model.patches.states, state_name))
        assert per_patch.max() < 10 * active_count, (
            f"patches.states.{state_name}.max()={per_patch.max():,} is implausibly large — uint32 underflow signature."
        )
        # uint32 wraparound would land at ~UINT32_MAX; sanity-check we're nowhere close.
        assert per_patch.max() < UINT32_MAX / 2


if __name__ == "__main__":
    # pytest.main([__file__ + "::test_initial_age_pyramid", "-v", "-s"])
    pytest.main([__file__, "-v", "-s"])
