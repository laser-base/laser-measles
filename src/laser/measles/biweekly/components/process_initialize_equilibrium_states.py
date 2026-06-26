"""
Component for initializing the population in each of the model states by rough equilibrium of R0.
"""

from laser.measles.components import BaseInitializeEquilibriumStatesParams
from laser.measles.components import BaseInitializeEquilibriumStatesProcess


class InitializeEquilibriumStatesParams(BaseInitializeEquilibriumStatesParams):
    """
    Parameters for the InitializeEquilibriumStatesProcess.

    Examples:

        from laser.measles.biweekly.components.process_initialize_equilibrium_states import InitializeEquilibriumStatesParams

        params = InitializeEquilibriumStatesParams()
    """


class InitializeEquilibriumStatesProcess(BaseInitializeEquilibriumStatesProcess):
    """
    Initialize S, R states of the population in each of the model states by rough equilibrium of R0.

    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.InitializeEquilibriumStatesProcess, components.InitializeEquilibriumStatesParams()))
    """
