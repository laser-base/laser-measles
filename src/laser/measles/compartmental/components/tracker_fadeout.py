from laser.measles.components import BaseFadeOutTracker
from laser.measles.components import BaseFadeOutTrackerParams


class FadeOutTracker(BaseFadeOutTracker):
    """A component that tracks the number of nodes experiencing fade-outs over time.

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = CompartmentalModel(scenario, params)
        model.add_component(create_component(components.FadeOutTracker, components.FadeOutTrackerParams()))
        ```
    """


class FadeOutTrackerParams(BaseFadeOutTrackerParams):
    """Parameters for the FadeOutTracker component.

    **Example:**

        ```python
        from laser.measles.compartmental.components.tracker_fadeout import FadeOutTrackerParams

        params = FadeOutTrackerParams()
        ```
    """
