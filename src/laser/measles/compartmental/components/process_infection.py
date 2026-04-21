"""
Component for simulating the SEIR infection process in the compartmental model.
"""

from typing import Any

import numpy as np
from pydantic import Field

from laser.measles.base import BaseLaserModel
from laser.measles.components import BaseInfectionParams
from laser.measles.components import BaseInfectionProcess
from laser.measles.mixing.gravity import GravityMixing
from laser.measles.utils import cast_type


class InfectionParams(BaseInfectionParams):
    """Parameters for the compartmental SEIR infection process.

    Spatial mixing is configured via the ``mixer`` parameter. Any
    :class:`~laser.measles.mixing.base.BaseMixing` subclass is accepted
    (e.g. :class:`~laser.measles.mixing.gravity.GravityMixing`,
    :class:`~laser.measles.mixing.radiation.RadiationMixing`).
    The model sets the patch scenario on the mixer automatically at
    initialisation, so passing ``scenario=`` to the mixer at construction
    is not required.

    Example::

        from laser.measles.mixing.gravity import GravityMixing, GravityParams

        infection_params = InfectionParams(
            beta=0.8,
            seasonality=0.2,
            mixer=GravityMixing(params=GravityParams(a=1.0, b=1.0, c=2.0, k=0.01)),
        )
    """

    model_config = {"arbitrary_types_allowed": True}  # noqa: RUF012

    beta: float = Field(default=1.0, description="Base transmission rate", ge=0.0)
    exp_mu: float = Field(default=6.0, description="Exposure mean", gt=0.0)
    inf_mu: float = Field(default=8.0, description="Infection mean", gt=0.0)
    seasonality: float = Field(default=0.0, description="Seasonality factor, default is no seasonality", ge=0.0, le=1.0)
    season_start: float = Field(default=0, description="Season start day (0-364)", ge=0, le=364)
    mixer: Any = Field(default_factory=lambda: GravityMixing(), description="Spatial mixing model")

    @property
    def sigma(self) -> float:
        """Progression rate from exposed to infectious (1/exposure_period)"""
        return 1 / self.exp_mu

    @property
    def gamma(self) -> float:
        """Recovery rate from infection (1/infectious_period)"""
        return 1 / self.inf_mu

    @property
    def basic_reproduction_number(self) -> float:
        """Calculate R0 = beta / gamma"""
        return self.beta / self.gamma

    @property
    def incubation_period(self) -> float:
        """Average incubation period in days"""
        return 1.0 / self.sigma

    @property
    def infectious_period(self) -> float:
        """Average infectious period in days"""
        return 1.0 / self.gamma


class InfectionProcess(BaseInfectionProcess):
    """
    Component for simulating SEIR disease progression with daily timesteps.

    This class implements a stochastic SEIR infection process that models disease transmission
    and progression through compartments. It uses daily rates and accounts for mixing between
    different population groups.

    The SEIR infection process follows these steps:

    1. Calculate force of infection based on:

       - Base transmission rate (beta)
       - Seasonal variation
       - Population mixing matrix
       - Current number of infectious individuals

    2. Stochastic transitions using binomial sampling:

       - S → E: New exposures based on force of infection
       - E → I: Progression from exposed to infectious
       - I → R: Recovery from infection

    3. Update population states for all compartments

    Parameters
    ----------
    model : object
        The simulation model containing population states and parameters
    verbose : bool, default=False
        Whether to print detailed information during execution
    params : InfectionParams | None, default=None
        Component-specific parameters. If None, will use default parameters

    Notes
    -----
    The infection process uses daily rates and seasonal transmission that varies
    sinusoidally over time with a period of 365 days.
    """

    def __init__(self, model: BaseLaserModel, params: InfectionParams | None = None, verbose: bool = False) -> None:
        super().__init__(model, verbose)

        self.params = params if params is not None else InfectionParams()

        # set the scenario for the mixing object
        self.params.mixer.scenario = model.scenario

        # per-patch new-exposure count, written every tick
        model.patches.add_scalar_property("incidence", dtype=np.int32, default=0)

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        # Get state counts: states is (4, num_patches) for [S, E, I, R]
        states = model.patches.states

        # Calculate total population per patch
        total_patch_pop = states.sum(axis=0)

        # Avoid division by zero
        total_patch_pop = np.maximum(total_patch_pop, 1)

        # Calculate prevalence of infectious individuals in each patch
        prevalence = states.I  # / total_patch_pop  # I_j / N_j

        # Calculate force of infection with seasonal variation
        seasonal_factor = 1 + self.params.seasonality * np.sin(2 * np.pi * (tick - self.params.season_start) / 365.0)
        lambda_i = (
            (self.params.beta * seasonal_factor * prevalence) @ self.params.mixer.mixing_matrix  # recall mixing is pij: i -> j
        )

        # normalize by the population of the patch
        lambda_i /= total_patch_pop

        # Stochastic transitions using binomial sampling

        # 1. S → E: New exposures
        # prob_exposure = 1 - np.exp(-lambda_i)
        prob_exposure = -1 * np.expm1(-lambda_i)
        new_exposures = cast_type(model.prng.binomial(states.S, prob_exposure), states.dtype, round=True)

        # 2. E → I: Progression to infectious
        # prob_infection = 1 - np.exp(-self.params.sigma)
        prob_infection = -1 * np.expm1(-self.params.sigma)
        new_infections = cast_type(model.prng.binomial(states.E, prob_infection), states.dtype, round=True)

        # 3. I → R: Recovery
        # prob_recovery = 1 - np.exp(-self.params.gamma)
        prob_recovery = -1 * np.expm1(-self.params.gamma)
        new_recoveries = cast_type(model.prng.binomial(states.I, prob_recovery), states.dtype, round=True)

        # Record new exposures for tracking
        model.patches.incidence[:] = new_exposures

        # Update compartments
        states.S -= new_exposures  # S decreases
        states.E += new_exposures  # E increases
        states.E -= new_infections  # E decreases
        states.I += new_infections  # I increases
        states.I -= new_recoveries  # I decreases
        states.R += new_recoveries  # R increases

        return

    # @property
    # def mixing(self) -> np.ndarray:
    #     """Returns the mixing matrix, initializing if necessary"""
    #     if self._mixing is None:
    #         self._mixing = init_gravity_diffusion(self.model.scenario, self.params.mixing_scale, self.params.distance_exponent)
    #     return self._mixing

    # @mixing.setter
    # def mixing(self, mixing: np.ndarray) -> None:
    #     """Sets the mixing matrix"""
    #     self._mixing = mixing

    # def _initialize(self, model: BaseLaserModel) -> None:
    #     """Initializes the mixing component"""
    #     self.mixing = init_gravity_diffusion(model.scenario, self.params.mixing_scale, self.params.distance_exponent)
