from laser.measles.components import BaseFadeOutTracker
from laser.measles.components import BaseFadeOutTrackerParams


class FadeOutTracker(BaseFadeOutTracker):
    """A component that tracks the number of nodes experiencing fade-outs over time.

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.FadeOutTracker, components.FadeOutTrackerParams()))
        ```
    """

    def __init__(self, model, verbose: bool = False) -> None:
        super().__init__(model, verbose)


class FadeOutTrackerParams(BaseFadeOutTrackerParams):
    """Parameters for the FadeOutTracker component.

    **Example:**

        ```python
        from laser.measles.biweekly.components.tracker_fadeout import FadeOutTrackerParams

        params = FadeOutTrackerParams()
        ```
    """
