# laser-measles

[![PyPI Package latest release](https://img.shields.io/pypi/v/laser-measles.svg)](https://pypi.org/project/laser-measles/)
[![MIT License](https://img.shields.io/github/license/laser-base/laser-measles.svg)](https://github.com/laser-base/laser-measles/blob/main/LICENSE)
[![Documentation Status](https://github.com/laser-base/laser-measles/actions/workflows/github-actions.yml/badge.svg)](https://laser.idmod.org/laser-measles/)

laser-measles is a spatial epidemiological modeling toolkit that helps researchers and public health teams simulate measles transmission, evaluate vaccination strategies, and plan outbreak responses. It translates surveillance data and demographic information into projections that inform immunization planning and resource allocation — with a focus on settings where measles remains a leading cause of vaccine-preventable death.

Developed by the [Institute for Disease Modeling](https://idmod.org) (IDM) at the Gates Foundation, laser-measles is built on the open-source [LASER framework](https://github.com/laser-base).

## Installation

```bash
pip install laser-measles
```

**Recommended stable release: version 0.13** — the current validated and supported version:

```bash
pip install "laser-measles>=0.13,<1.0"
```

For development installation:

```bash
pip install -e ".[dev]"
```

## Getting started

The recommended first example is the [Quick Start Tutorial](https://laser.idmod.org/laser-measles/tutorials/tut_quickstart_hello_world/).

## Model types

laser-measles provides three modeling approaches:

- **ABM (Agent-Based Model)**: Individual-level simulation with stochastic agents and daily timesteps. Best for detailed heterogeneity and contact structure.
- **Biweekly Compartmental Model**: Population-level SIR dynamics with 2-week timesteps. Recommended for scenario building and policy analysis.
- **Compartmental Model**: Population-level SEIR dynamics with daily timesteps. Recommended for parameter estimation and outbreak modeling.

```python
from laser.measles.abm import ABMModel, ABMParams

params = ABMParams(num_ticks=365, seed=42, start_time="2000-01")
model = ABMModel(scenario, params)
model.run()
```

## Documentation

Full documentation is available at [laser.idmod.org/laser-measles](https://laser.idmod.org/laser-measles/).

## AI-assisted code generation & ChatBot (Jenner)

`jenner-measles-mcp` is a Model Context Protocol (MCP) server that lets Claude and other MCP-compatible tools search the laser-measles documentation and generate model code from natural-language prompts. See [InstituteforDiseaseModeling/laser-mcp](https://github.com/InstituteforDiseaseModeling/laser-mcp) for setup, supported clients, and the deployed endpoint.

Foundation employees can use JENNER-Measles-GPT [here](https://chatgpt.com/g/g-678ae681f5b48191b3e91619e649e598-jenner-measles).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and submission guidelines.

Bug reports and feature requests can be filed on the [GitHub issue tracker](https://github.com/laser-base/laser-measles/issues).

## License

MIT License — Copyright (c) 2026, Gates Foundation
