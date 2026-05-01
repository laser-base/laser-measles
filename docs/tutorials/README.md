# Tutorials

Welcome! This folder contains the source files for the **laser-measles** tutorial series — a hands-on guide to building spatially-explicit measles models with [laser-measles](https://github.com/laser-base/laser-measles).

> **Note for contributors**: The `.py` files here are the canonical source. Jupyter notebooks (`.ipynb`) are generated from them by the doc build pipeline and are not tracked in the repository. If you're looking for executable notebooks, see the [rendered documentation](https://laser-base.github.io/laser-measles/).

---

## What you can learn

### Quick start

**Hello world** — The fastest path to a running spatial ABM. Covers building an 8-patch scenario with heterogeneous populations, seeding an outbreak, configuring gravity-based spatial mixing, and plotting the resulting epidemic curves across patches. If you're new to laser-measles, start here.

### Getting started

**Basic model** — The full model lifecycle from first principles: scenario setup, parameter configuration, assembling components, running the simulation, and visualizing results. Covers both ABM and compartmental model variants side by side.

**Model structure** — How models run under the hood. Explains the tick loop, the `LaserFrame` data structures that hold population state, and how the ABM and compartmental architectures differ in their internal representations.

**ABM introduction** — ABM-specific setup in depth: initializing an agent population, understanding `LaserFrame` capacity (how many agents to pre-allocate and why it matters), and the per-agent data layout.

**Scenarios** — Building real-world geographic scenarios from scratch. Covers downloading shapefiles, estimating patch populations from WorldPop raster data, and subdividing regions into roughly equal-area patches. Uses Ethiopia as a worked example (supporting data in `ETH/`).

### Features in depth

**Creating a component** — How to write a custom simulation component and wire it into a model. Illustrated by building a PIRI (Periodic Intensification of Routine Immunization) process for the compartmental model.

**ABM vital dynamics** — Options for births, deaths, and age structure in the ABM: the simple constant-population process, age-structured demographics, and the WPP-based process that ingests real United Nations demographic data.

**Spatial mixing models** — Configuring and comparing the four built-in spatial mixing models: gravity, radiation, competing destinations, and Stouffer. Shows how mixing model choice shapes spatial transmission dynamics.

**Parameter validation with Pydantic** — Defining component parameters using Pydantic `BaseModel`: type checking, range constraints, default values, and auto-generated documentation — and why this is preferable to plain dictionaries.

**State arrays** — `StateArray`, the data structure that backs compartmental state tracking. Covers reading and writing compartmental counts, slicing by patch or state, and integration with NumPy.

**Random numbers and reproducibility** — How laser-measles seeds and manages random number generators, what affects run-to-run variation, and patterns for writing components that produce reproducible results.

### End-to-end examples

**Vaccination modeling** — Three vaccination strategies implemented in one model: pre-existing immunity at initialization, routine MCV1 coverage applied at birth, and supplemental immunization activity (SIA) campaigns at a specific time.

**Traveling waves** — Investigating a classic measles epidemiology phenomenon: building a spatial network, seeding infection in the largest city, and analyzing how the epidemic front propagates outward across the landscape.

---

## Supporting data

| Path | Contents |
|---|---|
| `ETH/` | Ethiopia shapefiles (GADM levels 0–3) and a WorldPop 1 km population raster — used by the Scenarios tutorial |

---

## Getting help

- **Rendered tutorials with outputs**: https://laser-base.github.io/laser-measles/
- **Issues and questions**: https://github.com/laser-base/laser-measles/issues
- **AI assistant**: IDM users can get modeling help from [Laser-GPT Jenner](https://chatgpt.com/g/g-674f5fd33aec8191bcdc1a2736fb7c8d-laser-gpt-jenner)
