"""
Component defining the ConstantPopProcess, which handles the birth events in a model with constant population - that is, births == deaths.
"""

import numpy as np
from pydantic import Field

from laser.measles.base import BaseLaserModel
from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess


class BaseConstantPopParams(BaseVitalDynamicsParams):
    """Parameters specific to the births process component."""

    crude_birth_rate: float = Field(default=20, description="Crude birth rate per 1000 people per year", ge=0.0)

    @property
    def crude_death_rate(self) -> float:
        """Death rate is always equal to birth rate to maintain constant population."""
        return self.crude_birth_rate


class BaseConstantPopProcess(BaseVitalDynamicsProcess):
    """
    A component to handle the birth events in a model with constant population - that is, births == deaths.

    Attributes:

        model: The model instance containing population and parameters.
        initializers (list): List of initializers to be called on birth events.
        metrics (DataFrame): DataFrame to holding timing metrics for initializers.
    """

    def __init__(self, model: BaseLaserModel, params: BaseConstantPopParams | None = None):
        """
        Initialize the Births component.

        Parameters:

            model (object): The model object which must have a `population` attribute.
            params (BirthsParams, optional): Component parameters. If None, uses model.params.

        """

        super().__init__(model)

        self.params = params if params is not None else BaseConstantPopParams()

        return

    def __call__(self, model, tick) -> None:
        """
        Adds new agents to each patch based on expected daily births calculated from CBR. Calls each of the registered initializers for the newborns.

        Args:

            model: The simulation model containing patches, population, and parameters.
            tick: The current time step in the simulation.

        Returns:

            None

        This method performs the following steps:

            1. Draw a random set of indices, or size size "number of births"  from the population,
        """
        raise NotImplementedError("This method should be implemented in the subclass.")

    @property
    def lambda_birth(self) -> float:
        """birth rate per tick"""
        return (1 + self.params.crude_birth_rate / 1000) ** (1 / 365 * self.model.params.time_step_days) - 1

    @property
    def mu_death(self) -> float:
        """death rate per tick"""
        return self.lambda_birth

    def calculate_capacity(self, model) -> np.ndarray:
        """
        Calculate the capacity of the model.
        """
        return model.scenario["pop"].sum()
