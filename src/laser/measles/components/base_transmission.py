"""Base transmission component for laser.measles models.

This module defines the common interface and parameters for transmission
components across different model types (ABM, biweekly, compartmental).
"""

from abc import ABC
from abc import abstractmethod

import numpy as np
from pydantic import BaseModel
from pydantic import Field

from ..base import BasePhase


class BaseTransmissionParams(BaseModel):
    """Common parameters for all transmission components."""

    # Core transmission parameters
    beta: float = Field(default=0.1, description="Transmission rate parameter", gt=0.0)

    # Seasonality parameters
    seasonal_amplitude: float = Field(default=0.0, description="Amplitude of seasonal variation (0.0 = no seasonality)", ge=0.0, le=1.0)
    seasonal_phase: float = Field(default=0.0, description="Phase offset for seasonal variation (in radians)", ge=0.0, le=2 * np.pi)

    # Spatial mixing parameters
    mixing_matrix: np.ndarray | None = Field(default=None, description="Spatial mixing matrix between patches")

    # Import/export parameters
    importation_rate: float = Field(default=0.0, description="Rate of imported infections per time step", ge=0.0)

    # Model-specific parameters that may be overridden
    random_seed: int | None = Field(default=None, description="Random seed for stochastic processes")

    class Config:
        arbitrary_types_allowed = True  # Allow numpy arrays


class BaseTransmission(BasePhase, ABC):
    """Abstract base class for transmission components.

    This class defines the common interface that all transmission
    components must implement, regardless of their underlying
    mathematical approach (agent-based, compartmental, etc.).
    """

    def __init__(self, model, params: BaseTransmissionParams | None = None):
        """Initialize the transmission component.

        Args:
            model: The model instance this component belongs to
            params: Component parameters (uses defaults if None)
        """
        super().__init__(model)
        self.params = params if params is not None else BaseTransmissionParams()

        # Set random seed if specified
        if self.params.random_seed is not None:
            np.random.seed(self.params.random_seed)

    @abstractmethod
    def __call__(self, model, tick: int):
        """Execute transmission dynamics for one time step.

        This method must be implemented by each model type to define
        how transmission occurs in that specific mathematical framework.

        Args:
            model: The model instance
            tick: Current time step
        """

    def get_force_of_infection(self, model, tick: int) -> np.ndarray:
        """Calculate force of infection for each patch.

        This method provides a common interface for calculating
        the force of infection, which can be overridden by
        model-specific implementations.

        Args:
            model: The model instance
            tick: Current time step

        Returns:
            Array of force of infection values per patch
        """
        # Default implementation - should be overridden by subclasses
        return np.zeros(model.n_patches)

    def get_seasonal_multiplier(self, tick: int, time_scale: str = "daily") -> float:
        """Calculate seasonal transmission multiplier.

        Args:
            tick: Current time step
            time_scale: Time scale of the model ('daily', 'biweekly')

        Returns:
            Seasonal multiplier (1.0 = no seasonal effect)
        """
        if self.params.seasonal_amplitude == 0.0:
            return 1.0

        # Convert tick to appropriate time scale
        if time_scale == "daily":
            t = tick / 365.25  # Convert to years
        elif time_scale == "biweekly":
            t = tick / 26.0  # Convert to years (26 biweekly periods per year)
        else:
            raise ValueError(f"Unknown time scale: {time_scale}")

        # Calculate seasonal variation
        seasonal_factor = 1.0 + self.params.seasonal_amplitude * np.sin(2 * np.pi * t + self.params.seasonal_phase)

        return max(0.0, seasonal_factor)  # Ensure non-negative

    def apply_spatial_mixing(self, local_infections: np.ndarray) -> np.ndarray:
        """Apply spatial mixing to infection rates.

        Args:
            local_infections: Local infection rates per patch

        Returns:
            Mixed infection rates accounting for spatial coupling
        """
        if self.params.mixing_matrix is None:
            return local_infections

        # Apply mixing matrix
        mixed_infections = np.dot(self.params.mixing_matrix, local_infections)
        return mixed_infections

    def get_effective_beta(self, tick: int, time_scale: str = "daily") -> float:
        """Get effective transmission rate accounting for seasonality.

        Args:
            tick: Current time step
            time_scale: Time scale of the model

        Returns:
            Effective transmission rate
        """
        seasonal_multiplier = self.get_seasonal_multiplier(tick, time_scale)
        return self.params.beta * seasonal_multiplier
