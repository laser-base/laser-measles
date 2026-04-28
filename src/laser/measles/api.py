# ruff: noqa: F401, E402
# Public API Export List

__all__ = []

# ----- Submodule re-exports -----
from . import abm
from . import base
from . import biweekly
from . import compartmental
from . import components
from . import demographics
from . import migration
from . import mixing
from . import scenarios
from .scenarios import synthetic

__all__.extend(
    [
        "abm",
        "base",
        "biweekly",
        "compartmental",
        "components",
        "demographics",
        "migration",
        "mixing",
        "scenarios",
        "synthetic",
    ]
)

# ----- Base classes (laser.measles.base) -----
from .base import BaseComponent
from .base import BaseLaserModel
from .base import BaseModelParams
from .base import BasePatchLaserFrame
from .base import BasePeopleLaserFrame
from .base import BasePhase
from .base import BaseScenario
from .base import ParamsProtocol

__all__.extend(
    [
        "BaseComponent",
        "BaseLaserModel",
        "BaseModelParams",
        "BasePatchLaserFrame",
        "BasePeopleLaserFrame",
        "BasePhase",
        "BaseScenario",
        "ParamsProtocol",
    ]
)

# ----- Utilities (laser.measles.utils) -----
from .utils import StateArray
from .utils import assert_row_vector
from .utils import calc_capacity
from .utils import calc_distances
from .utils import cast_type
from .utils import dual_implementation
from .utils import get_laserframe_properties
from .utils import seed_infections_in_patch
from .utils import seed_infections_randomly
from .utils import select_implementation

__all__.extend(
    [
        "StateArray",
        "assert_row_vector",
        "calc_capacity",
        "calc_distances",
        "cast_type",
        "dual_implementation",
        "get_laserframe_properties",
        "seed_infections_in_patch",
        "seed_infections_randomly",
        "select_implementation",
    ]
)

# ----- Migration (laser.measles.migration) -----
from .migration import get_diffusion_matrix
from .migration import init_gravity_diffusion
from .migration import pairwise_haversine

__all__.extend(["get_diffusion_matrix", "init_gravity_diffusion", "pairwise_haversine"])

# ----- Wrappers (laser.measles.wrapper) -----
from .wrapper import PrettyComponentsList
from .wrapper import PrettyLaserFrameWrapper
from .wrapper import pretty_laserframe
from .wrapper import return_pretty_laserframe
from .wrapper import wrap_laserframe

__all__.extend(
    [
        "PrettyComponentsList",
        "PrettyLaserFrameWrapper",
        "pretty_laserframe",
        "return_pretty_laserframe",
        "wrap_laserframe",
    ]
)

# ----- Model classes -----
from .abm import ABMModel
from .abm import ABMParams
from .abm import BaseABMScenario
from .abm import load_snapshot
from .abm import save_snapshot
from .biweekly import BiweeklyModel
from .biweekly import BiweeklyParams
from .compartmental import CompartmentalModel
from .compartmental import CompartmentalParams

__all__.extend(
    [
        "ABMModel",
        "ABMParams",
        "BaseABMScenario",
        "BiweeklyModel",
        "BiweeklyParams",
        "CompartmentalModel",
        "CompartmentalParams",
        "load_snapshot",
        "save_snapshot",
    ]
)

# ----- Shared base components (laser.measles.components) -----
from .components import *  # noqa: F403
from .components import __all__ as _components_all

__all__.extend(_components_all)

# ----- Demographics -----
from .demographics import WPP
from .demographics import GADMShapefile
from .demographics import RasterPatchGenerator
from .demographics import RasterPatchParams
from .demographics import get_shapefile_dataframe
from .demographics import plot_shapefile_dataframe

__all__.extend(
    [
        "WPP",
        "GADMShapefile",
        "RasterPatchGenerator",
        "RasterPatchParams",
        "get_shapefile_dataframe",
        "plot_shapefile_dataframe",
    ]
)

# ----- Mixing -----
from .mixing import *  # noqa: F403
from .mixing import __all__ as _mixing_all

__all__.extend(_mixing_all)

# ----- Scenario generators -----
from .scenarios import satellites_scenario
from .scenarios import single_patch_scenario
from .scenarios import two_cluster_scenario
from .scenarios import two_patch_scenario

__all__.extend(
    [
        "satellites_scenario",
        "single_patch_scenario",
        "two_cluster_scenario",
        "two_patch_scenario",
    ]
)
