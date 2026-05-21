"""Tests for spatial migration of disease through the network mixing matrix.

Each test sets up a 5x5 grid of patches with the following mixing topology:

    * 4-neighbour adjacency coupling for the "interior" cells.
    * Row override: 100% of contagion from cell (0,0) is routed to cell (4,4).
    * Row override: cell (4,4) keeps all contagion internally (no leaks).
    * Seed infections are placed only in cell (0,0).

If the network math routes contagion correctly, no patch other than (4,4)
should ever see a new infection. Patch (0,0) starts with seeded cases, but
its row M[0,:] sends contagion exclusively to (4,4), so no internal
transmission happens there either — the susceptible count in (0,0) should
stay at ``initial_pop - SEEDED_INFECTIONS`` for the entire run.

Failure of any of these assertions would indicate a regression in how the
mixing matrix is applied to the force-of-infection computation, or in
patch_id bookkeeping during transmission.
"""

import importlib

import numpy as np
import polars as pl
import pytest

import laser.measles as lm
from laser.measles import MEASLES_MODULES
from laser.measles.mixing.base import BaseMixing

# Per-module override for ``num_ticks``; modules not listed use the default.
_DEFAULT_NUM_TICKS = 365
_MODULE_NUM_TICKS = {
    "laser.measles.biweekly": 52,
}

GRID_ROWS = 5
GRID_COLS = 5
GRID_POP = 10_000
ADJACENT_PROB = 0.1
SEEDED_INFECTIONS = 100
SEED = 42


def _grid_index(r: int, c: int) -> int:
    """Flatten a (row, col) grid coordinate to a scenario row index."""
    return r * GRID_COLS + c


def make_grid_scenario(pop: int = GRID_POP) -> pl.DataFrame:
    """Build a 5x5 grid scenario DataFrame with equal per-patch populations.

    Patch ids are formatted as ``"r_c"`` so (0,0) → ``"0_0"`` and (4,4) → ``"4_4"``.
    """
    rows = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            rows.append({"id": f"{r}_{c}", "pop": pop, "lat": float(r), "lon": float(c), "mcv1": 0.0})
    return pl.DataFrame(
        rows,
        schema={"id": pl.Utf8, "pop": pl.Int64, "lat": pl.Float64, "lon": pl.Float64, "mcv1": pl.Float64},
    )


def make_adjacency_mixing_matrix(p: float = ADJACENT_PROB) -> np.ndarray:
    """Build a 25x25 4-neighbour adjacency mixing matrix.

    Each cell gets off-diagonal weight ``p`` to each of its (up to four) grid
    neighbours and self-weight ``1 - p * n_neighbours`` so every row sums to 1.

    Returns:
        np.ndarray: 25x25 mixing matrix.
    """
    n = GRID_ROWS * GRID_COLS
    M = np.zeros((n, n), dtype=np.float64)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            i = _grid_index(r, c)
            neighbours = []
            if r > 0:
                neighbours.append(_grid_index(r - 1, c))
            if r < GRID_ROWS - 1:
                neighbours.append(_grid_index(r + 1, c))
            if c > 0:
                neighbours.append(_grid_index(r, c - 1))
            if c < GRID_COLS - 1:
                neighbours.append(_grid_index(r, c + 1))
            for j in neighbours:
                M[i, j] = p
            M[i, i] = 1.0 - p * len(neighbours)
    return M


def make_routing_mixing_matrix(p: float = ADJACENT_PROB) -> np.ndarray:
    """Build a 25x25 mixing matrix encoding the test routing topology.

    Starts from a 4-neighbour adjacency mixing matrix, then overrides:

    * Row 0 (cell (0,0)): all probability mass on column 24 (cell (4,4)).
    * Row 24 (cell (4,4)): identity row — all probability mass on the diagonal.

    Returns:
        np.ndarray: 25x25 mixing matrix.
    """
    M = make_adjacency_mixing_matrix(p)

    i00 = _grid_index(0, 0)
    i44 = _grid_index(GRID_ROWS - 1, GRID_COLS - 1)

    # Override row (0,0): send 100% of contagion to (4,4).
    M[i00, :] = 0.0
    M[i00, i44] = 1.0

    # Override row (4,4): keep all contagion internal (identity row).
    M[i44, :] = 0.0
    M[i44, i44] = 1.0

    return M


class _FixedMatrixMixing(BaseMixing):
    """BaseMixing subclass that exposes a pre-computed mixing matrix.

    Bypasses the gravity-style migration_matrix -> mixing_matrix derivation so
    the test directly controls the routing of contagion between patches.
    """

    def __init__(self, matrix: np.ndarray):
        # Skip BaseMixing.__init__ since we don't need a scenario or params
        # at construction time; the model sets scenario via the property
        # setter inherited from BaseMixing.
        self._scenario = None
        self.params = None
        self._migration_matrix = matrix
        self._mixing_matrix = matrix

    def get_migration_matrix(self) -> np.ndarray:
        return self._migration_matrix


