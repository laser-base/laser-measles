import importlib

import numpy as np
import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_seed_single_patch(measles_module):
    """
    Test infection seeding for different model types.

    Args:
        measles_module (str): The module path to import as MeaslesModel.
    """
    MeaslesModel = importlib.import_module(measles_module)

    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=0))
    model.components = [
        MeaslesModel.components.InfectionSeedingProcess,
        MeaslesModel.components.InfectionProcess,
    ]  # NB: No disease progression included in the components
    model.run()
    if "E" in model.params.states:
        assert model.patches.states.E.sum() == 1
    else:
        assert model.patches.states.I.sum() == 1


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_seed_two_patch(measles_module):
    """Test the infection process in two patches."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=0))
    model.components = [
        MeaslesModel.components.InfectionSeedingProcess,
        MeaslesModel.components.InfectionProcess,
    ]  # NB: No disease progression included in the components
    model.run()
    if "E" in model.params.states:
        assert model.patches.states.E.sum() == 1
    else:
        assert model.patches.states.I.sum() == 1


def test_abm_no_births_initial_patch_id_distribution():
    """Given a multi-patch ABM scenario with no vital-dynamics component,
    when the model auto-prepends NoBirthsProcess and initializes,
    then the per-patch agent counts must match scenario["pop"].

    NoBirthsProcess builds the patch_id array by run-length expansion of the
    scenario populations. A regression in that expansion (e.g. swapping
    np.repeat for a faulty implementation) would manifest as a mismatch
    between np.bincount(people.patch_id) and scenario["pop"].
    """
    scenario = lm.scenarios.synthetic.two_patch_scenario(population=20_000)
    model = lm.abm.Model(scenario, lm.abm.Params(num_ticks=0))
    # No vital-dynamics component → NoBirthsProcess is auto-prepended.
    model.components = [
        lm.abm.components.InfectionSeedingProcess,
        lm.abm.components.InfectionProcess,
    ]
    model.run()

    pops = scenario["pop"].to_numpy()
    counts = np.bincount(model.people.patch_id[: model.people.count], minlength=len(pops))
    assert np.array_equal(counts[: len(pops)], pops), (
        f"Per-patch agent counts {counts[: len(pops)]} do not match scenario pop {pops}"
    )


if __name__ == "__main__":
    for module in MEASLES_MODULES:
        print(f"Testing {module}...")
        test_seed_single_patch(module)
        print(f"✓ {module} test passed")
