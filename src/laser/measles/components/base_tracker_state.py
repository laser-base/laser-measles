import inspect
from collections.abc import Callable

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.figure import Figure
from pydantic import BaseModel
from pydantic import Field

from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase
from laser.measles.base import StateArray


class BaseStateTrackerParams(BaseModel):
    """Parameters specific to the state tracker component.

    Attributes:
        filter_fn: Function to filter which nodes to include in aggregation.
        aggregation_level: Controls the geographic level at which states are reported.

            - ``-1`` (default): Sum over all patches; ``get_dataframe()`` returns a single
              row per tick/state with ``patch_id="all_patches"``.
            - ``0``: Aggregate to the top level of the node-ID hierarchy (e.g. ``"NG"`` from
              ``"NG:KN:LGA"``).
            - ``N >= 0``: Keep the first ``N+1`` colon-separated components of the node ID
              (e.g. ``aggregation_level=1`` → ``"NG:KN"`` from ``"NG:KN:LGA"``).

            To get **per-patch** data, set ``aggregation_level`` to the depth of your hierarchy
            minus one.  For flat IDs (no ``":"``), ``aggregation_level=0`` gives per-patch rows.
            The ``patch_id`` column in ``get_dataframe()`` matches the ``id`` column of the
            scenario DataFrame at the requested hierarchy level.
    """

    filter_fn: Callable[[str], bool] = Field(default=lambda x: True, description="Function to filter which nodes to include in aggregation")
    aggregation_level: int = Field(
        default=-1,
        description=(
            "Geographic aggregation level. -1 = sum all patches; "
            "N >= 0 = keep first N+1 colon-separated ID components. "
            "Use the hierarchy depth minus one to get per-patch rows."
        ),
    )


