"""
Component for initializing the population in each of the model states by rough equilibrium of R0.
"""

from laser.measles.components import BaseInitializeEquilibriumStatesParams
from laser.measles.components import BaseInitializeEquilibriumStatesProcess


class InitializeEquilibriumStatesParams(BaseInitializeEquilibriumStatesParams):
    """
    Parameters for the InitializeEquilibriumStatesProcess.


    **Example:**

        ```python
        from laser.measles.compartmental.components.process_initialize_equilibrium_states import InitializeEquilibriumStatesParams

        params = InitializeEquilibriumStatesParams()
        ```
    """


class InitializeEquilibriumStatesProcess(BaseInitializeEquilibriumStatesProcess):
    """
    Initialize S, R states of the population in each of the model states by rough equilibrium of R0.


    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = CompartmentalModel(scenario, params)
        model.add_component(create_component(components.InitializeEquilibriumStatesProcess, components.InitializeEquilibriumStatesParams()))
        ```
    """
