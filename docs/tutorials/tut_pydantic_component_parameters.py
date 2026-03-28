# %% [markdown]
# # Parameter Validation
#
# This tutorial demonstrates the strengths of using Pydantic's `BaseModel` to define simulation
# parameters. Pydantic provides type
# validation, documentation, and error handling that makes component configuration more
# robust and user-friendly.
#
# Benefits:
# 1. Type Validation: Automatic validation of parameter types and values
# 2. Range Constraints: Built-in support for numerical bounds (gt, ge, lt, le)
# 3. Documentation: Self-documenting parameters with descriptions
# 4. Default Values: Clear default parameter values
# 5. Error Messages: Detailed error messages for validation failures
# 6. IDE Support: Better autocomplete and type hints
# 7. Serialization: Easy conversion to/from JSON and dictionaries

# %%
import traceback
from datetime import date

import polars as pl
from pydantic import Field
from pydantic import ValidationError

from laser.measles.biweekly.components import CaseSurveillanceParams
from laser.measles.biweekly.components import ImportationPressureParams

# Import the component parameter classes
from laser.measles.biweekly.components import InfectionParams
from laser.measles.biweekly.components import SIACalendarParams

# %% [markdown]
# ## Type validation and default values
#
# Pydantic automatically validates parameter types and provides clear default values:

# %%
print("=== Type Validation and Default Values ===")

# Create parameters with default values
infection_params = InfectionParams()
print("Default InfectionParams:")
print(f"  beta: {infection_params.beta}")
print(f"  seasonality: {infection_params.seasonality}")
print(f"  season_start: {infection_params.season_start}")

# Create parameters with custom values
custom_infection_params = InfectionParams(beta=50.0, seasonality=0.1, season_start=13)
print("\nCustom InfectionParams:")
print(f"  beta: {custom_infection_params.beta}")
print(f"  seasonality: {custom_infection_params.seasonality}")
print(f"  season_start: {custom_infection_params.season_start}")

# %% [markdown]
# ## Range constraints and validation
#
# Pydantic enforces numerical constraints automatically:

# %%
print("\n=== Range Constraints and Validation ===")
print("Testing range constraints:")

# This will work - beta > 0
try:
    valid_params = InfectionParams(beta=15.0)
    print(f"✓ Valid beta=15.0: {valid_params.beta}")
except ValidationError as e:
    print(f"✗ Validation error: {e}")
    print(traceback.format_exc())

# This will fail - beta must be > 0
try:
    invalid_params = InfectionParams(beta=-5.0)
    print(f"✓ Invalid beta=-5.0: {invalid_params.beta}")
except ValidationError:
    print("✗ Validation error for beta=-5.0:")
    print(traceback.format_exc())

# This will fail - seasonality must be 0 <= value <= 1
try:
    invalid_params = InfectionParams(seasonality=1.5)
    print(f"✓ Invalid seasonality=1.5: {invalid_params.seasonality}")
except ValidationError:
    print("✗ Validation error for seasonality=1.5:")
    print(traceback.format_exc())

# %% [markdown]
# ## Self-documenting parameters
# Pydantic Field descriptions provide built-in documentation:

# %%
print("\n=== Self-Documenting Parameters ===")

# Display parameter documentation
print("InfectionParams Documentation:")
schema = InfectionParams.model_json_schema()["properties"]
for field_name, field_schema in schema.items():
    print(f"  {field_name}: {field_schema.get('description', 'No description')}")

print("\nImportationPressureParams Documentation:")
for field_name, field_info in ImportationPressureParams.model_fields.items():
    print(f"  {field_name}: {field_info.description} (default: {field_info.default})")

# %% [markdown]
# ## Complex parameter types
# Pydantic handles complex types like `DataFrames` and functions with proper configuration:

# %%
print("\n=== Complex Parameter Types ===")

