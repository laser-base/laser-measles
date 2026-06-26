from laser.measles.components import BaseStateTracker
from laser.measles.components import BaseStateTrackerParams


class StateTrackerParams(BaseStateTrackerParams):
    """
    Parameters for State tracking component.

    Inherits all parameters from BaseStateTrackerParams with
    ABM-specific defaults and validation.

    Examples:

        from laser.measles.biweekly.components.tracker_state import StateTrackerParams

        params = StateTrackerParams()
    """


class StateTracker(BaseStateTracker):
    """
    Atate tracking component.

    Tracks disease state populations over time in agent-based models.
    Records detailed temporal dynamics of S, I, R compartments
    at the patch level.

    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.StateTracker, components.StateTrackerParams()))
    """
