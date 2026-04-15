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
    """
    A class to represent the biweekly model.

    Args:

        scenario (BaseScenario): A scenario containing the scenario data, including population, latitude, and longitude.
        params (BiweeklyParams): A set of parameters for the model.
        name (str, optional): The name of the model. Defaults to "biweekly".

    Notes:

        This class initializes the model with the given scenario and parameters. The scenario must include the following columns:

            - `id` (string): The name of the patch or location.
            - `pop` (integer): The population count for the patch.
            - `lat` (float degrees): The latitude of the patches (e.g., from geographic or population centroid).
            - `lon` (float degrees): The longitude of the patches (e.g., from geographic or population centroid).
            - `mcv1` (float): The MCV1 coverage for the patches.
    """

    patches: PatchLaserFrame

    # Specify the scenario wrapper class for auto-wrapping DataFrames
    scenario_wrapper_class = BaseBiweeklyScenario

    def __init__(self, scenario: BaseBiweeklyScenario | pl.DataFrame, params: BiweeklyParams, name: str = "biweekly") -> None:
        """
        Initialize the disease model with the given scenario and parameters.

        Args:

            scenario (BaseScenario): A scenario containing the scenario data, including population, latitude, and longitude.
            params (BiweeklyParams): A set of parameters for the model, including seed, nticks, k, a, b, c, max_frac, cbr, verbose, and pyramid_file.
            name (str, optional): The name of the model. Defaults to "biweekly".

        Returns:

            None
        """
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
