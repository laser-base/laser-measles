"""
This module provides wrapper classes for LaserFrame objects with enhanced printing capabilities.

Classes:
    LaserFrameWrapper: A wrapper around LaserFrame that provides clean and snazzy printing.
"""

from typing import Any

import numpy as np
from laser.core.laserframe import LaserFrame

from .utils import get_laserframe_properties


class PrettyComponentsList(list):
    """
    A list wrapper that provides enhanced printing for model components.

    This class maintains full list functionality while adding a formatted
    display similar to the LaserFrame wrapper style.
    

    **Example:**

        ```python
        # PrettyComponentsList wraps model.components for readable display
        model.components  # prints a formatted table of all components
        ```
    """

    def __str__(self) -> str:
        """Return a formatted string representation of the components list."""
        if not self:
            return (
                "┌─ Components (count: 0) ───────────────────────────┐\n"
                "│  No components found                              │\n"
                "└───────────────────────────────────────────────────┘"
            )

        # Get component count
        count = len(self)

        # Build the header
        header = f"┌─ Components (count: {count}) "
        header += "─" * max(0, 50 - len(header)) + "┐"

        # Build component lines
        lines = []
        for i, component in enumerate(self):
            # Get component name - handle ComponentFactory objects from create_component()
            if hasattr(component, "component_class"):
                component_name = component.component_class.__name__
            else:
                component_name = getattr(component, "__name__", str(component))

            # Add bullet points
            bullet = "├─" if i < len(self) - 1 else "└─"
            line = f"{bullet} {component_name}"
            lines.append(line)

        # Combine everything
        result = header + "\n"
        result += "\n".join(lines)
        result += "\n" + "└" + "─" * (len(header) - 2) + "┘"

        return result

    def __repr__(self) -> str:
        """Return a detailed representation."""
        return f"PrettyComponentsList({super().__repr__()})"


class PrettyLaserFrameWrapper:
    """
    A wrapper around LaserFrame that provides enhanced printing capabilities.

    This wrapper maintains full compatibility with the underlying LaserFrame while
    adding a clean and snazzy print method that displays all properties.

    Example:

        >>> lf = LaserFrame(capacity=1000)
        >>> lf.add_scalar_property("age", dtype=np.uint8)
        >>> lf.add_vector_property("states", 4)  # S, E, I, R
        >>> wrapped_lf = LaserFrameWrapper(lf)
        >>> print(wrapped_lf)  # Clean and snazzy output
    """

    def __init__(self, laserframe: LaserFrame):
        """
        Initialize the wrapper with a LaserFrame.

        Args:
            laserframe: The LaserFrame object to wrap
        """
        self._laserframe = laserframe

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped LaserFrame."""
        return getattr(self._laserframe, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Delegate attribute setting to the wrapped LaserFrame."""
        if name == "_laserframe":
            super().__setattr__(name, value)
        else:
            setattr(self._laserframe, name, value)

    def __len__(self) -> int:
        """Return the length of the wrapped LaserFrame."""
        return len(self._laserframe)

    def __str__(self) -> str:
        """Return a clean and snazzy string representation of the LaserFrame."""
        return self._format_laserframe()

    def __repr__(self) -> str:
        """Return a detailed representation of the wrapper."""
        return f"LaserFrameWrapper({self._laserframe!r})"

    def _format_laserframe(self) -> str:
        """
        Format the LaserFrame properties in a clean and snazzy way.

        Returns:
            A formatted string showing all LaserFrame properties
        """
        properties = get_laserframe_properties(self._laserframe)

        if not properties:
            return (
                "┌─ LaserFrame ──────────────────────────────────────┐\n"
                "│  No properties found                              │\n"
                "└───────────────────────────────────────────────────┘"
            )

        # Get basic info
        capacity = getattr(self._laserframe, "_capacity", "Unknown")
        count = getattr(self._laserframe, "_count", "Unknown")

        # Build the header
        header = f"┌─ {self._laserframe.__class__.__name__} (capacity: {capacity}, count: {count}) ─"
        header += "─" * max(0, 50 - len(header)) + "┐"

        # Build property lines
        lines = []
        for i, prop_name in enumerate(sorted(properties)):
            prop_value = getattr(self._laserframe, prop_name)

            # Format the property info
            dtype = str(prop_value.dtype)
            shape = str(prop_value.shape)

            # Truncate long shapes for display
            if len(shape) > 20:
                shape = shape[:17] + "..."

            # Add some visual flair
            bullet = "├─" if i < len(properties) - 1 else "└─"
            line = f"{bullet} {prop_name:<15} {dtype:<12} {shape}"
            lines.append(line)

        # Combine everything
        result = header + "\n"
        result += "\n".join(lines)
        result += "\n" + "└" + "─" * (len(header) - 2) + "┘"

        return result

    def print_laserframe(self, max_items: int | None = None) -> None:
        """
        Print the LaserFrame with optional data preview.

        Args:
            max_items: Maximum number of items to show in data preview (None for all)
        """
        print(self._format_laserframe())

        if max_items is not None:
            self._print_data_preview(max_items)

    def _print_data_preview(self, max_items: int) -> None:
        """
        Print a preview of the actual data in the LaserFrame.

        Args:
            max_items: Maximum number of items to show
        """
        properties = get_laserframe_properties(self._laserframe)

        if not properties:
            return

        print(f"\n📊 Data Preview (showing first {max_items} items):")
        print("─" * 60)

        # Create a simple table
        headers = ["Property"] + [f"Item {i}" for i in range(min(max_items, len(self._laserframe)))]
        header_line = "│ " + " │ ".join(f"{h:<12}" for h in headers) + " │"
        separator = "├─" + "─┼─".join("─" * 12 for _ in headers) + "─┤"

        print("┌─" + "─┬─".join("─" * 12 for _ in headers) + "─┐")
        print(header_line)
        print(separator)

        for prop_name in sorted(properties):
            prop_value = getattr(self._laserframe, prop_name)
            values = []

            # Get the first few values
            for i in range(min(max_items, len(self._laserframe))):
                if prop_value.ndim == 1:
                    val = prop_value[i]
                else:
                    val = prop_value[:, i] if prop_value.shape[0] <= 3 else f"[{prop_value.shape[0]} values]"

                # Format the value
                if isinstance(val, np.integer | int):
                    val_str = f"{val}"
                elif isinstance(val, np.floating | float):
                    val_str = f"{val:.3f}"
                elif isinstance(val, np.ndarray):
                    val_str = f"[{', '.join(f'{x:.3f}' for x in val[:3])}{'...' if len(val) > 3 else ''}]"
                else:
                    val_str = str(val)

                values.append(val_str[:10] + "..." if len(val_str) > 10 else val_str)

            # Create the row
            row = [f"{prop_name:<12}"] + [f"{v:<12}" for v in values]
            print("│ " + " │ ".join(row) + " │")

        print("└─" + "─┴─".join("─" * 12 for _ in headers) + "─┘")


