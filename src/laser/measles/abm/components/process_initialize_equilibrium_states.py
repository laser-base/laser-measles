"""
Component for initializing the population in each of the model states by rough equilibrium of R0.
"""

import numpy as np
import polars as pl

from laser.measles.abm.base import PatchLaserFrame
from laser.measles.abm.base import PeopleLaserFrame
from laser.measles.abm.model import ABMModel
from laser.measles.components import BaseInitializeEquilibriumStatesParams
from laser.measles.components import BaseInitializeEquilibriumStatesProcess


class InitializeEquilibriumStatesParams(BaseInitializeEquilibriumStatesParams):
    """
    Parameters for the InitializeEquilibriumStatesProcess.
    """


class InitializeEquilibriumStatesProcess(BaseInitializeEquilibriumStatesProcess):
    """
    Initialize S, R states of the population in each of the model states by rough equilibrium of R0.

    This component extends the base functionality to handle both patch-level state counts
    and individual agent initialization consistent with those counts.
    """

    def _initialize(self, model: ABMModel) -> None:
        """
        Initialize the population in each of the model states by rough equilibrium of R0.

        For ABM models, this involves:
        1. Calculating equilibrium patch-level state counts
        2. Initializing individual agents with states consistent with patch counts
        3. Assigning patch_id and susceptibility values appropriately
        """
        # First, apply the base equilibrium calculation to patch states
        super()._initialize(model)

        # Now initialize the people LaserFrame to match the patch states
        self._initialize_people_from_patches(model)

    def _initialize_people_from_patches(self, model: ABMModel) -> None:
        """
        Initialize individual agents to match the patch-level state counts.
        """
        # Get scenario data
        scenario = model.scenario
        scenario_df = scenario.unwrap()

        people: PeopleLaserFrame = model.people
        patches: PatchLaserFrame = model.patches
        num_active = len(model.people)

        # Assign patch_id to each agent based on patch population
        people.patch_id[:num_active] = np.array(
            scenario_df.with_row_index().select(pl.col("index").repeat_by(pl.col("pop"))).explode("index")["index"].to_numpy(),
            dtype=people.patch_id.dtype,
        )

        # Initialize all agents as susceptible first
        people.state[:num_active] = model.params.states.index("S")
        people.susceptibility[:num_active] = 1.0

        # Now assign R state agents according to equilibrium calculation
        # We need to round the equilibrium counts to integers and adjust patch states to match
        current_index = 0
        for patch_idx in range(len(scenario_df)):
            patch_pop = scenario_df["pop"][patch_idx]

            # Calculate equilibrium R count for this patch and round to integer
            equilibrium_r_fraction = patch_pop * (1 - 1 / self.params.R0)
            patch_r_count = int(np.round(equilibrium_r_fraction))

            # Ensure we don't exceed the patch population or go negative
            patch_r_count = max(0, min(patch_r_count, patch_pop))
            patch_s_count = patch_pop - patch_r_count

            # Update patch states to match integer counts
            patches.states.S[patch_idx] = patch_s_count
            patches.states.R[patch_idx] = patch_r_count

            # Get indices of agents in this patch
            patch_agents = np.arange(current_index, current_index + patch_pop)

            # Randomly select agents to be in R state
            if patch_r_count > 0:
                r_agents = model.prng.choice(patch_agents, size=patch_r_count, replace=False)
                people.state[r_agents] = model.params.states.index("R")
                people.susceptibility[r_agents] = 0.0

            current_index += patch_pop

        if self.verbose:
            total_s = np.sum(people.state == model.params.states.index("S"))
            total_r = np.sum(people.state == model.params.states.index("R"))
            print(f"Initialized {total_s} susceptible and {total_r} recovered agents")
