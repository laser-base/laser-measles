# laser-measles on COMPS

This directory contains everything needed to run `laser-measles` simulations on the
[COMPS](https://comps.idmod.org) HPC platform using Singularity containers.

## Overview

The workflow has four steps:

```
Build image → Upload assets → Submit sweep → Retrieve & plot
  Dockerfile      createac       run_comps.py    retrieve_outputs.py
                                                 plot_outputs.py
```

The demo runs a compartmental SEIR model on a synthetic 8-patch linear scenario
(total population ~810k), sweeping `beta` across 5 values corresponding to R0 ≈ 3–16.
Each simulation writes `output.csv` with per-tick SEIR counts; the retrieval script
combines all simulations into `all_outputs.csv`.

## Prerequisites

- Singularity installed locally
- `python3.11` with `idmtools` and `COMPS` packages installed
- COMPS credentials (log in once interactively to cache the auth token):
  ```bash
  python3.11 -c "from COMPS import Client; Client.login('https://comps.idmod.org')"
  ```

## Step-by-step

### 1. Build the Docker image and SIF

```bash
docker build -t laser-measles .
singularity build laser-measles.sif docker-daemon://laser-measles:latest
```

The `Dockerfile` installs `laser_measles` (pre-release) from PyPI into an Ubuntu 22.04
image with Python 3.11. The resulting SIF is ~1 GB — it is gitignored and must be built
locally.

### 2. Upload assets to COMPS

Copy the model script alongside the SIF, then create an AssetCollection:

```bash
cp main_measles.py assets/
cp laser-measles.sif assets/
python3.11 -m COMPS create_asset_collection assets --name laser-measles-assets
```

This uploads any new files and prints the AssetCollection UUID. Save it:

```bash
echo "<uuid-from-above>" > laser-measles.id
```

The SIF is content-addressed, so re-uploading it on subsequent runs is a no-op as long
as the file hasn't changed.

### 3. Submit the sweep

```bash
python3.11 run_comps.py
```

This submits 5 simulations (one per beta value), waits for them to finish, and saves
the experiment UUID to `experiment.id`.

Sweep values and their approximate R0 (R0 = beta × inf_mu, inf_mu = 8 days):

| beta  | R0 ≈ |
|-------|-------|
| 0.375 | 3     |
| 0.625 | 5     |
| 1.0   | 8     |
| 1.5   | 12    |
| 2.0   | 16    |

Each simulation starts with a naive (fully susceptible) population seeded with
10 infections in the largest patch. Runtime is ~1–2 minutes for the full sweep.

### 4. Retrieve outputs

```bash
python3.11 retrieve_outputs.py
```

Downloads `output.csv` from each simulation and concatenates them into `all_outputs.csv`.

### 5. Plot

```bash
python3.11 plot_outputs.py
```

Writes `beta_sweep.png` — a 2×2 panel of S/E/I/R time series, one line per beta value.

## File reference

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the container image with `laser_measles` from PyPI |
| `main_measles.py` | Model entry point — accepts `--beta` and `--seed`, writes `output.csv` |
| `run_comps.py` | Submits the beta sweep experiment to COMPS |
| `retrieve_outputs.py` | Downloads simulation outputs and combines into `all_outputs.csv` |
| `plot_outputs.py` | Plots SEIR time series from `all_outputs.csv` |
| `assets/` | Staging directory for SIF + script (gitignored, built locally) |

## Extending the sweep

To sweep different parameters, edit the constants at the top of `run_comps.py` and the
corresponding `argparse` arguments in `main_measles.py`. The `set_beta` callback in
`run_comps.py` shows the pattern for injecting per-simulation command-line arguments.

## Notes

- **First run is slow**: the first time a SIF is used on a COMPS worker node, there is
  extra setup time (~minutes). Subsequent runs with the same SIF are faster.
- **Auth token expiry**: COMPS tokens are session-scoped. If you get auth errors, re-run
  the login command above.
- **Asset reuse**: COMPS deduplicates assets by checksum. Updating only `main_measles.py`
  (without rebuilding the SIF) requires only a new `create_asset_collection` call — the
  SIF upload is skipped automatically.
