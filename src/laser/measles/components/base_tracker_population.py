import numpy as np
from pydantic import BaseModel

from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase


class BasePopulationTrackerParams(BaseModel):
    """Parameters for the population tracker (currently empty — reserved for future options).

    **Example:**

        ```python
        from laser.measles.biweekly.components.tracker_population import PopulationTrackerParams

        params = PopulationTrackerParams()
        ```
    """


class BasePopulationTracker(BasePhase):
    """
    Tracks the population size of each patch at each time tick.
    

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.PopulationTracker, components.PopulationTrackerParams()))
        ```
    """

    def __init__(self, model: BaseLaserModel, verbose: bool = False, params: BasePopulationTrackerParams | None = None) -> None:
        super().__init__(model, verbose)
        self.params = params or BasePopulationTrackerParams()
        self.population_tracker = np.zeros((model.patches.count, model.params.num_ticks), dtype=model.patches.states.dtype)

    def __call__(self, model, tick: int) -> None:
        self.population_tracker[:, tick] = model.patches.states.sum(axis=0)

    def _initialize(self, model: BaseLaserModel) -> None:
        pass
