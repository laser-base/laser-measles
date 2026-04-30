"""Tests for SIA calendar component across all model types."""
# ruff: noqa: DTZ001, RUF100, PT012, PT011

import importlib
from datetime import datetime

import numpy as np
import polars as pl
import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES


def setup_sia_sim(scenario, model_params, sia_params, module):
    """Set up a SIA simulation for testing."""
    # Create model
    model = module.Model(scenario, model_params)

    # Create SIA component with parameters
    sia_component = lm.create_component(module.components.SIACalendarProcess, sia_params)

    # Add basic components needed for SIA testing
    components = [sia_component]

    # Add state tracker if available
    if hasattr(module.components, "StateTracker"):
        components.append(module.components.StateTracker)

    # Add initialization component if available
    if hasattr(module.components, "InitializeEquilibriumStatesProcess"):
        components.insert(0, module.components.InitializeEquilibriumStatesProcess)

    model.components = components

    return model


@pytest.fixture
def mock_scenario():
    """Create a mock scenario for testing."""
    data = {
        "id": ["NG:KN:001", "NG:KN:002", "NG:KD:001", "NG:KD:002"],
        "pop": [1000, 1500, 2000, 800],
        "lat": [12.0, 12.1, 11.9, 12.2],
        "lon": [8.5, 8.6, 8.4, 8.7],
        "mcv1": [0.8, 0.75, 0.85, 0.9],
    }
    df = pl.DataFrame(data)
    return df


def create_sia_schedule(model_type=None):
    """Create a mock SIA schedule."""
    schedule = pl.DataFrame({"id": ["NG:KN", "NG:KD", "NG:KN"], "date": ["2023-01-10", "2023-01-15", "2023-01-25"]})

    if model_type and "compartmental" not in model_type:
        # ABM and biweekly models expect datetime dates
        schedule = schedule.with_columns(pl.col("date").str.to_datetime())

    return schedule


@pytest.fixture
def mock_sia_schedule():
    """Create a mock SIA schedule for compartmental model (default)."""
    return create_sia_schedule()


def create_model_params(module, num_ticks=100, start_time="2023-01"):
    """Create model parameters for a given module."""
    return module.Params(num_ticks=num_ticks, start_time=start_time)


def create_model(scenario, module, num_ticks=100, start_time="2023-01"):
    """Create a model for a given module."""
    model_params = create_model_params(module, num_ticks, start_time)
    return module.Model(scenario, model_params)


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
class TestSIACalendarParams:
    """Test SIACalendarParams class."""

    def test_default_params(self, measles_module):
        """Test default parameter values."""
        module = importlib.import_module(measles_module)
        sia_schedule = create_sia_schedule(measles_module)
        params = module.components.SIACalendarParams(sia_schedule=sia_schedule)
        assert params.sia_efficacy == 0.9
        assert params.aggregation_level == 3
        assert params.date_column == "date"
        assert params.group_column == "id"

    def test_custom_params(self, measles_module):
        """Test custom parameter values."""
        module = importlib.import_module(measles_module)
        sia_schedule = create_sia_schedule(measles_module)
        params = module.components.SIACalendarParams(
            sia_schedule=sia_schedule, sia_efficacy=0.8, aggregation_level=2, date_column="schedule_date", group_column="region_id"
        )
        assert params.sia_efficacy == 0.8
        assert params.aggregation_level == 2
        assert params.date_column == "schedule_date"
        assert params.group_column == "region_id"

    def test_efficacy_bounds(self, measles_module):
        """Test SIA efficacy bounds validation."""
        module = importlib.import_module(measles_module)
        sia_schedule = create_sia_schedule(measles_module)
        # Valid bounds
        module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=0.0)
        module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=1.0)

        # Invalid bounds should raise validation error
        with pytest.raises(ValueError):
            module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=-0.1)
        with pytest.raises(ValueError):
            module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=1.1)


