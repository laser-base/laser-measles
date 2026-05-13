"""Base importation component for laser.measles models."""

from abc import ABC
from abc import abstractmethod

import numpy as np
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from ..base import BasePhase


class BaseImportationParams(BaseModel):
    """Common parameters for importation components."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    importation_rate: float = Field(default=0.0, description="Rate of imported infections per time step", ge=0.0)

    importation_schedule: np.ndarray | None = Field(default=None, description="Time-varying importation schedule")

    target_patches: list | None = Field(default=None, description="Patches that receive importations (None = all patches)")


class BaseImportation(BasePhase, ABC):
    """Abstract base class for importation components."""

    def __init__(self, model, params: BaseImportationParams | None = None):
        super().__init__(model)
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
