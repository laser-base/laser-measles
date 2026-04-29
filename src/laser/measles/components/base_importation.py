"""Base importation component for laser.measles models."""

from abc import ABC
from abc import abstractmethod

import numpy as np
from pydantic import BaseModel
from pydantic import Field

from ..base import BasePhase


class BaseImportationParams(BaseModel):
    """Common parameters for importation components.

    **Example:**

        ```python
        from laser.measles.abm.components.process_importation import ImportationParams

        params = ImportationParams()
        ```
    """

    importation_rate: float = Field(default=0.0, description="Rate of imported infections per time step", ge=0.0)

    importation_schedule: np.ndarray | None = Field(default=None, description="Time-varying importation schedule")

    target_patches: list | None = Field(default=None, description="Patches that receive importations (None = all patches)")

    class Config:
        """Pydantic config allowing numpy array fields."""

        arbitrary_types_allowed = True


class BaseImportation(BasePhase, ABC):
    """Abstract base class for importation components.

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.InfectRandomAgentsProcess, components.ImportationParams()))
        ```
    """

    def __init__(self, model, verbose: bool = False, params: BaseImportationParams | None = None):
        super().__init__(model, verbose)
        self.params = params if params is not None else BaseImportationParams()

    @abstractmethod
    def __call__(self, model, tick: int):
        """Execute importation for one time step."""

    def get_importation_rate(self, tick: int) -> float:
        """Get importation rate for current time step."""
        if self.params.importation_schedule is not None:
            if tick < len(self.params.importation_schedule):
                return self.params.importation_schedule[tick]
        return self.params.importation_rate
