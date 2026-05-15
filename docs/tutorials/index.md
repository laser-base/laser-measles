# Tutorials

These tutorials walk you through laser-measles step by step, from your first simulation to full vaccination modeling. All tutorials run in under one minute on a standard laptop — no cloud compute, GPU, or HPC cluster required.

!!! note "Hardware requirements"
    Every tutorial is designed to run on a standard laptop or desktop with 4 GB of RAM and a modern Python installation (3.10+). If you are working in a setting with limited internet access, install laser-measles and its example dependencies while connected, then run tutorials offline.

## Quick start

New to laser-measles? Start here. This single example walks through a complete
spatial ABM from scenario construction to visualization.

- [Quick start: Hello world](tut_quickstart_hello_world.py)

## Beginning tutorials

These tutorials cover the fundamentals of building and running models. They introduce the three model types, the scenario format, and the component system.

- [Basic model](tut_basic_model.py) — build your first compartmental model
- [Model structure](tut_model_structure.py) — understand model internals and data flow
- [ABM introduction](tut_abm_intro.py) — switch to agent-based modeling
- [Scenarios](tut_scenarios.py) — construct scenario DataFrames from geographic data

## Feature tutorials

These tutorials highlight specific features of the library. Each one focuses on a single capability that you can combine with others.

- [Random numbers](tut_random_numbers.py) — reproducible stochastic simulations
- [Creating a component](tut_creating_component.py) — write a custom process or tracker ([how-to guide](../user-guide/components/custom-component.md))
- [ABM vital dynamics](tut_abm_vital_dynamics.py) — births, deaths, and aging in agent-based models
- [Spatial mixing](tut_spatial_mixing.py) — model disease spread between patches ([concepts](../user-guide/model-types/spatial-mixing.md))
- [Pydantic component parameters](tut_pydantic_component_parameters.py) — validated configuration with Pydantic
- [State arrays](tut_state_arrays.py) — efficient array operations on agent properties

## End-to-end tutorials

These tutorials combine multiple features into realistic analysis workflows.

- [Vaccination](tut_vaccination.py) — model supplementary immunization activities and evaluate campaign impact

## Next steps

After completing the tutorials, explore these resources:

- [Model types](../user-guide/model-types/index.md) — explanation of the three model types and their trade-offs
- [Choosing a model type](../user-guide/model-types/choosing-a-model.md) — decision guide for selecting the right model
- [Components](../user-guide/components/index.md) — how the component system works
- [Worked examples](../user-guide/components/worked-examples.md) — copy-paste runnable scripts for all three models
- [API reference](../reference/laser/measles/index.md) — full details on all classes and functions

## AI assistance

For those within IDM you can use our custom GPT [Laser-GPT Jenner](https://chatgpt.com/g/g-674f5fd33aec8191bcdc1a2736fb7c8d-laser-gpt-jenner)
to get help with `laser-core`.
