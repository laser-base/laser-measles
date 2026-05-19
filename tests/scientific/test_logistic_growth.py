"""
SI model with logistic growth:
I(t) = pop_size / (1 + (pop_size / i0 - 1) * np.exp(-beta * (t - t0)))

Solves for the time at which the number of infected individuals is half the population size:
t_2 = 1 / beta * np.log(pop_size / i0 - 1)

"""
# ruff: noqa: PT006

import importlib

import numpy as np
import polars as pl
import pytest
from laser.core import PropertySet

import laser.measles as lm
from laser.measles import MEASLES_MODULES
from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase

# drop ABM, TODO: create SI conversion for the module
MEASLES_MODULES = [module for module in MEASLES_MODULES if module != "laser.measles.abm"]

SEED = 42
RNG = np.random.default_rng(SEED)


def SI_logistic_half_life(pop_size: int, beta: float, i0: int = 1) -> float:
    """
    Solves for the time at which the number of infected individuals is half the population size.
    """
    return 1 / beta * np.log(pop_size / i0 - 1)


class ConvertToSI(BasePhase):
    """
    Converts SEIR model to SI by removing E and R compartments.
    Works for both biweekly and compartmental models.
    """

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        states = model.patches.states
        if states.shape[0] == 3:  # Biweekly: S, I, R
            states.I += states.R  # Move R to I
            states.R = 0
        elif states.shape[0] == 4:  # Compartmental: S, E, I, R
            states.I += states.E  # Move E to I
            states.E = 0
            states.I += states.R  # Move R to I
            states.R = 0


def single_test(MeaslesModel, problem_params, measles_module):
    scenario = pl.DataFrame(
        {
            "id": ["node_0"],
            "pop": [problem_params["population_size"]],
            "lat": [40.0],
            "lon": [4.0],
            "mcv1": [0.0],
        }
    )

    # Create model-specific parameters
    if "biweekly" in measles_module:
        num_ticks = int(np.ceil(problem_params["num_days"] / 365 * 26))
    else:
        num_ticks = problem_params["num_days"]

    params = MeaslesModel.Params(num_ticks=num_ticks, start_time="2001-01", seed=RNG.integers(1000000))

    # Create model
    model = MeaslesModel.Model(params=params, scenario=scenario)

    transmission_params = MeaslesModel.components.InfectionParams(beta=problem_params["beta"])
    seeding_params = MeaslesModel.components.InfectionSeedingParams(num_infections=problem_params["initial_infections"])
    model.components = [
        MeaslesModel.components.StateTracker,
        lm.create_component(MeaslesModel.components.InfectionSeedingProcess, params=seeding_params),
        lm.create_component(MeaslesModel.components.InfectionProcess, params=transmission_params),
        ConvertToSI,
    ]

    # run model
    model.run()

    # Find StateTracker instance
    state_tracker = model.get_instance("StateTracker")[0]

    # Time to half the population is infectious
    t_2_theory = SI_logistic_half_life(
        pop_size=problem_params["population_size"], beta=problem_params["beta"], i0=problem_params["initial_infections"]
    )
    t_2_simulated = np.interp(
        0.5 * problem_params["population_size"], state_tracker.I, model.params.time_step_days * np.arange(model.params.num_ticks)
    )

    rel_error = (t_2_simulated - t_2_theory) / t_2_theory

    return rel_error


@pytest.mark.slow
@pytest.mark.parametrize("measles_module,num_reps", [(module, 5) for module in MEASLES_MODULES])
def test_no_vital_dynamics(measles_module, num_reps):
    """
    Test logistic growth for SI model with no vital dynamics.
    https://github.com/laser-base/laser-generic/blob/main/notebooks/01_SI_nobirths_logistic_growth.ipynb
    """
    MeaslesModel = importlib.import_module(measles_module)

    problem_params = PropertySet(
        {
            "population_size": 1_000_000,
            "beta": 2 / 14,
            "num_days": 730,  # in days
            "initial_infections": 1,
        }
    )

    rel_errors = []
    for _ in range(num_reps):
        rel_errors.append(single_test(MeaslesModel, problem_params, measles_module))

    print(f"Relative error: {np.mean(rel_errors):.4f} ± {np.std(rel_errors):.4f}")
    # Different error tolerances for different model types
    if "compartmental" in measles_module:
        assert np.mean(rel_errors) < 0.15, f"Relative error: {np.mean(rel_errors):.4f} (max 0.15)"
    elif "abm" in measles_module:
        assert np.mean(rel_errors) < 0.15, f"Relative error: {np.mean(rel_errors):.4f} (max 0.15)"
    elif "biweekly" in measles_module:
        assert np.mean(rel_errors) < 1.0, f"Relative error: {np.mean(rel_errors):.4f} (max 1.0)"


if __name__ == "__main__":
    for module in MEASLES_MODULES:
        print(f"Testing {module}...")
        test_no_vital_dynamics(module, num_reps=5)
        print(f"✓ {module} test passed")