# Create a sample SIA schedule DataFrame
sia_schedule = pl.DataFrame(
    {
        "id": ["country:state1:lga1", "country:state1:lga2", "country:state2:lga3"],
        "date": [date(2024, 3, 15), date(2024, 6, 20), date(2024, 9, 10)],
    }
)


# Custom filter function
def filter_northern_states(node_id: str) -> bool:
    """Filter to include only northern states"""
    return "north" in node_id.lower()


# Create SIACalendarParams with complex types
sia_params = SIACalendarParams(
    sia_efficacy=0.95,
    filter_fn=filter_northern_states,
    aggregation_level=2,
    sia_schedule=sia_schedule,
    date_column="date",
    group_column="id",
)

print("SIA Calendar Parameters created successfully:")
print(f"  Efficacy: {sia_params.sia_efficacy}")
print(f"  Aggregation level: {sia_params.aggregation_level}")
print(f"  Schedule shape: {sia_params.sia_schedule.shape}")
print(f"  Filter function test: {sia_params.filter_fn('country:north_state:lga1')}")

# %% [markdown]
# ## Parameter serialization and persistence
# Pydantic makes it easy to save and load parameter configurations:

# %%
print("\n=== Parameter Serialization and Persistence ===")

# Serialize parameters to dictionary
infection_dict = custom_infection_params.model_dump()
print("Serialized InfectionParams:")
print(infection_dict)

# Recreate from dictionary
recreated_params = InfectionParams(**infection_dict)
print(f"\nRecreated parameters match: {recreated_params == custom_infection_params}")

# JSON serialization (excluding complex types)
importation_params = ImportationPressureParams(crude_importation_rate=2.5, importation_start=2, importation_end=8)

json_str = importation_params.model_dump_json()
print(f"\nJSON representation: {json_str}")

# Load from JSON
from_json = ImportationPressureParams.model_validate_json(json_str)
print(f"From JSON matches: {from_json == importation_params}")

# %% [markdown]
# ## Parameter validation in practice
# Let's see how validation helps prevent common configuration errors:

# %%
print("\n=== Parameter Validation in Practice ===")
print("Testing type validation:")

try:
    # This will be automatically converted
    params = CaseSurveillanceParams(detection_rate="0.15")  # string instead of float
    print(f"✓ String '0.15' converted to float: {params.detection_rate} (type: {type(params.detection_rate)})")
except ValidationError as e:
    print(f"✗ Type conversion failed: {e}")

try:
    # This will fail - can't convert non-numeric string
    params = CaseSurveillanceParams(detection_rate="high")
    print(f"✓ String 'high' converted: {params.detection_rate}")
except ValidationError:
    print("✗ Invalid string conversion:")
    print(traceback.format_exc())

# Common mistake: out of range values
# Note: ImportationPressureParams validation happens in the component's _validate_params method
# Let's demonstrate with a negative importation rate instead:
try:
    params = ImportationPressureParams(crude_importation_rate=-1.0)
    print(f"✓ Negative importation rate accepted: {params.crude_importation_rate}")
except ValidationError:
    print("✗ Negative importation rate caught:")
    print(traceback.format_exc())

# Time range validation happens at component level, not parameter level
params_with_bad_time_range = ImportationPressureParams(importation_start=10, importation_end=5)
print(
    f"✓ Parameters created (time range validation happens in component): start={params_with_bad_time_range.importation_start}, end={params_with_bad_time_range.importation_end}"
)

# %% [markdown]
# ## Parameter inheritance and customization
# You can easily extend parameter classes for specialized use cases:

# %%
print("\n=== Parameter Inheritance and Customization ===")


# Extend InfectionParams for a specific study
class SeasonalInfectionParams(InfectionParams):
    """Extended infection parameters with seasonal variations"""

    winter_multiplier: float = Field(default=1.2, description="Winter transmission multiplier", gt=0.0)
    summer_multiplier: float = Field(default=0.8, description="Summer transmission multiplier", gt=0.0)
    humidity_effect: float = Field(default=0.05, description="Humidity effect on transmission", ge=0.0, le=0.5)


