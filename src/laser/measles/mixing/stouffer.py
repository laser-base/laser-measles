import numpy as np
import polars as pl
from laser.core.migration import stouffer
from pydantic import BaseModel
from pydantic import Field

from laser.measles.mixing.base import BaseMixing


class StoufferParams(BaseModel):
    """Parameters for the Stouffer migration model.

    Attributes:
        include_home: Whether to include home in the migration matrix
        k: Scale parameter (avg trip probability)

    **Example:**

        ```python
        from laser.measles.mixing.stouffer import StoufferParams

        params = StoufferParams(k=0.02, include_home=True, a=1.0, b=1.0)
        ```
    """

    include_home: bool = Field(default=True, description="Whether to include home in the migration matrix")
    k: float = Field(default=0.01, description="Scale parameter (avg trip probability)", ge=0, le=1)
    a: float = Field(default=1.0, description="Population source exponent")
    b: float = Field(default=1.0, description="Population target exponent")


class StoufferMixing(BaseMixing):
    """Stouffer intervening-opportunities migration model.

    Long-distance travel is suppressed by the cumulative population of
    patches between origin and destination (intervening opportunities):

    $$M_{i,j} = k \\, p_i^{a} \\sum_j \\left(\\frac{p_j}{\\sum_{k \\in \\Omega(i,j)} p_k}\\right)^{b}$$

    Args:
        scenario (pl.DataFrame | None): Patch data.  ``None`` when the
            model will set it automatically.
        params (StoufferParams | None): Model parameters.  Uses
            [`StoufferParams`][laser.measles.mixing.stouffer.StoufferParams]
            defaults if ``None``.

    **Example:**

        ```python
        from laser.measles.mixing.stouffer import StoufferMixing, StoufferParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        mixer = StoufferMixing(params=StoufferParams(k=0.01))
        infection_params = components.InfectionParams(beta=0.8, mixer=mixer)
        model.add_component(create_component(components.InfectionProcess, infection_params))
        ```

    The ``include_home`` model parameter is configured via :class:`StoufferParams`.
    """

    def __init__(self, scenario: pl.DataFrame | None = None, params: StoufferParams | None = None):
        if params is None:
            params = StoufferParams()
        super().__init__(scenario, params)

    def get_migration_matrix(self) -> np.ndarray:
        """Compute the Stouffer migration matrix.

        Returns:
            Migration matrix of shape ``(N, N)``.
        """
        if len(self.scenario) == 1:
            return np.array([[0.0]])
        distances = self.get_distances()
        mat = stouffer(
            self.scenario["pop"].to_numpy(), distances, k=1.0, include_home=self.params.include_home, a=self.params.a, b=self.params.b
        )  # TODO: find a better k?
        # normalize w/ k
        nrm = self.params.k / (np.sum(mat * self.scenario["pop"].to_numpy()[:, np.newaxis], axis=1) / self.scenario["pop"].to_numpy())
        mat *= nrm
        return mat
