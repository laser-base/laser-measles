"""
Component defining the ConstantPopProcess, which handles the birth events in a model with constant population - that is, births == deaths.
"""

from laser.measles.components import BaseConstantPopParams
from laser.measles.components import BaseConstantPopProcess
from laser.measles.utils import cast_type


class ConstantPopParams(BaseConstantPopParams):
    """Parameters for constant-population vital dynamics (inherits all fields from base).

    **Example:**

        ```python
        from laser.measles.biweekly.components.process_constant_pop import ConstantPopParams

        params = ConstantPopParams(crude_birth_rate=20)
        ```
    """


class ConstantPopProcess(BaseConstantPopProcess):
    """
    A component to handle the birth events in a model with constant population - that is, births == deaths.

    Attributes:

        model: The model instance containing population and parameters.
        initializers (list): List of initializers to be called on birth events.
        metrics (DataFrame): DataFrame to holding timing metrics for initializers.


    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.ConstantPopProcess, components.ConstantPopParams(crude_birth_rate=20)))
        ```
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
