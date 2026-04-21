"""
Base classes for laser-measles components and models.

This module contains the base classes for laser-measles components and models.

The BaseComponent class is the base class for all laser-measles components.
It provides a uniform interface for all components with a __call__(model, tick) method
for execution during simulation loops.

The BaseLaserModel class is the base class for all laser-measles models.
"""

from __future__ import annotations

import gc
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Protocol
from typing import TypeVar

import alive_progress
import matplotlib.pyplot as plt
import polars as pl
from laser.core.laserframe import LaserFrame
from laser.core.random import seed as seed_prng
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from laser.measles.utils import StateArray
from laser.measles.utils import get_laserframe_properties
from laser.measles.utils import select_implementation
from laser.measles.wrapper import PrettyComponentsList
from laser.measles.wrapper import pretty_laserframe


class ParamsProtocol(Protocol):
    """Protocol defining the expected structure of model parameters."""

    seed: int
    start_time: str
    num_ticks: int
    verbose: bool
    show_progress: bool

    @property
    def time_step_days(self) -> int: ...
    @property
    def states(self) -> list[str]: ...


class BaseModelParams(BaseModel):
    """
    Base parameter schema for all laser-measles simulation models.

    This class defines configuration options that are common across all
    model variants. Subclasses must extend this class and implement
    model-specific properties.

    Validation behavior:
        - Extra/unknown fields are forbidden.
        - `start_time` must be a string in "YYYY-MM" format (year and month only).
        - `num_ticks` represents discrete simulation steps, not calendar days.
          The duration of each tick is determined by the subclass implementation
          of `time_step_days`.

    Attributes:
        seed (int):
            Random seed used to initialize all stochastic processes.
            Ensures reproducibility of simulation results.

        start_time (str):
            Simulation start time in "YYYY-MM" format (e.g., "2000-01").
            Day values are not supported; the model assumes the first day
            of the given month unless otherwise defined by subclasses.

        num_ticks (int):
            Total number of discrete time steps to simulate.
            The total simulated duration equals:
                num_ticks x time_step_days

        verbose (bool):
            If True, prints detailed logging output during execution.

        show_progress (bool):
            If True, displays a progress bar during simulation runs.

        use_numba (bool):
            If True, enables numba JIT acceleration when available.
            Falls back to pure Python if numba is unavailable.
    """

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=20250314, description="Random seed")
    start_time: str = Field(default="2000-01", description="Initial start time of simulation in YYYY-MM format")
    num_ticks: int = Field(default=365, description="Number of time steps")
    verbose: bool = Field(default=False, description="Whether to print verbose output")
    show_progress: bool = Field(default=True, description="Whether to show progress bar during simulation")
    use_numba: bool = Field(default=True, description="Whether to use numba acceleration when available")

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: str) -> str:
        # Accept "YYYY-MM" (canonical) or "YYYY-MM-DD" (strip the day).
        try:
            datetime.strptime(v, "%Y-%m")  # noqa DTZ007
            return v
        except ValueError:
            pass
        try:
            datetime.strptime(v, "%Y-%m-%d")  # noqa DTZ007
            return v[:7]  # truncate to "YYYY-MM"
        except ValueError:
            pass
        raise ValueError(f"start_time must be in 'YYYY-MM' or 'YYYY-MM-DD' format, got '{v}'")

    @property
    def time_step_days(self) -> int:
        """Time step in days. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement time_step_days")

    @property
    def states(self) -> list[str]:
        """List of model states. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement states")


@pretty_laserframe
class BasePatchLaserFrame(LaserFrame):
    """LaserFrame that has a states property."""

    states: StateArray  # StateArray with attribute access (S, E, I, R, etc.)


