from abc import ABC

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from laser.measles.base import BasePhase


class BaseInfectionParams(BaseModel):
    """Parameters specific to the infection process component."""

    model_config = ConfigDict(extra="forbid")

    beta: float = Field(
        default=1, description="Base transmission rate (infections per day)", ge=0.0
    )  # beta = R0 / (mean infectious period)
    seasonality: float = Field(default=0.0, description="Seasonality factor, default is no seasonality", ge=0.0, le=1.0)
    season_start: int = Field(default=0, description="Season start tick (0-25)", ge=0, le=25)
    distance_exponent: float = Field(default=1.5, description="Distance exponent", ge=0.0)
    mixing_scale: float = Field(default=0.001, description="Mixing scale", ge=0.0)


class BaseInfectionProcess(BasePhase, ABC):
    """Base class for infection (transmission and disease progression)."""
