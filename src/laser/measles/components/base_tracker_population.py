import numpy as np
from pydantic import BaseModel
from pydantic import ConfigDict

from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase


class BasePopulationTrackerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BasePopulationTracker(BasePhase):
    """Tracks the population size of each patch at each time tick.

    After ``model.run()``, the recorded time series is available as a numpy
    array on the ``population_tracker`` attribute:

        ``tracker.population_tracker`` — shape ``(n_patches, n_ticks)``, the
        total agent count per patch at each tick. Sum across the patch axis
        (``axis=0``) to get the global population time series.

    Subclasses for ABM, biweekly, and compartmental models share this layout;
    see their docstrings for end-to-end examples that include the post-run
    access pattern.
    """

    def __init__(self, model: BaseLaserModel, params: BasePopulationTrackerParams | None = None) -> None:
        super().__init__(model)
        self.params = params or BasePopulationTrackerParams()
        self.population_tracker = np.zeros((model.patches.count, model.params.num_ticks), dtype=model.patches.states.dtype)

    def __call__(self, model, tick: int) -> None:
        self.population_tracker[:, tick] = model.patches.states.sum(axis=0)

    def _initialize(self, model: BaseLaserModel) -> None:
        pass
