# Welcome to laser-measles

laser-measles is a spatial epidemiological modeling toolkit that helps answer critical questions about measles transmission, vaccination strategy, and outbreak response. It enables researchers and public health teams to simulate how measles spreads across communities, evaluate the impact of immunization campaigns, and identify where susceptible populations are most at risk.

Measles remains one of the leading causes of vaccine-preventable death worldwide, disproportionately affecting children in low- and middle-income countries. Modeling tools like laser-measles support evidence-based decision-making by translating surveillance data and demographic information into actionable projections that inform vaccination planning, resource allocation, and outbreak preparedness.

laser-measles is developed and maintained by the [Institute for Disease Modeling](https://idmod.org) (IDM) at the Gates Foundation. It is built on the [LASER framework](https://github.com/laser-base), an open-source platform for large-scale agent-based and compartmental simulation.

---

## What questions can laser-measles help answer?

- **Where are children most vulnerable?** Identify subnational regions with low vaccination coverage and high transmission risk.
- **How effective is a planned campaign?** Simulate supplementary immunization activities (SIAs) and estimate their impact on outbreak probability.
- **What happens if routine coverage drops?** Project the accumulation of susceptible children over time and the resulting outbreak risk.
- **How does disease spread between communities?** Model spatial transmission driven by population movement and geographic connectivity.

---

## Getting started

Install laser-measles using pip (requires Python 3.10+):

```bash
pip install laser-measles
```

**Recommended stable release: version 0.10**

New users should install the latest 0.10.x release, which is the current stable version:

```bash
pip install "laser-measles>=0.10,<1.0"
```

Our recommended first example is the [Quick Start Tutorial](tutorials/tut_quickstart_hello_world.py).

## AI-powered on-ramp: JENNER-MEASLES

The fastest way to get started with laser-measles is through [JENNER-MEASLES](https://chatgpt.com/g/g-678ae681f5b48191b3e91619e649e598-jenner-measles), a chat-based AI assistant purpose-built for this framework.

JENNER-MEASLES can help you:

- Understand the modeling framework and architecture
- Walk through tutorials and examples interactively
- Debug your model configurations and code
- Explore epidemiological scenarios and parameter choices

!!! note

    JENNER-MEASLES is currently pinned to **version 0.9.4** of laser-measles. If you are using a newer version, some details may differ.

Access requires a ChatGPT account and IDM organization access. If you have access, this is the recommended on-ramp before diving into the documentation or source code.

## MCP server for Claude Code users

If you use Claude Code (or any MCP-compatible AI assistant), you can connect it directly to laser-measles and laser-core documentation and source via a local MCP server.

See the [laser-mcp README](https://github.com/InstituteforDiseaseModeling/laser-mcp/blob/main/README.md) for setup instructions (requires organization access).

This gives Claude Code (and similar tools) deep, up-to-date context about laser-measles and laser-core — making it an excellent alternative to JENNER-MEASLES for developers who prefer working in their local environment with their own AI tooling.

## What to expect: Performance and compute

All tutorials and examples included in this repository are designed to run in **under one minute on a standard laptop or desktop computer**. No special compute resources, cloud instances, or GPU hardware are required to get started.

Special compute becomes relevant only when you move to:

- **Calibration workflows**: Fitting model parameters to data using optimization or MCMC methods
- **Large-scale parameter sweeps**: Exploring wide parameter spaces across many simulation runs

For day-to-day exploration, scenario building, and learning the framework, your local machine is all you need.

## Model types

laser-measles provides three modeling approaches, all sharing the same [component system](user-guide/components/index.md) and [scenario format](user-guide/model-types/demographics.md):

- **ABM (Agent-based model)**: Individual-level simulation with stochastic agents. Best for detailed heterogeneity and contact structure. Supports [snapshotting](user-guide/snapshotting/index.md) for long runs.
- **Biweekly compartmental model**: Population-level SIR dynamics with 2-week timesteps. Recommended for scenario building and policy analysis.
- **Compartmental model**: Population-level SEIR dynamics with daily timesteps. Recommended for parameter estimation and outbreak modeling. Supports [snapshotting](user-guide/snapshotting/index.md).

Not sure which model to use? See [Choosing a model type](user-guide/model-types/choosing-a-model.md) or start with the [model types overview](user-guide/model-types/index.md).

## Contributing

Contributions are welcome. Please see the [contributing guide](contributing.md) for development guidelines, including how to write tests, follow code style conventions, and submit pull requests.

Bug reports and feature requests can be filed on the [GitHub issue tracker](https://github.com/laser-base/laser-measles/issues).

<div class="grid cards" markdown>

-   :simple-jupyter:{ .lg .middle } __Tutorials__

    ---

    An interactive tour of key features.

    [:octicons-arrow-right-24: Tutorials](tutorials/index.md)

-   :simple-jupyter:{ .lg .middle } __User guide__

    ---

    Overview of key features and how to use them.

    [:octicons-arrow-right-24: User guide](user-guide/index.md)

-   :material-api:{ .lg .middle } __Reference__

    ---

    Full details on all classes and functions.

    [:octicons-arrow-right-24: API reference](reference/laser/measles/index.md)

-   :material-new-box:{ .lg .middle } __What's new__

    See what's in the latest releases.

    [:octicons-arrow-right-24: What's new](whatsnew.md)

</div>