@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
class TestSIACalendarProcess:
    """Test SIACalendarProcess class."""

    def test_initialization(self, mock_scenario, measles_module):
        """Test component initialization."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        # Test with aggregation level 2 to group by state
        sia_schedule = create_sia_schedule(measles_module)
        params = module.components.SIACalendarParams(sia_schedule=sia_schedule, aggregation_level=2)
        component = module.components.SIACalendarProcess(model, params=params)

        assert len(component.node_mapping) == 2  # NG:KN and NG:KD
        assert "NG:KN" in component.node_mapping
        assert "NG:KD" in component.node_mapping
        assert len(component.node_mapping["NG:KN"]) == 2  # Two nodes in KN
        assert len(component.node_mapping["NG:KD"]) == 2  # Two nodes in KD

    def test_initialization_without_params(self, mock_scenario, measles_module):
        """Test initialization fails without parameters."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        with pytest.raises(ValueError, match="SIACalendarParams must be provided"):
            module.components.SIACalendarProcess(model)

    def test_date_parsing(self, mock_scenario, measles_module):
        """Test date parsing functionality."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        # Test that component has access to current_date from model
        # Different models may have different date handling
        assert hasattr(model, "current_date")

    def test_date_parsing_month_format(self, mock_scenario, measles_module):
        """Test date parsing with YYYY-MM format."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module, start_time="2023-01")

        sia_schedule = create_sia_schedule(measles_module)
        sia_params = module.components.SIACalendarParams(sia_schedule=sia_schedule)
        component = module.components.SIACalendarProcess(model, params=sia_params)

        # Test that component initializes successfully with month format
        assert len(component.params.sia_schedule) == 3

    def test_invalid_date_format(self, mock_scenario, measles_module):
        """Test invalid date format handling."""
        module = importlib.import_module(measles_module)

        # Test invalid format in model initialization
        with pytest.raises(ValueError):
            model_params = module.Params(num_ticks=100, start_time="invalid-date")
            module.Model(mock_scenario, model_params)

    def test_parameter_validation(self, mock_scenario, measles_module):
        """Test parameter validation."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        # Test missing required columns
        invalid_schedule = pl.DataFrame({"wrong_column": ["value"]})
        params = module.components.SIACalendarParams(sia_schedule=invalid_schedule)

        with pytest.raises(ValueError, match="sia_schedule must contain columns"):
            module.components.SIACalendarProcess(model, params=params)

        # Test invalid aggregation level
        valid_schedule = pl.DataFrame({"id": ["test"], "date": ["2023-01-01"]})
        params = module.components.SIACalendarParams(sia_schedule=valid_schedule, aggregation_level=0)

        with pytest.raises(ValueError, match="aggregation_level must be at least 1"):
            module.components.SIACalendarProcess(model, params=params)

    def test_sia_implementation(self, mock_scenario, measles_module):
        """Test SIA implementation functionality."""
        module = importlib.import_module(measles_module)

        # Create a model with SIA component
        model_params = create_model_params(module)
        sia_schedule = create_sia_schedule(measles_module)
        sia_params = module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=1.0, aggregation_level=2)
        model = setup_sia_sim(mock_scenario, model_params, sia_params, module)

        # Set seed for reproducible testing
        np.random.seed(42)

        # Get the SIA component
        sia_component = model.get_instance(module.components.SIACalendarProcess)[0]

        # Set current_date to simulate tick 10 (2023-01-11) - should trigger KN SIA scheduled for 2023-01-10
        model.current_date = datetime(2023, 1, 11)
        sia_component(model, tick=10)

        # Check that SIA was marked as implemented
        assert len(sia_component.implemented_sias) > 0

    def test_sia_not_implemented_twice(self, mock_scenario, measles_module):
        """Test that SIAs are not implemented twice."""
        module = importlib.import_module(measles_module)

        model_params = create_model_params(module)
        sia_schedule = create_sia_schedule(measles_module)
        sia_params = module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=1.0, aggregation_level=2)
        model = setup_sia_sim(mock_scenario, model_params, sia_params, module)

        np.random.seed(42)

        # Get the SIA component
        sia_component = model.get_instance(module.components.SIACalendarProcess)[0]

        # Run component twice at the same tick
        sia_component(model, tick=10)
        first_implemented = len(sia_component.implemented_sias)

        sia_component(model, tick=10)
        second_implemented = len(sia_component.implemented_sias)

        # Should not have implemented additional SIAs
        assert first_implemented == second_implemented

    def test_multiple_sias_different_dates(self, mock_scenario, measles_module):
        """Test multiple SIAs at different dates."""
        module = importlib.import_module(measles_module)

        model_params = create_model_params(module)
        sia_schedule = create_sia_schedule(measles_module)
        sia_params = module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=1.0, aggregation_level=2)
        model = setup_sia_sim(mock_scenario, model_params, sia_params, module)

        np.random.seed(42)

        # Get the SIA component
        sia_component = model.get_instance(module.components.SIACalendarProcess)[0]

        # Set current_date to simulate tick 10 (2023-01-11) - should trigger KN SIA scheduled for 2023-01-10
        model.current_date = datetime(2023, 1, 11)
        sia_component(model, tick=10)
        assert len(sia_component.implemented_sias) >= 1

        # Set current_date to simulate tick 15 (2023-01-16) - should trigger KD SIA scheduled for 2023-01-15
        model.current_date = datetime(2023, 1, 16)
        sia_component(model, tick=15)
        assert len(sia_component.implemented_sias) >= 2

        # Set current_date to simulate tick 25 (2023-01-26) - should trigger second KN SIA scheduled for 2023-01-25
        model.current_date = datetime(2023, 1, 26)
        sia_component(model, tick=25)
        assert len(sia_component.implemented_sias) >= 3

    def test_filtering_function(self, mock_scenario, measles_module):
        """Test custom filtering function."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        # Filter to only include KN nodes
        def filter_fn(x: str) -> bool:
            return "KN" in x

        sia_schedule = create_sia_schedule(measles_module)
        params = module.components.SIACalendarParams(sia_schedule=sia_schedule, filter_fn=filter_fn, aggregation_level=2)
        component = module.components.SIACalendarProcess(model, params=params)

        # Should only have KN nodes in mapping
        assert len(component.node_mapping) == 1
        assert "NG:KN" in component.node_mapping
        assert "NG:KD" not in component.node_mapping

    def test_different_aggregation_levels(self, mock_scenario, measles_module):
        """Test different aggregation levels."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        # Test aggregation level 2 (country:state)
        sia_schedule = create_sia_schedule(measles_module)
        params = module.components.SIACalendarParams(sia_schedule=sia_schedule, aggregation_level=2)
        component = module.components.SIACalendarProcess(model, params=params)

        # Should group by NG:KN and NG:KD
        assert len(component.node_mapping) == 2
        assert "NG:KN" in component.node_mapping
        assert "NG:KD" in component.node_mapping

    def test_get_sia_schedule(self, mock_scenario, measles_module):
        """Test getting SIA schedule."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        sia_schedule = create_sia_schedule(measles_module)
        params = module.components.SIACalendarParams(sia_schedule=sia_schedule)
        component = module.components.SIACalendarProcess(model, params=params)

        schedule = component.get_sia_schedule()
        # For compartmental model, returned schedule may be different due to conversion
        if "compartmental" in measles_module:
            assert len(schedule) == 3  # Same number of rows
        else:
            assert len(schedule) == 3

    def test_verbose_output(self, mock_scenario, measles_module, capsys):
        """Test verbose output."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)
        model.params.verbose = True

        # Create verbose component
        sia_schedule = create_sia_schedule(measles_module)
        sia_params = module.components.SIACalendarParams(sia_schedule=sia_schedule, sia_efficacy=1.0, aggregation_level=2)
        module.components.SIACalendarProcess(model, params=sia_params)

        # Check initialization message
        captured = capsys.readouterr()
        assert "SIACalendar initialized with 2 groups" in captured.out

    def test_empty_sia_schedule(self, mock_scenario, measles_module):
        """Test behavior with empty SIA schedule."""
        module = importlib.import_module(measles_module)
        model = create_model(mock_scenario, module)

        # Create empty schedule with proper types based on model type
        if "compartmental" in measles_module:
            # Compartmental model expects string dates that it converts
            empty_schedule = pl.DataFrame({"id": [], "date": []}).with_columns(
                [pl.col("id").cast(pl.String), pl.col("date").cast(pl.String)]
            )
        else:
            # ABM and biweekly models expect datetime dates
            empty_schedule = pl.DataFrame({"id": [], "date": []}).with_columns(
                [pl.col("id").cast(pl.String), pl.col("date").cast(pl.Datetime)]
            )

        params = module.components.SIACalendarParams(sia_schedule=empty_schedule)
        component = module.components.SIACalendarProcess(model, params=params)

        # Should not crash and should not implement any SIAs
        component(model, tick=10)
        assert len(component.implemented_sias) == 0
