"""
Component for tracking case surveillance
"""

from collections.abc import Callable

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.figure import Figure
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase
from laser.measles.utils import cast_type


class BaseCaseSurveillanceParams(BaseModel):
    """Parameters specific to the case surveillance component.

    Attributes:
        detection_rate: Probability of detecting an infected case.
        filter_fn: Function to filter which nodes to include in aggregation.
        aggregate_cases: Whether to aggregate cases by geographic level.
        aggregation_level: Number of levels to use for aggregation (e.g., 2 for country:state:lga).
    """

    model_config = ConfigDict(extra="forbid")

    detection_rate: float = Field(default=0.1, description="Probability of detecting an infected case", ge=0.0, le=1.0)
    filter_fn: Callable[[str], bool] = Field(default=lambda x: True, description="Function to filter which nodes to include in aggregation")
    aggregation_level: int = Field(default=-1, description="Number of levels to use for aggregation (e.g., 2 for country:state:lga)")


class BaseCaseSurveillanceTracker(BasePhase):
    """Component for tracking detected cases in the model.

    This component:
    1. Simulates case detection based on a detection rate
    2. Optionally tracks detected cases aggregated by geographic level
    3. Uses a filter function to determine which nodes to include

    Case detection is simulated using a binomial distribution. Cases can be tracked
    at individual node level or aggregated by geographic level. Uses a filter function
    to determine which nodes to include. Note that a single infection can be detected multiple times.

    Args:
        model: The simulation model containing nodes, states, and parameters.
        params: Component-specific parameters. If None, will use default parameters.
    """

    def __init__(self, model, params: BaseCaseSurveillanceParams | None = None) -> None:
        super().__init__(model)
        self.params = params or BaseCaseSurveillanceParams()
        self._validate_params()

        # Extract node IDs and create mapping for filtered nodes
        self.node_mapping = {}
        self.node_indices = []

        for node_idx, node_id in enumerate(model.scenario["id"]):
            if self.params.filter_fn(node_id):
                if self.params.aggregation_level >= 0:
                    # Create geographic grouping key
                    group_key = ":".join(node_id.split(":")[: self.params.aggregation_level + 1])
                    if group_key not in self.node_mapping:
                        self.node_mapping[group_key] = []
                    self.node_mapping[group_key].append(node_idx)
                else:
                    group_key = node_id
                    self.node_mapping[group_key] = [node_idx]

        # Initialize reported cases tracker
        # For aggregated cases: nticks x num_groups
        self.reported_cases = np.zeros((len(self.node_mapping), model.params.num_ticks), dtype=model.patches.states.dtype)
        # Store group IDs in order
        self.group_ids = sorted(self.node_mapping.keys())

    def _validate_params(self) -> None:
        """Validate component parameters.

        Raises:
            ValueError: If aggregation_level is less than 1.
        """
        if self.params.aggregation_level < -1:
            raise ValueError("aggregation_level must be at least -1")

    def __call__(self, model, tick: int) -> None:
        """Process case surveillance for the current tick.

        Args:
            model: The simulation model.
            tick: Current time step.
        """
        # Get current infected cases
        infected = model.patches.states.I  # Infected state is index 1

        # For each group, aggregate detected cases from its nodes
        for group_idx, (_, node_indices) in enumerate(self.node_mapping.items()):
            # Get infected cases for this group's nodes
            group_infected = infected[node_indices]

            if self.params.detection_rate < 1:
                # Simulate case detection using binomial distribution
                detected_cases = cast_type(model.prng.binomial(n=group_infected, p=self.params.detection_rate), model.patches.states.dtype)
            else:
                # Otherwise report infections
                detected_cases = cast_type(group_infected, model.patches.states.dtype)

            # Store total detected cases for this group
            self.reported_cases[group_idx, tick] = detected_cases.sum()

    def get_dataframe(self) -> pl.DataFrame:
        """Get a DataFrame of reported cases over time.

        Returns:
            DataFrame with columns:
                - tick: Time step
                - patch_id: Patch/group identifier.  Matches the ``id`` column of the scenario
                  DataFrame at the requested ``aggregation_level``.
                - cases: Number of reported cases
        """
        # Create a list to store the data
        data = []

        # For each tick and group, add the reported cases
        for tick in range(self.model.params.num_ticks):
            for group_idx, patch_id in enumerate(self.group_ids):
                data.append({"tick": tick, "patch_id": patch_id, "cases": self.reported_cases[group_idx, tick]})
        # Create DataFrame
        return pl.DataFrame(data)

    def initialize(self, model: BaseLaserModel) -> None:
        pass

    def plot(self, fig: Figure | None = None):
        """Create a heatmap visualization of log(cases+1) over time.

        Args:
            fig: Existing figure to plot on. If None, a new figure will be created.

        Yields:
            The figure containing the heatmap visualization.
        """
        # Get the case data
        df = self.get_dataframe()

        # Convert to pandas for easier plotting
        pdf = df.to_pandas()

        # Create pivot table for heatmap
        pivot_df = pdf.pivot(index="patch_id", columns="tick", values="cases")

        # Create figure and axis if not provided
        if fig is None:
            fig, ax = plt.subplots(figsize=(12, 8))
        else:
            ax = fig.gca()

        # Create heatmap with log scale
        heatmap_data = np.log1p(pivot_df.values)
        im = ax.imshow(heatmap_data, aspect="auto", cmap="viridis")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("log(cases + 1)")

        # Set axis ticks and labels
        ax.set_xticks(np.arange(pivot_df.shape[1]))
        ax.set_xticklabels(pivot_df.columns)
        ax.set_yticks(np.arange(pivot_df.shape[0]))
        ax.set_yticklabels(pivot_df.index)

        # Customize plot
        ax.set_title("Log Cases Heatmap")
        ax.set_xlabel("Time Step")
        ax.set_ylabel("Location ID")

        # Rotate x-axis labels for better readability
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        # Adjust layout to prevent label cutoff
        plt.tight_layout()

        yield fig
