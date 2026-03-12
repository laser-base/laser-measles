"""
Main laser-measles script for COMPS.

Runs a compartmental SEIR model on a synthetic 8-patch linear scenario
with a naive (fully susceptible) starting population seeded with 10 infections.

Accepts --beta and --seed as command-line arguments.
Writes output.csv to the working directory (collected by COMPS).
"""

import argparse
import numpy as np
import polars as pl

from laser.measles import create_component
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
from laser.measles.compartmental import components
from laser.measles.compartmental.components import InfectionParams, InfectionSeedingParams


def create_scenario():
    n_patches = 8
    populations = np.array([50_000, 80_000, 120_000, 200_000, 150_000, 100_000, 70_000, 40_000])
    return pl.DataFrame({
        "id":   [f"patch_{i}" for i in range(n_patches)],
        "lat":  np.zeros(n_patches),
        "lon":  np.linspace(0, 7, n_patches),
        "pop":  populations,
        "mcv1": np.zeros(n_patches),
    })


def run(beta: float, seed: int):
    scenario = create_scenario()
    params = CompartmentalParams(
        num_ticks=365 * 3,
        seed=seed,
        show_progress=False,
    )

    model = CompartmentalModel(scenario, params, name="comps_run")
    model.components = [
        create_component(components.InfectionSeedingProcess, params=InfectionSeedingParams(num_infections=10)),
        components.ImportationPressureProcess,
        create_component(components.InfectionProcess, params=InfectionParams(beta=beta, seasonality=0.15)),
        components.VitalDynamicsProcess,
        components.StateTracker,
    ]
    model.run()

    tracker = model.get_instance("StateTracker")[0]
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
