"""
https://github.com/InstituteforDiseaseModeling/laser-polio/blob/main/tests/test_transmission.py
"""

import importlib

import numpy as np
import polars as pl
import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES
from laser.measles.base import BaseLaserModel


def setup_sim(scenario, params, module):
    model_params = module.Params(num_ticks=50, seed=42)
    kwargs = {}
    if "beta" in params:
        kwargs["beta"] = params["beta"]

    infection_params = module.components.InfectionParams(**kwargs)
    sim = module.Model(scenario, model_params)
    sim.components = [
        module.components.InitializeEquilibriumStatesProcess,
        module.components.StateTracker,
        lm.create_component(module.components.InfectionSeedingProcess, module.components.InfectionSeedingParams(num_infections=10)),
        lm.create_component(module.components.InfectionProcess, infection_params),
        module.components.VitalDynamicsProcess,
    ]
    return sim


def setup_NxN_sim(params, module):
    N = params.get("N", 4)
    scenario = pl.DataFrame(
        {
            "id": [f"patch_{i}" for i in range(N)],
            "pop": N * [10_000],
            "lat": np.linspace(0, 1, N),
            "lon": np.linspace(0, 1, N),
            "mcv1": N * [0.0],
        }
    )
    sim = setup_sim(scenario, params, module)
    return sim


class ChainTransmissionProcess(lm.base.BaseComponent):
    def _initialize(self, model: BaseLaserModel):
        c = model.get_component("InfectionProcess")
        assert len(c) == 1, "There should be exactly one infection process"
        assert c[0].initialized, "Infection process must be initialized"
        num_patches = len(model.scenario)
        # ABM InfectionParams now has a `mixer` field that defaults to None
        # (the actual mixer lives on TransmissionParams in that case), so we
        # check for a non-None value rather than just the attribute's presence.
        if getattr(c[0].params, "mixer", None) is not None:
            c[0].params.mixer._mixing_matrix = np.diag(np.ones(num_patches - 1), k=1)
        elif hasattr(c[0], "transmission"):
            c[0].transmission.params.mixer._mixing_matrix = np.diag(np.ones(num_patches - 1), k=1)
        else:
            raise ValueError("No mixing attribute found")


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_zero_trans_single_patch(measles_module):
    # Test with r0 = 0x
    MeaslesModel = importlib.import_module(measles_module)
    scenario = lm.scenarios.synthetic.single_patch_scenario()
    sim_r0_zero = setup_sim(scenario, {"beta": 0.0}, MeaslesModel)
    sim_r0_zero.run()
    seeding = sim_r0_zero.get_component("InfectionSeedingProcess")[0]
    assert np.max(sim_r0_zero.get_component("StateTracker")[0].state_tracker.I) <= seeding.params.num_infections, (
        "There should be NO additional infections when r0 is 0."
    )


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_linear_transmission(measles_module):
    MeaslesModel = importlib.import_module(measles_module)
    sim = setup_NxN_sim({"N": 40}, MeaslesModel)
    sim.add_component(ChainTransmissionProcess)
    sim.add_component(
        lm.create_component(
            MeaslesModel.components.CaseSurveillanceTracker, MeaslesModel.components.CaseSurveillanceParams(detection_rate=1.0)
        )
    )
    sim.run()
    cases = sim.get_component("CaseSurveillanceTracker")[0]
    assert np.any(cases.reported_cases > 0, axis=1).sum() > 2, "There should be at least two patches with cases"
    last_first_case_idx = -1
    for i in range(len(sim.scenario)):
        patch_cases = cases.reported_cases[i, :]
        first_case_idx = np.where(patch_cases > 0)[0]
        if len(first_case_idx) > 0:
            assert first_case_idx[0] > last_first_case_idx, (
                f"Node {i} has a first case at {first_case_idx[0]} but the first case for Node {i - 1} was at {last_first_case_idx}"
            )
            last_first_case_idx = first_case_idx[0]


if __name__ == "__main__":
    pytest.main([__file__ + "::test_zero_trans_single_patch", "-v", "-s"])