@pretty_laserframe
class BasePeopleLaserFrame(LaserFrame):
    """
    Base class for people LaserFrames with enhanced printing capabilities.

    This class provides factory methods for creating new instances with the same
    properties but different capacity, making it easy to resize people collections.
    """

    @classmethod
    def create_with_capacity(cls, capacity: int, source_frame: BasePeopleLaserFrame, initial_count: int = -1) -> Any:
        """
        Create a new instance of the same type with specified capacity.

        This factory method creates a new instance of the same class as the source_frame,
        with the specified capacity, and copies all properties from the source.

        Args:
            capacity: The capacity for the new LaserFrame.
            source_frame: The source LaserFrame to copy properties from.
            initial_count: The initial number of "active" agents in the new frame.
                If -1, the count is set to the capacity. Defaults to -1.

        Returns:
            A new instance of the same type with copied properties.
        """
        # Create new instance of the same type
        new_frame = cls(capacity=capacity, initial_count=initial_count)

        # Copy all properties from source
        new_frame.copy_properties_from(source_frame)

        return new_frame

    def copy_properties_from(self, source_frame: BasePeopleLaserFrame) -> None:
        """
        Copy all properties from another LaserFrame instance.

        This method copies all scalar and vector properties from the source frame,
        including their data types and default values.

        Args:
            source_frame: The source LaserFrame to copy properties from.
        """

        properties = get_laserframe_properties(source_frame)

        for property_name in properties:
            source_property = getattr(source_frame, property_name)

            if source_property.ndim == 1:
                # Scalar property — add then copy actual values
                self.add_scalar_property(property_name, dtype=source_property.dtype, default=0)
                target_property = getattr(self, property_name)
                n = min(len(source_property), len(target_property))
                target_property[:n] = source_property[:n]
            elif source_property.ndim == 2:
                # Vector property — add then copy actual values
                self.add_vector_property(
                    property_name,
                    len(source_property),
                    dtype=source_property.dtype,
                    default=0,
                )
                target_property = getattr(self, property_name)
                n = min(source_property.shape[1], target_property.shape[1])
                target_property[:, :n] = source_property[:, :n]
            else:
                # Handle higher dimensional properties if needed
                raise NotImplementedError(f"Property {property_name} has {source_property.ndim} dimensions, not supported")


