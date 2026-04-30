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
    """
    Decorator for creating components with default parameters.

    This decorator makes it easier to create components with parameters by:
    1. Allowing default parameters to be specified at class definition time
    2. Creating a factory function that can be used to create component instances
    3. Preserving type hints and docstrings

    Parameters
    ----------
    cls : Type[BaseComponent], optional
        The component class to decorate. If None, returns a decorator function.
    **default_params
        Default parameters to use when creating the component instance.

    Returns
    -------
    Union[Type[BaseComponent], Callable]
        If cls is provided, returns a factory function for creating component instances.
        If cls is None, returns a decorator function.

    Examples
    --------
    Basic usage:

    >>> @component
    ... class MyComponent(BaseComponent):
    ...     def __init__(self, model, param1=1, param2=2):
    ...         super().__init__(model)
    ...         self.param1 = param1
    ...         self.param2 = param2

    With default parameters:

    >>> @component(param1=10, param2=20)
    ... class MyComponent(BaseComponent):
    ...     def __init__(self, model, param1=1, param2=2):
    ...         super().__init__(model)
    ...         self.param1 = param1
    ...         self.param2 = param2

    Using the factory:

    >>> # Create with default parameters
    >>> MyComponent.create(model)
    >>> # Create with custom parameters
    >>> MyComponent.create(model, param1=100, param2=200)
    """

    def decorator(component_cls: type[T]) -> type[T]:
        # Store the default parameters
        component_cls._default_params = default_params  # type: ignore

        # Create a factory function for creating instances
        @wraps(component_cls)
        def create(model: Any, **kwargs) -> T:
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


def create_component(component_class: type[T], params: type[B] | None = None) -> Callable[[Any], T]:  # noqa: UP047
    """
    Helper function to create a component instance with parameters.

    This function creates a callable object that will instantiate the component
    with the given parameters when called by the model.

    Parameters
    ----------
    component_class : Type[BaseComponent]
        The component class to instantiate
    params : BaseModel, optional
        Parameter object to pass to the component constructor as ``params=...``.

    Returns
    -------
    Callable[[Any], BaseComponent]
        A single-argument factory: when called by the model with the model
        instance, it returns ``component_class(model, params=params)``.

    Examples
    --------
    >>> model.components = [
    ...     create_component(MyComponent, params=MyComponentParams),
    ...     AnotherComponent,
    ... ]
    """

    class ComponentFactory:
        def __init__(self, component_class: type[T], params: BaseModel | None = None):
            self.component_class = component_class
            if params is not None:
                self.params = params
            else:
                self.params = None

        def __call__(self, model: Any) -> T:
            return self.component_class(model, params=self.params)

        def __str__(self) -> str:
            return f"<{self.component_class.__name__} factory>"

        def __repr__(self) -> str:
            return f"<{self.component_class.__name__} factory>"

    return ComponentFactory(component_class, params)
