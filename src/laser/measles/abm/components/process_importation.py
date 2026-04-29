"""
This module defines Importation classes, which provide methods to import cases into a population during simulation.

Classes:
    Infect_Random_Agents: A class to periodically infect a random subset of agents in the population

Functions:
    Infect_Random_Agents.__init__(self, model, period, count, start, verbose: bool = False) -> None:
        Initializes the Infect_Random_Agents class with a given model, period, count, and verbosity option.

    Infect_Random_Agents.__call__(self, model, tick) -> None:
        Checks whether it is time to infect a random subset of agents and infects them if necessary.

    Infect_Random_Agents.plot(self, fig: Figure = None):
        Nothing yet.
"""

import numpy as np
from matplotlib.figure import Figure
from pydantic import BaseModel
from pydantic import Field

from ..utils import seed_infections_in_patch
from ..utils import seed_infections_randomly


class ImportationParams(BaseModel):
    """Parameters specific to the importation process components.

    **Example:**

        ```python
        from laser.measles.abm.components.process_importation import ImportationParams

        params = ImportationParams()
        ```
    """

    nticks: int = Field(description="Total number of simulation ticks", gt=0)
    importation_period: int = Field(description="Period between importation events", gt=0)
    importation_count: int = Field(description="Number of agents to import per event", gt=0)
    importation_start: int | None = Field(default=0, description="Start tick for importations", ge=0)
    importation_end: int | None = Field(default=None, description="End tick for importations")
    importation_patchlist: list | None = Field(default=None, description="List of patches to import into")


class InfectRandomAgentsProcess:
    """
    A component to update the infection timers of a population in a model.
    

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.InfectRandomAgentsProcess, components.ImportationParams()))
        ```
    """

    def __init__(self, model, verbose: bool = False, params: ImportationParams | None = None) -> None:
        """
        Initialize an Infect_Random_Agents instance.

        Args:

            model: The model object that contains the population.
            period: The number of ticks between each infection event.
            count: The number of agents to infect at each event.
            start (int, optional): The tick at which to start the infection events.
            verbose (bool, optional): If True, enables verbose output. Defaults to False.

        Attributes:

            model: The model object that contains the population.

        Side Effects:

        """

        self.model = model
        if params is None:
            # Use model.params for backward compatibility
            params = ImportationParams(
                nticks=model.params.nticks,
                importation_period=model.params.importation_period,
                importation_count=model.params.importation_count,
                importation_start=getattr(model.params, "importation_start", 0),
                importation_end=getattr(model.params, "importation_end", None),
            )
        self.params = params

        self.period = self.params.importation_period
        self.count = self.params.importation_count
        self.start = self.params.importation_start or 0
        self.end = self.params.importation_end or self.params.nticks

        return

    def __call__(self, model, tick) -> None:
        """
        Updates the infection timers for the population in the model.

        Args:

            model: The model containing the population data.
            tick: The current tick or time step in the simulation.

        Returns:

            None
        """
        if (tick >= self.start) and ((tick - self.start) % self.period == 0) and (tick < self.end):
            inf_nodeids = seed_infections_randomly(model, self.count)
            if hasattr(model.patches, "cases_test"):
                unique, counts = np.unique(inf_nodeids, return_counts=True)
                for nodeid, count in zip(unique, counts, strict=False):
                    model.patches.cases_test[tick + 1, nodeid] += count
                    model.patches.susceptibility_test[tick + 1, nodeid] -= count

        return

    def plot(self, fig: Figure | None = None):
        """
        Nothing yet
        """
        return


class InfectAgentsInPatchProcess:
    """
    A component to update the infection timers of a population in a model.
    

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.InfectAgentsInPatchProcess, components.ImportationParams()))
        ```
    """

    def __init__(self, model, verbose: bool = False, params: ImportationParams | None = None) -> None:
        """
        Initialize an Infect_Random_Agents instance.

        Args:

            model: The model object that contains the population.
            period: The number of ticks between each infection event.
            count: The number of agents to infect at each event.
            start (int, optional): The tick at which to start the infection events.
            verbose (bool, optional): If True, enables verbose output. Defaults to False.

        Attributes:

            model: The model object that contains the population.

        Side Effects:

        """

        self.model = model
        if params is None:
            # Use model.params for backward compatibility
            params = ImportationParams(
                nticks=model.params.nticks,
                importation_period=model.params.importation_period,
                importation_count=getattr(model.params, "importation_count", 1),
                importation_start=getattr(model.params, "importation_start", 0),
                importation_end=getattr(model.params, "importation_end", None),
                importation_patchlist=getattr(model.params, "importation_patchlist", None),
            )
        self.params = params

        self.period = self.params.importation_period
        self.count = self.params.importation_count or 1
        self.patchlist = self.params.importation_patchlist or np.arange(model.patches.count)
        self.start = self.params.importation_start or 0
        self.end = self.params.importation_end or self.params.nticks

        return

    def __call__(self, model, tick) -> None:
        """
        Updates the infection timers for the population in the model.

        Args:

            model: The model containing the population data.
            tick: The current tick or time step in the simulation.

        Returns:

            None
        """
        if (tick >= self.start) and ((tick - self.start) % self.period == 0) and (tick < self.end):
            for patch in self.patchlist:
                seed_infections_in_patch(model, patch, self.count)

        return

    def plot(self, fig: Figure | None = None):
        """
        Nothing yet
        """
        return
