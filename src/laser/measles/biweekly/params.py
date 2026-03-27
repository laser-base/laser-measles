"""Parameters for the biweekly model."""

import json
from collections import OrderedDict

from laser.measles.base import BaseModelParams

TIME_STEP_DAYS = 14
STATES = ["S", "I", "R"]  # Compartments/states for discrete-time model


class BiweeklyParams(BaseModelParams):
    """
    Parameters for the biweekly compartmental measles model (14-day timesteps).

    All fields are inherited from :class:`BaseModelParams`. Key fields:

    Attributes:
        num_ticks (int): Number of biweekly (14-day) simulation steps
            (e.g., 26 = 1 year, 130 = 5 years).
        seed (int): Random seed for reproducibility. Default: 20250314.
        start_time (str): Simulation start in ``"YYYY-MM"`` format. Default: ``"2000-01"``.
        verbose (bool): Print detailed logging. Default: False.

    Example::

        params = BiweeklyParams(num_ticks=26, seed=42)           # 1 year
        params = BiweeklyParams(num_ticks=130, seed=0)           # 5 years
        params = BiweeklyParams(num_ticks=260, start_time="2005-01")  # 10 years
    """

    @property
    def time_step_days(self) -> int:
        return TIME_STEP_DAYS

    @property
    def states(self) -> list[str]:
        return STATES

    def __str__(self) -> str:
        return json.dumps(OrderedDict(sorted(self.model_dump().items())), indent=2)


Params = BiweeklyParams
