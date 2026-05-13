"""Tests for the `mixer=` field on the ABM `InfectionParams`.

Previously the ABM `InfectionParams` had no `mixer` field — passing
``mixer=`` was silently accepted (pre-#140) or rejected (post-#140) but
either way did nothing. Users needed to construct a TransmissionParams
manually or monkey-patch after model.components=. This file locks in the
new behaviour:

  - `InfectionParams(mixer=X)` puts X into `transmission_params.mixer`.
  - When `mixer` is not set, `transmission_params.mixer` is a
    `GravityMixing` configured from `distance_exponent` and
    `mixing_scale` (the #140 fix path).
"""

import pytest

from laser.measles.abm.components import InfectionParams
from laser.measles.mixing.gravity import GravityMixing
from laser.measles.mixing.gravity import GravityParams


def test_default_mixer_is_gravity_using_distance_exponent_and_mixing_scale():
    p = InfectionParams(beta=1.0, distance_exponent=3.5, mixing_scale=0.07)
    tp = p.transmission_params

    assert isinstance(tp.mixer, GravityMixing)
    # GravityMixing was built with params=GravityParams(c=3.5, k=0.07)
    assert tp.mixer.params.c == 3.5
    assert tp.mixer.params.k == 0.07


def test_explicit_mixer_overrides_distance_exponent_and_mixing_scale():
    # User passes a fully-configured mixer; distance_exponent / mixing_scale
    # should be ignored.
    custom = GravityMixing(params=GravityParams(c=42.0, k=0.42))
    p = InfectionParams(beta=1.0, distance_exponent=3.5, mixing_scale=0.07, mixer=custom)
    tp = p.transmission_params

    assert tp.mixer is custom
    assert tp.mixer.params.c == 42.0
    assert tp.mixer.params.k == 0.42


def test_custom_mixer_class_accepted_via_mixer_kwarg():
    # The fix's reason for being: a non-gravity mixer (e.g. RadiationMixing)
    # must be acceptable as the InfectionParams `mixer=` value, not only
    # GravityMixing. We probe with any mixing object — RadiationMixing if
    # importable, else any sentinel that has the same shape.
    try:
        from laser.measles.mixing.radiation import RadiationMixing

        mixer = RadiationMixing()
    except ImportError:
        pytest.skip("RadiationMixing not importable; cannot exercise non-gravity mixer")

    p = InfectionParams(beta=1.0, mixer=mixer)
    tp = p.transmission_params

    assert tp.mixer is mixer


def test_mixer_defaults_to_none_on_construction():
    p = InfectionParams(beta=1.0)
    assert p.mixer is None
    # The property still produces a usable TransmissionParams with a
    # GravityMixing default.
    tp = p.transmission_params
    assert isinstance(tp.mixer, GravityMixing)
