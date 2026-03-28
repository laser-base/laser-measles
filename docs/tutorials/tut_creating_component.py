# %% [markdown]
# # Creating Custom Components
#
# This tutorial demonstrates how to create custom components for the compartmental model.
# We'll build a PIRI component that periodically strengthens vaccination coverage.

# %%
import polars as pl
from pydantic import BaseModel
from pydantic import Field

import laser.measles as lm
from laser.measles import create_component
from laser.measles.base import BasePhase
from laser.measles.compartmental import InitializeEquilibriumStatesProcess, InitializeEquilibriumStatesParams, ImportationPressureProcess, ImportationPressureParams, VitalDynamicsProcess, InfectionProcess, StateTracker, CaseSurveillanceTracker, CaseSurveillanceParams

# %% [markdown]
# ## Component architecture
#
# Components in laser-measles follow a standard pattern:
# 1. **Parameter Class**: Pydantic model defining component parameters
# 2. **Component Class**: Inherits from `BasePhase` and implements the logic
# 3. **Integration**: Add to model's component list and run simulation

# %% [markdown]
# ## Creating the PIRI component
#
# Let's create a component that implements Periodic Intensification of Routine Immunization (PIRI)
# to simulate vaccination campaigns that temporarily boost MCV1 coverage for newborn vaccination.
# Note: This requires VitalDynamicsProcess to be included in the model for births to occur.


# %%
class PIRIParams(BaseModel):
    """Parameters for the PIRI (Periodic Intensification of Routine Immunization) component."""

    mcv1_boost: float = Field(default=0.15, description="Temporary increase in MCV1 coverage during boost periods", ge=0.0, le=1.0)
    boost_interval: int = Field(default=365, description="Days between vaccination campaigns", gt=0)
    boost_duration: int = Field(default=30, description="Duration of vaccination campaign in days", gt=0)
    start_day: int = Field(default=90, description="Day to start first vaccination campaign", ge=0)


class PIRIProcess(BasePhase):
    """
    Component that implements Periodic Intensification of Routine Immunization (PIRI).

    This component simulates vaccination campaigns that occur at regular intervals,
    temporarily boosting MCV1 coverage to improve routine immunization of newborns.
    """

    def __init__(self, model, verbose: bool = False, params: PIRIParams | None = None):
        super().__init__(model, verbose)
        self.params = params if params is not None else PIRIParams()
        self.original_mcv1 = None  # Store original MCV1 values

    def __call__(self, model, tick: int):
        """Execute vaccination campaign if within boost period."""
        is_boost_active = self._is_boost_active(tick)

        # If boost should be active and we haven't applied it yet
        if is_boost_active and self.original_mcv1 is None:
            self._apply_mcv1_boost(model, tick)

        # If boost should not be active and we have an active boost
        elif not is_boost_active and self.original_mcv1 is not None:
            self._restore_mcv1(model, tick)

    def _is_boost_active(self, tick: int) -> bool:
        """Check if current tick is within an active boost period."""
        if tick < self.params.start_day:
            return False

        # Calculate days since start
        days_since_start = tick - self.params.start_day

        # Check if we're in a boost period
        cycle_position = days_since_start % self.params.boost_interval
        return cycle_position < self.params.boost_duration

    def _apply_mcv1_boost(self, model, tick: int):
        """Apply temporary MCV1 boost to scenario."""
        if "mcv1" not in model.scenario.columns:
            raise ValueError("MCV1 column not found in scenario")

        # Store original MCV1 values
        self.original_mcv1 = model.scenario["mcv1"].clone()

        # Apply boost to MCV1 coverage
        boosted_mcv1 = (self.original_mcv1 + self.params.mcv1_boost).clip(0.0, 1.0)
        model.scenario = model.scenario.with_columns(mcv1=boosted_mcv1)

        if self.verbose:
            boost_amount = (boosted_mcv1 - self.original_mcv1).mean()
            print(f"Day {tick}: Applied MCV1 boost, average increase: {boost_amount:.3f}")

    def _restore_mcv1(self, model, tick: int):
        """Restore original MCV1 values after boost period."""
        if self.original_mcv1 is not None:
            model.scenario = model.scenario.with_columns(mcv1=self.original_mcv1)

            if self.verbose:
                print(f"Day {tick}: Restored original MCV1 coverage")

            self.original_mcv1 = None

    def initialize(self, model):
        """Initialize component (no special initialization needed)."""
        return


# %% [markdown]
# ## Testing the component
#
# Let's create two simulations: one with the PIRI component and one without,
# to see the impact on disease transmission.


# %%
import numpy as np

RNG = np.random.default_rng(42)


