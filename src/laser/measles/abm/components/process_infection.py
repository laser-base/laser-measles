"""
Component defining the InfectionProcess, which orchestrates the transmission and disease progression of measles in a population.
"""

import numpy as np
from matplotlib.figure import Figure
from pydantic import Field

from laser.measles.abm.model import ABMModel
from laser.measles.components import BaseInfectionParams
from laser.measles.components import BaseInfectionProcess
from laser.measles.mixing.gravity import GravityMixing
from laser.measles.mixing.gravity import GravityParams

from .process_disease import DiseaseParams
from .process_disease import DiseaseProcess
from .process_transmission import TransmissionParams
from .process_transmission import TransmissionProcess


class InfectionParams(BaseInfectionParams):
    """Combined parameters for ABM transmission and disease processes.

    Spatial mixing strength is controlled via ``distance_exponent`` and
    ``mixing_scale``, which configure the default
    :class:`~laser.measles.mixing.gravity.GravityMixing` model used
    internally. The model sets the patch scenario on the mixer automatically
    at initialisation.

    .. note::

        Unlike the compartmental :class:`InfectionParams
        <laser.measles.compartmental.components.process_infection.InfectionParams>`,
        this class does not currently accept a ``mixer=`` argument. To use
        a custom mixing model or non-default gravity parameters, configure
        ``distance_exponent`` and ``mixing_scale`` here, or construct a
        :class:`~laser.measles.abm.components.process_transmission.TransmissionProcess`
        directly with a custom
        :class:`~laser.measles.abm.components.process_transmission.TransmissionParams`.

    Example::

        # Control gravity mixing decay and scale via InfectionParams
        infection_params = InfectionParams(
            beta=20.0,
            seasonality=0.0,
            distance_exponent=2.0,  # stronger distance decay
            mixing_scale=0.005,     # lower overall mixing rate
        )
    """

    beta: float = Field(default=1.0, description="Base transmission rate", ge=0.0)
    seasonality: float = Field(default=0.0, description="Seasonality factor", ge=0.0, le=1.0)
    season_start: float = Field(default=0, description="Season start day (0-364)", ge=0, le=364)
    exp_mu: float = Field(default=6.0, description="Exposure mean (lognormal)", gt=0.0)
    exp_sigma: float = Field(default=2.0, description="Exposure sigma (lognormal)", gt=0.0)
    inf_mean: float = Field(default=8.0, description="Mean infection duration", gt=0.0)
    inf_sigma: float = Field(default=2.0, description="Shape parameter for infection duration", gt=0.0)
    distance_exponent: float = Field(default=1.5, description="Distance exponent", ge=0.0)
    mixing_scale: float = Field(default=0.001, description="Mixing scale", ge=0.0)

    @property
    def transmission_params(self) -> TransmissionParams:
        """Extract transmission-specific parameters.

        Wires user-facing ``distance_exponent`` and ``mixing_scale`` into the
        default ``GravityMixing`` instance.
        """
        return TransmissionParams(
            beta=self.beta,
            seasonality=self.seasonality,
            season_start=self.season_start,
            exp_mu=self.exp_mu,
            exp_sigma=self.exp_sigma,
            mixer=GravityMixing(params=GravityParams(c=self.distance_exponent, k=self.mixing_scale)),
        )

    @property
    def disease_params(self) -> DiseaseParams:
        """Extract disease-specific parameters."""
        return DiseaseParams(inf_mean=self.inf_mean, inf_sigma=self.inf_sigma)


class InfectionProcess(BaseInfectionProcess):
    """
    Combined infection process that orchestrates transmission and disease progression.

    This component provides a unified interface for both disease transmission
    (handled by TransmissionProcess) and disease progression through states
    (handled by DiseaseProcess), similar to the biweekly model's InfectionProcess
    but for agent-based modeling.
    """

    def __init__(self, model: ABMModel, params: InfectionParams | None = None) -> None:
        """
        Initialize the combined infection process.

        Args:
            model: The model object that contains the patches and parameters.
            params: Combined parameters for both transmission and disease processes.
        """
        super().__init__(model)

        self.params = params if params is not None else InfectionParams()

        # Initialize sub-components
        self.transmission = TransmissionProcess(model, self.params.transmission_params)
        self.disease = DiseaseProcess(model, self.params.disease_params)

    def __call__(self, model, tick: int) -> None:
        """
        Execute both transmission and disease progression for the given tick.

        Args:
            model: The model object containing the population, patches, and parameters.
            tick: The current time step in the simulation.
        """
        # First handle disease progression (exposed -> infectious -> recovered)
        self.disease(model, tick)

        # Then handle transmission (susceptible -> exposed)
        self.transmission(model, tick)

    def infect(self, model: ABMModel, idx: np.ndarray) -> None:
        self.transmission.infect(model, idx)

    def plot(self, fig: Figure | None = None):
        """
        Plot cases and incidence using the transmission component's plotting functionality.

        Args:
            fig: A Matplotlib Figure object to plot on. If None, a new figure is created.
        """
        yield from self.transmission.plot(fig)

    def _initialize(self, model: ABMModel) -> None:
        self.transmission._initialize(model)
        self.disease._initialize(model)
