"""
Age Pyramid Tracker

This component tracks the age distribution of the population.
"""

import numpy as np
import pyvd
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from laser.measles.abm.model import ABMModel
from laser.measles.base import BasePhase


class AgePyramidTrackerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: str = Field(default="yearly", description="Frequency of the age pyramid tracker (yearly, monthly, daily)")
    age_bins: list[int] = Field(default=pyvd.constants.MORT_XVAL[::2], description="Age bins for the age pyramid (in days)")

    @field_validator("frequency")
    def validate_frequency(cls, v):
        if v not in ["yearly", "monthly", "daily"]:
            raise ValueError("Frequency must be one of: yearly, monthly, daily")
        return v

    @field_validator("age_bins")
    def validate_age_bins(cls, v):
        if not np.all(np.diff(v) > 0):
            raise ValueError("Age bins must be in increasing order")
        return v


class AgePyramidTracker(BasePhase):
    """Track the age distribution of the population."""

    def __init__(self, model, params: AgePyramidTrackerParams | None = None):
        super().__init__(model)
        self.params = params or AgePyramidTrackerParams()
        self.age_pyramid = {}
        self.last_call = model.current_date

    def _initialize(self, model: ABMModel) -> None:
        pass

    def __call__(self, model: ABMModel, tick: int) -> None:
        if self.params.frequency == "yearly":
            if model.current_date.month == 1 and model.current_date.day == 1:
                self._get_age_pyramid(model, tick)
        elif self.params.frequency == "monthly":
            if model.current_date.day == 1:
                self._get_age_pyramid(model, tick)
        elif self.params.frequency == "daily":
            self._get_age_pyramid(model, tick)
        else:
            raise ValueError(f"Frequency {self.params.frequency} not supported")

    def _get_age_pyramid(self, model: ABMModel, tick: int) -> dict:
        people = model.people
        idx = np.where(people.active)[0]
        self.age_pyramid[model.current_date.strftime("%Y-%m-%d")] = np.histogram(
            tick - people.date_of_birth[idx], bins=self.params.age_bins
        )[0]
