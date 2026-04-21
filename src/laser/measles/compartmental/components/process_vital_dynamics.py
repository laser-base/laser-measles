"""
Component for simulating the vital dynamics in the compartmental model with MCV1.
"""

import numpy as np

from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess


class VitalDynamicsParams(BaseVitalDynamicsParams):
    """
    Parameters for the vital dynamics process.
    """


class VitalDynamicsProcess(BaseVitalDynamicsProcess):
    """
    Phase for simulating the vital dynamics in the model with MCV1.
    """

    def __init__(self, model, verbose: bool = False, params: VitalDynamicsParams | None = None) -> None:
        super().__init__(model, verbose, params)
        model.patches.add_scalar_property("births", dtype=np.uint32)
        model.patches.add_scalar_property("deaths", dtype=np.uint32)

    def calculate_capacity(self, model) -> int:
        raise RuntimeError("No capacity for this model")
