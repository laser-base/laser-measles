"""
This module defines the `CompartmentalModel` class for SEIR simulation with daily timesteps

Classes:
    CompartmentalModel: A class to represent the compartmental SEIR model.

Imports:


Model Class:
    Methods:
        __init__(self, scenario: BaseScenario, parameters: CompartmentalParams, name: str = "compartmental") -> None:
            Initializes the model with the given scenario and parameters.

        components(self) -> list:
            Gets the list of components in the model.

        components(self, components: list) -> None:
            Sets the list of components in the model and initializes instances and phases.

        __call__(self, model, tick: int) -> None:
            Updates the model for a given tick.

        run(self) -> None:
            Runs the model for the specified number of ticks.

        visualize(self, pdf: bool = True) -> None:
            Generates visualizations of the model's results, either displaying them or saving to a PDF.

        plot(self, fig: Figure = None):
            Generates plots for the scenario patches and populations, distribution of day of birth, and update phase times.
"""

import numpy as np
import polars as pl

from laser.measles.base import BaseLaserModel
from laser.measles.compartmental.base import BaseCompartmentalScenario
from laser.measles.compartmental.base import PatchLaserFrame
from laser.measles.compartmental.params import CompartmentalParams
from laser.measles.utils import StateArray
from laser.measles.utils import cast_type


class CompartmentalModel(BaseLaserModel):
    """
    A class to represent the compartmental model with daily timesteps.

    Args:

        scenario (BaseScenario): A scenario containing the scenario data, including population, latitude, and longitude.
        params (CompartmentalParams): A set of parameters for the model.
        name (str, optional): The name of the model. Defaults to "compartmental".

    Notes:

        This class initializes the model with the given scenario and parameters. The scenario must include the following columns:

            - `id` (string): The name of the patch or location.
            - `pop` (integer): The population count for the patch.
            - `lat` (float degrees): The latitude of the patches (e.g., from geographic or population centroid).
            - `lon` (float degrees): The longitude of the patches (e.g., from geographic or population centroid).
            - `mcv1` (float): The MCV1 coverage for the patches.

        The default model uses SEIR compartments:
            - S: Susceptible individuals
            - E: Exposed individuals (infected but not yet infectious)
            - I: Infectious individuals
            - R: Recovered/immune individuals
    """

    # Specify the scenario wrapper class for auto-wrapping DataFrames
    scenario_wrapper_class = BaseCompartmentalScenario

    def __init__(
        self, scenario: BaseCompartmentalScenario | pl.DataFrame, params: CompartmentalParams, name: str = "compartmental"
    ) -> None:
        """
        Initialize the disease model with the given scenario and parameters.

        Args:

            scenario (BaseScenario): A scenario containing the scenario data, including population, latitude, and longitude.
            params (CompartmentalParams): A set of parameters for the model, including seed, num_ticks, beta, sigma, gamma, and other SEIR parameters.
            name (str, optional): The name of the model. Defaults to "compartmental".

        Returns:

            None
        """
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


# Create an alias for CompartmentalModel as Model
Model = CompartmentalModel
