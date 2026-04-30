from collections.abc import Callable

import numpy as np
import polars as pl
from pydantic import BaseModel
from pydantic import Field

from laser.measles.abm.model import ABMModel
from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase


class SIACalendarParams(BaseModel):
    """Parameters specific to the SIA calendar component."""

    model_config = {"arbitrary_types_allowed": True}

    sia_efficacy: float = Field(0.9, description="Fraction of susceptibles to vaccinate in SIA", ge=0.0, le=1.0)
    filter_fn: Callable[[str], bool] = Field(lambda x: True, description="Function to filter which nodes to include in aggregation")
    aggregation_level: int = Field(3, description="Number of levels to use for aggregation (e.g., 3 for country:state:lga)")
    sia_schedule: pl.DataFrame = Field(description="DataFrame containing SIA schedule information")
    date_column: str = Field("date", description="Name of the column containing SIA dates")
    group_column: str = Field("id", description="Name of the column containing group identifiers")


class SIACalendarProcess(BasePhase):
    """
    Phase for implementing Supplementary Immunization Activities (SIAs) based on a calendar schedule.

    This component:
    1. Groups nodes by geographic level using the same aggregation schema as CaseSurveillanceTracker
    2. Implements SIAs at scheduled times by vaccinating individual agents
    3. Uses the model's current_date to determine when to implement SIAs
    4. Applies vaccination with configurable efficacy rate to individual agents

    Parameters
    ----------
    model : ABMModel
        The ABM simulation model containing agents, patches, and parameters
    params : Optional[SIACalendarParams], default=None
        Component-specific parameters. If None, will use default parameters

    Notes
    -----
    - SIA efficacy determines the fraction of susceptibles that get vaccinated
    - Individual agents are randomly selected for vaccination based on efficacy
    - SIAs are implemented when the model's current_date has passed the scheduled date
    - Vaccination moves agents from susceptible (S=0) to recovered (R=3) state
    - Both individual agent states and patch-level state aggregations are updated
    - Each SIA is implemented exactly once
    """

    def __init__(self, model: ABMModel, params: SIACalendarParams | None = None) -> None:
        super().__init__(model)
        if params is None:
            raise ValueError("SIACalendarParams must be provided")
        self.params = params
        self._validate_params()

        # Extract node IDs and create mapping for filtered nodes
        self.node_mapping = {}

        for node_idx, node_id in enumerate(model.scenario["id"]):
            if self.params.filter_fn(node_id):
                # Create geographic grouping key
                group_key = ":".join(node_id.split(":")[: self.params.aggregation_level])
                if group_key not in self.node_mapping:
                    self.node_mapping[group_key] = []
                self.node_mapping[group_key].append(node_idx)

        # Track which SIAs have been implemented
        self.implemented_sias = set()

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

    def __call__(self, model: ABMModel, tick: int) -> None:
        # Check for SIAs scheduled for dates up to and including the current date
        current_date = model.current_date
        sia_schedule = self.params.sia_schedule.filter(pl.col(self.params.date_column) <= current_date)

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
                vaccinated_count = self._vaccinate_agents(model, node_indices)

                # Mark this SIA as implemented
                self.implemented_sias.add(sia_id)

                if self.verbose and vaccinated_count > 0:
                    print(
                        f"Date {current_date}: Implementing SIA for {group_key} (scheduled for {scheduled_date}) - vaccinated {vaccinated_count} individuals"
                    )

    def _vaccinate_agents(self, model: ABMModel, patch_indices: list[int]) -> int:
        """
        Vaccinate agents in specified patches.

        Args:
            model: The ABM model
            patch_indices: List of patch indices to vaccinate in

        Returns:
            Total number of agents vaccinated
        """
        people = model.people
        patches = model.patches

        # Find susceptible agents in target patches
        susceptible_mask = people.state[: people.count] == 0  # Susceptible state
        patch_mask = np.isin(people.patch_id[: people.count], patch_indices)
        target_mask = susceptible_mask & patch_mask

        target_indices = np.where(target_mask)[0]

        if len(target_indices) == 0:
            return 0

        # Randomly select agents to vaccinate based on efficacy
        num_to_vaccinate = int(len(target_indices) * self.params.sia_efficacy)
        if num_to_vaccinate == 0:
            return 0

        # Randomly select agents without replacement
        selected_indices = np.random.choice(target_indices, size=num_to_vaccinate, replace=False)

        # Update agent states to recovered (R = 3)
        recovered_state = model.params.states.index("R")
        people.state[selected_indices] = recovered_state

        # Update patch-level state counts
        for patch_idx in patch_indices:
            # Count vaccinated agents in this patch
            patch_vaccinated = np.sum(people.patch_id[selected_indices] == patch_idx)
            if patch_vaccinated > 0:
                patches.states.S[patch_idx] -= patch_vaccinated
                patches.states.R[patch_idx] += patch_vaccinated

        return len(selected_indices)

    def initialize(self, model: BaseLaserModel) -> None:
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
        return self.params.sia_schedule
