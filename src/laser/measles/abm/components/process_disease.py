"""
Component defining the DiseaseProcess, which simulates the disease progression in the ABM model with MCV1.
"""

import numpy as np
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from laser.measles.abm.model import ABMModel
from laser.measles.base import BaseComponent

# Import numba conditionally for the numba implementation
try:
    import numba as nb

    NUMBA_AVAILABLE = True
    NUM_THREADS = nb.get_num_threads()
except ImportError:
    NUMBA_AVAILABLE = False


# Numpy Implementation
def numpy_gamma_update(count, timers_0, timers_1, state, shape, scale, flow, patch_id):
    """Numpy function to check and update exposed timers for the population."""
    # Find individuals with active exposure timers
    active_mask = timers_0[:count] > 0
    active_indices = np.where(active_mask)[0]

    if len(active_indices) == 0:
        return

    # Decrement timers for active individuals
    timers_0[active_indices] -= 1

    # Find individuals transitioning from E to I (timer reaches 0)
    transition_mask = timers_0[active_indices] <= 0
    transition_indices = active_indices[transition_mask]

    if len(transition_indices) > 0:
        # Set infectious timers using gamma distribution
        new_timers = np.maximum(1, np.round(np.random.gamma(shape, scale, len(transition_indices))))
        timers_1[transition_indices] = new_timers.astype(np.uint16)

        # Update state to infectious (I)
        state[transition_indices] = 2

        # Update flow counts by patch
        patch_counts = np.bincount(patch_id[transition_indices], minlength=len(flow))
        flow += patch_counts.astype(np.uint32)


# Numba Implementation (if available)
if NUMBA_AVAILABLE:

    @nb.njit(
        (nb.uint32, nb.uint16[:], nb.uint16[:], nb.uint8[:], nb.float32, nb.float32, nb.uint32[:], nb.uint16[:]), parallel=True, cache=True
    )
    def nb_gamma_update(count, timers_0, timers_1, state, shape, scale, flow, patch_id):  # pragma: no cover
        """Numba compiled function to check and update exposed timers for the population in parallel."""
        max_node_id = np.max(patch_id) + 1
        thread_flow = np.zeros((NUM_THREADS, max_node_id), dtype=np.uint32)

        for i in nb.prange(count):
            timer_0 = timers_0[i]
            if timer_0 > 0:
                timer_0 -= 1
                # if we have decremented etimer from >0 to <=0, set infectious timer.
                if timer_0 <= 0:
                    timers_1[i] = np.maximum(np.uint16(1), np.uint16(np.round(np.random.gamma(shape, scale))))
                    thread_flow[nb.get_thread_id(), patch_id[i]] += 1
                    state[i] = 2
                timers_0[i] = timer_0
        flow[:] += thread_flow.sum(axis=0)
        return
else:
    nb_gamma_update = None


# Numpy Implementation
def numpy_state_update(count, timers, state, new_state, flow, patch_id):
    """Numpy function to check and update infection timers for the population."""
    # Find individuals with active timers
    active_mask = timers[:count] > 0
    active_indices = np.where(active_mask)[0]

    if len(active_indices) == 0:
        return

    # Decrement timers for active individuals
    timers[active_indices] -= 1

    # Find individuals transitioning (timer reaches 0)
    transition_mask = timers[active_indices] == 0
    transition_indices = active_indices[transition_mask]

    if len(transition_indices) > 0:
        # Update state
        state[transition_indices] = new_state

        # Update flow counts by patch
        patch_counts = np.bincount(patch_id[transition_indices], minlength=len(flow))
        flow += patch_counts.astype(np.uint32)


# Numba Implementation (if available)
if NUMBA_AVAILABLE:

    @nb.njit((nb.uint32, nb.uint16[:], nb.uint8[:], nb.uint8, nb.uint32[:], nb.uint16[:]), parallel=True, cache=True)
    def nb_state_update(count, timers, state, new_state, flow, patch_id):  # pragma: no cover
        """Numba compiled function to check and update infection timers for the population in parallel."""
        max_patch_id = np.max(patch_id) + 1
        thread_flow = np.zeros((NUM_THREADS, max_patch_id), dtype=np.uint32)
        for i in nb.prange(count):
            timer = timers[i]
            if timer > 0:
                timer -= 1
                if timer == 0:
                    thread_flow[nb.get_thread_id(), patch_id[i]] += 1
                    state[i] = new_state
                timers[i] = timer
        flow[:] += thread_flow.sum(axis=0)
        return
else:
    nb_state_update = None


class DiseaseParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inf_mean: float = Field(default=8.0, description="Mean infectious period (days)")
    inf_sigma: float = Field(default=2.0, description="Shape of the infectious period (days)")

    @property
    def inf_shape(self) -> float:
        return (self.inf_mean / self.inf_sigma) ** 2

    @property
    def inf_scale(self) -> float:
        return self.inf_sigma**2 / self.inf_mean


class DiseaseProcess(BaseComponent):
    """
    This component provides disease progression (E->I->R)
    It is used to update the infectious timers and the exposed timers.
    """

    def __init__(self, model, params: DiseaseParams | None = None):
        super().__init__(model)
        self.params = params if params is not None else DiseaseParams()

    def __call__(self, model, tick: int) -> None:
        people = model.people
        patches = model.patches
        flow = np.zeros(len(model.patches), dtype=np.uint32)
        # Update the infectious timers
        # I --> R
        self.state_update_func(people.count, people.itimer, people.state, np.uint8(model.params.states.index("R")), flow, people.patch_id)
        patches.states.I -= flow
        patches.states.R += flow

        # Update the exposure timers for the population in the model,
        # move to infectious which follows a gamma distribution
        flow = np.zeros(len(model.patches), dtype=np.uint32)
        self.gamma_update_func(
            people.count,
            people.etimer,
            people.itimer,
            people.state,
            self.params.inf_shape,
            self.params.inf_scale,
            flow,
            people.patch_id,
        )
        patches.states.E -= flow
        patches.states.I += flow
        return

    def _initialize(self, model: ABMModel) -> None:
        # Select function implementations based on model configuration
        self.state_update_func = self.select_function(numpy_state_update, nb_state_update)
        self.gamma_update_func = self.select_function(numpy_gamma_update, nb_gamma_update)
