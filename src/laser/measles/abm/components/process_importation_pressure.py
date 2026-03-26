import numpy as np
from collections.abc import Sequence
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from laser.measles.abm.model import ABMModel
from laser.measles.base import BasePhase
from laser.measles.utils import cast_type


class ImportationPressureParams(BaseModel):
    """
    Parameters specific to the importation pressure component.
    crude_importation_rate can be float, list or dict to support flexible patch-wise importation rates.
    """

    crude_importation_rate: float | list[float] | dict[str, float] = Field(
        default=1.0,
        description=(
            "Yearly crude importation rate per 1k population. "
            "Can be a scalar (all patches), a sequence (list, tuple, numpy array) aligned to scenario rows, "
            "or a dict keyed by patch id."
        ),
    )
    importation_start: int = Field(default=0, description="Start time for importation (in days)", ge=0)
    importation_end: int = Field(default=-1, description="End time for importation (in days)", ge=-1)

    @field_validator("importation_end")
    @classmethod
    def validate_importation_end(cls, v, info):
        if v != -1:
            start = info.data.get("importation_start", 0)
            if v <= start:
                raise ValueError("importation_end must be greater than importation_start")
        return v

    @field_validator("crude_importation_rate")
    @classmethod
    def validate_importation_rate(cls, v):
        if isinstance(v, (int, float)):
            if v < 0:
                raise ValueError("crude_importation_rate must be >= 0")
        elif isinstance(v, np.ndarray):
            if np.any(v < 0):
                raise ValueError("All crude_importation_rate values must be >= 0")
            return v.tolist()
        elif isinstance(v, Sequence) and not isinstance(v, (str, bytes)):
            if any(x < 0 for x in v):
                raise ValueError("All crude_importation_rate values must be >= 0")
            return list(v)
        elif isinstance(v, dict):
            if any(x < 0 for x in v.values()):
                raise ValueError("All crude_importation_rate values must be >= 0")
        else:
            raise TypeError("crude_importation_rate must be a float, sequence of floats, or dict[str, float]")
        return v


class ImportationPressureProcess(BasePhase):
    """
    Component for simulating the importation pressure in the model.

    This component handles the simulation of disease importation into the population.
    It processes:
    - Importation of cases based on crude importation rate
    - Time-windowed importation (start/end times)
    - Population updates: Moves individuals from susceptible to infected state

    Parameters
    ----------
    model : object
        The simulation model containing nodes, states, and parameters
    verbose : bool, default=False
        Whether to print verbose output during simulation
    params : Optional[ImportationPressureParams], default=None
        Component-specific parameters. If None, will use default parameters

    Notes
    -----
    - Importation rates are calculated per year
    - Importation is limited to the susceptible population
    - All state counts are ensured to be non-negative
    """

    def __init__(self, model, verbose: bool = False, params: ImportationPressureParams | None = None) -> None:
        super().__init__(model, verbose)
        self.params = params or ImportationPressureParams()
        self.patch_rates_per_year_per_1k: np.ndarray | None = None

    def __call__(self, model, tick: int) -> None:
        if tick < (self.params.importation_start // model.params.time_step_days) or (
            self.params.importation_end != -1 and tick > (self.params.importation_end // model.params.time_step_days)
        ):
            return

        if self.patch_rates_per_year_per_1k is None:
            raise RuntimeError("ImportationPressureProcess not initialized")

        states = model.patches.states
        population = states.sum(axis=0, dtype=np.int64)

        p = self.patch_rates_per_year_per_1k / 365.0 / 1000.0
        p = np.clip(p, 0.0, 1.0)

        imported_cases = model.prng.binomial(population, p)
        imported_cases = cast_type(imported_cases, states.dtype)

        infection_component = None
        count = 0
        for instance in model.instances:
            if hasattr(instance, "infect"):
                infection_component = instance
                count += 1
        if count != 1:
            raise RuntimeError("Issue with the infection component")

        susceptible_state = model.params.states.index("S")

        for patch_idx, num_imported_cases in enumerate(imported_cases):
            if num_imported_cases == 0:
                continue

            if hasattr(model.people, "active"):
                idx = np.where(model.people.active & (model.people.patch_id == patch_idx))[0]
            else:
                idx = np.where(model.people.patch_id == patch_idx)[0]

            if len(idx) == 0:
                imported_cases[patch_idx] = 0
                continue

            n_draw = min(num_imported_cases, len(idx))
            idx = model.prng.choice(idx, size=n_draw, replace=False)
            idx = idx[model.people.state[idx] == susceptible_state]

            if len(idx) > 0:
                infection_component.infect(model, idx)

            imported_cases[patch_idx] = len(idx)

    def _initialize(self, model: ABMModel) -> None:
        n_patches = model.patches.count
        patch_ids = model.scenario["id"].to_list()

        rates = self.params.crude_importation_rate

        if isinstance(rates, (int, float)):
            arr = np.full(n_patches, float(rates), dtype=np.float64)

        elif isinstance(rates, (np.ndarray, list)) or (isinstance(rates, Sequence) and not isinstance(rates, (str, bytes))):
            if len(rates) != n_patches:
                raise ValueError(f"crude_importation_rate length {len(rates)} does not match number of patches {n_patches}")
            arr = np.asarray(rates, dtype=np.float64)

        elif isinstance(rates, dict):
            unknown = set(rates) - set(patch_ids)
            if unknown:
                raise ValueError(f"Unknown patch ids in crude_importation_rate: {sorted(unknown)}")
            arr = np.array([rates.get(pid, 0.0) for pid in patch_ids], dtype=np.float64)

        else:
            raise TypeError("Unsupported crude_importation_rate type")

        self.patch_rates_per_year_per_1k = arr
