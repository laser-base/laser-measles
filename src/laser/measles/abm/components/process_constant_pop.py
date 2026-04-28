"""
Component defining the ConstantPopProcess, which handles the birth events in a model with constant population - that is, births == deaths.
"""

import numpy as np
import polars as pl

from laser.measles.abm.model import ABMModel
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

    def __init__(self, model: ABMModel, verbose: bool = False, params: ConstantPopParams | None = None):
        """
        Initialize the Births component.

        Parameters:

            model (object): The model object which must have a `population` attribute.
            verbose (bool, optional): If True, enables verbose output. Defaults to False.
            params (BirthsParams, optional): Component parameters. If None, uses model.params.

        """

        super().__init__(model, verbose)

        self.params = params if params is not None else ConstantPopParams()

        if getattr(model, "_from_snapshot", False):
            # ── Snapshot-load path ────────────────────────────────────────────
            # People frame already populated; only add fresh patch property.
            model.patches.add_scalar_property("births", dtype=np.uint32)
            return

        # ── Normal initialization ─────────────────────────────────────────────
        # re-initialize people frame with correct capacity
        capacity = self.calculate_capacity(model=model)
        model.initialize_people_capacity(capacity=int(capacity), initial_count=model.scenario["pop"].sum())

        model.people.add_scalar_property("date_of_birth", dtype=np.int32, default=model.params.num_ticks + 1)

        model.patches.add_scalar_property("births", dtype=np.uint32)

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

        if self.lambda_birth == 0:
            return

        patches = model.patches
        people = model.people
        populations = patches.states.sum(axis=0)

        # When we get to having birth rate per node, will need to be more clever here, but with constant birth rate across nodes,
        # random selection will be population proportional.  If node id is not contiguous, could be tricky?
        births = model.prng.poisson(lam=populations * self.lambda_birth, size=populations.shape)
        idx = model.prng.choice(populations.sum(), size=births.sum(), replace=False)

        # Get number of deaths per patch per state
        num_states = len(model.params.states)
        num_patches = len(patches)
        deaths = np.bincount(people.state[idx] * num_patches + people.patch_id[idx], minlength=num_patches * num_states)
        deaths = deaths.reshape((num_states, num_patches))

        # update state counters
        patches.states -= cast_type(deaths, patches.states.dtype)
        # Count births per patch from the actual agents being reborn (they keep their patch_id)
        actual_births_per_patch = np.bincount(people.patch_id[idx], minlength=num_patches)
        patches.states.S += cast_type(actual_births_per_patch, patches.states.dtype)

        # Births, set date of birth and state to 0 (susceptible)
        people.date_of_birth[idx] = tick  # set to current tick
        people.state[idx] = model.params.states.index("S")  # set to susceptible
        # Reset timers to prevent phantom state transitions from leftover timers
        if hasattr(people, "etimer"):
            people.etimer[idx] = 0
        if hasattr(people, "itimer"):
            people.itimer[idx] = 0

    def _initialize(self, model: ABMModel) -> None:
        """
        Simple initializer for ages where birth rate = mortality rate

        Args:
            model: The ABM model instance to initialize
        """
        if getattr(model, "_from_snapshot", False):
            # Population state already loaded from snapshot.
            return

        people = model.people
        scenario = model.scenario

        # Initialize patch_id according to scenario population
        people.patch_id[:] = np.array(
            scenario.with_row_index().select(pl.col("index").repeat_by(pl.col("pop"))).explode("index")["index"].to_numpy(),
            dtype=people.patch_id.dtype,
        )

        # Simple initializer for ages where birth rate = mortality rate:
        # Initialize ages for existing population
        if self.mu_death > 0:
            people.date_of_birth[0 : people.count] = cast_type(
                -1 * model.prng.exponential(1 / self.mu_death, people.count), people.date_of_birth.dtype
            )
