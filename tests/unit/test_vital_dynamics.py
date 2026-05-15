import importlib

import numpy as np
import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES

VERBOSE = False
SEED = 42


def expected_growth(model, module) -> np.ndarray:
    """Expected growth of the population."""
    component = model.get_component(module.components.VitalDynamicsProcess)[0]
    rate = component.lambda_birth - component.mu_death  # calculated per tick
    N = model.scenario["pop"].to_numpy() * np.exp(rate * model.params.num_ticks)
    return np.array(N)


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_vital_dynamics_single_patch(measles_module):
    """Test the vital dynamics in a single patch."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=365, verbose=VERBOSE, seed=SEED))
    model.components = [MeaslesModel.components.VitalDynamicsProcess]
    model.run()
    expected = expected_growth(model, MeaslesModel)
    assert model.patches.states.sum(axis=0) > model.scenario["pop"].sum()
    assert np.abs(model.patches.states.sum(axis=0) - expected) / expected < 0.10


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_vital_dynamics_two_patch(measles_module):
    """Test the vital dynamics in two patches."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=365, verbose=VERBOSE, seed=SEED))
    model.components = [MeaslesModel.components.VitalDynamicsProcess]
    model.run()
    expected = expected_growth(model, MeaslesModel)
    assert np.sum(model.patches.states) > model.scenario["pop"].sum()
    assert np.all(np.abs(model.patches.states.sum(axis=0) - expected) / expected < 0.10)


@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_infection_with_vital_dynamics_no_underflow(measles_module):
    """Regression test: InfectionProcess(beta>0) must not underflow patches.states.S.

    When an epidemic burns through all susceptibles in a single tick, the ABM's
    InfectionProcess can decrement patches.states.S (uint32) below zero, wrapping it
    to ~4 294 967 273. VitalDynamicsProcess then computes deaths from this inflated
    count and crashes with:
        ValueError: Cannot take a larger sample than population when replace=False

    This is the community-transmission complement to test_importation_with_vital_dynamics
    (which covers the same underflow triggered by ImportationPressureProcess at beta=0).

    The fix: InfectionProcess must clamp the patch-state decrement so that
    patches.states.S never goes below 0.
    """
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=100, verbose=VERBOSE, seed=SEED))
    model.components = [
        MeaslesModel.components.VitalDynamicsProcess,
        lm.create_component(
            MeaslesModel.components.InfectionSeedingProcess,
            MeaslesModel.components.InfectionSeedingParams(num_infections=10),
        ),
        lm.create_component(
            MeaslesModel.components.InfectionProcess,
            MeaslesModel.components.InfectionParams(beta=20.0),
        ),
    ]

    # Currently crashes with ValueError before reaching assertions.
    # After the fix this should complete and both assertions should hold.
    model.run()

    # S values must be physically meaningful (no uint32 wrap-around)
    assert np.all(model.patches.states.S < 1_000_000), f"patches.states.S looks like uint32 underflow: {model.patches.states.S}"

    # Population must be conserved: patch state counts == active agent count
    active_count = model.people.active[: model.people.count].sum()
    state_total = np.sum(model.patches.states)
    assert state_total == active_count, f"State total {state_total} != active agent count {active_count}"


def test_abm_vital_dynamics_births_per_patch_assignment():
    """Given a multi-patch ABM scenario with VitalDynamicsProcess (combined
    with InitializeEquilibriumStatesProcess to set up initial patch_ids),
    when the model is run for enough ticks to generate births, then every
    active agent's patch_id must agree with the per-patch state-count totals.

    VitalDynamicsProcess assigns newborn patch_ids by run-length expansion
    of the per-patch birth counts. A regression in that expansion (e.g. a
    bad np.repeat replacement) would skew the per-patch active-agent
    distribution and cause it to diverge from patches.states.sum(axis=0).
    """
    MeaslesModel = importlib.import_module("laser.measles.abm")
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario(population=50_000))
    model = MeaslesModel.Model(
        scenario,
        MeaslesModel.Params(num_ticks=180, verbose=VERBOSE, seed=SEED),
    )
    # InitializeEquilibriumStatesProcess sets initial patch_ids from scenario["pop"];
    # VitalDynamicsProcess then handles births whose patch_ids are assigned by the
    # run-length expansion under test.
    model.components = [
        MeaslesModel.components.VitalDynamicsProcess,
        MeaslesModel.components.InitializeEquilibriumStatesProcess,
    ]
    model.run()

    num_patches = len(scenario)
    active_idx = np.where(model.people.active[: model.people.count])[0]
    agent_counts = np.bincount(model.people.patch_id[active_idx], minlength=num_patches)
    state_counts = np.asarray(model.patches.states.sum(axis=0))

    assert np.array_equal(agent_counts, state_counts), (
        f"Active agents per patch {agent_counts} do not match patches.states sum {state_counts}"
    )


if __name__ == "__main__":
    for module in MEASLES_MODULES:
        print(f"Testing {module}...")
        test_vital_dynamics_single_patch(module)
        print(f"✓ {module} single patch test passed")

        test_vital_dynamics_two_patch(module)
        print(f"✓ {module} two patch test passed")

    print("Testing ABM-only regression...")
    test_infection_with_vital_dynamics_no_underflow("laser.measles.abm")
    print("✓ ABM infection+vital_dynamics underflow test passed")
