# laser-measles

[![PyPI Package latest release](https://img.shields.io/pypi/v/laser-measles.svg)](https://pypi.org/project/laser-measles/)
[![MIT License](https://img.shields.io/github/license/InstituteforDiseaseModeling/laser-measles.svg)](https://github.com/InstituteforDiseaseModeling/laser-measles/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/laser-measles/badge/?style=flat)](https://laser-measles.readthedocs.io/en/latest/)
[![Coverage Status](https://codecov.io/gh/InstituteforDiseaseModeling/laser-measles/graph/badge.svg?branch=main)](https://app.codecov.io/github/InstituteforDiseaseModeling/laser-measles)

laser-measles is a spatial epidemiological modeling toolkit that helps researchers and public health teams simulate measles transmission, evaluate vaccination strategies, and plan outbreak responses. It translates surveillance data and demographic information into projections that inform immunization planning and resource allocation — with a focus on settings where measles remains a leading cause of vaccine-preventable death.

Developed by the [Institute for Disease Modeling](https://idmod.org) (IDM) at the Bill & Melinda Gates Foundation, laser-measles is built on the open-source [LASER framework](https://github.com/InstituteforDiseaseModeling/laser).

## Installation

```bash
pip install laser-measles
```

**Recommended stable release: version 0.10** — the current validated and supported version:

```bash
pip install "laser-measles>=0.10,<1.0"
```

For development installation:

```bash
pip install -e ".[dev]"
```

## Getting started

The recommended first example is the [Quick Start Tutorial](https://institutefordiseasemodeling.github.io/laser-measles/tutorials/tut_quickstart_hello_world/).

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

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and submission guidelines.

Bug reports and feature requests can be filed on the [GitHub issue tracker](https://github.com/InstituteforDiseaseModeling/laser-measles/issues).

## License

MIT License — Copyright (c) 2024, Bill & Melinda Gates Foundation
