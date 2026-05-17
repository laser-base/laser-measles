import numpy as np
import polars as pl
from laser.core.migration import gravity
from pydantic import BaseModel
from pydantic import Field

from laser.measles.mixing.base import BaseMixing


class GravityParams(BaseModel):
    """Parameters for the gravity migration model.

    The gravity kernel computes migration flow as:

    $$M_{i,j} = k \\cdot p_i^{a-1} \\cdot p_j^{b} \\cdot d_{i,j}^{-c}$$

    Args:
        a (float): Population source exponent (applied as *a − 1*
            inside the kernel).
        b (float): Population destination exponent.
        c (float): Distance decay exponent — larger values suppress
            long-distance travel.
        k (float): Average trip probability (scales the overall matrix).

    **Example:**

        ```python
        from laser.measles.mixing.gravity import GravityParams

        params = GravityParams(a=1.0, b=1.0, c=2.0, k=0.01)
        ```
    """

    a: float = Field(default=1.0, description="Population source scale parameter", ge=1.0)
    b: float = Field(default=1.0, description="Population target scale parameter")
    c: float = Field(default=1.5, description="Distance exponent")
    k: float = Field(default=0.01, description="Scale parameter (avg trip probability)", ge=0, le=1)


class GravityMixing(BaseMixing):
    """Gravity migration model for spatial mixing.

    Computes a spatial mixing matrix where travel probability between
    patches is proportional to population sizes and inversely proportional
    to distance:

    $$M_{i,j} = k \\cdot p_i^{a-1} \\cdot p_j^{b} \\cdot d_{i,j}^{-c}$$

    The ``scenario`` is optional at construction time.  When attached to a
    model via ``InfectionParams(mixer=...)``, the model sets the scenario
    automatically before the mixing matrix is first computed.

    Args:
        scenario (pl.DataFrame | None): Patch data with ``pop``, ``lat``,
            and ``lon`` columns.  ``None`` when the model will set it.
        params (GravityParams | None): Gravity model parameters.  Uses
            [`GravityParams`][laser.measles.mixing.gravity.GravityParams]
            defaults if ``None``.

    **Example:**

        ```python
        from laser.measles.mixing.gravity import GravityMixing, GravityParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        mixer = GravityMixing(params=GravityParams(a=1.0, b=1.0, c=2.0, k=0.01))
        infection_params = components.InfectionParams(beta=0.8, mixer=mixer)
        model.components = [create_component(components.InfectionProcess, infection_params)]
        ```
    """

    def __init__(self, scenario: pl.DataFrame | None = None, params: GravityParams | None = None):
        if params is None:
            params = GravityParams()
        super().__init__(scenario, params)

    def get_migration_matrix(self) -> np.ndarray:
        """Compute the gravity-based migration matrix.

        Returns:
            Migration matrix of shape ``(N, N)`` where entry ``[i, j]``
                is the probability of travel from patch *i* to patch *j*.
        """
        if len(self.scenario) == 1:
            return np.array([[0.0]])
        distances = self.get_distances()
        mat = gravity(
            self.scenario["pop"].to_numpy(), distances, k=1.0, a=self.params.a - 1, b=self.params.b, c=self.params.c
        )  # TODO: find a better k?
        # normalize w/ k
        nrm = self.params.k / (np.sum(mat * self.scenario["pop"].to_numpy()[:, np.newaxis], axis=1) / self.scenario["pop"].to_numpy())
        mat *= nrm
        return mat
