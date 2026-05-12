"""Base tracker component for laser.measles models."""

from abc import ABC
from abc import abstractmethod
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from ..base import BaseComponent


class BaseTrackerParams(BaseModel):
    """Common parameters for tracker components."""

    model_config = ConfigDict(extra="forbid")

    track_states: bool = Field(default=True, description="Whether to track disease states")

    track_population: bool = Field(default=True, description="Whether to track population dynamics")

    output_frequency: int = Field(default=1, description="Frequency of output (every N time steps)", gt=0)


class BaseTracker(BaseComponent, ABC):
    """Abstract base class for tracker components."""

    def __init__(self, model, params: BaseTrackerParams | None = None):
        super().__init__(model)
        self.params = params if params is not None else BaseTrackerParams()
        self.data = {}  # Storage for tracked data

    @abstractmethod
    def initialize(self, model):
        """Initialize tracker with model."""

    @abstractmethod
    def update(self, model, tick: int):
        """Update tracker with current model state."""

    def should_track(self, tick: int) -> bool:
        """Check if we should track data at this time step."""
        return tick % self.params.output_frequency == 0

    def get_data(self) -> dict[str, Any]:
        """Get all tracked data."""
        return self.data

    def reset(self):
        """Reset tracked data."""
        self.data = {}