# Create extended parameters
seasonal_params = SeasonalInfectionParams(beta=40.0, seasonality=0.15, winter_multiplier=1.5, humidity_effect=0.1)

print("Extended Seasonal Parameters:")
print(f"  Base beta: {seasonal_params.beta}")
print(f"  Seasonality: {seasonal_params.seasonality}")
print(f"  Winter multiplier: {seasonal_params.winter_multiplier}")
print(f"  Summer multiplier: {seasonal_params.summer_multiplier}")
print(f"  Humidity effect: {seasonal_params.humidity_effect}")

# Validation still works for extended class
try:
    invalid_seasonal = SeasonalInfectionParams(humidity_effect=0.8)  # > 0.5
except ValidationError as e:
    print(f"\n✗ Extended validation works: {e.errors()[0]['msg']}")

# %% [markdown]
# ## Configuration management
#
# Pydantic makes it easy to manage multiple parameter sets for different scenarios:

# %%
print("\n=== Configuration Management ===")

# Define parameter sets for different scenarios
scenarios = {
    "baseline": {"infection": InfectionParams(), "importation": ImportationPressureParams(), "surveillance": CaseSurveillanceParams()},
    "high_transmission": {
        "infection": InfectionParams(beta=60.0, seasonality=0.2),
        "importation": ImportationPressureParams(crude_importation_rate=3.0),
        "surveillance": CaseSurveillanceParams(detection_rate=0.2),
    },
    "low_surveillance": {
        "infection": InfectionParams(beta=25.0),
        "importation": ImportationPressureParams(crude_importation_rate=0.5),
        "surveillance": CaseSurveillanceParams(detection_rate=0.05),
    },
}

# Display scenario configurations
for scenario_name, params in scenarios.items():
    print(f"\n{scenario_name.upper()} Scenario:")
    print(f"  Transmission rate: {params['infection'].beta}")
    print(f"  Importation rate: {params['importation'].crude_importation_rate}/1k/year")
    print(f"  Detection rate: {params['surveillance'].detection_rate * 100}%")


# Easy parameter comparison
def compare_scenarios(scenario1, scenario2, param_type):
    """Compare parameters between scenarios"""
    params1 = scenarios[scenario1][param_type]
    params2 = scenarios[scenario2][param_type]

    print(f"\nComparing {param_type} parameters: {scenario1} vs {scenario2}")
    for field_name in params1.__class__.model_fields:
        val1 = getattr(params1, field_name)
        val2 = getattr(params2, field_name)
        if val1 != val2:
            print(f"  {field_name}: {val1} → {val2}")


compare_scenarios("baseline", "high_transmission", "infection")

# %% [markdown]
# ## IDE support and type hints
#
# Pydantic provides excellent IDE support with autocomplete and type checking:

# %%

print("\n=== IDE Support and Type Hints ===")


# Demonstrate type hints and IDE support
def create_infection_component_params(transmission_rate: float, seasonal_variation: float) -> InfectionParams:
    """Create infection parameters with type hints for better IDE support"""
    return InfectionParams(beta=transmission_rate, seasonality=seasonal_variation, season_start=0)


# Function with proper type annotations
def validate_parameter_ranges(params: InfectionParams) -> bool:
    """Validate parameter ranges with type checking"""
    # IDE will provide autocomplete for params.beta, params.seasonality, etc.
    return 0 < params.beta < 100 and 0 <= params.seasonality <= 1 and 0 <= params.season_start <= 25


# Test the functions
test_params = create_infection_component_params(35.0, 0.08)
is_valid = validate_parameter_ranges(test_params)
print(f"Created parameters are valid: {is_valid}")
print(f"  Beta: {test_params.beta}")
print(f"  Seasonality: {test_params.seasonality}")
