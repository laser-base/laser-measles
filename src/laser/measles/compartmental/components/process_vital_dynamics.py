"""
Component for simulating the vital dynamics in the compartmental model with MCV1.
"""

import numpy as np

from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess


class VitalDynamicsParams(BaseVitalDynamicsParams):
    """
    Parameters for the vital dynamics process.


    **Example:**

        ```python
        from laser.measles.compartmental.components.process_vital_dynamics import VitalDynamicsParams

        params = VitalDynamicsParams()
        ```
    """


class VitalDynamicsProcess(BaseVitalDynamicsProcess):
    """
    Phase for simulating the vital dynamics in the model with MCV1.


    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = CompartmentalModel(scenario, params)
        model.add_component(create_component(components.VitalDynamicsProcess, components.VitalDynamicsParams()))
        ```
    """

    def __init__(self, model, params: VitalDynamicsParams | None = None) -> None:
        super().__init__(model, params)
        model.patches.add_scalar_property("births", dtype=np.uint32)
        model.patches.add_scalar_property("deaths", dtype=np.uint32)

    def calculate_capacity(self, model) -> int:
        """Raise because compartmental models use fixed-size patch arrays."""
        raise RuntimeError("No capacity for this model")
