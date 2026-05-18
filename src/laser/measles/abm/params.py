"""
Parameters for the ABM model.
"""

import json
from collections import OrderedDict

from laser.measles.base import BaseModelParams

TIME_STEP_DAYS = 1
STATES = ["S", "E", "I", "R"]


class ABMParams(BaseModelParams):
    """Parameters for the agent-based measles model (daily timesteps).

    Inherits all fields from
    [`BaseModelParams`][laser.measles.base.BaseModelParams].  Each tick
    represents one day, and the model tracks four SEIR states.

    Attributes:
        num_ticks: Number of daily simulation steps (e.g., 365 = 1 year).
        seed: Random seed for reproducibility.  Default: ``20250314``.
        start_time: Simulation start in ``"YYYY-MM"`` format.
            Default: ``"2000-01"``.
        verbose: Print detailed logging.  Default: ``False``.

    **Example:**

        ```python
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        ```
    """

    @property
    def time_step_days(self) -> int:
        """Duration of one tick in days (always ``1`` for the ABM)."""
        return TIME_STEP_DAYS

    @property
    def states(self) -> list[str]:
        """SEIR state names: ``["S", "E", "I", "R"]``."""
        return STATES

    def __str__(self) -> str:
        return json.dumps(OrderedDict(sorted(self.model_dump().items())), indent=2)


Params = ABMParams
