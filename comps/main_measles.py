"""
Main laser-measles script for COMPS.

Runs an ABM SEIR model on a synthetic 10-patch scenario (1.2M population,
heterogeneous patch sizes) with a naive starting population seeded with 10
infections in the largest patch.

Accepts --beta and --seed as command-line arguments.
Writes output.csv to the working directory (collected by COMPS).
"""

import os
import shutil

# Copy the pre-compiled numba cache from the read-only SIF to /tmp so numba
# can both read and write it, avoiding ~24-minute JIT recompilation per sim.
_cache_src = "/app/.numba_cache"
_cache_dst = "/tmp/.numba_cache"
if os.path.exists(_cache_src):
    shutil.copytree(_cache_src, _cache_dst, dirs_exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = _cache_dst

import argparse
import numpy as np
import polars as pl

from laser.measles.abm import ABMModel, ABMParams, components
from laser.measles.components import create_component


def create_scenario():
    # 10 patches: 1 large metro, 3 medium cities, 6 small towns — total 1.2M
    populations = np.array([400_000, 150_000, 120_000, 100_000, 80_000,
                             70_000, 60_000, 80_000, 90_000, 50_000])
    n_patches = len(populations)
    return pl.DataFrame({
        "id":   [f"patch_{i}" for i in range(n_patches)],
        "lat":  np.linspace(0, 3, n_patches),
        "lon":  np.linspace(0, 9, n_patches),
        "pop":  populations,
        "mcv1": np.zeros(n_patches),
    })


def run(beta: float, seed: int):
    scenario = create_scenario()
    params = ABMParams(
        num_ticks=365 * 3,
        seed=seed,
        show_progress=False,
        use_numba=True,
    )

    model = ABMModel(scenario=scenario, params=params, name="comps_abm")

    # R0=1.0 → fully susceptible naive population with correct patch_id assignment
    model.add_component(
        create_component(
            components.InitializeEquilibriumStatesProcess,
            components.InitializeEquilibriumStatesParams(R0=1.0),
        )
    )
    model.add_component(
        create_component(
            components.VitalDynamicsProcess,
            components.VitalDynamicsParams(crude_birth_rate=30.0, crude_death_rate=30.0),
        )
    )
    model.add_component(
        create_component(
            components.InfectionSeedingProcess,
            components.InfectionSeedingParams(num_infections=10, use_largest_patch=True),
        )
    )
    model.add_component(
        create_component(
            components.ImportationPressureProcess,
            components.ImportationPressureParams(crude_importation_rate=0.05),
        )
    )
    model.add_component(
        create_component(
            components.InfectionProcess,
            components.InfectionParams(beta=beta, seasonality=0.15),
        )
    )
    model.add_component(
        create_component(
            components.StateTracker,
            components.StateTrackerParams(aggregation_level=-1),  # global totals
        )
    )

    model.run()

    tracker = model.get_instance(components.StateTracker)[0]
    ticks = np.arange(params.num_ticks)
    df = pl.DataFrame({
        "tick":  ticks,
        "S":     tracker.S.astype(int),
        "E":     tracker.E.astype(int),
        "I":     tracker.I.astype(int),
        "R":     tracker.R.astype(int),
        "beta":  np.full(params.num_ticks, beta),
        "seed":  np.full(params.num_ticks, seed, dtype=int),
    })
    df.write_csv("output.csv")
    print(f"Done. beta={beta}, seed={seed}. Peak I={int(tracker.I.max())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--beta", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(beta=args.beta, seed=args.seed)
