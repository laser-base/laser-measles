import numpy as np
import polars as pl
from laser.core.migration import radiation
from pydantic import BaseModel
from pydantic import Field

from laser.measles.mixing.base import BaseMixing


class RadiationParams(BaseModel):
    """Parameters for the radiation migration model.

    Attributes:
        include_home: Whether to include home in the migration matrix
        k: Scale parameter (avg trip probability)

    **Example:**

        ```python
        from laser.measles.mixing.radiation import RadiationParams

        params = RadiationParams(k=0.02, include_home=True)
        ```
    """

    include_home: bool = Field(default=True, description="Whether to include home in the migration matrix")
    k: float = Field(default=0.01, description="Scale parameter (avg trip probability)", ge=0, le=1)


class RadiationMixing(BaseMixing):
    """Radiation migration model for spatial mixing.

    Outbound migration from origin *i* to destination *j* is enhanced by
    the destination population and absorbed by the density of nearer
    destinations (intervening opportunities):

    $$M_{i,j} = k \\frac{p_i \\, p_j}{(p_i + s_{ij})(p_i + p_j + s_{ij})}$$

    where $s_{ij} = \\sum_{k \\in \\Omega(i,j)} p_k$ is the total population
    of patches closer to *i* than *j*.

    Args:
        scenario (pl.DataFrame | None): Patch data.  ``None`` when the
            model will set it automatically.
        params (RadiationParams | None): Model parameters.  Uses
            [`RadiationParams`][laser.measles.mixing.radiation.RadiationParams]
            defaults if ``None``.

    **Example:**

        ```python
        from laser.measles.mixing.radiation import RadiationMixing, RadiationParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        mixer = RadiationMixing(params=RadiationParams(k=0.01))
        infection_params = components.InfectionParams(beta=0.8, mixer=mixer)
        model.add_component(create_component(components.InfectionProcess, infection_params))
        ```

    The ``include_home`` and ``k`` model parameters are configured via
    :class:`RadiationParams`.
    """

    def __init__(self, scenario: pl.DataFrame | None = None, params: RadiationParams | None = None):
        if params is None:
            params = RadiationParams()
        super().__init__(scenario, params)

    def get_migration_matrix(self) -> np.ndarray:
        """Compute the radiation-based migration matrix.

        Returns:
            Migration matrix of shape ``(N, N)``.
        """
        if len(self.scenario) == 1:
            return np.array([[0.0]])
        distances = self.get_distances()
        mat = radiation(self.scenario["pop"].to_numpy(), distances, k=1.0, include_home=self.params.include_home)  # TODO: find a better k?
        # normalize w/ k
        nrm = self.params.k / (np.sum(mat * self.scenario["pop"].to_numpy()[:, np.newaxis], axis=1) / self.scenario["pop"].to_numpy())
        mat *= nrm
        return mat
