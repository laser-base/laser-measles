"""
Component utilities for the laser-measles package.

This module provides utilities for creating and managing components in the laser-measles package.
The main feature is a decorator that makes it easier to create components with parameters.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any
from typing import TypeVar

from pydantic import BaseModel

from laser.measles.base import BaseComponent

T = TypeVar("T", bound=BaseComponent)
B = TypeVar("B", bound=BaseModel)


def component(cls: type[T] | None = None, **default_params):  # noqa: UP047
    """Decorator that adds a ``create`` factory to a component class.

    Use this at *set parameters* time to bake default parameter values into
    a component class.  The decorated class gains a ``create(model, **overrides)``
    static method that merges defaults with caller-supplied overrides.

    Can be applied with or without arguments:

    Args:
        cls: The component class to decorate.  When ``None``, the decorator
            returns a wrapper that accepts keyword defaults.
        **default_params: Default parameter values passed through to the
            component constructor.

    Returns:
        The decorated class (with ``create`` attached), or a decorator
            function if ``cls`` is ``None``.

    **Example:**

        ```python
        @component
        class MyProcess(BaseComponent):
            def __init__(self, model, verbose=False, beta=0.3):
                super().__init__(model, verbose)
                self.beta = beta

        # With defaults baked in:
        @component(beta=0.8)
        class HighBetaProcess(BaseComponent): ...

        # Use the factory:
        model.add_component(HighBetaProcess.create(model, beta=0.9))
        ```
    """

    def decorator(component_cls: type[T]) -> type[T]:
        """Apply the ``create`` factory to *component_cls*."""
        # Store the default parameters
        component_cls._default_params = default_params  # type: ignore

        # Create a factory function for creating instances
        @wraps(component_cls)
        def create(model: Any, **kwargs) -> T:
            """Instantiate the component, merging default and caller-supplied params."""
            # Merge default parameters with provided parameters
            params = {**default_params, **kwargs}
            return component_cls(model, **params)

        # Add the factory function to the class
        component_cls.create = staticmethod(create)  # type: ignore

        return component_cls

    # If cls is provided, apply the decorator immediately
    if cls is not None:
        return decorator(cls)

    # Otherwise, return the decorator function
    return decorator


def create_component(component_class: type[T], params: type[B] | None = None) -> Callable[[Any, Any], T]:  # noqa: UP047
    """Wrap a component class and its parameters into a single callable.

    Use this at *set parameters* time when a component requires a custom
    Pydantic parameter object.  The returned factory is callable with the
    same ``(model, verbose)`` signature that
    [`BaseLaserModel.components`][laser.measles.base.BaseLaserModel.components]
    expects, so it can be placed directly in the component list.

    Args:
        component_class: The component class to instantiate.
        params: A Pydantic parameter object (or ``None`` for defaults).

    Returns:
        A callable that creates the component when invoked by the model.

    **Example:**

        ```python
        from laser.measles import create_component
        from laser.measles.compartmental.components import InfectionProcess, InfectionParams

        model.components = [
            create_component(InfectionProcess, InfectionParams(beta=0.8)),
        ]
        ```
    """

    class ComponentFactory:
        """Callable wrapper that pairs a component class with its parameters.

    **Example:**

        ```python
        from laser.measles.components.utils import ComponentFactory
        from laser.measles.biweekly.components.process_infection import InfectionProcess, InfectionParams

        factory = ComponentFactory()
        component = factory.create(InfectionProcess, InfectionParams(beta=0.57), model=model)
        ```
    """

        def __init__(self, component_class: type[T], params: BaseModel | None = None):
            self.component_class = component_class
            if params is not None:
                self.params = params
            else:
                self.params = None

        def __call__(self, model: Any, verbose: bool = False) -> T:
            return self.component_class(model, params=self.params, verbose=verbose)

        def __str__(self) -> str:
            return f"<{self.component_class.__name__} factory>"

        def __repr__(self) -> str:
            return f"<{self.component_class.__name__} factory>"

    return ComponentFactory(component_class, params)
