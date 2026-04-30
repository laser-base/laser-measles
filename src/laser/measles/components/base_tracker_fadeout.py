"""
FadeOutTracker component for tracking the number of nodes with fade-outs.

This module provides a component that monitors and records the number of nodes that have
experienced fade-outs (state transitions to 0) at each time tick in the simulation.
The tracker maintains a time series of fade-out counts that can be used for analysis
and visualization of the model's behavior over time.
"""

import numpy as np
from pydantic import BaseModel

from laser.measles.base import BaseLaserModel
from laser.measles.base import BasePhase


class BaseFadeOutTrackerParams(BaseModel):
    """Parameters for the FadeOutTracker component."""


class BaseFadeOutTracker(BasePhase):
    """A phase that tracks and records the number of nodes experiencing fade-outs over time.

    This component maintains a time series of fade-out counts by monitoring the number of nodes
    that have transitioned to state 0 at each simulation tick. The data can be used for
    analyzing the temporal dynamics of fade-outs in the network.

    Attributes:
        fade_out_tracker (numpy.ndarray): An array of length nticks that stores the count of
            nodes in state 0 at each time tick.

    Args:
        model: The simulation model instance.
    """

    def __init__(self, model) -> None:
        super().__init__(model)
        self.fade_out_tracker = np.zeros(model.params.num_ticks)

    def __call__(self, model, tick: int) -> None:
        self.fade_out_tracker[tick] = np.sum(model.patches.states.I == 0)  # number of nodes with 0 in I state

    def initialize(self, model: BaseLaserModel) -> None:
        pass