def run_simulation(use_piri: bool = True, num_ticks: int = 365 * 10) -> tuple:
    """Run a simulation with or without the PIRI component."""

    # Create scenario with low initial MCV1 coverage
    scenario = lm.compartmental.BaseScenario(lm.scenarios.synthetic.single_patch_scenario(population=1_00_000, mcv1_coverage=0.5))

    # Create model parameters
    params = lm.compartmental.CompartmentalParams(num_ticks=num_ticks, verbose=False, seed=RNG.integers(0, 1000000))

    # Create and configure model
    model = lm.compartmental.CompartmentalModel(scenario, params)

    # Base components for all simulations
    components = [
        # Initialize with some immune individuals based on MCV1 coverage
        create_component(
            InitializeEquilibriumStatesProcess, InitializeEquilibriumStatesParams()
        ),
        # Seed infection to start outbreak
        create_component(
            ImportationPressureProcess, ImportationPressureParams()
        ),
        # Vital dynamics (births/deaths) - needed for MCV1 effects
        VitalDynamicsProcess,
        # Disease transmission
        InfectionProcess,
        # Track states over time
        StateTracker,
        # Track cases over time
        create_component(
            CaseSurveillanceTracker, CaseSurveillanceParams(detection_rate=1.0)
        ),
    ]

    # Add PIRI component if requested
    if use_piri:
        piri_params = PIRIParams(
            mcv1_boost=0.40,  # 20% increase in MCV1 coverage
            boost_interval=365,  # Annual campaigns
            boost_duration=90,  # Month-long campaigns
            start_day=0,  # Start at the beginning
        )
        components.append(create_component(PIRIProcess, piri_params))

    model.components = components

    # Run simulation
    model.run()

    # Get results
    state_tracker = model.get_instance(StateTracker)[0]
    results_df = state_tracker.get_dataframe()

    # Pivot to get state counts over time (tick, S, E, I, R format)
    results = results_df.pivot(index="tick", on="state", values="count").with_columns(pl.col("tick").cast(pl.Int32))

    # Get case surveillance data
    case_tracker = model.get_instance(CaseSurveillanceTracker)[0]
    cases_df = case_tracker.get_dataframe()

    return model, results, cases_df


# %% [markdown]
# ## Comparison of results
#
# Let's run both simulations and compare the outcomes.

# %%
print("Running simulation without PIRI...")
model_no_piri, results_no_piri, cases_no_piri = run_simulation(use_piri=False)

print("Running simulation with PIRI...")
model_with_piri, results_with_piri, cases_with_piri = run_simulation(use_piri=True)

print("\n" + "=" * 50)
print("SIMULATION RESULTS COMPARISON")
print("=" * 50)

# %%
# Compare final outcomes
final_no_piri = results_no_piri.tail(1)
final_with_piri = results_with_piri.tail(1)

print(f"\nFinal Results (Day {final_no_piri['tick'][0]}):")
print(f"{'Metric':<20} {'No PIRI':<15} {'With PIRI':<15} {'Difference':<15}")
print("-" * 65)
no_piri_val = cases_no_piri["cases"].sum()
with_piri_val = cases_with_piri["cases"].sum()
difference = with_piri_val - no_piri_val

print(f"{'cases' + ' (final)':<20} {no_piri_val:<15,} {with_piri_val:<15,} {difference:<15,}")


# %%
# Find peak infections
peak_no_piri = results_no_piri.select(pl.col("I").max()).item()
peak_with_piri = results_with_piri.select(pl.col("I").max()).item()

print("\nPeak Infections:")
print(f"No PIRI:    {peak_no_piri:,}")
print(f"With PIRI:  {peak_with_piri:,}")
print(f"Reduction:     {peak_no_piri - peak_with_piri:,} ({100 * (peak_no_piri - peak_with_piri) / peak_no_piri:.1f}%)")

# %% [markdown]
# ## Key insights
#
# This tutorial demonstrates:
#
# 1. **Component Structure**: Parameter class + component class inheriting from `BasePhase`
# 2. **Pydantic Validation**: Use Field() with constraints for robust parameter handling
# 3. **Model Integration**: Components are added to model.components list
# 4. **State Manipulation**: Direct access to model.patches.states for SEIR compartments
# 5. **Scenario Modification**: Direct manipulation of model.scenario for dynamic coverage
# 6. **Timing Logic**: Implement periodic behavior using modulo arithmetic
#
# The PIRI component successfully reduces peak infections by boosting MCV1 coverage,
# demonstrating the public health impact of improving routine immunization. The enhanced
# coverage affects newborn vaccination rates through the VitalDynamicsProcess component,
# leading to gradual population-level immunity improvements as more immune individuals
# are born during boost periods.

# %% [markdown]
# ## Best practices
#
# When creating components:
# - Use Pydantic BaseModel for parameters with proper validation
# - Inherit from BasePhase for components that run each tick
# - Store original values when making temporary modifications
# - Include verbose logging for debugging
# - Follow Google docstring conventions
# - Test components with simple scenarios first
