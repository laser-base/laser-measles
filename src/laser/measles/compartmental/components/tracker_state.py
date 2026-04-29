"""
Component for tracking the state of the population in the compartmental model.
"""

from laser.measles.components import BaseStateTracker
from laser.measles.components import BaseStateTrackerParams


class StateTrackerParams(BaseStateTrackerParams):
    """
    Parameters for State tracking component.

    Inherits all parameters from BaseStateTrackerParams with
    ABM-specific defaults and validation.
    

    **Example:**

        ```python
        from laser.measles.compartmental.components.tracker_state import StateTrackerParams

        params = StateTrackerParams()
        ```
    """


class StateTracker(BaseStateTracker):
    """
    Atate tracking component.

    Tracks disease state populations over time in agent-based models.
    Records detailed temporal dynamics of S, E, I, R compartments
    at the patch level.
    

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = CompartmentalModel(scenario, params)
        model.add_component(create_component(components.StateTracker, components.StateTrackerParams()))
        ```
    """
