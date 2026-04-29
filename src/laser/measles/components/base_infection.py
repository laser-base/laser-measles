from abc import ABC

from pydantic import BaseModel
from pydantic import Field

from laser.measles.base import BasePhase


class BaseInfectionParams(BaseModel):
    """Parameters specific to the infection process component.

    **Example:**

        ```python
        from laser.measles.biweekly.components.process_infection import InfectionParams

        params = InfectionParams(beta=0.57, seasonality=0.2)
        ```
    """

    beta: float = Field(
        default=1, description="Base transmission rate (infections per day)", ge=0.0
    )  # beta = R0 / (mean infectious period)
    seasonality: float = Field(default=0.0, description="Seasonality factor, default is no seasonality", ge=0.0, le=1.0)
    season_start: int = Field(default=0, description="Season start tick (0-25)", ge=0, le=25)
    distance_exponent: float = Field(default=1.5, description="Distance exponent", ge=0.0)
    mixing_scale: float = Field(default=0.001, description="Mixing scale", ge=0.0)


class BaseInfectionProcess(BasePhase, ABC):
    """Base class for infection (transmission and disease progression).

    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.InfectionProcess, components.InfectionParams(beta=0.57)))
        ```
    """
