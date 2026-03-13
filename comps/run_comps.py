import argparse
import os
import sys

from idmtools.assets import Asset, AssetCollection
from idmtools.core.platform_factory import Platform
from idmtools.entities import CommandLine
from idmtools.entities.command_task import CommandTask
from idmtools.builders import SimulationBuilder
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations
from idmtools_platform_comps.utils.scheduling import add_schedule_config

# --- fixed parameters ---
SEED = 42
BETA_MIN, BETA_MAX = 0.25, 2.5

NODE_GROUP = "idm_abcd"
NUM_CORES = 8
NUM_THREADS = 8


def make_beta_values(n: int):
    if n <= 1:
        return [0.8]
    return [
        round(BETA_MIN + i * (BETA_MAX - BETA_MIN) / (n - 1), 3)
        for i in range(n)
    ]


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--num-sims", type=int, default=20)
    parser.add_argument("--pop-scale", type=float, default=1.0)
    parser.add_argument("--num-ticks", type=int, default=365 * 3)
    args = parser.parse_args()

    betas = make_beta_values(args.num_sims)

    print(f"Submitting {len(betas)} sims: beta={betas}")

    platform = Platform("CALCULON", priority="AboveNormal", max_workers=1)

    # Base command WITHOUT beta (we will inject per sim)
    base_cmd = (
        "singularity exec ./Assets/laser-measles.sif "
        "python3 ./Assets/main_measles.py "
        f"--seed {SEED} "
        f"--pop-scale {args.pop_scale} "
        f"--num-ticks {args.num_ticks}"
    )

    task = CommandTask(command=CommandLine(base_cmd))

    task.common_assets.add_assets(
        AssetCollection.from_id_file("laser-measles.id")
    )
    task.common_assets.add_asset(
        Asset(absolute_path=os.path.abspath("main_measles.py"))
    )

    ts = TemplatedSimulations(base_task=task)

    # --- scheduling (SLURM schema for CALCULON) ---
    add_schedule_config(
        ts,
        command=base_cmd,
        NodeGroupName=NODE_GROUP,
        NumNodes=1,
        NumProcesses=1,
        NumCores=NUM_CORES,
        Environment={
            "OMP_NUM_THREADS": str(NUM_THREADS),
            "NUMBA_NUM_THREADS": str(NUM_THREADS),
            "OMP_PLACES": "cores",
            "OMP_PROC_BIND": "close",
        },
    )

    # Sweep only modifies task.command (no WorkOrder hacking)
    def set_beta(simulation, beta):
        cmd = base_cmd + f" --beta {beta}"
        simulation.task.command = CommandLine(cmd)
        return {"beta": beta}

    sb = SimulationBuilder()
    sb.add_sweep_definition(set_beta, betas)
    ts.add_builder(sb)

    experiment = Experiment.from_template(
        ts,
        name="laser_measles_beta_sweep",
        tags={"model": "laser-measles"},
    )

    with platform:
        experiment.run(wait_until_done=True, scheduling=True)

    if experiment.succeeded:
        experiment.to_id_file("experiment.id")
        print("Experiment succeeded.")
    else:
        print("Experiment failed.")
        sys.exit(1)
