"""Parameters for the biweekly model."""

import json
from collections import OrderedDict

from laser.measles.base import BaseModelParams

TIME_STEP_DAYS = 14
STATES = ["S", "I", "R"]  # Compartments/states for discrete-time model


class BiweeklyParams(BaseModelParams):
    """Parameters for the biweekly compartmental measles model (14-day timesteps).

    Inherits all fields from
    [`BaseModelParams`][laser.measles.base.BaseModelParams].  Each tick
    represents 14 days, and the model tracks three SIR states (no explicit
    Exposed compartment).

    Attributes:
        num_ticks: Number of biweekly simulation steps
            (e.g., 26 ≈ 1 year, 130 ≈ 5 years).
        seed: Random seed for reproducibility.  Default: ``20250314``.
        start_time: Simulation start in ``"YYYY-MM"`` format.
            Default: ``"2000-01"``.
        verbose: Print detailed logging.  Default: ``False``.

    Examples:

        params = BiweeklyParams(num_ticks=26, seed=42, start_time="2000-01")
    """

    @property
    def time_step_days(self) -> int:
        """Duration of one tick in days (always ``14`` for the biweekly model)."""
        return TIME_STEP_DAYS

    @property
    def states(self) -> list[str]:
        """SIR state names: ``["S", "I", "R"]``."""
        return STATES

    def __str__(self) -> str:
        return json.dumps(OrderedDict(sorted(self.model_dump().items())), indent=2)


Params = BiweeklyParams