class BaseStateTracker(BasePhase):
    """
    Component for tracking the number in each SEIR state for each time tick.

    This class maintains a time series of state counts across nodes in the model.
    The states are dynamically generated as properties based on model.params.states
    (e.g., "S", "E", "I", "R"). Each state can be accessed as a property that returns
    a numpy array containing the time series for that state.

    The tracking can be done at different aggregation levels:
    - aggregation_level = -1: Sum over all patches (default, backward compatible)
    - aggregation_level >= 0: Group by geographic level and track separately

    Args:
        model: The simulation model containing nodes, states, and parameters.
        verbose: Whether to print verbose output during simulation. Defaults to False.
        params: Component-specific parameters. If None, will use default parameters.
    """

    def __init__(self, model, verbose: bool = False, params: BaseStateTrackerParams | None = None) -> None:
        super().__init__(model, verbose)
        self.name = "StateTracker"
        self.params = params or BaseStateTrackerParams()
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
                    self.node_indices.append(node_idx)

        # Initialize state tracker with appropriate shape
        if self.params.aggregation_level >= 0:
            # Shape: (num_states, num_ticks, num_groups)
            num_groups = len(self.node_mapping)
            self.group_ids = sorted(self.node_mapping.keys())
        else:
            # Shape: (num_states, num_ticks, 1) - sum over all patches
            num_groups = 1
            self.group_ids = ["all_patches"]

        self.state_tracker = StateArray(
            state_names=model.params.states,
            shape=(len(model.params.states), model.params.num_ticks, num_groups),
            state_axis=0,
            dtype=model.patches.states.dtype,
        )

        # Dynamically create properties for each state
        for i, state in enumerate(model.params.states):
            setattr(self.__class__, state, property(lambda self, idx=i: self._get_state_data(idx)))

    def _validate_params(self) -> None:
        """Validate component parameters.

        Raises:
            ValueError: If aggregation_level is less than -1.
        """
        if self.params.aggregation_level < -1:
            raise ValueError("aggregation_level must be at least -1")

    def _get_state_data(self, state_idx: int) -> np.ndarray:
        """Get state data for a specific state index.

        Args:
            state_idx: Index of the state to retrieve.

        Returns:
            Array of shape (num_ticks,) for aggregation_level = -1,
            or (num_ticks, num_groups) for aggregation_level >= 0.
        """
        if self.params.aggregation_level == -1:
            # Return (num_ticks,) for backward compatibility
            return self.state_tracker[state_idx, :, 0]
        else:
            # Return (num_ticks, num_groups)
            return self.state_tracker[state_idx, :, :]

    def __call__(self, model, tick: int) -> None:
        if self.params.aggregation_level >= 0:
            # For each group, aggregate states from its nodes
            for group_idx, (_, node_indices) in enumerate(self.node_mapping.items()):
                # Get states for this group's nodes and sum them
                group_states = model.patches.states[:, node_indices].sum(axis=1)
                self.state_tracker[:, tick, group_idx] = group_states
        else:
            # Sum over all filtered patches (default behavior)
            if self.node_indices:
                # Use filtered nodes
                filtered_states = model.patches.states[:, self.node_indices].sum(axis=1)
            else:
                # Use all patches (backward compatibility)
                filtered_states = model.patches.states.sum(axis=1)
            self.state_tracker[:, tick, 0] = filtered_states

    def plot(self, fig: Figure | None = None):
        """
        Plots the time series of SEIR state counts across all nodes using subplots.

        This function creates a separate subplot for each state, showing how the number of individuals
        in each state changes over time. Each state gets its own subplot for better visibility.

        Parameters:
            fig (Figure, optional): A matplotlib Figure object. If None, a new figure will be created.

        Yields:
            None: This function uses a generator to yield control back to the caller.
            If used directly (not as a generator), it will show the plot immediately.

        Example:
            # Use as a generator (for model.visualize()):
            for _ in tracker.plot():
                plt.show()
        """
        n_states = len(self.model.params.states)
        fig = plt.figure(figsize=(12, 3 * n_states), dpi=128) if fig is None else fig
        fig.suptitle("SEIR State Counts Over Time")

        time = np.arange(self.model.params.num_ticks)
        colors = ["blue", "orange", "red", "green"]  # S, E, I, R

        for i, state in enumerate(self.model.params.states):
            ax = plt.subplot(n_states, 1, i + 1)
            color = colors[i] if i < len(colors) else "black"
            ax.plot(time, self._get_state_data(i), label=f"{state} (Total)", color=color, linewidth=2)
            ax.set_ylabel(f"Number in {state}")
            ax.grid(True, alpha=0.3)
            ax.legend()

            # Format y-axis with scientific notation for large numbers
            ax.ticklabel_format(style="scientific", axis="y", scilimits=(0, 0))

            # Only add xlabel to the bottom subplot
            if i == n_states - 1:
                ax.set_xlabel("Time (days)")

        plt.tight_layout()

        # Check if the function is being used as a generator
        frame = inspect.currentframe()
        try:
            yield
        finally:
            if frame:
                del frame

    def plot_combined(self, fig: Figure | None = None):
        """
        Plots all SEIR states on a single plot for easy comparison.

        Parameters:
            fig (Figure, optional): A matplotlib Figure object. If None, a new figure will be created.

        Yields:
            None: This function uses a generator to yield control back to the caller.
        """
        fig = plt.figure(figsize=(12, 6), dpi=128) if fig is None else fig

        time = np.arange(self.model.params.num_ticks)
        colors = ["blue", "orange", "red", "green"]  # S, E, I, R
        linestyles = ["-", "--", "-.", ":"]

        for i, state in enumerate(self.model.params.states):
            color = colors[i] if i < len(colors) else "black"
            linestyle = linestyles[i] if i < len(linestyles) else "-"
            plt.plot(time, self._get_state_data(i), label=f"{state}", color=color, linestyle=linestyle, linewidth=2)

        plt.xlabel("Time (days)")
        plt.ylabel("Number of Individuals")
        plt.title("SEIR Model Dynamics")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.ticklabel_format(style="scientific", axis="y", scilimits=(0, 0))
        plt.tight_layout()

        # Check if the function is being used as a generator
        frame = inspect.currentframe()
        try:
            yield
        finally:
            if frame:
                del frame

    def get_dataframe(self) -> pl.DataFrame:
        """Get a DataFrame of state counts over time.

        Returns:
            DataFrame with columns:
                - tick: Time step
                - state: State name (S, E, I, R, etc.)
                - patch_id: Patch/group identifier.  Matches the ``id`` column of the scenario
                  DataFrame at the requested ``aggregation_level``, or ``"all_patches"`` when
                  ``aggregation_level=-1`` (the default).
                - count: Number of individuals in this state
        """
        data = []

        for tick in range(self.model.params.num_ticks):
            for state_idx, state_name in enumerate(self.model.params.states):
                if self.params.aggregation_level >= 0:
                    # For each group
                    for group_idx, patch_id in enumerate(self.group_ids):
                        data.append(
                            {
                                "tick": tick,
                                "state": state_name,
                                "patch_id": patch_id,
                                "count": self.state_tracker[state_idx, tick, group_idx],
                            }
                        )
                else:
                    # Single aggregated value
                    data.append(
                        {"tick": tick, "state": state_name, "patch_id": "all_patches", "count": self.state_tracker[state_idx, tick, 0]}
                    )

        return pl.DataFrame(data)

    def _initialize(self, model: BaseLaserModel) -> None:
        pass
