from laser.measles.components import BaseCaseSurveillanceParams
from laser.measles.components import BaseCaseSurveillanceTracker


class CaseSurveillanceParams(BaseCaseSurveillanceParams):
    """Parameters for CaseSurveillanceParams (inherits all fields from base).

    **Example:**

        ```python
        from laser.measles.compartmental.components.tracker_case_surveillance import CaseSurveillanceParams

        params = CaseSurveillanceParams()
        ```
    """


class CaseSurveillanceTracker(BaseCaseSurveillanceTracker):
    """Tracks detected cases in the model.

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
        from laser.measles.compartmental import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = CompartmentalParams(num_ticks=365, seed=42, start_time="2000-01")
        model = CompartmentalModel(scenario, params)
        model.add_component(create_component(components.CaseSurveillanceTracker, components.CaseSurveillanceParams()))
        ```
    """
