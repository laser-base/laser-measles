"""
Component defining the VitalDynamicsProcess, which simulates the vital dynamics in the ABM model with MCV1.
"""

import numpy as np
from laser.core import SortedQueue
from pydantic import Field

from laser.measles.abm.model import ABMModel
from laser.measles.components import BaseVitalDynamicsParams
from laser.measles.components import BaseVitalDynamicsProcess
from laser.measles.utils import cast_type


class VitalDynamicsParams(BaseVitalDynamicsParams):
    """
    Parameters for VitalDynamicsProcess.
    """

    routine_immunization_delay: int = Field(default=9 * 30, description="Delay in days before routine immunization is administered")


class VitalDynamicsProcess(BaseVitalDynamicsProcess):
    """
    Process for simulating vital dynamics in the ABM model with MCV1 and constant birth and mortality rates (not age-structured).
    """

    def __init__(self, model, verbose: bool = False, params: VitalDynamicsParams | None = None) -> None:
        params_: VitalDynamicsParams = params or VitalDynamicsParams()
        super().__init__(model, verbose=verbose, params=params_)

        date_of_birth_dtype = np.int32
        self.null_value = np.iinfo(date_of_birth_dtype).max

        if getattr(model, "_from_snapshot", False):
            # ── Snapshot-load path ────────────────────────────────────────────
            # The people frame is already populated from the HDF5 file.
            # People properties are already present; skip re-adding them.
            # patches are always freshly constructed, so add births property.
            model.patches.add_scalar_property("births", dtype=np.uint32)
            model.patches.add_scalar_property("deaths", dtype=np.uint32)
            # Resize frame to accommodate projected births during the resumed run.
            needed_capacity = self.calculate_capacity(model=model)
            current_count = model.people.count
            if model.people.capacity < needed_capacity:
                model.initialize_people_capacity(needed_capacity, initial_count=current_count)
            people = model.people
            # Rebuild the vaccination queue from agents with pending dates.
            self.vaccination_queue = SortedQueue(capacity=people.capacity, values=people.date_of_vaccination)
            pending = people.date_of_vaccination[: people.count].astype(np.int64) < self.null_value
            for idx in np.where(pending)[0]:
                self.vaccination_queue.push(int(idx))
            return

        # ── Normal (non-snapshot) initialization ─────────────────────────────
        # re-initialize people frame with correct capacity
        capacity = self.calculate_capacity(model=model)
        model.initialize_people_capacity(capacity=capacity, initial_count=model.scenario["pop"].sum())

        people = model.people
        patches = model.patches

        people.add_scalar_property("active", dtype=np.bool, default=False)
        people.add_scalar_property("date_of_birth", dtype=date_of_birth_dtype, default=self.null_value)
        people.add_scalar_property("date_of_vaccination", dtype=np.uint32, default=self.null_value)
        patches.add_scalar_property("births", dtype=np.uint32)
        patches.add_scalar_property("deaths", dtype=np.uint32)

        self.vaccination_queue: SortedQueue = SortedQueue(capacity=capacity, values=people.date_of_vaccination)

        if model.params.num_ticks >= self.null_value:
            raise ValueError("Simulation is too long; birth and vaccination dates must be able to store the number of ticks")

    def __call__(self, model, tick: int) -> None:
        """
        Simulate the vital dynamics process.
        """
        patches = model.patches
        people = model.people
        population = patches.states.sum(axis=0)

        # Deaths
        # ------
        # Calculate number of deaths
        deaths = model.prng.poisson(population.sum() * self.mu_death)  # over all patches
        # select agents
        idx = model.prng.choice(np.where(model.people.active)[0], size=deaths, replace=False)
        # deactivate agents
        model.people.active[idx] = False
        # update state counter
        for state_idx, _ in enumerate(model.params.states):
            mask = model.people.state[idx] == state_idx  # mask of in-active agents in the current state
            cnt = np.bincount(model.people.patch_id[idx][mask], minlength=model.patches.states.shape[-1])
            model.patches.states[state_idx] -= cast_type(cnt, model.patches.states.dtype)

        # Reset dead agents' epidemic state to prevent ghost processing by downstream components.
        # Without this, agents deactivated mid-epidemic retain non-zero exposure/infection timers
        # and susceptible-state flags, causing DiseaseProcess to generate spurious E→I and I→R
        # transitions that decrement patches.states below zero (uint32 underflow).
        if len(idx) > 0:
            r_state = np.uint8(model.params.states.index("R"))
            model.people.state[idx] = r_state
            if hasattr(model.people, "etimer"):
                model.people.etimer[idx] = 0
            if hasattr(model.people, "itimer"):
                model.people.itimer[idx] = 0

        # Record per-patch death count for tracking
        patches.deaths[:] = (
            cast_type(np.bincount(people.patch_id[idx], minlength=patches.states.shape[-1]), np.uint32) if len(idx) > 0 else 0
        )

        if self.lambda_birth > 0:
            # Births
            # ------
            # Calculate number of births
            births = model.prng.poisson(population * self.lambda_birth)  # in each patch
            # find indices of the people frame for initializing
            istart, iend = people.add(births.sum())
            people.active[istart:iend] = True  # mark newborns as active
            people.date_of_birth[istart:iend] = tick  # born today
            people.susceptibility[istart:iend] = 1.0  # all newborns are susceptible TODO: add maternal immunity component
            people.date_of_vaccination[istart:iend] = tick + self._routine_immunization_delay()
            index = istart
            # update patch id
            for this_patch_id, this_patch_births in enumerate(births):
                people.patch_id[index : index + this_patch_births] = this_patch_id
                index += this_patch_births
            # update states
            patches.states.S += cast_type(births, patches.states.dtype)
            # Record per-patch birth count for tracking
            patches.births[:] = cast_type(births, np.uint32)

        # Routine immunization
        # --------------------
        while len(self.vaccination_queue) > 0 and people.date_of_vaccination[self.vaccination_queue.peeki()] <= tick:
            i = self.vaccination_queue.popi()
            people.susceptibility[i] = 0.0  # susceptibility
            people.state[i] = model.params.states.index("R")  # move to recovered state

    def calculate_capacity(self, model) -> int:
        """Estimate the necessary capacity of the people laserframe."""
        rate = self.lambda_birth  # - self.mu_death # calculated per tick
        buffered_ticks = (model.params.num_ticks * model.params.time_step_days // 365 + 1) * 365 / model.params.time_step_days
        N = model.scenario["pop"].to_numpy() * np.exp(rate * buffered_ticks)
        return int(N.sum())

    def _routine_immunization_delay(self) -> int:
        """Delay in ticks before routine immunization is administered."""
        params: VitalDynamicsParams = self.params  # type: ignore
        return params.routine_immunization_delay * self.model.params.time_step_days

    def _initialize(self, model: ABMModel) -> None:
        if getattr(model, "_from_snapshot", False):
            # Population state (active, date_of_birth) already loaded from snapshot.
            return

        # initialize the people laserframe with correct capacity
        # initial_pop = model.scenario["pop"].sum()
        # model.initialize_people_capacity(capacity=self.calculate_capacity(model), initial_count=initial_pop)

        # Activate population
        model.people.active[0 : model.people.count] = True
        # Simple initializer for ages where birth rate = mortality rate:
        # Initialize ages for existing population
        if self.mu_death > 0:
            model.people.date_of_birth[0 : model.people.count] = cast_type(
                -1 * model.prng.exponential(1 / self.mu_death, model.people.count), model.people.date_of_birth.dtype
            )
