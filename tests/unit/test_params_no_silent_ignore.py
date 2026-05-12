"""Regression tests for Issue #140 and related silent-kwarg bugs.

Pydantic's default behavior (``extra="ignore"``) silently discards unknown
fields. For component parameters this turns user typos and stale kwarg names
into silent simulation bugs: the misnamed value vanishes, defaults fill in,
and the model runs without complaint while doing the wrong thing.

These tests demonstrate the bug class and lock in the fix: every *Params
class should declare ``model_config = ConfigDict(extra="forbid")`` so unknown
kwargs raise immediately at construction time.

Concrete known instances of this bug:
  - VitalDynamicsParams: ``cbr=50`` silently ignored — actual field is
    ``crude_birth_rate``. Reported in MEMORY.md (CRITICAL).
  - InfectionParams / TransmissionParams: ``distance_exponent`` declared on
    InfectionParams but not on TransmissionParams; forwarding drops it.
    Reported in https://github.com/laser-base/laser-measles/issues/140 .
"""

import pytest
from pydantic import ValidationError

# Pull a representative sample of params classes (ABM variant). Each is
# tested for the same property: unknown kwargs must raise ValidationError.
from laser.measles.abm.components import InfectionParams
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import VitalDynamicsParams
from laser.measles.abm.components.process_transmission import TransmissionParams


@pytest.mark.parametrize(
    ("params_cls", "valid_kwargs", "bad_kwarg"),
    [
        # Documented bug: cbr/cdr typo silently uses defaults (20/8) instead of
        # user's intent. Correct field names are crude_birth_rate / crude_death_rate.
        pytest.param(
            VitalDynamicsParams,
            {},
            ("cbr", 50),
            id="vital_dynamics-cbr-typo",
        ),
        pytest.param(
            VitalDynamicsParams,
            {},
            ("cdr", 30),
            id="vital_dynamics-cdr-typo",
        ),
        # Any made-up kwarg on InfectionParams must not be silently swallowed.
        pytest.param(
            InfectionParams,
            {"beta": 1.0},
            ("totally_made_up_field", 42),
            id="infection-made-up-kwarg",
        ),
        # Issue #140: distance_exponent is real on InfectionParams but dropped
        # when forwarded to TransmissionParams. Directly: TransmissionParams
        # should not silently accept fields it doesn't declare.
        pytest.param(
            TransmissionParams,
            {},
            ("distance_exponent", 20.0),
            id="transmission-distance-exponent",
        ),
        # Seeding params: arbitrary unknown kwarg must raise.
        pytest.param(
            InfectionSeedingParams,
            {},
            ("misnamed_count", 7),
            id="seeding-made-up-kwarg",
        ),
    ],
)
def test_params_reject_unknown_kwargs(params_cls, valid_kwargs, bad_kwarg):
    """Unknown kwargs must surface as ValidationError, not silently ignored."""
    name, value = bad_kwarg
    with pytest.raises(ValidationError):
        params_cls(**valid_kwargs, **{name: value})


def test_vital_dynamics_cbr_typo_does_not_silently_default():
    """Concrete documentation of the user-memory bug: cbr=50 → was using 20.0."""
    with pytest.raises(ValidationError, match=r"cbr"):
        VitalDynamicsParams(cbr=50, cdr=30)
