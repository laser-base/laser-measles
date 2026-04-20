import numpy as np
import polars as pl
from laser.core.migration import gravity
from pydantic import BaseModel
from pydantic import Field

from laser.measles.mixing.base import BaseMixing


class GravityParams(BaseModel):
    """
    Parameters for the gravity migration model.

    Formula:
        .. math::
            M_{i,j} = k \\cdot p_i^{a-1} \\cdot p_j^b \\cdot d_{i,j}^{-c}

    Attributes:
        a (float): Population source scale parameter
        b (float): Population target scale parameter
        c (float): Distance exponent
        k (float): Scale parameter
    """

    a: float = Field(default=1.0, description="Population source scale parameter", ge=1.0)
    b: float = Field(default=1.0, description="Population target scale parameter")
    c: float = Field(default=1.5, description="Distance exponent")
    k: float = Field(default=0.01, description="Scale parameter (avg trip probability)", ge=0, le=1)


class GravityMixing(BaseMixing):
    """
    Gravity migration model.

    Computes a spatial mixing matrix based on patch populations and distances:

    .. math::

        M_{i,j} = k \\cdot p_i^{a-1} \\cdot p_j^b \\cdot d_{i,j}^{-c}

    The ``scenario`` argument is optional. When this mixer is attached to a model via
    ``InfectionParams(mixer=...)`` the model automatically sets the scenario before
    the mixing matrix is first computed (lazy initialisation). You only need to pass
    ``scenario`` explicitly when using the mixer standalone (e.g. to inspect the
    matrix before running a simulation).

    Parameters
    ----------
    scenario : pl.DataFrame or None, optional
        Patch data with ``id``, ``lat``, ``lon``, ``pop``, and ``mcv1`` columns.
        If ``None``, must be set before the mixing matrix is accessed (happens
        automatically when the mixer is attached to a model component).
    params : GravityParams or None, optional
        Gravity model parameters. Uses :class:`GravityParams` defaults if ``None``.

    Examples
    --------
    Typical usage — let the model set the scenario automatically:

    .. code-block:: python

        from laser.measles.mixing.gravity import GravityMixing, GravityParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        mixer = GravityMixing(params=GravityParams(a=1.0, b=1.0, c=2.0, k=0.01))
        infection_params = components.InfectionParams(beta=0.8, mixer=mixer)
        model.components = [create_component(components.InfectionProcess, infection_params)]

    Standalone usage (inspect the matrix before running):

    .. code-block:: python

        mixer = GravityMixing(scenario=scenario, params=GravityParams(c=2.0, k=0.01))
        print(mixer.mixing_matrix)
    """

    def __init__(self, scenario: pl.DataFrame | None = None, params: GravityParams | None = None):
        if params is None:
            params = GravityParams()
        super().__init__(scenario, params)

    def get_migration_matrix(self) -> np.ndarray:
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
