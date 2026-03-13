"""
Main laser-measles script for COMPS.

Runs an ABM SEIR model on a synthetic 10-patch scenario with a naive starting
population seeded with 10 infections in the largest patch.

Arguments:
  --beta        Transmission rate (default 0.8)
  --seed        RNG seed (default 42)
  --pop-scale   Scale factor applied to all patch populations (default 1.0,
                i.e. ~1.2M total). Use e.g. 0.1 for ~120k for quick tests.
  --num-ticks   Simulation length in days (default 1095 = 3 years)

Writes output.csv to the working directory (collected by COMPS).
run_comps.py sets OMP_NUM_THREADS / NUMBA_NUM_THREADS via add_schedule_config.
"""

import argparse
import os
import time
import numpy as np
import polars as pl

from laser.measles.abm import ABMModel, ABMParams, components
from laser.measles.components import create_component


def create_scenario(pop_scale: float = 1.0):
    # 10 patches: 1 large metro, 3 medium cities, 6 small towns — total ~1.2M at scale=1.0
    base_populations = np.array([400_000, 150_000, 120_000, 100_000, 80_000,
                                  70_000, 60_000, 80_000, 90_000, 50_000])
    populations = np.maximum(1, (base_populations * pop_scale).astype(int))
    n_patches = len(populations)
    return pl.DataFrame({
        "id":   [f"patch_{i}" for i in range(n_patches)],
        "lat":  np.linspace(0, 3, n_patches),
        "lon":  np.linspace(0, 9, n_patches),
        "pop":  populations,
        "mcv1": np.zeros(n_patches),
    })


def run(beta: float, seed: int, pop_scale: float = 1.0, num_ticks: int = 365 * 3):
    scenario = create_scenario(pop_scale=pop_scale)
    total_pop = scenario["pop"].sum()
    t_start = time.time()
    print(f"Starting: beta={beta}, seed={seed}, pop={total_pop:,}, ticks={num_ticks}", flush=True)
    params = ABMParams(
        num_ticks=num_ticks,
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

    t_built = time.time()
    print(f"  model built in {t_built - t_start:.1f}s", flush=True)

    model.run()

    t_ran = time.time()
    print(f"  model.run() took {t_ran - t_built:.1f}s", flush=True)

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
    print(f"Done. beta={beta}, seed={seed}. Peak I={int(tracker.I.max())}. Total={time.time()-t_start:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--beta", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pop-scale", type=float, default=1.0,
                        help="Scale factor for patch populations (default 1.0 = ~1.2M total)")
    parser.add_argument("--num-ticks", type=int, default=365 * 3,
                        help="Simulation length in days (default 1095 = 3 years)")
    args = parser.parse_args()
    run(beta=args.beta, seed=args.seed, pop_scale=args.pop_scale, num_ticks=args.num_ticks)
