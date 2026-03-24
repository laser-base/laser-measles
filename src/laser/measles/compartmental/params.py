"""Parameters for the compartmental SEIR model with daily timesteps."""

import json
from collections import OrderedDict

from laser.measles.base import BaseModelParams

TIME_STEP_DAYS = 1
STATES = ["S", "E", "I", "R"]  # Compartments/states for SEIR model


class CompartmentalParams(BaseModelParams):
    """
    Parameters for the compartmental SEIR model with daily timesteps.

    All fields are inherited from :class:`BaseModelParams`. Key fields:

    Attributes:
        num_ticks (int): Number of daily simulation steps (e.g., 365 = 1 year).
        seed (int): Random seed for reproducibility. Default: 20250314.
        start_time (str): Simulation start in ``"YYYY-MM"`` format. Default: ``"2000-01"``.
        verbose (bool): Print detailed logging. Default: False.

    Example::

        params = CompartmentalParams(num_ticks=365, seed=42)
        params = CompartmentalParams(num_ticks=730, seed=0, start_time="2010-01")
    """

    @property
    def time_step_days(self) -> int:
        return TIME_STEP_DAYS

    @property
    def states(self) -> list[str]:
        return STATES

    def __str__(self) -> str:
        return json.dumps(OrderedDict(sorted(self.model_dump().items())), indent=2)


Params = CompartmentalParams