def _build_transmission_components(MeaslesModel, mixer):
    """Build the seeding + infection components list for a given model."""
    return [
        lm.create_component(
            MeaslesModel.components.InfectionSeedingProcess,
            MeaslesModel.components.InfectionSeedingParams(
                target_patches=["0_0"],
                infections_per_patch=SEEDED_INFECTIONS,
                use_largest_patch=False,
            ),
        ),
        lm.create_component(
            MeaslesModel.components.InfectionProcess,
            MeaslesModel.components.InfectionParams(beta=2.0, seasonality=0.0, mixer=mixer),
        ),
    ]


def _assert_all_patches_have_new_infections(
    states_S: np.ndarray,
    initial_pop: int,
) -> None:
    """Verify that every patch's susceptible count dropped from ``initial_pop``.

    With pure adjacency mixing and a single seed, after a long enough simulation
    contagion should have propagated to every node in the grid (each node will
    have S strictly less than ``initial_pop``).

    Args:
        states_S: per-patch susceptible counts at end of simulation.
        initial_pop: equal initial population per patch.
    """
    untouched = [int(i) for i in np.where(states_S >= initial_pop)[0]]
    assert len(untouched) == 0, (
        f"Expected contagion to reach every patch but {len(untouched)} patches still have "
        f"S >= initial_pop ({initial_pop}): patch indices {untouched}; S values per patch: "
        f"{[int(s) for s in states_S]}"
    )


def _assert_only_sink_patch_has_new_infections(
    states_S: np.ndarray,
    initial_pop: int,
    seeded: int,
    seeded_patch: int,
    sink_patch: int,
) -> None:
    """Verify post-simulation S counts match the routing-only expectation.

    The sink patch (cell (4,4)) is the only patch allowed to lose susceptibles;
    the seeded patch (cell (0,0)) must have lost exactly ``seeded`` susceptibles
    to seeding (no new infections); every other patch must retain its initial
    susceptible count exactly.

    Args:
        states_S: per-patch susceptible counts at end of simulation.
        initial_pop: equal initial population per patch.
        seeded: number of infections seeded into ``seeded_patch``.
        seeded_patch: flat index of cell (0,0).
        sink_patch: flat index of cell (4,4).
    """
    for i in range(len(states_S)):
        if i == sink_patch:
            assert states_S[i] < initial_pop, (
                f"Sink patch (4,4) idx={i}: expected S < {initial_pop} after transmission, got S={int(states_S[i])}"
            )
        elif i == seeded_patch:
            assert states_S[i] == initial_pop - seeded, (
                f"Seeded patch (0,0) idx={i}: expected S=={initial_pop - seeded} (seeded only, no new infections), got S={int(states_S[i])}"
            )
        else:
            assert states_S[i] == initial_pop, (
                f"Patch idx={i}: expected S=={initial_pop} (no contagion should reach this patch), "
                f"got S={int(states_S[i])} — indicates stray transmission outside the routed (4,4) sink"
            )


@pytest.mark.slow
@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_network_routing(measles_module):
    """Given a 5x5 patch grid with all contagion from (0,0) routed to (4,4) and
    no contagion leaving (4,4), when the model runs with seed infections only
    in (0,0), then only (4,4) sees new infections.

    Failure here would indicate a regression in how the model's transmission
    component applies the mixing matrix to compute the per-patch force of
    infection (or, for ABM, in patch_id bookkeeping during transmission).
    """
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(make_grid_scenario())
    mixer = _FixedMatrixMixing(make_routing_mixing_matrix())

    params = MeaslesModel.Params(num_ticks=_MODULE_NUM_TICKS.get(measles_module, _DEFAULT_NUM_TICKS), seed=SEED, verbose=False)
    model = MeaslesModel.Model(scenario, params)
    model.components = _build_transmission_components(MeaslesModel, mixer)
    model.run()

    _assert_only_sink_patch_has_new_infections(
        states_S=np.asarray(model.patches.states.S),
        initial_pop=GRID_POP,
        seeded=SEEDED_INFECTIONS,
        seeded_patch=_grid_index(0, 0),
        sink_patch=_grid_index(GRID_ROWS - 1, GRID_COLS - 1),
    )


@pytest.mark.slow
@pytest.mark.parametrize("measles_module", MEASLES_MODULES)
def test_normal_spread(measles_module):
    """Given a 5x5 patch grid with pure 4-neighbour adjacency mixing (no routing
    overrides), when the model runs long enough with seed infections in (0,0),
    then contagion spreads to every patch in the grid.

    Counterpart to ``test_network_routing``: removes the row overrides so the
    wave is free to propagate outward through the adjacency network. Failure
    here would indicate a regression in normal multi-patch transmission via
    the mixing matrix.
    """
    MeaslesModel = importlib.import_module(measles_module)
    scenario = MeaslesModel.BaseScenario(make_grid_scenario())
    mixer = _FixedMatrixMixing(make_adjacency_mixing_matrix())

    params = MeaslesModel.Params(num_ticks=_MODULE_NUM_TICKS.get(measles_module, _DEFAULT_NUM_TICKS), seed=SEED, verbose=False)
    model = MeaslesModel.Model(scenario, params)
    model.components = _build_transmission_components(MeaslesModel, mixer)
    model.run()

    _assert_all_patches_have_new_infections(
        states_S=np.asarray(model.patches.states.S),
        initial_pop=GRID_POP,
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
