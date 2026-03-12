"""
COMPS submission script for laser-measles beta (R0) parameter sweep.

Prerequisites:
    1. Build the Docker image and SIF:
           docker build -t laser-measles .
           singularity build laser-measles.sif docker-daemon://laser-measles:latest

    2. Copy assets and create an AssetCollection (requires python3.11 + COMPS auth):
           cp main_measles.py assets/
           cp laser-measles.sif assets/
           python3.11 -m COMPS create_asset_collection assets --name laser-measles-assets
       This prints an AC UUID. Write it to laser-measles.id:
           echo "<uuid>" > laser-measles.id

    3. Run this script:
           python3.11 run_comps.py
       Outputs: experiment.id (used by retrieve_outputs.py)
"""

import os
import sys

from idmtools.assets import AssetCollection
from idmtools.core.platform_factory import Platform
from idmtools.entities import CommandLine
from idmtools.entities.command_task import CommandTask
from idmtools.builders import SimulationBuilder
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations

# --- sweep values ---
# beta ≈ R0 / (inf_mu) where inf_mu=8 days → R0 = beta * 8
# R0=3 → beta≈0.375, R0=5 → beta≈0.625, R0=8 → beta≈1.0, R0=12 → beta≈1.5, R0=16 → beta≈2.0
BETA_VALUES = [0.375, 0.625, 1.0, 1.5, 2.0]
SEED = 42


def set_beta(simulation, beta):
    cmd = f"singularity exec ./Assets/laser-measles.sif python3 ./Assets/main_measles.py --beta {beta} --seed {SEED}"
    simulation.task.command = CommandLine(cmd)
    return {"beta": beta, "seed": SEED}


if __name__ == "__main__":
    platform = Platform("CALCULON")

    # Base task — command will be overridden per simulation by set_beta
    base_cmd = f"singularity exec ./Assets/laser-measles.sif python3 ./Assets/main_measles.py --beta 0.8 --seed {SEED}"
    task = CommandTask(command=CommandLine(base_cmd))

    # SIF + script as shared assets (from laser-measles.id created by createac)
    task.common_assets.add_assets(AssetCollection.from_id_file("laser-measles.id"))

    ts = TemplatedSimulations(base_task=task)
    sb = SimulationBuilder()
    sb.add_sweep_definition(set_beta, BETA_VALUES)
    ts.add_builder(sb)

    experiment = Experiment.from_template(ts, name=os.path.split(sys.argv[0])[1], tags={"model": "laser-measles", "sweep": "beta"})
    experiment.run(wait_until_done=True)
    if experiment.succeeded:
        experiment.to_id_file("experiment.id")
        print(f"Experiment succeeded. ID saved to experiment.id")
    else:
        print("Experiment failed or partially failed.")
        sys.exit(1)
