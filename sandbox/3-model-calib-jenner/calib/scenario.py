# calib/scenario.py
from __future__ import annotations

from typing import Dict, Tuple, List
import numpy as np
import polars as pl


def node_id(i: int, j: int) -> str:
    return f"n_{i}_{j}"


def build_grid_nodes() -> List[Tuple[int, int]]:
    return [(i, j) for j in range(5) for i in range(5)]


def assign_region(i: int, j: int) -> str:
    # 5 regions: metro cross + 4 quadrants
    if i == 2 or j == 2:
        return "R0_metro"
    if i < 2 and j < 2:
        return "R1_nw"
    if i > 2 and j < 2:
        return "R2_ne"
    if i < 2 and j > 2:
        return "R3_sw"
    return "R4_se"


def build_population_map() -> Dict[str, int]:
    # Total ~1,000,000: scaled from original 7.44M to keep geometry identical.
    # metro center 160k, inner cross 87k ×4, outer cross 47k ×4,
    # medium quadrant 27k ×8, small quadrant 11k ×8 → sum = 1,000,000
    pops: Dict[str, int] = {}
    for i, j in build_grid_nodes():
        nid = node_id(i, j)

        # Metro cross
        if i == 2 and j == 2:
            pops[nid] = 160_000
        elif (i == 2 and j in (1, 3)) or (j == 2 and i in (1, 3)):
            pops[nid] = 87_000
        elif (i == 2 and j in (0, 4)) or (j == 2 and i in (0, 4)):
            pops[nid] = 47_000
        else:
            # Quadrants: checkerboard medium/small to break symmetry
            pops[nid] = 27_000 if ((i + j) % 2 == 0) else 11_000

    return pops


def coverage_map(i: int, j: int) -> float:
    """
    RI map (mcv1) — gradient + pockets.
    """
    # pockets
    if (i, j) in [(4, 0), (0, 4), (4, 4)]:
        return 0.80

    v0 = 0.92
    g = 0.03
    return float(np.clip(v0 + g * ((i - 2) / 2.0), 0.0, 1.0))


def build_scenario() -> tuple[pl.DataFrame, Dict[str, str]]:
    pops = build_population_map()

    rows = []
    region_of: Dict[str, str] = {}

    for i, j in build_grid_nodes():
        nid = node_id(i, j)
        reg = assign_region(i, j)
        mcv1 = coverage_map(i, j)

        region_of[nid] = reg
        rows.append(
            {
                "id": nid,
                # Use lat/lon purely as geometry in “grid units”
                "lat": float(j),
                "lon": float(i),
                "pop": int(pops[nid]),
                "mcv1": float(mcv1),
            }
        )

    return pl.DataFrame(rows), region_of