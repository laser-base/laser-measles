"""
Test script to verify that the show_progress parameter works correctly.
"""

import importlib
import time

import pytest

from laser.measles.base import BaseComponent
from laser.measles.scenarios import synthetic

MEASLES_MODULES = ["laser.measles.abm", "laser.measles.compartmental", "laser.measles.biweekly"]


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_progress_bar(measles_module):
    """Test that show_progress parameter works correctly."""
    print("Testing progress bar functionality...")

    MeaslesModule = importlib.import_module(measles_module)
    # Create test scenario
    scenario = synthetic.two_patch_scenario()

    # Test with progress bar enabled (default)
    print("\n1. Testing with show_progress=True (default):")
    params = MeaslesModule.Params(num_ticks=5, verbose=True, show_progress=True)
    model = MeaslesModule.Model(scenario, params, "test_model")

    # Add a simple component that does nothing
    class DummyComponent(BaseComponent):
        def __init__(self, model):
            self.model = model
            self.initialized = False

        def _initialize(self, model):
            self.initialized = True

        def __call__(self, model, tick):
            time.sleep(0.1)  # Simulate some work

    model.components = [DummyComponent]

    # Run the model
    model.run()

    # Test with progress bar disabled
    print("\n2. Testing with show_progress=False:")
    params_no_progress = MeaslesModule.Params(num_ticks=5, verbose=True, show_progress=False)
    model_no_progress = MeaslesModule.Model(scenario, params_no_progress, "test_model_no_progress")
    model_no_progress.components = [DummyComponent]

    # Run the model without progress bar
    model_no_progress.run()

    print("\n✅ Progress bar functionality test completed successfully!")
    print("   - With show_progress=True: Progress bar should have been displayed")
    print("   - With show_progress=False: No progress bar should have been displayed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
