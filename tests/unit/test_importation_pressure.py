import importlib

import numpy as np
import polars as pl
import pytest
from pydantic import ValidationError

import laser.measles as lm
from laser.measles import MEASLES_MODULES
from laser.measles.abm import components
from laser.measles.components import create_component

VERBOSE = False
SEED = 42


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_importation_pressure_single_patch(measles_module):
    """Test the infection process in a single patch."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=100, verbose=VERBOSE, seed=SEED))
    model.components = [
        MeaslesModel.components.ImportationPressureProcess,
        lm.create_component(MeaslesModel.components.InfectionProcess, MeaslesModel.components.InfectionParams(beta=1.0)),
    ]
    model.run()
    if VERBOSE:
        print(
            f"Final fraction recovered: {100 * model.patches.states.R.sum() / scenario['pop'].sum():.2f}% (N={model.patches.states.R.sum()})"
        )
    assert model.patches.states.R.sum() > 1
    assert np.sum(model.patches.states) == np.sum(model.scenario["pop"].to_numpy())


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_importation_pressure_two_patch(measles_module):
    """Test the infection process in two patches."""
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=100, verbose=VERBOSE, seed=SEED))
    model.components = [
        MeaslesModel.components.ImportationPressureProcess,
        lm.create_component(MeaslesModel.components.InfectionProcess, MeaslesModel.components.InfectionParams(beta=0.0)),
    ]
    model.run()
    if VERBOSE:
        print(
            f"Final fraction recovered: {100 * model.patches.states.R.sum() / scenario['pop'].sum():.2f}% (N={model.patches.states.R.sum()})"
        )
    assert np.all(model.patches.states.R >= 1)
    assert model.patches.states.R.sum() > 1
    assert np.all(np.equal(model.patches.states.sum(axis=0), scenario["pop"].to_numpy()))


@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_importation_with_vital_dynamics(measles_module):
    """Regression test: ImportationPressureProcess should not infect inactive (unborn) agents.

    Without filtering by `active`, phantom agents beyond people.count get infected,
    causing S[0] to underflow (uint32 wrap) and VitalDynamicsProcess to compute
    massive birth counts that exhaust array capacity around tick 32-50.

    Uses beta=0.0 to disable community transmission and isolate the importation fix.
    """
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.two_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=50, verbose=VERBOSE, seed=SEED))
    model.components = [
        MeaslesModel.components.VitalDynamicsProcess,
        MeaslesModel.components.ImportationPressureProcess,
        lm.create_component(MeaslesModel.components.InfectionProcess, MeaslesModel.components.InfectionParams(beta=0.0)),
    ]
    model.run()

    # S values should remain reasonable (no uint32 underflow)
    assert np.all(model.patches.states.S < 1_000_000), f"S values look like uint32 underflow: {model.patches.states.S}"

    # Population conservation: state counts should equal active agent count
    active_count = model.people.active[: model.people.count].sum()
    state_total = np.sum(model.patches.states)
    assert state_total == active_count, f"State total {state_total} != active count {active_count}"


def _four_patch_scenario():
    return pl.DataFrame(
        {
            "id": ["patch_0", "patch_1", "patch_2", "patch_3"],
            "lat": [0.0, 0.0, 0.0, 0.0],
            "lon": [0.0, 1.0, 2.0, 3.0],
            "pop": [1000, 1000, 1000, 1000],
            "mcv1": [0.0, 0.0, 0.0, 0.0],
        }
    )


NON_ABM_MODULES = ["laser.measles.compartmental", "laser.measles.biweekly"]


def _build_model(measles_module, importation_rate, num_ticks=1, seed=123):
    """Generic model builder for compartmental and biweekly model types."""
    module = importlib.import_module(measles_module)
    scenario = _four_patch_scenario()
    model = module.Model(
        module.BaseScenario(scenario),
        module.Params(num_ticks=num_ticks, seed=seed),
    )
    imp_params = module.components.process_importation_pressure.ImportationPressureParams(crude_importation_rate=importation_rate)
    model.components = [create_component(module.components.ImportationPressureProcess, imp_params)]
    return model


def _build_abm_model(measles_module, importation_rate, num_ticks=1, seed=123):
    module = importlib.import_module(measles_module)
    scenario = _four_patch_scenario()

    model = module.ABMModel(
        scenario,
        module.ABMParams(num_ticks=num_ticks, seed=seed, start_time="2000-01"),
    )

    imp_params = module.components.process_importation_pressure.ImportationPressureParams(crude_importation_rate=importation_rate)

    model.components = [
        module.components.NoBirthsProcess,
        create_component(module.components.ImportationPressureProcess, imp_params),
        module.components.InfectionProcess,
        module.components.StateTracker,
    ]
    return model


def _run_and_get_importation_instance(model):
    model.run()
    return model.get_instance("ImportationPressureProcess")[0]


def _count_non_susceptible_by_patch(model):
    susceptible_state = model.params.states.index("S")
    people = model.people
    return [int(((people.patch_id == i) & (people.state != susceptible_state)).sum()) for i in range(4)]


# -----------------------------------------------------------------------------
# 1. Scalar rate applies to all patches
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_scalar_importation_rate_applies_to_all_patches(measles_module):
    model = _build_abm_model(measles_module, 5.0, num_ticks=1)
    imp = _run_and_get_importation_instance(model)
    assert imp.patch_rates_per_year_per_1k.tolist() == [5.0, 5.0, 5.0, 5.0]


# -----------------------------------------------------------------------------
# 2. List rate resolves by patch order
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_list_importation_rate_resolves_by_patch_order(measles_module):
    model = _build_abm_model(measles_module, [1.0, 2.0, 3.0, 4.0], num_ticks=1)
    imp = _run_and_get_importation_instance(model)
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 2.0, 3.0, 4.0]


# -----------------------------------------------------------------------------
# 3. Dict rate resolves by patch id
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_dict_importation_rate_resolves_by_patch_id(measles_module):
    model = _build_abm_model(measles_module, {"patch_0": 1.0, "patch_2": 3.0}, num_ticks=1)
    imp = _run_and_get_importation_instance(model)
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 0.0, 3.0, 0.0]


# -----------------------------------------------------------------------------
# 4. Wrong list length raises
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_importation_rate_list_wrong_length_raises(measles_module):
    model = _build_abm_model(measles_module, [1.0, 2.0, 3.0], num_ticks=1)
    with pytest.raises(ValueError, match="does not match number of patches"):
        model.run()


# -----------------------------------------------------------------------------
# 5. Unknown dict patch id raises
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_importation_rate_dict_unknown_patch_id_raises(measles_module):
    model = _build_abm_model(measles_module, {"patch_999": 5.0}, num_ticks=1)
    with pytest.raises(ValueError, match="Unknown patch ids"):
        model.run()


# -----------------------------------------------------------------------------
# 6. Negative values raise
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_rate",
    [
        -1.0,
        [1.0, -1.0, 0.0, 0.0],
        {"patch_0": 1.0, "patch_1": -1.0},
        np.array([-1.0, 0.0, 0.0, 0.0]),
        (-1.0, 0.0, 0.0, 0.0),
    ],
)
def test_negative_importation_rates_raise_validation_error(bad_rate):
    with pytest.raises(ValidationError):
        components.process_importation_pressure.ImportationPressureParams(crude_importation_rate=bad_rate)


# -----------------------------------------------------------------------------
# 6b. Invalid types raise a useful error
# -----------------------------------------------------------------------------
def test_invalid_importation_rate_type_raises():
    with pytest.raises((ValidationError, TypeError), match=r"(?i)(float|sequence|dict|type)"):
        components.process_importation_pressure.ImportationPressureParams(crude_importation_rate="fast")


# -----------------------------------------------------------------------------
# 6c. Numpy arrays and tuples are valid sequence inputs
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_numpy_array_importation_rate(measles_module):
    model = _build_abm_model(measles_module, np.array([1.0, 2.0, 3.0, 4.0]), num_ticks=1)
    imp = _run_and_get_importation_instance(model)
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_tuple_importation_rate(measles_module):
    model = _build_abm_model(measles_module, (1.0, 2.0, 3.0, 4.0), num_ticks=1)
    imp = _run_and_get_importation_instance(model)
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 2.0, 3.0, 4.0]


# -----------------------------------------------------------------------------
# 6d. Importation draws from susceptibles first (not all agents)
#
# Regression: old code sampled from all agents then filtered to S, so a
# 90%-immune patch would only receive ~10% of the intended importation even
# when enough susceptibles existed to fill the quota.  The fix filters to
# susceptibles before sampling.
# -----------------------------------------------------------------------------
def test_importation_draws_from_susceptibles_in_partially_immune_patch():
    m = importlib.import_module("laser.measles.abm")
    scenario = pl.DataFrame({"id": ["p0"], "lat": [0.0], "lon": [0.0], "pop": [1000], "mcv1": [0.0]})
    # Rate chosen so the binomial draw (~550 from 1000 agents) exceeds n_susceptible (100)
    # but is well below n_total (1000).  Old code would sample from all agents and infect
    # ~55 susceptibles; the fix samples from susceptibles first and infects all 100.
    imp_params = m.components.process_importation_pressure.ImportationPressureParams(crude_importation_rate=200_000.0)
    model = m.ABMModel(scenario, m.ABMParams(num_ticks=0, seed=42, start_time="2000-01"))
    model.components = [
        m.components.NoBirthsProcess,
        create_component(m.components.ImportationPressureProcess, imp_params),
        m.components.InfectionProcess,
    ]
    model.run()

    S_idx = model.params.states.index("S")
    E_idx = model.params.states.index("E")
    R_idx = model.params.states.index("R")
    n = model.people.count
    n_susceptible = 100  # leave only 10% susceptible

    # Set 90% of agents to recovered (immune)
    model.people.state[: n - n_susceptible] = R_idx
    model.patches.states.S[0] = n_susceptible
    model.patches.states.R[0] = n - n_susceptible

    imp = model.get_instance("ImportationPressureProcess")[0]
    imp(model, 0)

    exposed = int((model.people.state[:n] == E_idx).sum())
    remaining_s = int((model.people.state[:n] == S_idx).sum())

    # All susceptibles should have been infected — none left behind
    assert remaining_s == 0, f"Expected 0 susceptibles remaining, got {remaining_s}"
    assert exposed == n_susceptible, f"Expected {n_susceptible} exposed, got {exposed}"


# -----------------------------------------------------------------------------
# 7. Only one nonzero patch gets imports
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
def test_patch_specific_importation_targets_only_first_patch(measles_module):
    model = _build_abm_model(measles_module, [1000.0, 0.0, 0.0, 0.0], num_ticks=1, seed=123)
    imp = _run_and_get_importation_instance(model)

    assert imp.patch_rates_per_year_per_1k.tolist() == [1000.0, 0.0, 0.0, 0.0]

    non_susceptible_by_patch = _count_non_susceptible_by_patch(model)
    assert non_susceptible_by_patch[0] > 0
    assert non_susceptible_by_patch[1] == 0
    assert non_susceptible_by_patch[2] == 0
    assert non_susceptible_by_patch[3] == 0


# -----------------------------------------------------------------------------
# 8. Each node can be targeted individually
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", ["laser.measles.abm"])
@pytest.mark.parametrize("target_patch", [0, 1, 2, 3])
def test_each_patch_can_be_targeted_individually(measles_module, target_patch):
    rates = [0.0, 0.0, 0.0, 0.0]
    rates[target_patch] = 1000.0

    model = _build_abm_model(measles_module, rates, num_ticks=1, seed=123)
    imp = _run_and_get_importation_instance(model)

    expected = [0.0, 0.0, 0.0, 0.0]
    expected[target_patch] = 1000.0
    assert imp.patch_rates_per_year_per_1k.tolist() == expected

    non_susceptible_by_patch = _count_non_susceptible_by_patch(model)

    for i in range(4):
        if i == target_patch:
            assert non_susceptible_by_patch[i] > 0
        else:
            assert non_susceptible_by_patch[i] == 0


# -----------------------------------------------------------------------------
# Compartmental / biweekly: per-patch rate initialization
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_scalar_importation_rate_applies_to_all_patches_non_abm(measles_module):
    model = _build_model(measles_module, 5.0, num_ticks=1)
    model.run()
    imp = model.get_instance("ImportationPressureProcess")[0]
    assert imp.patch_rates_per_year_per_1k.tolist() == [5.0, 5.0, 5.0, 5.0]


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_list_importation_rate_resolves_by_patch_order_non_abm(measles_module):
    model = _build_model(measles_module, [1.0, 2.0, 3.0, 4.0], num_ticks=1)
    model.run()
    imp = model.get_instance("ImportationPressureProcess")[0]
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_dict_importation_rate_resolves_by_patch_id_non_abm(measles_module):
    model = _build_model(measles_module, {"patch_0": 1.0, "patch_2": 3.0}, num_ticks=1)
    model.run()
    imp = model.get_instance("ImportationPressureProcess")[0]
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 0.0, 3.0, 0.0]


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_importation_rate_list_wrong_length_raises_non_abm(measles_module):
    model = _build_model(measles_module, [1.0, 2.0, 3.0], num_ticks=1)
    with pytest.raises(ValueError, match="does not match number of patches"):
        model.run()


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_importation_rate_dict_unknown_patch_id_raises_non_abm(measles_module):
    model = _build_model(measles_module, {"patch_999": 5.0}, num_ticks=1)
    with pytest.raises(ValueError, match="Unknown patch ids"):
        model.run()


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
@pytest.mark.parametrize(
    "bad_rate",
    [
        -1.0,
        [1.0, -1.0, 0.0, 0.0],
        {"patch_0": 1.0, "patch_1": -1.0},
        np.array([-1.0, 0.0, 0.0, 0.0]),
        (-1.0, 0.0, 0.0, 0.0),
    ],
)
def test_negative_importation_rates_raise_validation_error_non_abm(measles_module, bad_rate):
    module = importlib.import_module(measles_module)
    with pytest.raises(ValidationError):
        module.components.process_importation_pressure.ImportationPressureParams(crude_importation_rate=bad_rate)


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_numpy_array_importation_rate_non_abm(measles_module):
    model = _build_model(measles_module, np.array([1.0, 2.0, 3.0, 4.0]), num_ticks=1)
    model.run()
    imp = model.get_instance("ImportationPressureProcess")[0]
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.parametrize("measles_module", NON_ABM_MODULES)
def test_tuple_importation_rate_non_abm(measles_module):
    model = _build_model(measles_module, (1.0, 2.0, 3.0, 4.0), num_ticks=1)
    model.run()
    imp = model.get_instance("ImportationPressureProcess")[0]
    assert imp.patch_rates_per_year_per_1k.tolist() == [1.0, 2.0, 3.0, 4.0]


if __name__ == "__main__":
    pytest.main([__file__ + "::test_importation_pressure_two_patch", "-v", "-s"])
