"""
Component for seeding initial infections in the compartmental model.

This component allows initialization of infections in specific patches or automatically
selects the largest patch by population for seeding.
"""

import numpy as np
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from laser.measles.abm.base import PatchLaserFrame
from laser.measles.abm.base import PeopleLaserFrame
from laser.measles.base import BaseComponent
from laser.measles.base import BaseLaserModel


class InfectionSeedingParams(BaseModel):
    """Parameters for the infection seeding component."""

    num_infections: int = Field(default=1, description="Default number of infections to seed", ge=1)
    target_patches: list[str] | None = Field(default=None, description="List of specific patch IDs to seed")
    infections_per_patch: (
        int | list[int]
    ) | None = Field(default=None, description="Number of infections per patch (single int or list matching target_patches)")
    use_largest_patch: bool = Field(default=True, description="Whether to seed the largest patch by default")

    @field_validator("infections_per_patch")
    @classmethod
    def validate_infections_per_patch(cls, v, info):
        """Validate that infections_per_patch matches target_patches length if both provided."""
        if v is not None and "target_patches" in info.data and info.data["target_patches"] is not None:
            if isinstance(v, list):
                if len(v) != len(info.data["target_patches"]):
                    raise ValueError("Length of infections_per_patch must match length of target_patches")
                if any(x < 1 for x in v):
                    raise ValueError("All values in infections_per_patch must be >= 1")
            elif isinstance(v, int):
                if v < 1:
                    raise ValueError("infections_per_patch must be >= 1")
        return v

    @field_validator("target_patches")
    @classmethod
    def validate_target_patches(cls, v):
        """Validate target_patches format."""
        if v is not None:
            for patch_id in v:
                if not isinstance(patch_id, str) or not patch_id.strip():
                    raise ValueError("All target_patches must be non-empty strings")
        return v


