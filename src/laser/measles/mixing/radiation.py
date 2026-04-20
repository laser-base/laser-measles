import numpy as np
import polars as pl
from laser.core.migration import radiation
from pydantic import BaseModel
from pydantic import Field

from laser.measles.mixing.base import BaseMixing


class RadiationParams(BaseModel):
    """
    Parameters for the radiation migration model.

    Attributes:
        include_home (bool): Whether to include home in the migration matrix
        k (float): Scale parameter (avg trip probability)

    """

    include_home: bool = Field(default=True, description="Whether to include home in the migration matrix")
    k: float = Field(default=0.01, description="Scale parameter (avg trip probability)", ge=0, le=1)


class RadiationMixing(BaseMixing):
    """
    Radiation migration model where outbound migration flux from origin to destination is
    enhanced by destination population and absorbed by the density of nearer destinations.

    Formula:
        .. math::
            M_{i,j} = k \\frac{p_i p_j}{\\left(p_i + \\sum_{k \\in \\Omega(i,j)} p_k\\right)\\left(p_i + p_j + \\sum_{k \\in \\Omega(i,j)} p_k\\right)}

    Attributes:
        include_home (bool): Whether to include home in the migration matrix
        k (float): Scale parameter (avg trip probability)
    """

    def __init__(self, scenario: pl.DataFrame | None = None, params: RadiationParams | None = None):
        if params is None:
            params = RadiationParams()
        super().__init__(scenario, params)

    def get_migration_matrix(self) -> np.ndarray:
        if len(self.scenario) == 1:
            return np.array([[0.0]])
        distances = self.get_distances()
        mat = radiation(self.scenario["pop"].to_numpy(), distances, k=1.0, include_home=self.params.include_home)  # TODO: find a better k?
        # normalize w/ k
        nrm = self.params.k / (np.sum(mat * self.scenario["pop"].to_numpy()[:, np.newaxis], axis=1) / self.scenario["pop"].to_numpy())
        mat *= nrm
        return mat