class BaseLaserModel(ABC):
    """
    Base class for laser-measles simulation models.

    Provides common functionality for model initialization, component management,
    timing, metrics collection, and execution loops.
    """

    ScenarioType = TypeVar("ScenarioType")
    ParamsType = TypeVar("ParamsType", bound=ParamsProtocol)

    def __init__(self, scenario: pl.DataFrame | BaseScenario, params: BaseModelParams, name: str) -> None:
        """
        Initialize the model with common attributes.

        Args:
            scenario: Scenario data (type varies by model).
            params: Model parameters (type varies by model).
            name: Model name.
        """
        self.tinit = datetime.now(tz=None)  # noqa: DTZ005
        if params.verbose:
            print(f"{self.tinit}: Creating the {name} model…")

        # Auto-wrap polars DataFrame in appropriate scenario class if needed
        if isinstance(scenario, pl.DataFrame) and self.scenario_wrapper_class is not None:
            scenario = self.scenario_wrapper_class(scenario)

        self.scenario: BaseScenario = scenario
        self.params: BaseModelParams = params
        self.name = name

        # Initialize random number generator
        seed_value = params.seed if hasattr(params, "seed") and params.seed is not None else self.tinit.microsecond
        self.prng = seed_prng(seed_value)

        # Component management attributes
        self._components: list = []
        self.instances: list = []
        self.phases: list = []  # Called every tick

        # Metrics and timing
        self.metrics: list = []
        self._tstart: datetime | None = None
        self._tfinish: datetime | None = None

        # Time tracking
        self.start_time = datetime.strptime(self.params.start_time, "%Y-%m")  # noqa DTZ007
        self.current_date = self.start_time

        # Type annotations for attributes that subclasses will set
        self.patches: BasePatchLaserFrame

        # Attribute for subclasses to specify scenario wrapper
        self.scenario_wrapper_class: type[BaseScenario] | None = None

    def __repr__(self) -> str:
        """
        Return a string representation of the model, showing key attributes.

        Returns:
            str: String representation of the model, including LaserFrame attributes.
        """
        attrs = []
        for attr in dir(self):
            if attr.startswith("_"):
                continue
            value = getattr(self, attr)
            # Check if the attribute is a LaserFrame
            if isinstance(value, LaserFrame):
                attrs.append(f"{attr}=<LaserFrame capacity={getattr(value, 'capacity', None)}>")
            else:
                # Only show simple types to avoid clutter
                if isinstance(value, int | float | str | bool | type(None)):
                    attrs.append(f"{attr}={value!r}")
        return f"<{self.__class__.__name__}({', '.join(attrs)})>"

    def __str__(self) -> str:
        """
        Return a string representation of the model, showing key attributes.
        """
        attrs = {}
        for attr in dir(self):
            if attr.startswith("_"):
                continue
            value = getattr(self, attr)
            # Check if the attribute is a LaserFrame
            if isinstance(value, LaserFrame):
                attrs[attr] = "\n" + value.__str__()
            else:
                # Only show simple types to avoid clutter
                if isinstance(value, int | float | str | bool | type(None)):
                    attrs[attr] = value.__str__()
        newline = "\n"
        return f"<{self.__class__.__name__}>:\n{newline.join([f'{k}: {v}' for k, v in attrs.items()])}>"

    @abstractmethod
    def __call__(self, model: BaseLaserModel, tick: int) -> None:
        """
        Hook for subclasses to update the model for a given tick.

        Args:
            model: The model instance.
            tick: The current time step or tick.
        """

    @property
    def components(self) -> PrettyComponentsList:
        """
        Retrieve the list of model components.

        Returns:
            A PrettyComponentsList containing the components with enhanced formatting.
        """
        return PrettyComponentsList(self._components)

    @components.setter
    def components(self, components: list[type[BaseComponent]]) -> None:
        """
        Sets up the components of the model and constructs all instances.

        Args:
            components: A list of component classes to be initialized and integrated into the model.
        """
        self._components = components
        self.instances = []
        self.phases = []
        for component in components:
            instance = component(self, verbose=getattr(self.params, "verbose", False))
            self.instances.append(instance)
            if "__call__" in dir(instance):
                self.phases.append(instance)

        # Allow subclasses to perform additional component setup
        self._setup_components()

    def add_component(self, component: type[BaseComponent]) -> None:
        """
        Add the component class and an instance in model.instances.

        Note that this does not create new instances of other components.

        Args:
            component: A component class to be initialized and integrated into the model.
        """
        self._components.append(component)
        instance = component(self, verbose=getattr(self.params, "verbose", False))
        self.instances.append(instance)
        if "__call__" in dir(instance):
            self.phases.append(instance)
        self._setup_components()

    def prepend_component(self, component: type[BaseComponent]) -> None:
        """
        Add a component to the beginning of the component list.

        Args:
            component: A component class to be initialized and integrated into the model.
        """
        self._components.insert(0, component)
        instance = component(self, verbose=getattr(self.params, "verbose", False))
        self.instances.insert(0, instance)
        if "__call__" in dir(instance):
            self.phases.insert(0, instance)
        self._setup_components()

    def run(self) -> None:
        """
        Execute the model for a specified number of ticks, recording timing metrics.
        """
        # Check that there are some components to the model
        if len(self.components) == 0:
            raise RuntimeError("No components have been added to the model")

        # Initialize all component instances
        self._initialize()

        # TODO: Check that the model has been initialized
        num_ticks = self.params.num_ticks
        self._tstart = datetime.now(tz=None)  # noqa: DTZ005
        if self.params.verbose:
            print(f"{self._tstart}: Running the {self.name} model for {num_ticks} ticks…")

        self.metrics = []

        # Create progress bar only if show_progress is True
        if self.params.show_progress:
            with alive_progress.alive_bar(num_ticks) as bar:
                for tick in range(num_ticks):
                    self._execute_tick(tick)
                    bar()
        else:
            # Run without progress bar
            for tick in range(num_ticks):
                self._execute_tick(tick)

        self._tfinish = datetime.now(tz=None)  # noqa: DTZ005
        if self.params.verbose:
            print(f"Completed the {self.name} model at {self._tfinish}…")
            self._print_timing_summary()

    def time_elapsed(self, units: str = "days") -> int | float:
        """
        Return time elapsed since the start of the model.

        Args:
            units: Time units to return. Currently only supports "days" and "ticks".

        Returns:
            Time elapsed in the specified units.

        Raises:
            ValueError: If invalid time units are specified.
        """
        if units.lower() == "days":
            return (self.current_date - self.start_time).days
        elif units.lower() == "ticks":
            return (self.current_date - self.start_time).days / self.params.time_step_days
        else:
            raise ValueError(f"Invalid time units: {units}")

    def _initialize(self) -> None:
        """
        Initialize all component instances in the model.

        This method calls initialize() on all component instances and sets
        their initialized flag to True after successful initialization.
        """
        for instance in self.instances:
            if hasattr(instance, "_initialize") and hasattr(instance, "initialized"):
                instance._initialize(self)
                instance.initialized = True

    def get_tick_date(self, tick: int) -> datetime:
        """
        Return the date for a given tick.
        """
        return self.start_time + timedelta(days=tick * self.params.time_step_days)

    def cleanup(self) -> None:
        """
        Clean up model resources to prevent memory leaks.

        This method should be called when the model is no longer needed
        to free up memory from LaserFrame objects and other large data structures.
        """
        try:
            # Clear LaserFrame objects
            for key, value in list(vars(self).items()):
                if isinstance(value, LaserFrame):
                    delattr(self, key)

            # Do a garbage collection pass to free up memory from deleted LaserFrames
            gc.collect()

            # Clear component instances and their references
            if hasattr(self, "instances"):
                for instance in self.instances:
                    # Clear any LaserFrame references in components
                    if hasattr(instance, "model"):
                        instance.model = None
                    # Clear any large data structures in components
                    for attr_name in dir(instance):
                        if not attr_name.startswith("_") and attr_name not in ["initialized", "verbose"]:
                            attr_value = getattr(instance, attr_name, None)
                            if hasattr(attr_value, "__len__") and not callable(attr_value):
                                try:
                                    delattr(instance, attr_name)
                                except (AttributeError, TypeError):
                                    pass  # Skip if attribute is read-only
                self.instances.clear()

            # Clear phases and components
            if hasattr(self, "phases"):
                self.phases.clear()
            if hasattr(self, "_components"):
                self._components.clear()

            # Clear metrics and other large data structures
            if hasattr(self, "metrics"):
                self.metrics.clear()

            # Clear scenario and params references to large data
            if hasattr(self, "scenario"):
                del self.scenario
            if hasattr(self, "params"):
                # Clear any large data structures in params
                del self.params

            # Clear random number generator
            if hasattr(self, "prng"):
                del self.prng

        except Exception as e:
            # Don't let cleanup errors crash the program
            print(f"Warning: Error during model cleanup: {e}")

    def get_instance(self, cls: type | str) -> list:
        """
        Get all instances of a specific component class.

        Args:
            cls: The component class to search for.

        Returns:
            List of instances of the specified class, or [None] if none found.
            Works with inheritance - subclasses will match parent class searches.

        Example:
            state_trackers = model.get_instance(StateTracker)
            if state_trackers:
                state_tracker = state_trackers[0]  # Get first instance
        """
        if isinstance(cls, str):
            matches = [instance for instance in self.instances if instance.name == cls]
        else:
            matches = [instance for instance in self.instances if isinstance(instance, cls)]
        return matches if matches else [None]

    def get_component(self, cls: type | str) -> list:
        """
        Alias for get_instance (instances are instantiated, components are not).

        Args:
            cls: The component class to search for.

        Returns:
            List of instances of the specified class, or [None] if none found.
        """
        return self.get_instance(cls)

    def visualize(self, pdf: bool = True) -> None:
        """
        Visualize each component instances either by displaying plots or saving them to a PDF file.

        Args:
            pdf: If True, save the plots to a PDF file. If False, display the plots interactively.
                Defaults to True.

        Returns:
            None
        """
        if not pdf:
            for instance in self.instances:
                for _plot in instance.plot():
                    plt.show()
        else:
            print("Generating PDF output…")
            pdf_filename = f"{self.name} {self._tstart:%Y-%m-%d %H%M%S}.pdf"
            with PdfPages(pdf_filename) as pdf_file:
                for instance in self.instances:
                    for _plot in instance.plot():
                        pdf_file.savefig()
                        plt.close()

            print(f"PDF output saved to '{pdf_filename}'.")

        return

    def plot(self, fig: Figure | None = None):
        """
        Placeholder for plotting method.

        Args:
            fig: Optional matplotlib figure to plot on.

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _execute_tick(self, tick: int) -> None:
        """
        Execute a single tick.

        Can be overridden by subclasses for custom behavior.

        Args:
            tick: The current tick number.
        """
        timing = [tick]
        for phase in self.phases:
            tstart = datetime.now(tz=None)  # noqa: DTZ005
            phase(self, tick)
            tfinish = datetime.now(tz=None)  # noqa: DTZ005
            delta = tfinish - tstart
            timing.append(delta.seconds * 1_000_000 + delta.microseconds)
        self.metrics.append(timing)

        # Update current date by time_step_days
        self.current_date += timedelta(days=self.params.time_step_days)

    def _print_timing_summary(self) -> None:
        """
        Print timing summary for verbose mode.
        """
        try:
            import pandas as pd  # noqa: PLC0415

            names = [type(phase).__name__ for phase in self.phases]
            # Fix the pandas DataFrame creation by using proper column specification
            metrics = pd.DataFrame(self.metrics)
            if len(names) > 0:
                metrics.columns = ["tick", *names]
            plot_columns = metrics.columns[1:]
            sum_columns = metrics[plot_columns].sum()
            width = max(map(len, sum_columns.index))
            for key in sum_columns.index:
                print(f"{key:{width}}: {sum_columns[key]:13,} µs")
            print("=" * (width + 2 + 13 + 3))
            print(f"{'Total:':{width + 1}} {sum_columns.sum():13,} microseconds")
        except ImportError:
            try:
                import polars as pl  # noqa: PLC0415

                names = [type(phase).__name__ for phase in self.phases]
                metrics = pl.DataFrame(self.metrics, schema=["tick", *names])
                plot_columns = metrics.columns[1:]
                sum_columns = metrics.select(plot_columns).sum()
                # Handle polars DataFrame differently
                print("Timing summary available but detailed formatting requires pandas")
            except ImportError:
                print("Timing summary requires pandas or polars")

    @abstractmethod
    def _setup_components(self) -> None:
        """
        Hook for subclasses to perform additional component setup.
        """


class BaseComponent:
    """
    Base class for all laser-measles components.

    Components follow a uniform interface with __call__(model, tick) method
    for execution during simulation loops.
    """

    ModelType = TypeVar("ModelType")

    def __init__(self, model: BaseLaserModel, verbose: bool = False, params: None = None) -> None:  # TODO: add ParamsType
        """
        Initialize the component.

        Args:
            model: The model instance this component belongs to.
            verbose: Whether to enable verbose output. Defaults to False.
        """
        self.model = model
        self.verbose = verbose
        self.initialized = False
        self.params = params
        if not hasattr(self, "name"):
            self.name = self.__class__.__name__

    def __str__(self) -> str:
        """
        Return string representation using class docstring.

        Returns:
            String representation of the component.
        """
        # Use child class docstring if available, otherwise parent class
        doc = self.__class__.__doc__ or BaseComponent.__doc__
        return doc.strip() if doc else f"{self.__class__.__name__} component"

    def select_function(self, numpy_func: Any, numba_func: Any) -> Any:
        """
        Select between numpy and numba implementations based on model configuration.

        This method provides a convenient way for components to choose between
        numpy and numba implementations based on model parameters and environment
        variables.

        Args:
            numpy_func: The numpy implementation function.
            numba_func: The numba implementation function.

        Returns:
            The selected function implementation.

        Example:
            >>> # In a component's __init__ or _initialize method:
            >>> self.update_func = self.select_function(numpy_update, numba_update)
        """
        # Check if model has use_numba parameter
        use_numba = getattr(self.model.params, "use_numba", True)
        return select_implementation(numpy_func, numba_func, use_numba)

    def plot(self, fig: Figure | None = None):
        """
        Placeholder for plotting method.

        Args:
            fig: Optional matplotlib figure to plot on.

        Yields:
            None: Placeholder for plot objects.
        """
        yield None

    @abstractmethod
    def _initialize(self, model: BaseLaserModel) -> None:
        """
        Hook for subclasses to initialize the component based on other existing components.

        This is run at the beginning of model.run().

        Args:
            model: The model instance.
        """


class BasePhase(BaseComponent):
    """
    Base class for all laser-measles phases.

    Phases are components that are called every tick and include a __call__ method.
    """

    @abstractmethod
    def __call__(self, model, tick: int) -> None:
        """
        Execute component logic for a given simulation tick.

        Args:
            model: The model instance.
            tick: The current simulation tick.
        """

    @abstractmethod
    def _initialize(self, model: BaseLaserModel) -> None:
        pass


class BaseScenario(ABC):
    """
    Base class for scenario data wrappers.

    Provides a wrapper around polars DataFrames with additional validation
    and convenience methods.
    """

    def __init__(self, df: pl.DataFrame):
        """
        Initialize the scenario with a DataFrame.

        Args:
            df: The polars DataFrame containing scenario data.
        """
        self._df = df

    def __getattr__(self, attr):
        """
        Forward attribute access to the underlying DataFrame.

        Args:
            attr: The attribute name.

        Returns:
            The attribute value from the underlying DataFrame.
        """
        # Forward attribute access to the underlying DataFrame
        return getattr(self._df, attr)

    def __getitem__(self, key):
        """
        Forward item access to the underlying DataFrame.

        Args:
            key: The key to access.

        Returns:
            The value from the underlying DataFrame.
        """
        return self._df[key]

    def __repr__(self):
        """
        Return string representation of the scenario.

        Returns:
            String representation of the underlying DataFrame.
        """
        return repr(self._df)

    def __len__(self):
        """
        Return the length of the underlying DataFrame.

        Returns:
            The number of rows in the DataFrame.
        """
        return len(self._df)

    def unwrap(self) -> pl.DataFrame:
        """
        Return the underlying polars DataFrame.

        Returns:
            The underlying polars DataFrame.
        """
        return self._df

    def find_row_number(self, column: str, target_value: str) -> int:
        """
        Find the row number (0-based index) of a target string in a DataFrame column.

        Args:
            column: Column name to search in.
            target_value: String value to find.

        Returns:
            Row number (0-based index) of the target string.

        Raises:
            ValueError: If the target string is not found.
        """
        # Use arg_max on a boolean mask for maximum efficiency
        mask = self._df[column] == target_value

        # Check if value exists
        if not mask.any():
            raise ValueError(f"String '{target_value}' not found in column '{column}'")

        # arg_max returns the index of the first True value
        result = mask.arg_max()
        if result is None:
            raise ValueError(f"String '{target_value}' not found in column '{column}'")
        return result

    @abstractmethod
    def _validate(self, df: pl.DataFrame):
        """
        Validate required columns exist - derive from schema.

        Args:
            df: The DataFrame to validate.

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        # Validate required columns exist - derive from schema
        raise NotImplementedError("Subclasses must implement this method")
