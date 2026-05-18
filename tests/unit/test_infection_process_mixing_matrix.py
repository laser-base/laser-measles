"""Tests for InfectionProcess.mixing_matrix convenience property.

The mixing matrix used by spatial transmission is structurally non-obvious:
in the ABM variant it lives at
``InfectionProcess.transmission.params.mixer.mixing_matrix`` (three levels
deep, and TransmissionProcess isn't registered as a top-level model
instance). Biweekly and compartmental have it at
``InfectionProcess.params.mixer.mixing_matrix`` (one level).

The new ``InfectionProcess.mixing_matrix`` property unifies the access
pattern across all three model variants. These tests verify the property
returns the same matrix the underlying mixer holds.
"""

import importlib

import numpy as np
import polars as pl
import pytest

from laser.measles.abm import ABMModel
from laser.measles.abm import ABMParams
from laser.measles.abm.components import InfectionParams
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingParams
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import NoBirthsProcess
from laser.measles.abm.components import StateTracker
from laser.measles.components import BaseStateTrackerParams
from laser.measles.components import create_component


def _scenario(n_patches: int = 3):
    return pl.DataFrame(
        {
            "id": [f"patch_{i}" for i in range(n_patches)],
            "lat": [0.0 + i * 0.1 for i in range(n_patches)],
            "lon": [0.0] * n_patches,
            "pop": [10_000 * (i + 1) for i in range(n_patches)],
            "mcv1": [0.0] * n_patches,
        }
    )


def _build_and_run_abm():
    params = ABMParams(num_ticks=10, seed=42, start_time="2000-01", show_progress=False)
    model = ABMModel(_scenario(), params)
    model.add_component(NoBirthsProcess)
    model.add_component(create_component(InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=3)))
    model.add_component(create_component(InfectionProcess, params=InfectionParams()))
    model.add_component(create_component(StateTracker, params=BaseStateTrackerParams(aggregation_level=0)))
    model.run()
    return model


def test_abm_infection_process_mixing_matrix_property():
    model = _build_and_run_abm()
    ip = model.get_instance("InfectionProcess")[0]
    mm = ip.mixing_matrix

    # Property returns the same object the deep-path access returns
    deep = ip.transmission.params.mixer.mixing_matrix
    assert mm is deep, "mixing_matrix property should be the same object as the deep path"

    # Matrix shape matches patch count
    n_patches = len(model.scenario)
    assert mm.shape == (n_patches, n_patches), f"expected ({n_patches}, {n_patches}), got {mm.shape}"

    # Rows sum to ~1 (gravity mixer normalises)
    np.testing.assert_allclose(mm.sum(axis=1), 1.0, atol=1e-6)


@pytest.mark.parametrize(
    "module_path",
    [
        "laser.measles.compartmental",
        "laser.measles.biweekly",
    ],
)
def test_compartmental_and_biweekly_have_same_property(module_path):
    """Both non-ABM variants expose the same `mixing_matrix` property name."""
    mod = importlib.import_module(module_path)
    ip_cls = mod.components.InfectionProcess
    # Property exists on the class
    assert isinstance(getattr(ip_cls, "mixing_matrix", None), property), (
        f"{module_path}.InfectionProcess should expose `mixing_matrix` as a property"
    )
