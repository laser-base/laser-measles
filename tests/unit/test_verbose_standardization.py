"""
Tests for the standardization of the verbose flag on model.params.

The contract:
- BaseComponent.verbose is a dynamic property mirroring self.model.params.verbose.
- Components no longer accept a verbose constructor kwarg; passing one raises TypeError.
- Toggling model.params.verbose is immediately observable by every component instance.
"""

import importlib

import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES
from laser.measles.base import BaseComponent


class _TrivialComponent(BaseComponent):
    def __call__(self, model, tick):
        pass

    def _initialize(self, model):
        pass


def _make_model(measles_module, verbose):
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    return MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=0, verbose=verbose))


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_verbose_property_reads_model_params(measles_module):
    model = _make_model(measles_module, verbose=True)
    assert _TrivialComponent(model).verbose is True

    model = _make_model(measles_module, verbose=False)
    assert _TrivialComponent(model).verbose is False


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_verbose_property_is_dynamic(measles_module):
    """Mutating params.verbose after construction must be visible on the component.

    This is the regression test for the original 'dropped verbose' bug pattern:
    when verbose was a stored constructor arg, post-construction mutations were
    invisible. With verbose as a property over model.params.verbose, they are.
    """
    model = _make_model(measles_module, verbose=False)
    component = _TrivialComponent(model)
    assert component.verbose is False

    model.params.verbose = True
    assert component.verbose is True


def test_basecomponent_no_longer_accepts_verbose_kwarg():
    class _MockModel:
        pass

    with pytest.raises(TypeError):
        _TrivialComponent(_MockModel(), verbose=True)


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_infection_seeding_emits_when_verbose_true(measles_module, capsys):
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=1, verbose=True, show_progress=False))
    model.components = [
        MeaslesModel.components.InfectionSeedingProcess,
        MeaslesModel.components.InfectionProcess,
    ]
    model.run()
    assert "Initializing infection seeding" in capsys.readouterr().out


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_infection_seeding_silent_when_verbose_false(measles_module, capsys):
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(lm.scenarios.synthetic.single_patch_scenario())
    model = MeaslesModel.Model(scenario, MeaslesModel.Params(num_ticks=1, verbose=False, show_progress=False))
    model.components = [
        MeaslesModel.components.InfectionSeedingProcess,
        MeaslesModel.components.InfectionProcess,
    ]
    model.run()
    assert "Initializing infection seeding" not in capsys.readouterr().out
