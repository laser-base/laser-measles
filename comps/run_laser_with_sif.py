import os
import sys
from idmtools.assets import AssetCollection
from idmtools.core.platform_factory import Platform
from idmtools.entities import CommandLine
from idmtools.entities.command_task import CommandTask
from idmtools.builders import SimulationBuilder
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations
from laser_task import PyConfiguredSingularityTask as PCST
from idmtools_platform_comps.utils.scheduling import add_schedule_config

def update_parameter_callback(simulation, incubation_duration, base_infectivity, seasonal_multiplier, migration_fraction):
    simulation.task.set_parameter("incubation_duration", incubation_duration)
    simulation.task.set_parameter("base_infectivity", base_infectivity)
    simulation.task.set_parameter("seasonal_multiplier", seasonal_multiplier)
    simulation.task.set_parameter("migration_fraction", migration_fraction)
    ret_tags_dict = {"incubation_duration": incubation_duration, "base_infectivity": base_infectivity, "seasonal_multiplier": seasonal_multiplier, "migration_fraction": migration_fraction }
    return ret_tags_dict 


if __name__ == "__main__":
    here = os.path.dirname(__file__)

    # Create a platform to run the workitem
    platform = Platform("CALCULON", priority="Highest")

    # create commandline input for the task
    #cmdline = "singularity exec ./Assets/laser.sif python3 -m idmlaser.measles"
    cmdline = "singularity exec ./Assets/laser_cholera.sif python3 -m idmlaser_cholera.cholera"
    command = CommandLine(cmdline)
    task = PCST(command=command)

    # Add our image
    task.common_assets.add_assets(AssetCollection.from_id_file("laser_cholera.id"))
    task.common_assets.add_directory('inputs_ew')
    task.common_assets.add_directory('laser_cache')
  
    ts = TemplatedSimulations(base_task=task)

    sb = SimulationBuilder()
    sb.add_multiple_parameter_sweep_definition(
            update_parameter_callback,
            #incubation_duration=[6,7,8],
            incubation_duration=[7],
            #base_infectivity=[3.9,4.0,4.1],
            base_infectivity=[4.0],
            #seasonal_multiplier=[0.55, 0.60, 0.65],
            seasonal_multiplier=[0.60,],
            #migration_fraction=[0.03, 0.04, 0.05]
            migration_fraction=[0.04]
        )
    
    ts.add_builder(sb)
    num_threads = 24
    add_schedule_config(ts, command=cmdline, NumNodes=1, num_cores=num_threads, node_group_name="idm_abcd", Environment={"OMP_NUM_THREADS":str(num_threads)} )
    experiment = Experiment.from_template(ts, name=os.path.split(sys.argv[0])[1])
    experiment.run(wait_until_done=True, scheduling=True)
    if experiment.succeeded:
        experiment.to_id_file("experiment.id")
