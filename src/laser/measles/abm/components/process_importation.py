"""
Importation components: periodically introduce new infections into a population during simulation.

Classes:
    ImportationParams: Pydantic schema for configuring importation cadence, count, time window, and patch targets.
    InfectRandomAgentsProcess: Periodically infects a random subset of agents drawn from anywhere in the population.
    InfectAgentsInPatchProcess: Periodically infects a fixed number of agents in each patch listed in ``importation_patchlist`` (defaults to all patches).

Both process classes share the same ``__init__(model, params: ImportationParams | None = None)`` signature; if ``params`` is omitted, values are read from ``model.params`` for backward compatibility.
"""

import numpy as np
from matplotlib.figure import Figure
from pydantic import BaseModel
from pydantic import Field

from ..utils import seed_infections_in_patch
from ..utils import seed_infections_randomly


class ImportationParams(BaseModel):
    """Parameters specific to the importation process components."""

    nticks: int = Field(description="Total number of simulation ticks", gt=0)
    importation_period: int = Field(description="Period between importation events", gt=0)
    importation_count: int = Field(description="Number of agents to import per event", gt=0)
    importation_start: int | None = Field(default=0, description="Start tick for importations", ge=0)
    importation_end: int | None = Field(default=None, description="End tick for importations")
    importation_patchlist: list | None = Field(default=None, description="List of patches to import into")


class InfectRandomAgentsProcess:
    """
    A component to update the infection timers of a population in a model.
    """

    def __init__(self, model, params: ImportationParams | None = None) -> None:
        """
        Initialize an InfectRandomAgentsProcess instance.

        Args:
            model: The model object that contains the population.
            params: Optional importation configuration. If provided, this should be an
                ``ImportationParams`` instance whose ``importation_period``,
                ``importation_count``, and ``importation_start`` fields are used to
                initialize this process's ``period``, ``count``, and ``start``
                attributes (and ``importation_end`` maps to ``end``). If ``None``,
                the values are loaded from ``model.params`` for backward compatibility.

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
    """

    def __init__(self, model, params: ImportationParams | None = None) -> None:
        """
        Initialize an InfectAgentsInPatchProcess instance.

        Args:
            model: The model object that contains the population.
            params: Optional importation configuration. When provided, this should
                be an ``ImportationParams`` instance whose
                ``importation_period``, ``importation_count``,
                ``importation_start``, ``importation_end``, and
                ``importation_patchlist`` fields control the timing, number of
                imported infections, start/end ticks, and patches targeted by
                this process. If ``None``, these values are populated from
                ``model.params`` for backward compatibility.

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
