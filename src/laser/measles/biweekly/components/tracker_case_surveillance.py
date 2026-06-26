from laser.measles.components import BaseCaseSurveillanceParams
from laser.measles.components import BaseCaseSurveillanceTracker


class CaseSurveillanceParams(BaseCaseSurveillanceParams):
    """Parameters for CaseSurveillanceParams (inherits all fields from base).

    Examples:

        from laser.measles.biweekly.components.tracker_case_surveillance import CaseSurveillanceParams

        params = CaseSurveillanceParams()
    """


class CaseSurveillanceTracker(BaseCaseSurveillanceTracker):
    """Tracks detected cases in the model.

    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.CaseSurveillanceTracker, components.CaseSurveillanceParams()))
    """
