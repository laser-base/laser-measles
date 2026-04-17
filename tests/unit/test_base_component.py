"""
Tests for the BaseComponent class and its functionality.
"""

# ruff: noqa: PLC0415
from unittest.mock import Mock

import pytest

from laser.measles.base import BaseComponent
from laser.measles.base import BaseLaserModel


class MockModel:
    """Mock model class for testing."""


class MockComponentWithDocstring(BaseComponent):
    """
    A test component with a custom docstring.

    This component is used for testing the __str__ method
    functionality with child class docstrings.
    """

    def __call__(self, model, tick: int) -> None:
        return None

    def _initialize(self, model: BaseLaserModel) -> None:
        pass


class MockComponentWithoutDocstring(BaseComponent):
    def __call__(self, model, tick: int) -> None:
        return None

    def _initialize(self, model: BaseLaserModel) -> None:
        pass


class TestBaseComponent:
    """Test suite for BaseComponent class."""

    def test_initialization_default_params(self):
        """Test BaseComponent initialization with default parameters."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        assert component.model is model
        assert component.verbose is False
        assert component.initialized is False  # Should be False initially

    def test_initialization_with_verbose(self):
        """Test BaseComponent initialization with verbose=True."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model, verbose=True)

        assert component.model is model
        assert component.verbose is True
        assert component.initialized is False  # Should be False initially

    def test_call_method_exists(self):
        """Test that __call__ method exists and can be called."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        # Should not raise an exception
        result = component(model, 0)
        assert result is None

    def test_plot_method_exists(self):
        """Test that plot method exists and returns a generator."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        plot_gen = component.plot()
        assert hasattr(plot_gen, "__next__")  # Is a generator

        # Should yield None
        result = next(plot_gen)
        assert result is None

    def test_plot_method_with_figure(self):
        """Test that plot method accepts a figure parameter."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        mock_fig = Mock()
        plot_gen = component.plot(mock_fig)
        result = next(plot_gen)
        assert result is None

    def test_str_method_base_class(self):
        """Test __str__ method returns base class docstring."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        str_repr = str(component)
        expected = (
            "Base class for all laser-measles components.",
            "Components follow a uniform interface with __call__(model, tick) method",
            "for execution during simulation loops.",
        )
        assert all(sub_str in str_repr for sub_str in expected)

    def test_str_method_child_class_with_docstring(self):
        """Test __str__ method returns child class docstring when available."""
        model = MockModel()
        component = MockComponentWithDocstring(model)

        str_repr = str(component)
        expected = (
            "A test component with a custom docstring.",
            "This component is used for testing the __str__ method",
            "functionality with child class docstrings.",
        )
        assert all(sub_str in str_repr for sub_str in expected)

    def test_str_method_child_class_without_docstring(self):
        """Test __str__ method falls back to base class docstring when child has none."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        str_repr = str(component)
        expected = (
            "Base class for all laser-measles components.",
            "Components follow a uniform interface with __call__(model, tick) method",
        )
        assert all(sub_str in str_repr for sub_str in expected)

    def test_str_method_no_docstring_fallback(self):
        """Test __str__ method fallback when no docstring is available."""
        model = MockModel()
        component = MockComponentWithoutDocstring(model)

        # Temporarily remove docstring
        original_doc = BaseComponent.__doc__
        BaseComponent.__doc__ = None

        try:
            str_repr = str(component)
            assert str_repr == "MockComponentWithoutDocstring component"
        finally:
            # Restore original docstring
            BaseComponent.__doc__ = original_doc


class TestBaseComponentIntegration:
    """Integration tests for BaseComponent with actual laser-measles components."""

    def test_import_from_new_location(self):
        """Test that BaseComponent can be imported from the new location."""

        model = MockModel()
        component = MockComponentWithoutDocstring(model)
        assert isinstance(component, BaseComponent)

    def test_biweekly_components_still_work(self):
        """Test that existing biweekly components still work with refactored BaseComponent."""
        try:
            # Test importing some biweekly components
            from laser.measles.biweekly.components.process_infection import InfectionProcess
            from laser.measles.biweekly.components.tracker_state import StateTracker

            MockModel()

            # These should not raise import errors
            assert hasattr(StateTracker, "__init__")
            assert hasattr(InfectionProcess, "__init__")

        except ImportError as e:
            pytest.fail(f"Failed to import biweekly components: {e}")

    def test_components_utility_still_works(self):
        """Test that the components utility module still works with the refactored BaseComponent."""
        try:
            from laser.measles.components import component
            from laser.measles.components import create_component

            # These should not raise import errors
            assert callable(component)
            assert callable(create_component)

        except ImportError as e:
            pytest.fail(f"Failed to import components utilities: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
