"""
Age Pyramid Tracker

This component tracks the age distribution of the population.
"""

import numpy as np
import pyvd
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from laser.measles.abm.model import ABMModel
from laser.measles.base import BasePhase


class AgePyramidTrackerParams(BaseModel):
    """Parameters for the age-pyramid tracker (recording frequency and age bins).

    **Example:**

        ```python
        from laser.measles.abm.components.tracker_age_pyramid import AgePyramidTrackerParams

        params = AgePyramidTrackerParams()
        ```
    """
    frequency: str = Field(default="yearly", description="Frequency of the age pyramid tracker (yearly, monthly, daily)")
    age_bins: list[int] = Field(default=pyvd.constants.MORT_XVAL[::2], description="Age bins for the age pyramid (in days)")

    @field_validator("frequency")
    def validate_frequency(cls, v):
        """Validate that ``frequency`` is one of ``yearly``, ``monthly``, or ``daily``."""
        if v not in ["yearly", "monthly", "daily"]:
            raise ValueError("Frequency must be one of: yearly, monthly, daily")
        return v

    @field_validator("age_bins")
    def validate_age_bins(cls, v):
        """Validate that ``age_bins`` are in strictly increasing order."""
        if not np.all(np.diff(v) > 0):
            raise ValueError("Age bins must be in increasing order")
        return v


class AgePyramidTracker(BasePhase):
    """Track the age distribution of the population.

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.AgePyramidTracker, components.AgePyramidTrackerParams()))
        ```
    """

    def __init__(self, model, verbose: bool = False, params: AgePyramidTrackerParams | None = None):
        super().__init__(model, verbose)
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
