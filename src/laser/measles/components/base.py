from abc import abstractmethod

from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase


class BaseVitalDynamicsProcess(BasePhase):
    """Abstract base for vital-dynamics components (births, deaths, aging).

    Subclasses handle population turnover during the *per-timestep* stage of the
    simulation.  A vital-dynamics component must appear in the component list
    **before** any infection or transmission component so that the population
    counts are up-to-date when transmission is calculated.

    Subclasses must implement both `initialize` (called once at the start of
    `model.run()`) and `calculate_capacity` (called during model construction to
    pre-allocate agent storage in
    [`ABMModel`][laser.measles.abm.model.ABMModel]).


    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.VitalDynamicsProcess, components.VitalDynamicsParams()))
    """

    @abstractmethod
    def initialize(self, model: BaseLaserModel) -> None:
        """Set up initial population structure for the model.

        Called once at the beginning of `model.run()` before the first tick.
        Implementations typically distribute agents across age groups and
        vaccination states.

        Args:
            model: The simulation model instance.
        """
        ...

    @abstractmethod
    def calculate_capacity(self, model: BaseLaserModel) -> int:
        """Return the total agent capacity needed for the simulation.

        Called during model construction to pre-allocate the people
        LaserFrame.  The returned value should account for the initial
        population plus projected births over the full simulation duration.

        Args:
            model: The simulation model instance.

        Returns:
            Total number of agent slots to allocate.
        """
        ...
