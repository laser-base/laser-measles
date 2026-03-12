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
# beta ≈ R0 / inf_mu where inf_mu=8 days → R0 = beta * 8
# Range: R0 ≈ 2 (beta=0.25) to R0 ≈ 20 (beta=2.5), 20 evenly-spaced values
BETA_VALUES = [round(v, 3) for v in [0.25 + i * (2.25 / 19) for i in range(20)]]
SEED = 42


def set_beta(simulation, beta):
    cmd = f"singularity exec ./Assets/laser-measles.sif python3 ./Assets/main_measles.py --beta {beta} --seed {SEED}"
    simulation.task.command = CommandLine(cmd)
    return {"beta": beta, "seed": SEED}


if __name__ == "__main__":
    platform = Platform("CALCULON", priority="AboveNormal")

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
