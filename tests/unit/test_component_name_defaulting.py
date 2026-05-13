"""Regression test for the defensive `.name` defaulting in `_instantiate_component`.

Components that don't inherit from `BaseComponent` (and don't set
`self.name` in their own `__init__`) previously caused an `AttributeError`
the first time `model.get_instance("ClassName")` was called — the lookup
does `instance.name == cls` inside a list comprehension, which raises
mid-iteration on the missing attribute.

This file exercises all three component-creation paths
(`components` setter, `add_component`, `prepend_component`) against a
bare class that has neither inheritance nor a `.name` attribute, and
asserts the string-form `get_instance` returns the instance and that
the helper has set `.name` to the class name.

Every other unit test uses framework components that DO inherit from
`BaseComponent`, so the defensive defaulting in `_instantiate_component`
is never reached without a test like this one.
"""

import polars as pl
import pytest
from laser.core import PropertySet

import laser.measles as lm
from laser.measles.base import BaseLaserModel
from laser.measles.base import BaseScenario


class _MockScenario(BaseScenario):
    def _validate(self, df: pl.DataFrame) -> None:
        pass


class _BareComponent:
    """Custom component with neither `BaseComponent` inheritance nor `.name`.

    Represents the pattern an LLM commonly produces when asked for a
    one-off tracker: ``class FooTracker: def __init__(self, model): ...``.
    """

    def __init__(self, model):
        self.model = model


class _TestModel(BaseLaserModel):
    """Minimal BaseLaserModel subclass for component-management tests."""

    def __init__(self):
        scenario = _MockScenario(lm.scenarios.synthetic.single_patch_scenario())
        params = PropertySet({"verbose": False, "start_time": "2000-01"})
        super().__init__(scenario, params, "test")

    def __call__(self, model, tick):
        pass

    def _setup_components(self) -> None:
        pass


@pytest.mark.parametrize("creation_path", ["setter", "add_component", "prepend_component"])
def test_bare_class_component_findable_by_get_instance_str(creation_path):
    model = _TestModel()

    if creation_path == "setter":
        model.components = [_BareComponent]
    elif creation_path == "add_component":
        model.add_component(_BareComponent)
    elif creation_path == "prepend_component":
        model.prepend_component(_BareComponent)
    else:
        pytest.fail(f"unknown creation_path {creation_path!r}")

    # Without the defensive defaulting in _instantiate_component, this
    # raised: AttributeError: '_BareComponent' object has no attribute 'name'
    instances = model.get_instance("_BareComponent")
    assert len(instances) == 1, f"expected 1 instance, got {len(instances)}"
    assert isinstance(instances[0], _BareComponent)
    # Helper should have set .name to the class name
    assert instances[0].name == "_BareComponent"


@pytest.mark.parametrize("creation_path", ["setter", "add_component", "prepend_component"])
def test_bare_class_component_findable_by_get_instance_class(creation_path):
    """Class-form lookup (`get_instance(cls)`) uses isinstance, so it always
    worked. Cover it anyway — proves the fix didn't regress this path."""
    model = _TestModel()

    if creation_path == "setter":
        model.components = [_BareComponent]
    elif creation_path == "add_component":
        model.add_component(_BareComponent)
    elif creation_path == "prepend_component":
        model.prepend_component(_BareComponent)

    instances = model.get_instance(_BareComponent)
    assert len(instances) == 1
    assert isinstance(instances[0], _BareComponent)
