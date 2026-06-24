"""
Component defining the InfectionProcess, which orchestrates the transmission and disease progression of measles in a population.
"""

from typing import Any

import numpy as np
from matplotlib.figure import Figure
from pydantic import AliasChoices
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

    Spatial mixing is controlled in one of two ways:

    1. **Default gravity** — leave ``mixer`` as ``None`` and configure
       ``distance_exponent`` and ``mixing_scale``. Internally a
       :class:`~laser.measles.mixing.gravity.GravityMixing` is constructed
       using those values.
    2. **Custom mixer** — pass any mixing object (e.g. ``GravityMixing(...)``,
       ``RadiationMixing(...)``) as ``mixer=``. When set, this takes
       precedence; ``distance_exponent`` and ``mixing_scale`` are ignored.

    The model sets the patch scenario on the mixer automatically at
    initialisation, so callers don't need to assign ``mixer.scenario``
    themselves.

    Examples::

        # 1. Default gravity, tuned via the convenience knobs
        infection_params = InfectionParams(
            beta=20.0,
            distance_exponent=2.0,
            mixing_scale=0.005,
        )

        # 2. Custom mixer — e.g. radiation model
        from laser.measles.mixing.radiation import RadiationMixing
        infection_params = InfectionParams(
            beta=20.0,
            mixer=RadiationMixing(),
        )
    """

    beta: float = Field(default=1.0, description="Base transmission rate", ge=0.0)
    seasonality: float = Field(
        default=0.0,
        description=(
            "Amplitude of seasonal modulation of beta (range 0.0-1.0; e.g. 0.3 = "
            "30% amplitude, 0.0 = no seasonality). Accepts either `seasonality` "
            "or `seasonal_amplitude` on input. Pairs with `season_start`."
        ),
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("seasonality", "seasonal_amplitude"),
    )
    season_start: float = Field(default=0, description="Season start day (0-364)", ge=0, le=364)
    exp_mu: float = Field(default=6.0, description="Exposure mean (lognormal)", gt=0.0)
    exp_sigma: float = Field(default=2.0, description="Exposure sigma (lognormal)", gt=0.0)
    inf_mean: float = Field(default=8.0, description="Mean infection duration", gt=0.0)
    inf_sigma: float = Field(default=2.0, description="Shape parameter for infection duration", gt=0.0)
    distance_exponent: float = Field(default=1.5, description="Distance exponent (used only when mixer is None)", ge=0.0)
    mixing_scale: float = Field(default=0.001, description="Mixing scale (used only when mixer is None)", ge=0.0)
    mixer: Any | None = Field(
        default=None,
        description="Optional custom mixing object (GravityMixing, RadiationMixing, ...). When set, distance_exponent and mixing_scale are ignored.",
    )

    @property
    def transmission_params(self) -> TransmissionParams:
        """Build the TransmissionParams to hand to TransmissionProcess.

        If the caller supplied a ``mixer``, pass it through. Otherwise wire
        ``distance_exponent`` and ``mixing_scale`` into a default
        ``GravityMixing(GravityParams(c=..., k=...))``. The latter is the
        fix called out in #140 — passing those values to TransmissionParams
        directly silently dropped them because TransmissionParams doesn't
        declare them.
        """
        mixer = (
            self.mixer
            if self.mixer is not None
            else GravityMixing(
                params=GravityParams(c=self.distance_exponent, k=self.mixing_scale),
            )
        )
        return TransmissionParams(
            beta=self.beta,
            seasonality=self.seasonality,
            season_start=self.season_start,
            exp_mu=self.exp_mu,
            exp_sigma=self.exp_sigma,
            mixer=mixer,
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


    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.InfectionProcess, components.InfectionParams(beta=0.3)))
        ```
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

    def __call__(self, model: "ABMModel", tick: int) -> None:
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
        """Move agents at the given indices from susceptible to exposed.

        Args:
            model: The ABM model instance.
            idx: Array of agent indices to infect.
        """
        self.transmission.infect(model, idx)

    @property
    def mixing_matrix(self) -> np.ndarray:
        """The spatial mixing matrix the wrapped TransmissionProcess is using.

        Convenience accessor that walks down to the live mixer instance:
        ``self.transmission.params.mixer.mixing_matrix``. Once the model has
        run, ``mixer.scenario`` is set and the matrix is lazily computed on
        first access. Shape is ``(n_patches, n_patches)``.

        Provided here so code that has a handle on the InfectionProcess
        (e.g. ``model.get_instance("InfectionProcess")[0]``) can get the
        matrix in one hop, without knowing that TransmissionProcess is
        nested inside as a sub-component rather than registered separately.
        """
        return self.transmission.params.mixer.mixing_matrix

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
