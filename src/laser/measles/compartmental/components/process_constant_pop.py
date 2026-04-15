"""
Component defining the ConstantPopProcess, which handles the birth events in a model with constant population - that is, births == deaths.
"""

from laser.measles.components import BaseConstantPopParams
from laser.measles.components import BaseConstantPopProcess
from laser.measles.utils import cast_type


class ConstantPopParams(BaseConstantPopParams):
    pass


class ConstantPopProcess(BaseConstantPopProcess):
    """
    A component to handle the birth events in a model with constant population - that is, births == deaths.

    Attributes:

        model: The model instance containing population and parameters.
        verbose (bool): Flag to enable verbose output. Default is False.
        initializers (list): List of initializers to be called on birth events.
        metrics (DataFrame): DataFrame to holding timing metrics for initializers.
    """

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

        patches = model.patches

        # Get number of deaths per patch per state
        deaths = model.prng.poisson(lam=patches.states * self.mu_death, size=patches.states.shape)

        # Same number of births
        births = deaths.sum(axis=0)

        # update state counters
        patches.states -= cast_type(deaths, patches.states.dtype)
        patches.states.S += cast_type(births, patches.states.dtype)
