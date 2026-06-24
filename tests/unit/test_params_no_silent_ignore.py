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
from laser.measles.abm.components.process_infection import InfectionParams as ABMInfectionParams
from laser.measles.abm.components.process_infection_seeding import InfectionSeedingParams as ABMSeedingParams
from laser.measles.abm.components.process_transmission import TransmissionParams
from laser.measles.biweekly.components.process_infection import InfectionParams as BWInfectionParams
from laser.measles.biweekly.components.process_infection_seeding import InfectionSeedingParams as BWSeedingParams
from laser.measles.biweekly.components.process_initialize_equilibrium_states import InitializeEquilibriumStatesParams as BWInitEq
from laser.measles.biweekly.components.tracker_case_surveillance import CaseSurveillanceParams as BWCaseSurveillance
from laser.measles.compartmental.components.process_infection import InfectionParams as CompInfectionParams
from laser.measles.components import ResultsWriterParams


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


# ──────────────────────────────────────────────────────────────────────
# Alias contract: validation_alias accepts the documented synonym(s),
# model_dump() always emits the canonical field name. The dual property —
# input-permissive, output-canonical — is the whole point of using
# validation_alias rather than plain alias. Lock both directions in.
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("params_cls", "canonical_field", "alias_kwarg", "value"),
    [
        # InfectionParams.seasonality — the field is declared at the base AND
        # redeclared at each of the three subclasses. Pydantic field overrides
        # discard parent alias config, so the alias has to live on each
        # subclass declaration too — exercise all three to lock that in.
        pytest.param(ABMInfectionParams, "seasonality", "seasonal_amplitude", 0.3, id="abm-infection-seasonal_amplitude"),
        pytest.param(BWInfectionParams, "seasonality", "seasonal_amplitude", 0.3, id="biweekly-infection-seasonal_amplitude"),
        pytest.param(CompInfectionParams, "seasonality", "seasonal_amplitude", 0.3, id="compartmental-infection-seasonal_amplitude"),
        # ResultsWriterParams.path
        pytest.param(ResultsWriterParams, "path", "output_file", "results.json", id="results_writer-output_file"),
        pytest.param(ResultsWriterParams, "path", "output_path", "results.json", id="results_writer-output_path"),
        # InfectionSeedingParams.num_infections — biweekly+compartmental share
        # BaseInfectionSeedingParams via empty subclass pass-through. ABM has its
        # own parallel BaseModel declaration that has to carry the alias too.
        pytest.param(BWSeedingParams, "num_infections", "n_seeds", 5, id="biweekly-seeding-n_seeds"),
        pytest.param(BWSeedingParams, "num_infections", "n_initial_infections", 5, id="biweekly-seeding-n_initial_infections"),
        pytest.param(ABMSeedingParams, "num_infections", "n_seeds", 5, id="abm-seeding-n_seeds"),
        pytest.param(ABMSeedingParams, "num_infections", "n_initial_infections", 5, id="abm-seeding-n_initial_infections"),
        # InitializeEquilibriumStatesParams.R0 — all three variants share the base.
        pytest.param(BWInitEq, "R0", "r0", 4.0, id="initeq-r0"),
        pytest.param(BWInitEq, "R0", "R_0", 4.0, id="initeq-R_0"),
        pytest.param(BWInitEq, "R0", "effective_R0", 4.0, id="initeq-effective_R0"),
        pytest.param(BWInitEq, "R0", "effective_r0", 4.0, id="initeq-effective_r0"),
        # CaseSurveillanceParams.detection_rate — all three variants share the base.
        pytest.param(BWCaseSurveillance, "detection_rate", "reporting_prob", 0.3, id="surveillance-reporting_prob"),
        pytest.param(BWCaseSurveillance, "detection_rate", "reporting_probability", 0.3, id="surveillance-reporting_probability"),
        pytest.param(BWCaseSurveillance, "detection_rate", "notification_rate", 0.3, id="surveillance-notification_rate"),
        pytest.param(BWCaseSurveillance, "detection_rate", "notification_probability", 0.3, id="surveillance-notification_probability"),
        pytest.param(BWCaseSurveillance, "detection_rate", "detection_probability", 0.3, id="surveillance-detection_probability"),
    ],
)
def test_params_accept_documented_alias(params_cls, canonical_field, alias_kwarg, value):
    """Alias kwarg constructs cleanly AND model_dump() emits the canonical key.

    validation_alias is input-only, so consumers serializing the params back
    out (logging, JSON round-trip, results.json, etc.) always see the
    canonical field name regardless of which alias the user supplied.
    """
    p = params_cls(**{alias_kwarg: value})

    # Alias populated the canonical field
    assert getattr(p, canonical_field) == value

    # Canonical key is on output
    dump = p.model_dump()
    assert canonical_field in dump
    assert dump[canonical_field] == value

    # Alias key is NOT on output (would indicate plain alias was used instead
    # of validation_alias — that would surprise downstream consumers)
    assert alias_kwarg == canonical_field or alias_kwarg not in dump


@pytest.mark.parametrize(
    "params_cls",
    [ABMInfectionParams, BWInfectionParams, CompInfectionParams],
    ids=["abm", "biweekly", "compartmental"],
)
def test_seasonality_rejects_bare_amplitude(params_cls):
    """`amplitude` (bare, no prefix) is intentionally NOT an alias for
    `seasonality`. Too generic, undocumented in the field description.
    Keep it rejected loudly so a future drive-by addition has to defend it.
    """
    with pytest.raises(ValidationError):
        params_cls(amplitude=0.3)
