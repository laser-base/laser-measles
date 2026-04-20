"""
Component defining the TransmissionProcess, which models the transmission of measles in a population.
"""

from typing import Any

import numpy as np
from pydantic import BaseModel
from pydantic import Field

from laser.measles.abm.model import ABMModel
from laser.measles.base import BasePhase
from laser.measles.migration import init_gravity_diffusion
from laser.measles.mixing.gravity import GravityMixing
from laser.measles.utils import cast_type

# Import numba conditionally for the numba implementation
try:
    import numba as nb

    NUMBA_AVAILABLE = True
    NUM_THREADS = nb.get_num_threads()
except ImportError:
    NUMBA_AVAILABLE = False


# Numpy Implementation
def numpy_lognormal_update(states, patch_ids, susceptibilties, forces, etimers, count, exp_mu, exp_sigma, flow):
    """Numpy function to stochastically transmit infection to agents."""
    # Find susceptible individuals (state == 0)
    susceptible_mask = states[:count] == 0
    susceptible_indices = np.where(susceptible_mask)[0]

    if len(susceptible_indices) == 0:
        return

    # Get patch IDs and forces for susceptible individuals
    susceptible_patches = patch_ids[susceptible_indices]
    susceptible_forces = forces[susceptible_patches]

    # Find individuals with positive force of infection
    positive_force_mask = susceptible_forces > 0
    at_risk_indices = susceptible_indices[positive_force_mask]

    if len(at_risk_indices) == 0:
        return

    # Stochastic transmission: draw random numbers and compare to force
    random_draws = np.random.random(len(at_risk_indices))
    infected_mask = random_draws < susceptible_forces[positive_force_mask]
    newly_infected_indices = at_risk_indices[infected_mask]

    if len(newly_infected_indices) > 0:
        # Update states to exposed (1)
        states[newly_infected_indices] = 1

        # Set exposure timers using lognormal distribution
        new_etimers = np.maximum(1, np.round(np.random.lognormal(exp_mu, exp_sigma, len(newly_infected_indices))))
        etimers[newly_infected_indices] = new_etimers.astype(np.uint16)

        # Set susceptibility to 0
        susceptibilties[newly_infected_indices] = 0.0

        # Update flow counts by patch
        infected_patches = patch_ids[newly_infected_indices]
        patch_counts = np.bincount(infected_patches, minlength=len(flow))
        flow[:] = patch_counts.astype(np.uint32)
    else:
        # No new infections
        flow[:] = 0


# Numba Implementation (if available)
if NUMBA_AVAILABLE:

    @nb.njit(
        (nb.uint8[:], nb.uint16[:], nb.float32[:], nb.float64[:], nb.uint16[:], nb.uint32, nb.float32, nb.float32, nb.uint32[:]),
        parallel=True,
        nogil=True,
        cache=True,
    )
    def nb_lognormal_update(states, patch_ids, susceptibilties, forces, etimers, count, exp_mu, exp_sigma, flow):  # pragma: no cover
        """Numba compiled function to stochastically transmit infection to agents in parallel."""
        max_node_id = np.max(patch_ids)
        thread_incidences = np.zeros((NUM_THREADS, max_node_id + 1), dtype=np.uint32)

        for i in nb.prange(count):
            state = states[i]
            if state == 0:
                patch_id = patch_ids[i]
                force = forces[patch_id]  # force of infection attenuated by personal susceptibility
                if (force > 0) and (np.random.random_sample() < force):  # draw random number < force means infection
                    states[i] = 1  # set state to exposed
                    # set exposure timer for newly infected individuals to a draw from a lognormal distribution, must be at least 1 day
                    etimers[i] = np.uint16(np.maximum(1, np.round(np.random.lognormal(exp_mu, exp_sigma))))
                    susceptibilties[i] = 0.0
                    thread_incidences[nb.get_thread_id(), patch_id] += 1

        flow[:] = thread_incidences.sum(axis=0)

        return
else:
    nb_lognormal_update = None


class TransmissionParams(BaseModel):
    """Parameters specific to the transmission process component."""

    model_config = {"arbitrary_types_allowed": True}

    beta: float = Field(default=1.0, description="Base transmission rate", ge=0.0)
    seasonality: float = Field(default=1.0, description="Seasonality factor", ge=0.0, le=1.0)
    season_start: float = Field(default=0.0, description="Seasonality phase", ge=0, le=364)
    exp_mu: float = Field(default=6.0, description="Exposure mean (days)", gt=0.0)
    exp_sigma: float = Field(default=2.0, description="Exposure sigma (days)", gt=0.0)
    mixer: Any = Field(default_factory=lambda: GravityMixing(), description="Mixing object")

    @property
    def mu_underlying(self) -> float:
        """The mean of the underlying lognormal distribution."""
        return np.log(self.exp_mu**2 / np.sqrt(self.exp_mu**2 + self.exp_sigma**2))

    @property
    def sigma_underlying(self) -> float:
        """The standard deviation of the underlying lognormal distribution."""
        return np.sqrt(np.log(1 + (self.exp_sigma / self.exp_mu) ** 2))


