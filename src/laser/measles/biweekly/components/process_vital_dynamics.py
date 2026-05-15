from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess


class VitalDynamicsParams(BaseVitalDynamicsParams):
    """
    Parameters for the vital dynamics process.
    

    **Example:**

        ```python
        from laser.measles.biweekly.components.process_vital_dynamics import VitalDynamicsParams

        params = VitalDynamicsParams()
        ```
    """


class VitalDynamicsProcess(BaseVitalDynamicsProcess):
    """
    Phase for simulating the vital dynamics in the model with MCV1.
    

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.VitalDynamicsProcess, components.VitalDynamicsParams()))
        ```
    """

    def calculate_capacity(self, model) -> int:
        """Raise because biweekly models use fixed-size patch arrays."""
        raise RuntimeError("No capacity for this model")
