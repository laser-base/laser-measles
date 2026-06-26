"""
Process for setting a static population (no vital dynamics).
"""

import numpy as np

from laser.measles.abm.model import ABMModel
from laser.measles.base import BaseLaserModel
from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess


class NoBirthsParams(BaseVitalDynamicsParams):
    """Parameters for the no births process.

    Examples:

        from laser.measles.abm.components.process_no_births import NoBirthsParams

        params = NoBirthsParams()
    """

    @property
    def crude_birth_rate(self) -> float:
        """Birth rate fixed at zero (no-birth scenario)."""
        return 0.0

    @property
    def crude_death_rate(self) -> float:
        """Death rate fixed at zero (no-birth scenario)."""
        return 0.0


class NoBirthsProcess(BaseVitalDynamicsProcess):
    """
    Component for setting the population of the patches to not have births.


    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.NoBirthsProcess, components.NoBirthsParams()))
    """

    def __init__(
        self,
        model: BaseLaserModel,
        params: NoBirthsParams | None = None,
    ) -> None:
        super().__init__(model)

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
        # initialize the patch ids according to the scenario population
        pops = model.scenario["pop"].to_numpy()
        people.patch_id[:] = np.repeat(np.arange(len(pops), dtype=people.patch_id.dtype), pops)
        return
