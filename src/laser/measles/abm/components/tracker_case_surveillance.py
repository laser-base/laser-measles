from laser.measles.components import BaseCaseSurveillanceParams
from laser.measles.components import BaseCaseSurveillanceTracker


class CaseSurveillanceParams(BaseCaseSurveillanceParams):
    """Parameters for CaseSurveillanceParams (inherits all fields from base).

    Examples:

        from laser.measles.abm.components.tracker_case_surveillance import CaseSurveillanceParams

        params = CaseSurveillanceParams()
    """


class CaseSurveillanceTracker(BaseCaseSurveillanceTracker):
    """Case surveillance tracker for this model type.

    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.abm import ABMModel, ABMParams
        from laser.measles.abm import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
        model = ABMModel(scenario, params)
        model.add_component(create_component(components.CaseSurveillanceTracker, components.CaseSurveillanceParams()))
    """


"""Component for tracking detected cases in the model."""
