"""
Component for implementing Supplementary Immunization Activities (SIAs) based on a calendar schedule.
"""

from collections.abc import Callable
from datetime import datetime
from datetime import timedelta

import numpy as np
import polars as pl
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from laser.measles.base import BasePhase
from laser.measles.compartmental.model import CompartmentalModel
from laser.measles.utils import cast_type
from laser.measles.utils import coerce_utf8_date_column


class SIACalendarParams(BaseModel):
    """Parameters specific to the SIA calendar component."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    sia_efficacy: float = Field(0.9, description="Fraction of susceptibles to vaccinate in SIA", ge=0.0, le=1.0)
    filter_fn: Callable[[str], bool] = Field(lambda x: True, description="Function to filter which nodes to include in aggregation")
    aggregation_level: int = Field(3, description="Number of levels to use for aggregation (e.g., 3 for country:state:lga)")
    sia_schedule: pl.DataFrame = Field(description="DataFrame containing SIA schedule information")
    date_column: str = Field("date", description="Name of the column containing SIA dates")
    group_column: str = Field("id", description="Name of the column containing group identifiers")

    @model_validator(mode="after")
    def _coerce_sia_schedule_date_column(self) -> "SIACalendarParams":
        """Silently cast a Utf8 date column on ``sia_schedule`` to ``Datetime``
        so the per-tick filter in ``SIACalendarProcess.__call__`` doesn't
        blow up on string-typed user input. Shared logic lives in
        ``coerce_utf8_date_column``; see laser-measles #215.
        """
        self.sia_schedule = coerce_utf8_date_column(self.sia_schedule, self.date_column)
        return self


class SIACalendarProcess(BasePhase):
    """
    Phase for implementing Supplementary Immunization Activities (SIAs) based on a calendar schedule.

    This component:
    1. Groups nodes by geographic level using the same aggregation schema as CaseSurveillanceTracker
    2. Implements SIAs at scheduled times by moving susceptibles to recovered state
    3. Uses the model's current_date to determine when to implement SIAs
    4. Applies vaccination with configurable efficacy rate

    Parameters
    ----------
    model : object
        The simulation model containing nodes, states, and parameters
    params : Optional[SIACalendarParams], default=None
        Component-specific parameters. If None, will use default parameters

    Notes
    -----
    - SIA efficacy determines the fraction of susceptibles that get vaccinated
    - Vaccination is simulated using a binomial distribution
    - SIAs are implemented when the model's current_date has passed the scheduled date
    - Since the model steps in 14-day increments, SIAs are implemented on the first step after their scheduled date
    - Each SIA is implemented exactly once
    """

    def __init__(self, model: CompartmentalModel, params: SIACalendarParams | None = None) -> None:
        super().__init__(model)
        if params is None:
            raise ValueError("SIACalendarParams must be provided")
        self.params = params
        self._validate_params()

        # Extract node IDs and create mapping for filtered nodes
        self.node_mapping = {}

        for node_idx, node_id in enumerate(model.scenario["id"]):
            if self.params.filter_fn(node_id):
                # Create geographic grouping keynode
                group_key = ":".join(node_id.split(":")[: self.params.aggregation_level])
                if group_key not in self.node_mapping:
                    self.node_mapping[group_key] = []
                self.node_mapping[group_key].append(node_idx)

        # Track which SIAs have been implemented
        self.implemented_sias = set()

        # Store start date for compatibility with tests
        self.start_date = model.start_time

        # Store a copy of the original schedule for get_sia_schedule method
        self._original_schedule = self.params.sia_schedule.clone()

        # Empty-schedule type repair: an empty DataFrame whose `date` column
        # was never written keeps whatever dtype the user gave it (often
        # `Null`). The SIACalendarParams.@model_validator only fires on
        # `Utf8` → `Datetime`, so empty-but-not-Utf8 schedules still need
        # a tiny cast here so the filter works.
        if len(self.params.sia_schedule) == 0 and self.params.date_column in self.params.sia_schedule.columns:
            if self.params.sia_schedule.schema[self.params.date_column] != pl.Datetime:
                self.params.sia_schedule = self.params.sia_schedule.with_columns(pl.col(self.params.date_column).cast(pl.Datetime))

        if self.verbose:
            print(f"SIACalendar initialized with {len(self.node_mapping)} groups")

    def _validate_params(self) -> None:
        """Validate component parameters."""
        if self.params.aggregation_level < 1:
            raise ValueError("aggregation_level must be at least 1")

        # Validate SIA schedule DataFrame
        required_columns = [self.params.group_column, self.params.date_column]
        if not all(col in self.params.sia_schedule.columns for col in required_columns):
            raise ValueError(f"sia_schedule must contain columns: {required_columns}")

    def _tick_to_date(self, tick: int) -> datetime:
        """Convert tick number to datetime."""
        return self.start_date + timedelta(days=tick)

    def __call__(self, model: CompartmentalModel, tick: int) -> None:
        # Get current state counts
        states = model.patches.states

        # Check for SIAs scheduled for dates up to and including the current date
        # Calculate current date based on tick number and model's time step
        current_date = model.start_time + timedelta(days=tick * model.params.time_step_days)
        sia_schedule = self.params.sia_schedule.filter(pl.col(self.params.date_column) <= current_date)

        # If no SIAs are scheduled, do nothing
        if len(sia_schedule) == 0:
            return

        # Apply SIAs to each scheduled group
        for row in sia_schedule.iter_rows(named=True):
            group_key = row[self.params.group_column]
            scheduled_date = row[self.params.date_column]

            # Create a unique identifier for this SIA
            sia_id = f"{group_key}_{scheduled_date}"

            # Skip if this SIA has already been implemented
            if sia_id in self.implemented_sias:
                continue

            if group_key in self.node_mapping:
                node_indices = self.node_mapping[group_key]

                # Get susceptible population for this group
                susceptibles = states.S[node_indices]

                # Sample number to vaccinate using binomial distribution
                vaccinated = cast_type(np.random.binomial(n=susceptibles, p=self.params.sia_efficacy), states.dtype)

                # Update states: move vaccinated from susceptible to recovered
                states.S[node_indices] -= vaccinated
                states.R[node_indices] += vaccinated

                # Mark this SIA as implemented
                self.implemented_sias.add(sia_id)

                if self.verbose:
                    total_vaccinated = vaccinated.sum()
                    if total_vaccinated > 0:
                        print(
                            f"Date {current_date}: Implementing SIA for {group_key} (scheduled for {scheduled_date}) - vaccinated {total_vaccinated} individuals"
                        )

    def initialize(self, model: CompartmentalModel) -> None:
        pass

    def get_sia_schedule(self) -> pl.DataFrame:
        """
        Get the SIA schedule.

        Returns
        -------
        pl.DataFrame
            DataFrame with columns:
            - {group_column}: Group identifier
            - {date_column}: Scheduled date for SIA
        """
        return self._original_schedule
