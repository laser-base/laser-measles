"""
Basic classes
"""

import numpy as np
import patito as pt
import polars as pl

from laser.measles.base import BasePatchLaserFrame
from laser.measles.base import BasePeopleLaserFrame
from laser.measles.base import BaseScenario as LaserMeaslesBaseScenario


class PeopleLaserFrame(BasePeopleLaserFrame):
    """
    Laserframe for people (e.g., agent) properties


    **Example:**

        ```python
        # ABM people LaserFrame tracks individual agents
        model.people.state     # health state per agent
        model.people.age       # age in days per agent
        model.people.patch_id  # patch assignment per agent
        ```
    """

    patch_id: np.ndarray
    state: np.ndarray
    susceptibility: np.ndarray


class PatchLaserFrame(BasePatchLaserFrame):
    """
    LaserFrame for patch-level properties in ABM models.

    This class extends BasePatchLaserFrame to provide patch-level data
    storage and access patterns specific to agent-based models.


    **Example:**

        ```python
        model.patches.S  # susceptible counts, shape (nticks+1, num_patches)
        model.patches.I  # infectious counts
        ```
    """


class BaseABMScenarioSchema(pt.Model):
    """
    Schema for the scenario data.


    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        # Validated automatically when passed to ABMModel(scenario, params)
        ```
    """

    pop: int  # population
    lat: float  # latitude
    lon: float  # longitude
    id: str  # ids of the nodes
    mcv1: float  # Routine MCV1 coverage for newborns (0.0-1.0). Only affects births via VitalDynamicsProcess; does NOT vaccinate existing population.


class BaseABMScenario(LaserMeaslesBaseScenario):
    """Scenario wrapper for agent-based models.

    Validates that the input DataFrame conforms to the
    [`BaseABMScenarioSchema`][laser.measles.abm.base.BaseABMScenarioSchema]
    (columns ``id``, ``pop``, ``lat``, ``lon``, ``mcv1``) and makes the
    data available to model components during the *prepare scenario* stage.

    Args:
        df: Polars DataFrame with patch-level data.


    **Example:**

        ```python
        from laser.measles.scenarios.synthetic import single_patch_scenario

        scenario = single_patch_scenario(population=50_000, mcv1_coverage=0.85)
        ```
    """

    def __init__(self, df: pl.DataFrame):
        super().__init__(df)
        BaseABMScenarioSchema.validate(df, allow_superfluous_columns=True)

    def _validate(self, df: pl.DataFrame):
        # Validate required columns exist - derive from schema
        required_columns = list(BaseABMScenarioSchema.model_fields.keys())
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Validate data types using Polars' native operations
        try:
            # Validate pop is integer
            if not df["pop"].dtype == pl.Int64:
                raise ValueError("Column 'pop' must be integer type")

            # Validate lat and lon are float
            if not df["lat"].dtype == pl.Float64:
                raise ValueError("Column 'lat' must be float type")
            if not df["lon"].dtype == pl.Float64:
                raise ValueError("Column 'lon' must be float type")

            # Validate mcv1 is float
            if not df["mcv1"].dtype == pl.Float64:
                raise ValueError("Column 'mcv1' must be float type")

            # Validate mcv1 is between 0 and 1 (as percentages)
            if not df["mcv1"].is_between(0, 1).all():
                raise ValueError("Column 'mcv1' must be between 0 and 1")

            # Validate ids are either string or integer
            if not (df["id"].dtype == pl.String or df["id"].dtype == pl.Int64):
                raise ValueError("Column 'id' must be either string or integer type")

            # Validate no null values
            null_counts = df.null_count()
            if np.any(null_counts):
                raise ValueError(f"DataFrame contains null values:\n{null_counts}")

        except Exception as e:
            raise ValueError(f"DataFrame validation error:\n{e}") from e


BaseScenario = BaseABMScenario
