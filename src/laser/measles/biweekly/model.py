"""
A class to represent the biweekly model.
"""

import numpy as np
import polars as pl

from laser.measles.base import BaseLaserModel
from laser.measles.biweekly.base import BaseBiweeklyScenario
from laser.measles.biweekly.base import PatchLaserFrame
from laser.measles.biweekly.params import BiweeklyParams
from laser.measles.utils import StateArray
from laser.measles.utils import cast_type


class BiweeklyModel(BaseLaserModel):
    """Population-level measles model with 14-day (biweekly) timesteps.

    Tracks SEIR compartment counts per patch without individual agents,
    making it significantly faster than
    [`ABMModel`][laser.measles.abm.model.ABMModel] for large-scale parameter
    sweeps and multi-country analyses.  Choose this model when individual-level
    detail is not required and computational speed is a priority.  For daily
    timesteps with explicit SEIR compartment dynamics, see
    [`CompartmentalModel`][laser.measles.compartmental.model.CompartmentalModel].

    This is the first object created in the *build model* stage of the
    researcher workflow.  After construction, attach components with
    [`add_component`][laser.measles.base.BaseLaserModel.add_component] or
    by setting the `components` property, then call `model.run()`.

    Args:
        scenario (pl.DataFrame | BaseBiweeklyScenario): Metapopulation patch
            data.  Required columns: ``id`` (str), ``pop`` (int),
            ``lat`` (Float64), ``lon`` (Float64), ``mcv1`` (Float64).
            A plain `polars.DataFrame` is automatically wrapped.
        params (BiweeklyParams): Simulation parameters including
            ``num_ticks``, ``seed``, and ``start_time``.
        name (str): Display name for log messages.  Defaults to
            ``"biweekly"``.

    **Example:**

        ```python
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams

        params = BiweeklyParams(num_ticks=26, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario=df, params=params)
        model.components = [InfectionSeedingProcess, InfectionProcess]
        model.run()
        ```
    """

    patches: PatchLaserFrame

    # Specify the scenario wrapper class for auto-wrapping DataFrames
    scenario_wrapper_class = BaseBiweeklyScenario

    def __init__(self, scenario: BaseBiweeklyScenario | pl.DataFrame, params: BiweeklyParams, name: str = "biweekly") -> None:
        super().__init__(scenario, params, name)

        # Add patches to the model
        self.patches = PatchLaserFrame(capacity=len(scenario))

        # Create the state vector for each of the patches
        self.patches.states = StateArray(state_names=self.params.states, shape=(len(self.params.states), len(scenario)), state_axis=0)

        # Start with totally susceptible population
        self.patches.states.S[:] = scenario["pop"]

        return

    def __call__(self, model, tick: int) -> None:
        """
        Updates the model for the next tick.

        Args:

            model: The model containing the patches and their populations.
            tick (int): The current time step or tick.

        Returns:

            None
        """
        return

    def infect(self, indices: int | np.ndarray, num_infected: int | np.ndarray) -> None:
        """
        Infects the given nodes with the given number of infected individuals.

        Args:
            indices (int | np.ndarray): The indices of the nodes to infect.
            num_infected (int | np.ndarray): The number of infected individuals to infect.
        """

        self.patches.states.I[indices] += cast_type(num_infected, self.patches.states.dtype)
        self.patches.states.S[indices] -= cast_type(num_infected, self.patches.states.dtype)
        return

    def recover(self, indices: int | np.ndarray, num_recovered: int | np.ndarray) -> None:
        """
        Recovers the given nodes with the given number of recovered individuals.
        Moves individuals from Infected to Recovered compartment.

        Args:
            indices (int | np.ndarray): The indices of the nodes to recover.
            num_recovered (int | np.ndarray): The number of recovered individuals.
        """
        self.patches.states.R[indices] += cast_type(num_recovered, self.patches.states.dtype)  # Add to R
        self.patches.states.I[indices] -= cast_type(num_recovered, self.patches.states.dtype)  # Remove from I
        return

    def _setup_components(self) -> None:
        pass


# Create an alias for BiweeklyModel as Model
Model = BiweeklyModel
