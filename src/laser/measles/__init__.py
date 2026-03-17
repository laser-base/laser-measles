"""
Laser Measles - Measles simulation framework.

This package provides tools for simulating measles transmission dynamics
using agent-based and compartmental models with various spatial and temporal configurations.
"""

# ruff: noqa: F401, F403, E402
__version__ = "0.9.2"

# --- Exports ---
MEASLES_MODULES = ["laser.measles.abm", "laser.measles.compartmental", "laser.measles.biweekly"]

from .api import *
from .api import __all__
