import importlib

import numpy as np
import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES

VERBOSE = False
SEED = 42


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_constant_pop_single_patch(measles_module):
    """Test the constant population scenario."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=50, verbose=VERBOSE, seed=SEED))
    model.components = [MeaslesModel.components.ConstantPopProcess]
    model.run()
    assert model.patches.states[:-1, :].sum() == scenario["pop"].sum()
    component = model.get_component(MeaslesModel.components.ConstantPopProcess)[0]
    assert component.mu_death == component.lambda_birth


@pytest.mark.slow
def test_ABM_pop_agreement():
    scenario = lm.scenarios.synthetic.two_patch_scenario()
    model = lm.abm.Model(scenario, lm.abm.Params(num_ticks=50, verbose=VERBOSE, seed=SEED))
    model.components = [lm.abm.components.ConstantPopProcess]
    model.run()
    # Assert population between patches and people are in agreement
    assert model.patches.states.sum() == len(model.people)


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_constant_pop_two_patch(measles_module):
    """Test the constant population scenario."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=50, verbose=VERBOSE, seed=SEED))
    model.components = [MeaslesModel.components.ConstantPopProcess]
    model.run()
    assert model.patches.states[:-1, :].sum() == scenario["pop"].sum()


@pytest.mark.slow
@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_constant_pop_with_infection(measles_module):
    """Regression test for issue #95: model crash with ConstantPopProcess + infection components."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=50, verbose=VERBOSE, seed=SEED))
    model.components = [
        MeaslesModel.components.ConstantPopProcess,
        MeaslesModel.components.InfectionSeedingProcess,
        MeaslesModel.components.InfectionProcess,
    ]
    model.run()
    assert model.patches.states.sum() == scenario["pop"].sum()


def test_abm_constant_pop_initial_patch_id_distribution():
    """Given a multi-patch scenario, when ConstantPopProcess initializes the ABM
    people frame, then patch_id assignment must match the per-patch population
    counts from the scenario.

    Failure of this assertion would indicate that the contiguous run-length
    assignment of patch_id from scenario["pop"] has regressed (e.g. the
    np.repeat-based initialization produces wrong counts per patch).
    """
    scenario = lm.scenarios.synthetic.two_patch_scenario(population=20_000)
    model = lm.abm.Model(scenario, lm.abm.Params(num_ticks=0, verbose=VERBOSE, seed=SEED))
    model.components = [lm.abm.components.ConstantPopProcess]
    model.run()

    pops = scenario["pop"].to_numpy()
    counts = np.bincount(model.people.patch_id[: model.people.count], minlength=len(pops))
    assert np.array_equal(counts[: len(pops)], pops), f"Per-patch agent counts {counts[: len(pops)]} do not match scenario pop {pops}"


if __name__ == "__main__":
    for module in MEASLES_MODULES:
        print(f"Testing {module}...")
        test_constant_pop_single_patch(module)
        print(f"✓ {module} constant pop test passed")
        test_constant_pop_two_patch(module)
        print(f"✓ {module} constant pop test passed")
