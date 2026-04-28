"""
Process for setting a static population (no vital dynamics).
"""

import numpy as np
import polars as pl

from laser.measles.abm.model import ABMModel
from laser.measles.base import BaseLaserModel
from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess


class NoBirthsParams(BaseVitalDynamicsParams):
    """Parameters for the no births process."""

    @property
    def crude_birth_rate(self) -> float:
        return 0.0

    @property
    def crude_death_rate(self) -> float:
        return 0.0


class NoBirthsProcess(BaseVitalDynamicsProcess):
    """
    Component for setting the population of the patches to not have births.
    """

    def __init__(
        self,
        model: BaseLaserModel,
        verbose: bool = False,
        params: NoBirthsParams | None = None,
    ) -> None:
        super().__init__(model, verbose)

        if params is None:
            params = NoBirthsParams()
        self.params = params

        return

    def __call__(self, model, tick) -> None:
        pass

    def calculate_capacity(self, model: ABMModel) -> int:
        """
        Calculate the capacity of the people laserframe.

        Args:
            model: The ABM model instance

        Returns:
            The total population capacity needed across all patches
        """
        return int(model.patches.states.sum())

    def _initialize(self, model: ABMModel) -> None:
        """
        Initialize the no births process by setting up the population.

        Args:
            model: The ABM model instance to initialize
        """
        if getattr(model, "_from_snapshot", False):
            # People frame (capacity, patch_id) already loaded from snapshot.
            return

        # initialize the people laserframe with correct capacity
        model.initialize_people_capacity(self.calculate_capacity(model))
        # people laserframe
        people = model.people
        # scenario dataframe
        scenario = model.scenario
        # initialize the patch ids according to the scenario population
        people.patch_id[:] = np.array(
            scenario.with_row_index().select(pl.col("index").repeat_by(pl.col("pop"))).explode("index")["index"].to_numpy(),
            dtype=people.patch_id.dtype,
        )
        return