class TransmissionProcess(BasePhase):
    """
    A component to model the transmission of disease in a population.
    """

    def __init__(self, model, verbose: bool = False, params: TransmissionParams | None = None) -> None:
        """
        Initializes the transmission object.

        Args:

            model: The model object that contains the patches and parameters.
            verbose (bool, optional): If True, enables verbose output. Defaults to False.

        Attributes:

            model: The model object passed during initialization.

        The model's patches are extended with the following properties:

            - 'cases': A vector property with length equal to the number of ticks, dtype is uint32.
            - 'forces': A scalar property with dtype float32.
            - 'incidence': A vector property with length equal to the number of ticks, dtype is uint32.
        """

        super().__init__(model, verbose)

        self.params = params if params is not None else TransmissionParams()

        # Set mixer scenario
        self.params.mixer.scenario = model.scenario

        # add new properties to the laserframes
        assert hasattr(model.people, "susceptibility")  # susceptibility factor
        if not getattr(model, "_from_snapshot", False):
            # people properties already loaded from snapshot; skip re-adding
            model.people.add_scalar_property("etimer", dtype=np.uint16, default=0)  # exposure timer
            model.people.add_scalar_property("itimer", dtype=np.uint16, default=0)  # infection timer
        # patches are always freshly constructed — add regardless of snapshot mode
        model.patches.add_scalar_property("incidence", dtype=np.uint32, default=0)  # new infections per time step
        return

    def __call__(self, model, tick) -> None:
        """
        Simulate the transmission of measles for a given model at a specific tick.

        This method updates the state of the model by simulating the spread of disease
        through the population and patches. It calculates the contagion, handles the
        migration of infections between patches, and updates the forces of infection
        based on the effective transmission rate and seasonality factors. Finally, it
        updates the infected state of the population.

        Parameters:

            model (object): The model object containing the population, patches, and parameters.
            tick (int): The current time step in the simulation.

        Returns:

            None

        """
        # access the patch and people laserframes
        patches = model.patches
        people = model.people

        seasonal_factor = 1 + self.params.seasonality * np.sin(2 * np.pi * (tick - self.params.season_start) / 365)
        beta_effective = self.params.beta * seasonal_factor

        # transfer between and w/in patches
        # NB: this assumes that the mixing matrix is properly normalized
        # i.e., that the sum of each row is 1 (self.mixing.sum(axis=1) == 1)
        forces = (beta_effective * patches.states.I) @ self.params.mixer.mixing_matrix

        # normalize by the population of the patch
        forces /= patches.states.sum(axis=0)
        np.negative(forces, out=forces)
        np.expm1(forces, out=forces)  # exp(x) - 1
        np.negative(forces, out=forces)

        # S --> E
        self.lognormal_update_func(
            people.state,
            people.patch_id,
            people.susceptibility,
            forces,
            people.etimer,
            people.count,
            np.float32(self.params.mu_underlying),
            np.float32(self.params.sigma_underlying),
            model.patches.incidence,  # flow
        )
        # Update susceptible and exposed counters.
        # Clamp incidence to the available S count before decrementing to prevent
        # uint32 underflow.  Dead agents (active=False) retain state==0 and can
        # be counted by lognormal_update_func even though VitalDynamicsProcess has
        # already removed them from patches.states.S, so the raw incidence can
        # momentarily exceed the current S tally.
        effective_incidence = np.minimum(model.patches.incidence, patches.states.S)
        patches.states.S -= effective_incidence
        patches.states.E += effective_incidence

        return

    @property
    def mixing(self) -> np.ndarray:
        """Returns the mixing matrix, initializing if necessary"""
        if self._mixing is None:
            self._mixing = init_gravity_diffusion(self.model.scenario, self.params.mixing_scale, self.params.distance_exponent)
        return self._mixing

    @mixing.setter
    def mixing(self, mixing: np.ndarray) -> None:
        """Sets the mixing matrix"""
        self._mixing = mixing

    def infect(self, model: ABMModel, idx: np.ndarray | int) -> None:
        """Infect a set of agents. Moves agents from S to E state and updates patch counters."""
        if isinstance(idx, int):
            idx = np.array([idx])
        people = model.people
        patches = model.patches

        # Update individual agent states
        people.state[idx] = model.params.states.index("E")
        people.susceptibility[idx] = 0.0
        people.etimer[idx] = cast_type(
            np.maximum(1, np.round(np.random.lognormal(self.params.mu_underlying, self.params.sigma_underlying, size=len(idx)))),
            people.etimer.dtype,
        )

        # Update patch state counters
        # Count infections per patch
        patch_counts = np.bincount(people.patch_id[idx], minlength=patches.states.shape[-1])
        infections_per_patch = cast_type(patch_counts, patches.states.dtype)

        # Move from Susceptible to Exposed
        patches.states.S -= infections_per_patch
        patches.states.E += infections_per_patch

        return

    def _initialize(self, model: ABMModel) -> None:
        # Select function implementation based on model configuration
        self.lognormal_update_func = self.select_function(numpy_lognormal_update, nb_lognormal_update)
