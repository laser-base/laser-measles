from laser.measles.components import BasePopulationTracker
from laser.measles.components import BasePopulationTrackerParams


class PopulationTracker(BasePopulationTracker):
    """Tracks the population size of each patch at each time tick.

    The recorded series lives on ``tracker.population_tracker`` (shape
    ``(n_patches, n_ticks)``) after ``model.run()``. Sum across the patch
    axis for the global population time series.

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = CompartmentalModel(scenario, params)
        model.add_component(create_component(components.PopulationTracker, components.PopulationTrackerParams()))
        model.run()

        # Read the recorded time series after the run.
        tracker = model.get_instance("PopulationTracker")[0]
        pop_per_patch = tracker.population_tracker     # shape (n_patches, n_ticks)
        pop_global = pop_per_patch.sum(axis=0)         # shape (n_ticks,)
        print(f"start: {pop_global[0]:,}, end: {pop_global[-1]:,}")
        ```
    """


class PopulationTrackerParams(BasePopulationTrackerParams):
    """Parameters for PopulationTrackerParams (inherits all fields from base).

    **Example:**

        ```python
        from laser.measles.compartmental.components.tracker_population import PopulationTrackerParams

        params = PopulationTrackerParams()
        ```
    """
