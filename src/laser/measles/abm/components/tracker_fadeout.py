from laser.measles.components import BaseFadeOutTracker
from laser.measles.components import BaseFadeOutTrackerParams


class FadeOutTracker(BaseFadeOutTracker):
    """A component that tracks the number of nodes experiencing fade-outs over time.

    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.FadeOutTracker, components.FadeOutTrackerParams()))
    """


class FadeOutTrackerParams(BaseFadeOutTrackerParams):
    """Parameters for the FadeOutTracker component.

    Examples:

        from laser.measles.abm.components.tracker_fadeout import FadeOutTrackerParams

        params = FadeOutTrackerParams()
    """
