from laser.measles.components import BaseStateTracker
from laser.measles.components import BaseStateTrackerParams


class StateTrackerParams(BaseStateTrackerParams):
    """
    Parameters for ABM state tracking component.

    Inherits all parameters from BaseStateTrackerParams with
    ABM-specific defaults and validation.


    Examples:

        from laser.measles.abm.components.tracker_state import StateTrackerParams

        params = StateTrackerParams()
    """


class StateTracker(BaseStateTracker):
    """
    ABM state tracking component.

    Tracks disease state populations over time in agent-based models.
    Records detailed temporal dynamics of S, E, I, R compartments
    at the patch level.


    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.StateTracker, components.StateTrackerParams()))
    """