def wrap_laserframe(laserframe: LaserFrame) -> PrettyLaserFrameWrapper:
    """
    Convenience function to wrap a LaserFrame with enhanced printing.

    Args:
        laserframe: The LaserFrame to wrap

    Returns:
        A LaserFrameWrapper instance
    """
    return PrettyLaserFrameWrapper(laserframe)


def return_pretty_laserframe(func):
    """
    Decorator that wraps the return value of a function with LaserFrameWrapper.

    This decorator can be used to automatically wrap LaserFrame objects returned
    by functions with enhanced printing capabilities.

    Example:

        >>> @wrapper
        ... def create_patches():
        ...     lf = LaserFrame(capacity=1000)
        ...     lf.add_scalar_property("age", dtype=np.uint32)
        ...     return lf  # This will be automatically wrapped
        ...
        >>> patches = create_patches()
        >>> print(patches)  # Clean and snazzy output
    """

    def wrapper_func(*args, **kwargs):
        """Call *func* and wrap any returned LaserFrame in a pretty-printer."""
        result = func(*args, **kwargs)
        if isinstance(result, LaserFrame):
            return PrettyLaserFrameWrapper(result)
        return result

    return wrapper_func


def pretty_laserframe(cls):
    """
    Class decorator that wraps LaserFrame subclasses with enhanced printing.

    This decorator can be applied to LaserFrame subclasses to automatically
    provide enhanced printing capabilities to all instances.

    Example:

        >>> @wrapper_class
        ... class PeopleLaserFrame(LaserFrame):
        ...     patch_id: np.ndarray
        ...     state: np.ndarray
        ...
        ...     def __init__(self, capacity: int, initial_count: int = 0):
        ...         super().__init__(capacity=capacity, initial_count=initial_count)
        ...
        >>> people = PeopleLaserFrame(capacity=1000)
        >>> print(people)  # Clean and snazzy output
    """

    # Create a new class that inherits from the original class
    class WrappedClass(cls):
        """Subclass of *cls* with enhanced ``__str__`` and ``__repr__`` formatting."""

        def __init__(self, *args, **kwargs):
            # Call the parent class __init__
            super().__init__(*args, **kwargs)
            # Store the original methods
            self._original_str = self.__str__
            self._original_repr = self.__repr__

        def __str__(self):
            """Override __str__ to use the wrapper formatting."""
            return PrettyLaserFrameWrapper(self)._format_laserframe()

        def __repr__(self):
            """Override __repr__ to use the wrapper formatting."""
            return f"{self.__class__.__name__}({super().__repr__()})"

        def print_laserframe(self, max_items=None):
            """Add the print_laserframe method."""
            wrapper = PrettyLaserFrameWrapper(self)
            wrapper.print_laserframe(max_items)

        @classmethod
        def create_resized_copy(cls, capacity: int, source_frame) -> "WrappedClass":
            """
            Alternative factory method for creating resized copies.

            This method provides an alternative approach to the factory method
            in BasePeopleLaserFrame, allowing for flexible initialization
            through the wrapper decorator.

            Args:
                capacity: The capacity for the new LaserFrame
                source_frame: The source LaserFrame to copy properties from

            Returns:
                A new instance with the specified capacity and copied properties
            """
            # Create new instance
            new_frame = cls(capacity=capacity)

            # Copy properties if the source has the copy_properties_from method
            if hasattr(source_frame, "copy_properties_from"):
                new_frame.copy_properties_from(source_frame)
            else:
                # Fallback: manually copy properties
                properties = get_laserframe_properties(source_frame)

                for property_name in properties:
                    source_property = getattr(source_frame, property_name)

                    if source_property.ndim == 1:
                        new_frame.add_scalar_property(
                            property_name, dtype=source_property.dtype, default=source_property[0] if len(source_property) > 0 else 0
                        )
                    elif source_property.ndim == 2:
                        new_frame.add_vector_property(
                            property_name,
                            len(source_property),
                            dtype=source_property.dtype,
                            default=source_property[:, 0] if source_property.shape[1] > 0 else 0,
                        )

            return new_frame

    # Copy the class name and module
    WrappedClass.__name__ = cls.__name__
    WrappedClass.__module__ = cls.__module__
    WrappedClass.__doc__ = cls.__doc__

    return WrappedClass
