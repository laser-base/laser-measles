from abc import ABC
from abc import abstractmethod
from typing import TypeVar

import numpy as np
from pydantic import BaseModel
from pydantic import Field

from laser.measles.base import BasePhase
from laser.measles.utils import cast_type

ModelType = TypeVar("ModelType")


class BaseVitalDynamicsParams(BaseModel):
    """Parameters specific to vital dynamics."""

    crude_birth_rate: float = Field(default=20.0, description="Annual crude birth rate per 1000 population", ge=0.0)
    crude_death_rate: float = Field(default=8.0, description="Annual crude death rate per 1000 population", ge=0.0)
    mcv1_efficacy: float = Field(
        default=0.9,
        description="Efficacy of routine MCV1 vaccination for newborns. This only applies to births processed by VitalDynamicsProcess, not the existing population.",
        ge=0.0,
        le=1.0,
    )


class BaseVitalDynamicsProcess(BasePhase, ABC):
    """
    Phase for simulating the vital dynamics in the model with MCV1.

    This phase handles the simulation of births and deaths in the population model along
    with routine vaccination (MCV1).

    .. warning::

        The ``mcv1`` scenario parameter **only vaccinates newborns** at each tick.
        It does **not** immunize the existing population. In short simulations
        (< 5 years), this produces negligible population-level immunity changes.

        To model a population with pre-existing vaccine-derived immunity, either:

        - Use ``InitializeEquilibriumStatesProcess`` to set an appropriate S/R
          split at the start of the simulation, or
        - Directly set ``states.S`` and ``states.R`` before running.
        - Use ``SIACalendarProcess`` for discrete campaign-based vaccination.

        See the *Vaccination Modeling* tutorial (``docs/tutorials/tut_vaccination.py``)
        for detailed examples of each approach.

    Parameters
    ----------
    model : object
        The simulation model containing nodes, states, and parameters
    verbose : bool, default=False
        Whether to print verbose output during simulation
    params : VitalDynamicsParams | None, default=None
        Component-specific parameters. If None, will use default parameters

    Notes
    -----
    - Birth rates are calculated per tick
    - MCV1 coverage is applied only to newborns; expect 5-10+ years of simulation
      time before routine immunization significantly shifts population-level immunity
    """

    def __init__(self, model, verbose: bool = False, params: BaseVitalDynamicsParams | None = None) -> None:
        super().__init__(model, verbose)
        if params is None:
            params = BaseVitalDynamicsParams()
        self.params = params

    @property
    def lambda_birth(self) -> float:
        """birth rate per tick"""
        return (1 + self.params.crude_birth_rate / 1000) ** (1 / 365 * self.model.params.time_step_days) - 1

    @property
    def mu_death(self) -> float:
        """death rate per tick"""
        return (1 + self.params.crude_death_rate / 1000) ** (1 / 365 * self.model.params.time_step_days) - 1

    def __call__(self, model, tick: int) -> None:
        # state counts
        states = model.patches.states  # num_compartments x num_patches

        # Vital dynamics
        population = states.sum(axis=0)
        avg_births = population * self.lambda_birth
        vaccinated_births = cast_type(
            model.prng.poisson(avg_births * np.array(model.scenario["mcv1"]) * self.params.mcv1_efficacy), states.dtype
        )  # vaccinated AND protected
        unvaccinated_births = cast_type(
            model.prng.poisson(avg_births * (1 - np.array(model.scenario["mcv1"]) * self.params.mcv1_efficacy)), states.dtype
        )

        avg_deaths = states * self.mu_death
        deaths = cast_type(model.prng.poisson(avg_deaths), states.dtype)  # number of deaths

        states.S += unvaccinated_births  # add births to S
        states.R += vaccinated_births  # add births to R
        states -= deaths  # remove deaths from each compartment

        # make sure that all states >= 0
        np.maximum(states, 0, out=states)

        # Record per-patch births/deaths for tracking components (no-op if properties absent)
        if hasattr(model.patches, "births"):
            model.patches.births[:] = cast_type(unvaccinated_births + vaccinated_births, np.uint32)
        if hasattr(model.patches, "deaths"):
            model.patches.deaths[:] = cast_type(deaths.sum(axis=0), np.uint32)

    @abstractmethod
    def calculate_capacity(self, model) -> int:
        """
        Calculate the capacity of the model.
        """
        raise NotImplementedError("No capacity for this model")