class InfectionSeedingProcess(BaseComponent):
    """Component for seeding initial infections in the compartmental model.

    This component initializes infections by moving individuals from the Susceptible (S)
    compartment to the Infected (I) compartment. It can either:

    1. Automatically seed the patch with the largest population (default)
    2. Seed specific patches provided by the user

    The seeding occurs during initialize() before the simulation begins.

    Args:
        model: The compartmental model instance.
        params: Component-specific parameters. If None, uses default parameters.

    Example:
        .. code-block:: python

            # Seed 1 infection in largest patch (default)
            seeding_params = InfectionSeedingParams()

            # Seed 5 infections in largest patch
            seeding_params = InfectionSeedingParams(num_infections=5)

            # Seed specific patches with same number of infections
            seeding_params = InfectionSeedingParams(
                target_patches=["nigeria:kano:kano:A0001", "nigeria:kano:kano:A0002"],
                infections_per_patch=3,
            )

            # Seed specific patches with different numbers of infections
            seeding_params = InfectionSeedingParams(
                target_patches=["nigeria:kano:kano:A0001", "nigeria:kano:kano:A0002"],
                infections_per_patch=[5, 2],
            )
    """

    def __init__(self, model: BaseLaserModel, params: InfectionSeedingParams | None = None) -> None:
        super().__init__(model)
        self.params = params or InfectionSeedingParams()
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate component parameters."""
        if self.params.target_patches is None and not self.params.use_largest_patch:
            raise ValueError("Either target_patches must be provided or use_largest_patch must be True")

    def _initialize(self, model: BaseLaserModel) -> None:
        """
        Initialize infections by seeding susceptible individuals.

        This method is called once during model initialization, after equilibrium
        states are set up but before simulation begins.
        """
        if self.verbose:
            print("Initializing infection seeding...")

        # Get patch information from the scenario
        scenario_df = model.scenario.unwrap()
        patch_ids = scenario_df["id"].to_list()
        populations = scenario_df["pop"].to_list()

        # Determine which patches to seed and how many infections per patch
        if self.params.target_patches is None:
            # Use largest patch by default
            target_patches, infections_per_patch = self._get_largest_patch_seeding(patch_ids, populations)
        else:
            # Use specified patches
            target_patches, infections_per_patch = self._get_specified_patch_seeding()

        # Validate that target patches exist in the model
        self._validate_patches_exist(target_patches, patch_ids)

        # Perform the seeding
        total_seeded = self._seed_infections(model, target_patches, infections_per_patch, patch_ids)

        if self.verbose:
            print(f"Successfully seeded {total_seeded} infections across {len(target_patches)} patches")

    def _get_largest_patch_seeding(self, patch_ids: list[str], populations: list[int]) -> tuple[list[str], list[int]]:
        """Get the largest patch for seeding."""
        max_pop_idx = np.argmax(populations)
        largest_patch = patch_ids[max_pop_idx]

        if self.verbose:
            print(f"Selected largest patch: {largest_patch} (population: {populations[max_pop_idx]:,})")

        return [largest_patch], [self.params.num_infections]

    def _get_specified_patch_seeding(self) -> tuple[list[str], list[int]]:
        """Get specified patches and infection counts."""
        target_patches = self.params.target_patches.copy() if self.params.target_patches is not None else []

        if self.params.infections_per_patch is None:
            # Use default num_infections for all patches
            infections_per_patch = [self.params.num_infections] * len(target_patches)
        elif isinstance(self.params.infections_per_patch, int):
            # Use same number for all patches
            infections_per_patch = [self.params.infections_per_patch] * len(target_patches)
        else:
            # Use specified list
            infections_per_patch = self.params.infections_per_patch.copy()

        return target_patches, infections_per_patch

    def _validate_patches_exist(self, target_patches: list[str], patch_ids: list[str]) -> None:
        """Validate that all target patches exist in the model."""
        missing_patches = [p for p in target_patches if p not in patch_ids]
        if missing_patches:
            raise ValueError(f"Target patches not found in model: {missing_patches}")

    def _seed_infections(
        self, model: BaseLaserModel, target_patches: list[str], infections_per_patch: list[int], patch_ids: list[str]
    ) -> int:
        """Seed infections in the specified patches."""
        if not hasattr(model, "people") or model.people is None:
            raise RuntimeError("Model does not have people attribute or it is None")
        if not hasattr(model, "patches") or model.patches is None:
            raise RuntimeError("Model does not have patches attribute or it is None")

        people: PeopleLaserFrame = model.people
        patches: PatchLaserFrame = model.patches
        total_seeded = 0
        num_active = len(model.people)

        for patch_id, num_infections in zip(target_patches, infections_per_patch, strict=False):
            # Find patch index
            patch_idx = patch_ids.index(patch_id)

            # Get current susceptible population
            current_susceptible = int(patches.states.S[patch_idx])

            # Determine actual number of infections to seed (limited by susceptible population)
            actual_infections = min(num_infections, current_susceptible)

            if actual_infections < num_infections:
                if self.verbose:
                    print(
                        f"Warning: Patch {patch_id} has only {current_susceptible} susceptible individuals, "
                        f"seeding {actual_infections} instead of {num_infections}"
                    )

            if actual_infections > 0:
                idx = np.where(
                    np.logical_and(people.patch_id[:num_active] == patch_idx, people.state[:num_active] == model.params.states.index("S"))
                )[0]
                # idx = model.prng.choice(idx, size=actual_infections, replace=False)
                model.prng.shuffle(idx)
                idx = idx[:actual_infections]
                flag = 0
                for instance in model.instances:
                    if hasattr(instance, "infect"):
                        assert np.all(idx < num_active), "Index out of bounds"
                        instance.infect(model, idx)
                        flag += 1
                if flag == 0:
                    raise RuntimeError("No instance found with an infect method")
                elif flag > 1:
                    raise RuntimeError("Multiple instances found with an infect method")

                # Patch states are now updated by the component's infect method
                total_seeded += actual_infections

                if self.verbose:
                    print(f"Seeded {actual_infections} infections in patch {patch_id}")
            else:
                if self.verbose:
                    print(f"Warning: No susceptible individuals in patch {patch_id}, skipping")

        return total_seeded
