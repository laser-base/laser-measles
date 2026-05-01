"""Regression tests for pop dtype coercion in BaseScenario.

Any integer-width pop column must be silently coerced to Int64 at
construction time. Compartmental, ABM, and biweekly scenarios must all
accept non-Int64 integer pop without raising.
"""

import polars as pl
import pytest

from laser.measles.abm.base import BaseScenario as ABMScenario
from laser.measles.biweekly.base import BaseScenario as BiweeklyScenario
from laser.measles.compartmental.base import BaseScenario as CompartmentalScenario

_BASE_ROW = {"lat": [1.0], "lon": [2.0], "id": ["n1"], "mcv1": [0.5]}

_INTEGER_DTYPES = [
    pl.Int16,  # max 32767 — fits _POP_VALUE
    pl.Int32,  # max ~2.1B
    pl.UInt16,  # max 65535 — fits _POP_VALUE
    pl.UInt32,  # max ~4.3B
]

_POP_VALUE = 1_000  # fits in Int16/UInt16 and all wider types


@pytest.mark.parametrize("dtype", _INTEGER_DTYPES)
def test_abm_scenario_accepts_non_int64_pop(dtype):
    df = pl.DataFrame({"pop": pl.Series([_POP_VALUE], dtype=dtype), **_BASE_ROW})
    scenario = ABMScenario(df)
    assert scenario._df["pop"].dtype == pl.Int64


@pytest.mark.parametrize("dtype", _INTEGER_DTYPES)
def test_biweekly_scenario_accepts_non_int64_pop(dtype):
    df = pl.DataFrame({"pop": pl.Series([_POP_VALUE], dtype=dtype), **_BASE_ROW})
    scenario = BiweeklyScenario(df)
    assert scenario._df["pop"].dtype == pl.Int64


@pytest.mark.parametrize("dtype", _INTEGER_DTYPES)
def test_compartmental_scenario_accepts_non_int64_pop(dtype):
    """Regression: compartmental __init__ was validating pre-coercion df, causing Int32 to fail."""
    df = pl.DataFrame({"pop": pl.Series([_POP_VALUE], dtype=dtype), **_BASE_ROW})
    scenario = CompartmentalScenario(df)
    assert scenario._df["pop"].dtype == pl.Int64


def test_plain_python_list_pop_is_accepted():
    """Plain Python integer lists produce Int64 — must be accepted without any cast."""
    df = pl.DataFrame({"pop": [100_000], **_BASE_ROW})
    assert df["pop"].dtype == pl.Int64  # confirm Polars inference
    scenario = CompartmentalScenario(df)
    assert scenario._df["pop"].dtype == pl.Int64


def test_float_pop_is_still_rejected():
    """Float pop must continue to raise — coercion is integer-only."""
    df = pl.DataFrame({"pop": [100_000.0], **_BASE_ROW})
    with pytest.raises(ValueError, match=r"Float64|must be integer type"):
        CompartmentalScenario(df)
