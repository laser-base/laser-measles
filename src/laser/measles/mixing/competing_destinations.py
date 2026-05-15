import numpy as np
import polars as pl
from laser.core.migration import competing_destinations
from pydantic import BaseModel
from pydantic import Field

from laser.measles.mixing.base import BaseMixing


class CompetingDestinationsParams(BaseModel):
    """Parameters for the competing-destinations mixing model.

    Extends the gravity kernel with a correction factor that penalises
    destinations surrounded by many other attractive alternatives.

    Args:
        a (float): Population source exponent.
        b (float): Population destination exponent.
        c (float): Distance decay exponent.
        k (float): Average trip probability.
        delta (float): Destination-competition exponent — negative values
            penalise destinations with many nearby competitors.

    **Example:**

        ```python
        from laser.measles.mixing.competing_destinations import CompetingDestinationsParams

        params = CompetingDestinationsParams(a=1.0, b=1.0, c=1.5, k=0.01, delta=-0.5)
        ```
    """

    a: float = Field(default=1.0, description="Population source scale parameter", ge=1.0)
    b: float = Field(default=1.0, description="Population target scale parameter")
    c: float = Field(default=1.5, description="Distance exponent")
    k: float = Field(default=0.01, description="Scale parameter (avg trip probability)", ge=0, le=1)
    delta: float = Field(default=0.0, description="Destination selection parameter")


class CompetingDestinationsMixing(BaseMixing):
    """Competing-destinations migration model for spatial mixing.

    Extends the gravity kernel with a correction that accounts for the
    attractiveness of alternative destinations:

    $$M_{i,j} = k \\frac{p_i^{a-1} \\, p_j^{b}}{d_{i,j}^{c}}
    \\left(\\sum_{k \\ne i,j} \\frac{p_k^{b}}{d_{ik}^{c}}\\right)^{\\delta}$$

    When $\\delta < 0$, destinations that are surrounded by many other
    attractive locations receive *less* travel — the nearby alternatives
    "compete" for travellers.

    Args:
        scenario (pl.DataFrame | None): Patch data.  ``None`` when the
            model will set it automatically.
        params (CompetingDestinationsParams | None): Model parameters.

    **Example:**

        ```python
        from laser.measles.mixing.competing_destinations import (
            CompetingDestinationsMixing, CompetingDestinationsParams,
        )
        from laser.measles.compartmental import components
        from laser.measles import create_component

        mixer = CompetingDestinationsMixing(
            params=CompetingDestinationsParams(k=0.01, delta=-0.5),
        )
        infection_params = components.InfectionParams(beta=0.8, mixer=mixer)
        model.add_component(create_component(components.InfectionProcess, infection_params))
        ```
    """

    def __init__(self, scenario: pl.DataFrame | None = None, params: CompetingDestinationsParams | None = None):
        if params is None:
            params = CompetingDestinationsParams()
        super().__init__(scenario, params)

    def get_migration_matrix(self) -> np.ndarray:
        """Compute the competing-destinations migration matrix.

        Returns:
            Migration matrix of shape ``(N, N)``.
        """
        if len(self.scenario) == 1:
            return np.array([[0.0]])
        distances = self.get_distances()
        mat = competing_destinations(
            self.scenario["pop"].to_numpy(),
            distances,
            k=1.0,
            a=self.params.a - 1,
            b=self.params.b,
            c=self.params.c,
            delta=self.params.delta,
        )  # TODO: find a better k?
        # normalize w/ k
        nrm = self.params.k / (np.sum(mat * self.scenario["pop"].to_numpy()[:, np.newaxis], axis=1) / self.scenario["pop"].to_numpy())
        mat *= nrm
        return mat
