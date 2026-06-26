"""Compartmental SEIR model for measles transmission with daily timesteps."""

from pathlib import Path

import numpy as np
import polars as pl

from laser.measles.base import BaseLaserModel
from laser.measles.compartmental.base import BaseCompartmentalScenario
from laser.measles.compartmental.base import PatchLaserFrame
from laser.measles.compartmental.params import CompartmentalParams
from laser.measles.utils import StateArray
from laser.measles.utils import cast_type


class CompartmentalModel(BaseLaserModel):
    """Population-level SEIR model for measles transmission with daily timesteps.

    Tracks compartment counts (S, E, I, R) per patch using deterministic
    difference equations.  This model is the fastest option for calibrating
    transmission parameters to surveillance data because it avoids stochastic
    noise.  For individual-level tracking, see
    [`ABMModel`][laser.measles.abm.model.ABMModel]; for 14-day timesteps, see
    [`BiweeklyModel`][laser.measles.biweekly.model.BiweeklyModel].

    This is the first object created in the *build model* stage of the
    researcher workflow.  After construction, attach components with
    [`add_component`][laser.measles.base.BaseLaserModel.add_component] or
    by setting the `components` property, then call `model.run()`.

    Args:
        scenario (pl.DataFrame | BaseCompartmentalScenario): Metapopulation
            patch data.  Required columns: ``id`` (str), ``pop`` (int),
            ``lat`` (Float64), ``lon`` (Float64), ``mcv1`` (Float64).
            A plain `polars.DataFrame` is automatically wrapped.
        params (CompartmentalParams): Simulation parameters including
            ``num_ticks``, ``seed``, and ``start_time``.
        name (str): Display name for log messages.  Defaults to
            ``"compartmental"``.

    Examples:

        import laser.measles as lm
        from laser.measles.compartmental.components import (
            InfectionSeedingProcess,
            InfectionProcess,
        )

        params = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = lm.CompartmentalModel(scenario=df, params=params)
        model.components = [InfectionSeedingProcess, InfectionProcess]
        model.run()
    """

    # Specify the scenario wrapper class for auto-wrapping DataFrames
    scenario_wrapper_class = BaseCompartmentalScenario

    def __init__(
        self, scenario: BaseCompartmentalScenario | pl.DataFrame, params: CompartmentalParams, name: str = "compartmental"
    ) -> None:
        super().__init__(scenario, params, name)

        # Add patches to the model
        self.patches = PatchLaserFrame(capacity=len(scenario))

        # Create the state vector for each of the patches
        self.patches.states = StateArray(
            state_names=self.params.states,
            shape=(len(self.params.states), len(scenario)),
            state_axis=0,
        )

        # Start with totally susceptible population
        self.patches.states.S[:] = scenario["pop"]  # All susceptible initially
        self.patches.states.E[:] = 0  # No exposed initially
        self.patches.states.I[:] = 0  # No infected initially
        self.patches.states.R[:] = 0  # No recovered initially

        return

    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        return

    def expose(self, indices: int | np.ndarray, num_exposed: int | np.ndarray) -> None:
        """
        Exposes the given nodes with the given number of exposed individuals.
        Moves individuals from Susceptible to Exposed compartment.

        Args:
            indices (int | np.ndarray): The indices of the nodes to expose.
            num_exposed (int | np.ndarray): The number of exposed individuals.
        """
        self.patches.states.E[indices] += cast_type(num_exposed, self.patches.states.dtype)  # Add to E
        self.patches.states.S[indices] -= cast_type(num_exposed, self.patches.states.dtype)  # Remove from S
        return

    def infect(self, indices: int | np.ndarray, num_infected: int | np.ndarray) -> None:
        """
        Infects the given nodes with the given number of infected individuals.
        Moves individuals from Exposed to Infected compartment.

        Args:
            indices (int | np.ndarray): The indices of the nodes to infect.
            num_infected (int | np.ndarray): The number of infected individuals.
        """
        self.patches.states.I[indices] += cast_type(num_infected, self.patches.states.dtype)  # Add to I
        self.patches.states.E[indices] -= cast_type(num_infected, self.patches.states.dtype)  # Remove from E
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

    @classmethod
    def from_snapshot(
        cls, path: str | Path, params: CompartmentalParams, components: list | None = None, verbose: bool = True
    ) -> "CompartmentalModel":
        """Load a CompartmentalModel from an HDF5 snapshot.

        Convenience wrapper around
        [`load_snapshot`][laser.measles.compartmental.snapshot.load_snapshot].
        Use this to resume a simulation from a checkpoint saved with
        [`save_snapshot`][laser.measles.compartmental.snapshot.save_snapshot].

        Args:
            path: Path to the HDF5 file written by
                [`save_snapshot`][laser.measles.compartmental.snapshot.save_snapshot].
            params:
                [`CompartmentalParams`][laser.measles.compartmental.params.CompartmentalParams]
                for the resumed segment.
            components: Ordered list of component *classes* — same as the
                original model, minus ``InfectionSeedingProcess``.
            verbose: Print a loading summary.

        Returns:
            A configured
                [`CompartmentalModel`][laser.measles.compartmental.model.CompartmentalModel]
                ready for ``model.run()``.

        Examples:

            import laser.measles as lm
            from laser.measles.compartmental.components import InfectionProcess

            params2 = lm.CompartmentalParams(num_ticks=365, seed=42, start_time="2001-01")
            model2 = lm.CompartmentalModel.from_snapshot(
                "checkpoint.h5", params2, components=[InfectionProcess]
            )
            model2.run()
        """
        from laser.measles.compartmental.snapshot import load_snapshot  # noqa: PLC0415

        return load_snapshot(path, params, components=components, verbose=verbose)


# Create an alias for CompartmentalModel as Model
Model = CompartmentalModel
