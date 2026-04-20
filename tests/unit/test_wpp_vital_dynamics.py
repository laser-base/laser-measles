import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pytest
import pyvd
from scipy import stats

from laser.measles.abm.components import WPPVitalDynamicsProcess
from laser.measles.abm.model import ABMModel
from laser.measles.abm.model import ABMParams
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


if __name__ == "__main__":
    # pytest.main([__file__ + "::test_initial_age_pyramid", "-v", "-s"])
    pytest.main([__file__, "-v", "-s"])
