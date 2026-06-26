from laser.measles.base import BaseLaserModel
from laser.measles.components.base_infection_seeding import BaseInfectionSeedingParams
from laser.measles.components.base_infection_seeding import BaseInfectionSeedingProcess


class InfectionSeedingParams(BaseInfectionSeedingParams):
    """Parameters for infection seeding (inherits all fields from base).

    Examples:

        from laser.measles.biweekly.components.process_infection_seeding import InfectionSeedingParams

        params = InfectionSeedingParams()
    """


class InfectionSeedingProcess(BaseInfectionSeedingProcess):
    """Process infection seeding.

    Examples:

        from laser.measles.scenarios.synthetic import single_patch_scenario
        from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
        from laser.measles.biweekly import components
        from laser.measles import create_component

        scenario = single_patch_scenario(population=100_000, mcv1_coverage=0.85)
        params = BiweeklyParams(num_ticks=52, seed=42, start_time="2000-01")
        model = BiweeklyModel(scenario, params)
        model.add_component(create_component(components.InfectionSeedingProcess, components.InfectionSeedingParams()))
    """

    def _seed_infections_in_patch(self, model: BaseLaserModel, patch_idx: int, num_infections: int) -> int:
        """Seed infections in a specific patch."""
        # Move from Susceptible to Infected
        model.patches.states.S[patch_idx] -= num_infections
        model.patches.states.I[patch_idx] += num_infections
        return num_infections
