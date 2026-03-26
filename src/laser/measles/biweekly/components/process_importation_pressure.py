from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from laser.measles.base import BasePhase
from laser.measles.biweekly.model import BiweeklyModel
from laser.measles.utils import cast_type


class ImportationPressureParams(BaseModel):
    """Parameters for the importation pressure component.

    Importation pressure simulates external case introductions from outside the
    modeled population (e.g., international travel, cross-border movement),
    moving susceptible individuals directly to infected (I) each biweekly tick.

    Attributes:
        crude_importation_rate: Yearly importation rate per 1,000 population.
            Three forms are accepted:

            - **float** (scalar): uniform rate applied to every patch.
              ``0.0`` disables importation entirely.

            - **list / tuple / numpy array** (sequence): per-patch rates in the
              same order as ``model.scenario`` rows. Length must equal the number
              of patches.

            - **dict[str, float]** (sparse patch override): maps patch string ids
              (values from ``model.scenario["id"]``, e.g. ``"n_0_0"``, ``"n_2_2"``)
              to rates. Patches absent from the dict receive a rate of **0.0** —
              they do *not* inherit the scalar default of 1.0.

        importation_start: Day on which importation begins (inclusive). Supply in
            days; the model converts to biweekly ticks internally. Default ``0``
            starts importation at the first tick.

        importation_end: Day on which importation ends (inclusive). Supply in days;
            the model converts to biweekly ticks internally. Use ``-1`` (default)
            to keep importation active for the full simulation. Must be greater than
            ``importation_start`` when not ``-1``.

    Examples:
        Uniform low background pressure across all patches::

            params = ImportationPressureParams(crude_importation_rate=0.05)

        Disable importation entirely::

            params = ImportationPressureParams(crude_importation_rate=0.0)

        Per-patch sequence (one entry per patch, aligned to scenario row order)::

            # 25-patch model; patch at row index 12 is the metro hub
            rates = [0.02] * 25
            rates[12] = 0.5
            params = ImportationPressureParams(crude_importation_rate=rates)

        Sparse dict — only named patches receive importation; all others get 0.0::

            # Use string ids from model.scenario["id"], e.g. "n_0_0", "n_2_2"
            params = ImportationPressureParams(
                crude_importation_rate={"n_2_2": 0.5, "n_0_0": 0.1},
            )

        Numpy array input (accepted and converted to list internally)::

            import numpy as np
            params = ImportationPressureParams(
                crude_importation_rate=np.array([0.01, 0.05, 0.01, 0.01, 0.01])
            )

        Time-windowed importation active only during the first year (days 0-364)::

            params = ImportationPressureParams(
                crude_importation_rate=0.1,
                importation_start=0,
                importation_end=364,
            )

        Metro-only importation for the first year, then stop::

            params = ImportationPressureParams(
                crude_importation_rate={"n_2_2": 2.0},
                importation_start=0,
                importation_end=364,
            )
    """

    crude_importation_rate: float | list[float] | dict[str, float] = Field(
        default=1.0,
        description=(
            "Yearly crude importation rate per 1k population. "
            "Scalar: uniform across all patches. "
            "Sequence (list/tuple/ndarray): per-patch rates aligned to scenario row order, length must equal n_patches. "
            "Dict[str, float]: sparse override keyed by patch string id (from model.scenario['id']); "
            "omitted patches default to 0.0, not 1.0."
        ),
    )
    importation_start: int = Field(
        default=0,
        description="Day on which importation begins (inclusive). Converted to biweekly ticks internally.",
        ge=0,
    )
    importation_end: int = Field(
        default=-1,
        description="Day on which importation ends (inclusive). Converted to biweekly ticks internally. Use -1 (default) to run for the full simulation.",
        ge=-1,
    )

    @field_validator("importation_end")
    @classmethod
    def validate_importation_end(cls, v, info):
        """Validate that importation_end is greater than importation_start when not -1."""
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
        """
        Process importation pressure for the current tick.

        Args:
            model: The simulation model instance
            tick: The current simulation tick
        """
        if tick < (self.params.importation_start // model.params.time_step_days) or (
            self.params.importation_end != -1 and tick > (self.params.importation_end // model.params.time_step_days)
        ):
            return

        if self.patch_rates_per_year_per_1k is None:
            raise RuntimeError("ImportationPressureProcess not initialized")

        # state counts
        states = model.patches.states

        # population
        population = states.sum(axis=0, dtype=np.int64)  # promote to int64, otherwise binomial draw will fail

        p = self.patch_rates_per_year_per_1k / 28.0 / 1000.0
        p = np.clip(p, 0.0, 1.0)

        # Sample actual number of imported cases
        imported_cases = model.prng.binomial(population, p)
        imported_cases = cast_type(imported_cases, states.dtype)
        np.minimum(imported_cases, states.S, out=imported_cases)

        # update states
        states.S -= imported_cases
        states.I += imported_cases  # Move to infected state

    def _initialize(self, model: BiweeklyModel) -> None:
        """
        Initialize the importation pressure component.

        Args:
            model: The simulation model instance
        """
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
