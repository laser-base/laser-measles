# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Calibrating a spatial ABM: a progressive multi-model cascade
#
# This is the main calibration tutorial for laser-measles. It walks you
# through a realistic, hard-enough-to-be-instructive calibration of a
# **stochastic spatial ABM** — three clusters connected in a chain, with
# vaccination campaigns that create a stochastic invasion bottleneck.
#
# The point is **not** to show you a single command that calibrates a
# model. Stochastic spatial-ABM calibration is fundamentally a
# **multi-stage process**, and the central methodological argument of
# this tutorial is a **progressive multi-model cascade**: each stage uses
# a less-expensive, more-constrained model to provide a prior that the
# next, more-expensive, less-constrained model refines. A cheap
# deterministic **compartmental model (CMP)** locates the basin; an
# expensive stochastic ABM, run with enough independent simulations per
# parameter trial, pins the parameters down to within the irreducible
# binomial sampling noise.
#
# Along the way the tutorial demonstrates several patterns that come up
# in real spatial-ABM calibration work and that no toy single-population
# fit will surface:
#
# - **Custom mixing geometry** (a chain mixer that allows only adjacent-cluster coupling)
# - **Multi-level SIA campaigns** filtered by cluster
# - **Bimodal stochastic invasion** (only a stochastic model can fit it)
# - **Cross-model bias** — the deterministic CMP at TRUE parameters peaks
#   ~17 days later than the average peak across stochastic ABM
#   simulations, so a CMP-only fit can never reproduce ensemble timing
#   without inflating the migration parameter `k`. We diagnose this up
#   front rather than papering over it.
# - **M-vs-trials trade-off** — at fixed compute, the choice is between
#   running many parameter trials with few simulations per trial, or
#   fewer trials with more simulations per trial. The right move is to
#   push **M (simulations per trial) first** until the per-trial loss
#   noise is smaller than the loss differences between candidate
#   parameter sets; only then spend additional compute on more trials.
# - **Cumulative TPE** — Optuna's default Tree-structured Parzen
#   Estimator (TPE) sampler builds a probabilistic model of the loss
#   surface from previous trials. We pre-load earlier-stage trials via
#   `study.add_trial()` so each cascade stage sharpens rather than
#   restarts the search.
#
# ## Prerequisites
#
# **The tutorial is self-contained — you can run it end-to-end without
# any prior calibration experience.** That said, it'll be easier to
# follow if you've already worked through a basic Optuna calibration
# against a single-population compartmental model (two or three free
# parameters, one of Optuna's built-in samplers). If you haven't, the
# pieces below that may feel new are: `optuna.create_study`,
# `study.optimize`, reading a TPE convergence curve, and the
# trial-objective-loss pattern. Skim the
# [Optuna quickstart](https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/001_first.html)
# if any of those land cold.
#
# ## Runtime
#
# **About 5 minutes end-to-end on an M4 Max with 36 GB RAM** with `RUN_VALIDATION =
# True`; roughly 2–3 minutes with it off. That's longer than the other
# tutorials in this directory (which all aim for under one minute), but
# a faithful calibration walkthrough can't be done in 60 seconds.
#
# ## Stages that run live vs. stages that don't
#
# Some stages of the cascade are too expensive to run inside a notebook:
#
# - **20-simulation reference generation** at TRUE parameters — ~10
#   minutes of compute on a 16-core machine.
# - **Stage 2 ABM cascade** (the full multi-variant calibration loop
#   that pins down β, k, c) — ~3 hours.
# - **Per-stage diagnostic sweeps** (identifiability scans over each
#   parameter) — ~5–10 minutes each.
#
# For those stages we use pre-computed results bundled in an artifact
# tarball that the next cell auto-downloads (~2 MB, anonymous). The
# tutorial loads those results, shows what they look like, and explains
# the lessons.
#
# The cheaper stages — scenario building, single ABM ensembles, the
# Stage 1 CMP calibration, and an optional Stage 2 validation — run
# live in the notebook. They benefit from numba's JIT cache once the
# first ABM call has compiled.
#
# ## The scenario at a glance
#
# **What's being simulated.** A 3-year measles outbreak across 45
# patches organized into a chain of clusters:
# A (15 patches, ~626K population) → B_far (8 patches, ~262K) →
# B_near (7 patches, ~226K) → C (15 patches, ~489K).
# Transmission can only happen along the chain (custom chain
# mixer, defined in Section 4). The outbreak is seeded in the three
# largest A patches at day 0.
#
# **The interventions.** Two single-day SIA campaigns on day 10:
#
# - **B_far campaign, efficacy ε=0.85** — drives B_far's effective R₀ to
#   ~0.6, creating a stochastic bottleneck. Sometimes B_far gets wiped
#   out before seeding B_near; sometimes it doesn't.
# - **B_near campaign, efficacy ε=0.50** — leaves B_near supercritical
#   (R₀_eff ~ 2.0), *if* B_far manages to seed it.
#
# **The hidden TRUE parameters** we're trying to recover:
#
# - `β = 0.5`  — per-patch transmission rate
# - `k = 0.01` — gravity mixing scale
# - `c = 1.5`  — gravity distance exponent
#
# SIA efficacies are held fixed (see Section 5 for the rationale).
#
# **The calibration target — what we compare model output against.**
# Not a trajectory, not a curve, but **six summary statistics** computed
# across the 20 independent ABM simulations at TRUE:
#
# - `c_inv_frac` — fraction of simulations where C gets invaded (~0.45)
# - `mean_AR_A`, `mean_AR_BN` — mean attack rates in clusters A and B_near
# - **`std_AR_C` ≈ 0.50** — the *bimodality fingerprint*. Across the 20
#   simulations, cluster C's attack rate is either ~0 (never invaded)
#   or ~1 (full epidemic), with roughly equal weight. A deterministic
#   model cannot reproduce this number.
# - `mean_peak_A`, `std_peak_A` — outbreak peak timing in cluster A
#
# Section 7 defines these six precisely. Section 8 sweeps each parameter
# to show which ones the loss function can resolve.

# %% [markdown]
# ## 1. Setup
#
# Standard imports. The only laser-measles-specific imports are the
# scenario factory, the ABM model + components, the compartmental model
# (used for Stage 1), and `BaseMixing` (which we'll wrap a custom
# pre-computed migration matrix in for Section 4).

# %%
import json
from datetime import date
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import optuna
import polars as pl
from laser.core.migration import distance

from laser.measles.abm import ABMModel
from laser.measles.abm import ABMParams
from laser.measles.abm import components as abm_components
from laser.measles.compartmental import CompartmentalModel
from laser.measles.compartmental import CompartmentalParams
from laser.measles.compartmental import components as cmp_components
from laser.measles.components import create_component
from laser.measles.mixing.base import BaseMixing

optuna.logging.set_verbosity(optuna.logging.WARNING)  # quiet TPE chatter

# %% [markdown]
# ### Cached artifacts
#
# Several cells below load pre-computed results for stages too expensive
# to run live: the 20-simulation reference dataset, identifiability
# sweeps, CMP cold-start convergence diagnostics, and ABM cascade
# calibration results. These are bundled as a single ~2 MB tarball
# hosted on IDM's Artifactory.
#
# The next cell downloads + extracts on first run, then reuses the
# extracted files on subsequent runs. `SANDBOX` points at the extraction
# directory (`~/.cache/laser-measles/calibration_tutorial/`).
#
# The artifacts are a **hard requirement** — there is no fallback that
# skips the cached cells. If the auto-fetch fails (network down, server
# unreachable, tarball corrupt, bundle structure changed), the cell
# raises `RuntimeError` with explicit step-by-step manual-recovery
# instructions. The intent is that the failure is loud and actionable,
# not silent.
#
# **What's cached vs. what runs live**:
#
# - **Cached** (loaded from `SANDBOX/...`): the 20-simulation reference (Section 7),
#   identifiability sweep figures (Section 8), CMP cold-start result and
#   diagnostics (Section 9), ABM cascade summaries and diagnostic figures
#   (Section 10), validation and loss-curve figures (Sections 11–12).
# - **Live** (run in this notebook, runtimes for an M4 Max with 36 GB RAM): scenario
#   construction (Section 3, ~seconds), the single-simulation ABM sanity
#   check at TRUE (Section 6, ~30 s; the first ABM call also pays a
#   one-time numba JIT compile of ~30–60 s), the **Stage 1 CMP cold-
#   start calibration** (Section 9, ~30–60 s — 30 Optuna trials), and a
#   tiny M=3 ABM ensemble demo of one Stage-2 trial (Section 10, ~30 s).
#   An **optional 10-simulation live validation** at the calibrated parameters
#   (Section 11, ~1–2 min) is gated behind `RUN_VALIDATION = False` by
#   default. Downstream Stage-2 cells use the **cached** canonical
#   Stage-1 result for deterministic comparisons.

# %%
import shutil
import tarfile
import urllib.error
import urllib.request

ARTIFACT_URL = "https://packages.idmod.org/artifactory/idm-data/LASER/laser_measles_calib_tutorial.tgz"
SANDBOX = Path.home() / ".cache" / "laser-measles" / "calibration_tutorial"

_canary = SANDBOX / "reference" / "reference_meta.json"


def _artifact_recovery_message() -> str:
    """Manual-fix instructions printed when auto-fetch fails. No silent fallback."""
    return (
        "\n\nThese cached artifacts are a hard requirement — the tutorial cannot proceed "
        "without them. Auto-fetch failed; to recover manually:\n\n"
        f"    rm -rf {SANDBOX}\n"
        f"    mkdir -p {SANDBOX}\n"
        f"    curl -fL {ARTIFACT_URL} -o /tmp/artifacts.tgz\n"
        f"    tar -xzf /tmp/artifacts.tgz -C {SANDBOX}\n\n"
        "Then rerun this cell. If the URL itself is unreachable, contact the tutorial "
        "maintainers — the artifact bundle may have moved."
    )


if not _canary.exists():
    SANDBOX.mkdir(parents=True, exist_ok=True)
    _tarball = SANDBOX / "_artifacts.tgz"
    print(f"Downloading cached artifacts (~2 MB) -> {SANDBOX}")
    try:
        # Cloudflare's bot-fight rule on packages.idmod.org returns 403 to the
        # default `Python-urllib/<ver>` User-Agent regardless of source IP.
        # urlretrieve doesn't take headers, so use urlopen + Request with a
        # browser-like UA. The URL is fixed and we own the artifact, so the
        # UA spoof is purely a workaround for the WAF rule.
        req = urllib.request.Request(  # noqa: S310 - URL is hard-coded above
            ARTIFACT_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp, _tarball.open("wb") as f:  # noqa: S310 - URL is hard-coded above
            shutil.copyfileobj(resp, f)
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(
            f"Could not download tutorial artifacts from {ARTIFACT_URL}.\n"
            f"  Underlying error: {type(exc).__name__}: {exc}" + _artifact_recovery_message()
        ) from exc

    try:
        with tarfile.open(_tarball) as tf:
            tf.extractall(SANDBOX, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise RuntimeError(
            f"Downloaded tarball at {_tarball} is corrupt or unreadable.\n"
            f"  Underlying error: {type(exc).__name__}: {exc}" + _artifact_recovery_message()
        ) from exc

    _tarball.unlink()

    if not _canary.exists():
        raise RuntimeError(
            f"Extraction succeeded but expected canary file {_canary} is missing. "
            f"The artifact bundle may have changed structure." + _artifact_recovery_message()
        )

    print("Done.")
else:
    print(f"Cached artifacts already present at {SANDBOX}")

# %% [markdown]
# ## 2. The scenario factory (inlined)
#
# This tutorial ships with `three_cluster_chain_scenario` defined inline
# rather than imported from `laser.measles.scenarios`, so the tutorial
# is self-contained and runs against any laser-measles install. (If
# this factory ever lands on main as a public scenario builder, swap
# the inlined version below for the import — the call signature won't
# change.)
#
# **What it builds.** 45 patches in three named clusters along an
# east-west chain: cluster A → cluster B → cluster C. Cluster B is
# split into two sub-clusters by their **proximity to C**:
#
# - `cluster_b:far`  — B patches on the *A-side* (far from C)
# - `cluster_b:near` — B patches on the *C-side* (near to C)
#
# > **Naming caveat — read this once.** "far" and "near" are measured
# > *with respect to C*, not A. So `B_far` is geographically the
# > A-side of cluster B, and `B_near` is geographically the C-side.
# > This matches the scientific question being studied (*does the
# > epidemic reach C?*) and matters for the SIA design later: the
# > strong campaign goes on `B_far` because that's the cluster that,
# > if uncampaigned, would otherwise push transmission onward to
# > `B_near` and from there to C.
#
# Three-level hierarchical IDs (`cluster_b:far:node_K`) let SIA
# campaigns target each sub-cluster independently via
# `SIACalendarParams(aggregation_level=2, ...)`.

# %%
def three_cluster_chain_scenario(
    seed: int = 42,
    n_nodes_per_cluster: int = 15,
    chain_separation_km: float = 200.0,
    ab_separation_km: float | None = None,
    bc_separation_km: float | None = None,
    cluster_spread_km: float = 30.0,
    b_near_fraction: float = 0.5,
    chain_lat: float = 40.0,
    chain_lon_start: float = 4.0,
    mcv1_coverage_range: tuple[float, float] | None = None,
) -> pl.DataFrame:
    """Three-cluster chain scenario for SIA-calibration experiments.

    Args mirror the laser.measles.scenarios candidate of the same name.
    `ab_separation_km` and `bc_separation_km` override the symmetric
    `chain_separation_km` for asymmetric A-B vs B-C spacing.
    `b_near_fraction` controls the fraction of B patches assigned to
    the C-side sub-cluster.
    """
    if mcv1_coverage_range is None:
        mcv1_coverage_range = (0.3, 0.6)

    rng = np.random.default_rng(seed=seed)

    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * np.cos(np.radians(chain_lat))

    spread_deg_lat = cluster_spread_km / km_per_deg_lat
    spread_deg_lon = cluster_spread_km / km_per_deg_lon

    if ab_separation_km is not None and bc_separation_km is not None:
        ab_sep_deg = ab_separation_km / km_per_deg_lon
        bc_sep_deg = bc_separation_km / km_per_deg_lon
    else:
        ab_sep_deg = chain_separation_km / km_per_deg_lon
        bc_sep_deg = chain_separation_km / km_per_deg_lon

    a_center = (chain_lat, chain_lon_start)
    b_center = (chain_lat, chain_lon_start + ab_sep_deg)
    c_center = (chain_lat, chain_lon_start + ab_sep_deg + bc_sep_deg)

    n = n_nodes_per_cluster
    n_near = max(1, int(n * b_near_fraction))

    def _scatter(prefix, c_lat, c_lon, count):
        lats = c_lat + rng.normal(0.0, spread_deg_lat, count)
        lons = c_lon + rng.normal(0.0, spread_deg_lon, count)
        out = []
        for i, (lat, lon) in enumerate(zip(lats, lons, strict=False)):
            dist = np.hypot(lat - c_lat, lon - c_lon)
            pop = int(rng.integers(30_000, 150_000) * (0.3 + 0.7 * np.exp(-dist / (spread_deg_lat * 0.5))))
            out.append(
                {
                    "id": f"{prefix}:node_{i + 1}",
                    "pop": pop,
                    "lat": float(lat),
                    "lon": float(lon),
                    "mcv1": float(rng.uniform(*mcv1_coverage_range)),
                }
            )
        return out

    rows: list[dict] = []
    rows.extend(_scatter("cluster_a", *a_center, n))

    # Cluster B: generate all patches around the B centroid, then split
    # by distance to C — near = closest n_near to C, far = the rest.
    b_lats = b_center[0] + rng.normal(0.0, spread_deg_lat, n)
    b_lons = b_center[1] + rng.normal(0.0, spread_deg_lon, n)
    b_pops, b_mcv1s = [], []
    for lat, lon in zip(b_lats, b_lons, strict=False):
        dist = np.hypot(lat - b_center[0], lon - b_center[1])
        b_pops.append(int(rng.integers(30_000, 150_000) * (0.3 + 0.7 * np.exp(-dist / (spread_deg_lat * 0.5)))))
        b_mcv1s.append(float(rng.uniform(*mcv1_coverage_range)))

    dist_to_c = np.hypot(b_lats - c_center[0], b_lons - c_center[1])
    order = np.argsort(dist_to_c)
    near_idx = order[:n_near]
    far_idx = order[n_near:]

    for rank, i in enumerate(far_idx):
        rows.append(
            {"id": f"cluster_b:far:node_{rank + 1}", "pop": b_pops[i], "lat": float(b_lats[i]), "lon": float(b_lons[i]), "mcv1": b_mcv1s[i]}
        )
    for rank, i in enumerate(near_idx):
        rows.append(
            {
                "id": f"cluster_b:near:node_{rank + 1}",
                "pop": b_pops[i],
                "lat": float(b_lats[i]),
                "lon": float(b_lons[i]),
                "mcv1": b_mcv1s[i],
            }
        )

    rows.extend(_scatter("cluster_c", *c_center, n))
    return pl.DataFrame(rows)


# %% [markdown]
# ## 3. Building the scenario
#
# Construct the 45-patch chain with 400 km A–B spacing and 200 km B–C
# spacing. Asymmetric spacing makes B a genuine bottleneck: direct A→C
# gravity coupling becomes much weaker than B→C coupling, so
# transmission really does have to walk the chain.
# The hierarchical patch IDs:
#
# - `cluster_a:node_N`        — patches in cluster A (2-level IDs)
# - `cluster_b:far:node_N`    — patches in B_far    (3-level IDs)
# - `cluster_b:near:node_N`   — patches in B_near   (3-level IDs)
# - `cluster_c:node_N`        — patches in C        (2-level IDs)
#
# The mixed 2-vs-3 ID depth is intentional: cluster B is the only one
# we want to address as two sub-clusters (for the two-tier SIA design
# below). Reading the hierarchy via `StateTracker(aggregation_level=2)`
# gives us per-patch tracking for all four clusters; the same setting
# also lets SIA campaigns target `cluster_b:far` and `cluster_b:near`
# as independent groups.
#
# Cluster A is the largest by population and is where the outbreak is
# seeded. Cluster C is downstream; whether it gets invaded at all
# depends on whether the epidemic can punch through B.

# %%
scenario = three_cluster_chain_scenario(
    seed=42,
    ab_separation_km=400.0,
    bc_separation_km=200.0,
)
ids = scenario["id"].to_list()
pops = scenario["pop"].to_numpy().astype(np.int64)
lats = scenario["lat"].to_numpy()
lons = scenario["lon"].to_numpy()


# Cluster index arrays
def cluster_idx(prefix):
    return np.array([i for i, x in enumerate(ids) if x.startswith(prefix)], dtype=int)


a_idx = cluster_idx("cluster_a")
bf_idx = cluster_idx("cluster_b:far")
bn_idx = cluster_idx("cluster_b:near")
c_idx = cluster_idx("cluster_c")

print(f"{'cluster':12s} {'patches':>8s} {'population':>14s}")
for name, idx in (("A", a_idx), ("B_far", bf_idx), ("B_near", bn_idx), ("C", c_idx)):
    print(f"{name:12s} {len(idx):8d} {int(pops[idx].sum()):>14,d}")
print(f"{'TOTAL':12s} {len(ids):8d} {int(pops.sum()):>14,d}")

# %% [markdown]
# We'll seed the outbreak in the three largest A patches (top-3 by population).

# %%
a_pop_order = np.argsort(-pops[a_idx])[:3]
seed_patches = [ids[a_idx[i]] for i in a_pop_order]
print("Seed patches:", seed_patches)

# %% [markdown]
# Quick look at the geography. The chain layout is the key visual:
# transmission has to travel A → B_far → B_near → C and there are no
# shortcuts.

# %%
fig, ax = plt.subplots(figsize=(8, 4.5))
cluster_colors = {"A": "#2196F3", "B_far": "#FF9800", "B_near": "#FF5722", "C": "#4CAF50"}
for name, idx in (("A", a_idx), ("B_far", bf_idx), ("B_near", bn_idx), ("C", c_idx)):
    ax.scatter(lons[idx], lats[idx], s=pops[idx] / 500, c=cluster_colors[name], alpha=0.7, edgecolors="k", linewidths=0.3, label=name)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Three-cluster chain layout (marker size ∝ population)")
ax.legend(loc="upper right", frameon=False)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 4. Custom mixing geometry: a chain mixer
#
# A plain `GravityMixing` would let cluster A talk to cluster C
# **directly** via long-range gravity terms — short-circuiting the chain.
# We don't want that: the scientific motivation is geographic barriers
# (think mountain ranges or political borders) that force all A→C
# transport through B.
#
# Instead, we compute a custom migration matrix that **allows only
# adjacent-cluster coupling** (and within-cluster mixing). Within
# allowed routes we still use a gravity kernel
# (`pop_j / d_{ij}^c`); forbidden routes are exactly zero. We then
# row-normalize so each patch sends fraction `k` of its population
# per tick.
#
# Two pieces:
#
# 1. **`chain_migration_matrix`** is a pure function that takes a
#    scenario, the cluster groupings (in chain order), and the
#    parameters `k` and `c`, and returns the migration matrix
#    directly — no class, no inheritance, no semantic borrowing. It
#    generalizes to any number of clusters.
# 2. **`_PrecomputedMixer`** is a 4-line `BaseMixing` adapter that
#    just exposes a pre-computed matrix to laser-measles's
#    transmission component. The OOP exists only to satisfy the
#    component machinery; the modeling logic is in the function.
#
# This pattern — function for the logic, minimal adapter for the
# OOP contract — is a good one to copy when stock mixers don't fit
# your geography.
#
# > If you want to see the chain mixer in isolation — its matrix
# > structure, the chain network laid out geographically, and the
# > population flow over time — see the optional
# > [Chain mixing visualizer](tut_chain_mixing.ipynb) companion
# > notebook. It runs in ~30 s, has no model on top, and is the
# > standalone reference for this mixer.

# %%
def chain_migration_matrix(
    scenario: pl.DataFrame,
    cluster_indices: list[np.ndarray],
    k: float,
    c: float = 1.5,
) -> np.ndarray:
    """Build a row-stochastic migration matrix with chain topology.

    Migration is allowed only within a cluster and between **adjacent**
    clusters in ``cluster_indices`` (interpreted as a linear chain).
    Allowed-route weights come from a population-and-distance gravity
    kernel ``pop_j / d_{ij}**c``; each row is normalized so each patch
    sends fraction ``k`` of its population per tick.
    """
    pop = scenario["pop"].to_numpy()
    lat = scenario["lat"].to_numpy()
    lon = scenario["lon"].to_numpy()
    n = len(pop)

    # cluster-of-each-patch lookup
    cluster_of = np.full(n, -1, dtype=int)
    for ci, idx in enumerate(cluster_indices):
        cluster_of[idx] = ci

    # allowed routes: same cluster or adjacent cluster, no self-loops
    diff = np.abs(cluster_of[:, None] - cluster_of[None, :])
    allowed = (diff <= 1) & (cluster_of[:, None] >= 0) & (cluster_of[None, :] >= 0)
    np.fill_diagonal(allowed, False)

    # great-circle distances + gravity weights on allowed routes only
    distances = distance(lat, lon, lat, lon)
    with np.errstate(divide="ignore", invalid="ignore"):
        weight = np.where(allowed, pop[None, :] / distances**c, 0.0)
    weight = np.nan_to_num(weight, nan=0.0, posinf=0.0)

    # row-normalize: each nonzero row sums to k
    row_sums = weight.sum(axis=1)
    scale = np.where(row_sums > 0, k / row_sums, 0.0)
    return weight * scale[:, None]


class _PrecomputedMixer(BaseMixing):
    """Minimal BaseMixing adapter exposing a pre-computed migration matrix."""

    def __init__(self, matrix: np.ndarray, scenario: pl.DataFrame | None = None):
        super().__init__(scenario=scenario, params=None)
        self._matrix = matrix

    def get_migration_matrix(self) -> np.ndarray:
        return self._matrix


def make_chain_mixer(
    scenario: pl.DataFrame,
    cluster_indices: list[np.ndarray],
    k: float,
    c: float = 1.5,
) -> BaseMixing:
    """Build a BaseMixing-compatible chain mixer."""
    mat = chain_migration_matrix(scenario, cluster_indices, k, c)
    return _PrecomputedMixer(mat, scenario=scenario)


# %% [markdown]
# ## 5. The "hidden TRUE" parameters
#
# This is a **synthetic recovery test**. We've generated a reference
# dataset with known parameters and the calibration task is to find
# them back from the dynamics alone — without ever telling Optuna the
# answer.
#
# - `beta = 0.5`      — per-patch transmission rate
# - `k = 0.01`        — gravity mixing scale (rows of the migration matrix sum to k)
# - `c = 1.5`         — gravity distance exponent
# - `eps_far = 0.85`  — SIA efficacy in B_far (held fixed; intervention parameter)
# - `eps_near = 0.50` — SIA efficacy in B_near (held fixed; intervention parameter)
#
# **Only (β, k, c) are calibration targets.** SIA efficacies are
# held fixed in this tutorial to keep the parameter space tractable and
# the methodological lessons (multi-model cascade, M-vs-trials,
# bimodality fitting) clean. In real-world calibration SIA efficacy is
# **genuinely uncertain** — it's a function of campaign delivery
# quality, cold-chain effects, age-targeting accuracy, and post-campaign
# survey reliability — and it is itself a meaningful calibration target
# in other work. Adding ε to this tutorial's search space would have
# introduced step-function regime transitions in the dynamics that would
# obscure the patterns we want to teach.
#
# The day-10 SIA design is what makes the dynamics interesting:
# `eps_far=0.85` drives B_far's effective R₀ to ~0.6 (a **stochastic
# bottleneck** — sometimes B_far seeds B_near, sometimes it doesn't),
# while `eps_near=0.50` leaves B_near supercritical (R₀_eff ~ 2.0)
# only if it actually gets seeded.

# %%
TRUE = {"beta": 0.5, "k": 0.01, "c": 1.5, "eps_far": 0.85, "eps_near": 0.50}

N_TICKS = 1095  # 3 years
N_SEED_INF = 5  # initial infections per seed patch
SIA_TICK = 10  # day-10 SIA campaign
START_TIME = "2000-01"
START_DATE = date(2000, 1, 1)
S_IDX, E_IDX, I_IDX, R_IDX = 0, 1, 2, 3  # ABM state indices


def tick_to_date(tick: int) -> date:
    return START_DATE + timedelta(days=tick)


# %% [markdown]
# ## 6. Building an ABM run
#
# A clean `build_abm_model(beta, k, c, seed)` function that's used
# everywhere downstream (reference generation, identifiability sweeps,
# Stage 2 calibration trials). Three notes worth attention:
#
# - We pass `mixer=chain_mixer` into `InfectionParams`. This is the
#   modern API; older laser-measles code used a monkey-patch on
#   `transmission.params.mixer` because the `mixer=` kwarg wasn't
#   accepted on the ABM `InfectionParams` at the time. With the kwarg
#   now supported, you don't need the patch.
# - `aggregation_level=2` on the `StateTracker` matches the 3-level
#   hierarchical IDs and gives us one tracker row per patch.
# - `NoBirthsProcess` is required — without a vital-dynamics component
#   the ABM model setup raises.

# %%
def build_abm_model(beta: float, k: float, c: float, seed: int) -> ABMModel:
    params = ABMParams(num_ticks=N_TICKS, seed=seed, start_time=START_TIME, show_progress=False)
    model = ABMModel(scenario=scenario, params=params)

    # Mixing geometry
    chain_mixer = make_chain_mixer(
        scenario,
        [a_idx, bf_idx, bn_idx, c_idx],
        k=k,
        c=c,
    )

    # Infection — note mixer= goes straight on InfectionParams
    inf_params = abm_components.InfectionParams(
        beta=beta,
        seasonality=0.0,
        mixer=chain_mixer,
    )

    # Seeding
    seeding_params = abm_components.InfectionSeedingParams(
        target_patches=seed_patches,
        infections_per_patch=N_SEED_INF,
    )

    # SIA campaigns — one per B subcluster
    sia_d = tick_to_date(SIA_TICK)
    bf_sia = abm_components.SIACalendarParams(
        sia_efficacy=TRUE["eps_far"],
        aggregation_level=2,
        filter_fn=lambda x: x.startswith("cluster_b:far"),
        sia_schedule=pl.DataFrame({"id": ["cluster_b:far"], "date": [sia_d]}),
        date_column="date",
        group_column="id",
    )
    bn_sia = abm_components.SIACalendarParams(
        sia_efficacy=TRUE["eps_near"],
        aggregation_level=2,
        filter_fn=lambda x: x.startswith("cluster_b:near"),
        sia_schedule=pl.DataFrame({"id": ["cluster_b:near"], "date": [sia_d]}),
        date_column="date",
        group_column="id",
    )

    model.components = [
        abm_components.NoBirthsProcess,
        create_component(abm_components.InfectionSeedingProcess, seeding_params),
        create_component(abm_components.InfectionProcess, inf_params),
        create_component(abm_components.SIACalendarProcess, bf_sia),
        create_component(abm_components.SIACalendarProcess, bn_sia),
        create_component(
            abm_components.StateTracker,
            abm_components.StateTrackerParams(aggregation_level=2),
        ),
    ]
    return model


# %% [markdown]
# Let's sanity-check it: one simulation, dynamics at TRUE. On an M4 Max with 36 GB RAM
# the model run itself is ~5–10 s, but this first call also incurs a
# one-time numba JIT compile of ~30–60 s; subsequent ABM calls in this
# notebook are at warm-cache speed. We extract the per-patch time series
# from the StateTracker and plot per-cluster infectious counts — you
# should see the chain wave from A through B to (sometimes) C.

# %%
def run_and_extract(model: ABMModel) -> np.ndarray:
    """Run model and return state_tracker array (4, num_ticks, n_patches)."""
    model.run()
    tracker = model.get_instance("StateTracker")[0]
    return np.array(tracker.state_tracker, dtype=np.int32)


# %%
demo_model = build_abm_model(beta=TRUE["beta"], k=TRUE["k"], c=TRUE["c"], seed=42)
demo_st = run_and_extract(demo_model)
print("state_tracker shape:", demo_st.shape, "  (states, ticks, patches)")

fig, ax = plt.subplots(figsize=(9, 4))
for name, idx in (("A", a_idx), ("B_far", bf_idx), ("B_near", bn_idx), ("C", c_idx)):
    I_t = demo_st[I_IDX, :, idx].sum(axis=0)
    ax.plot(I_t, label=name, color=cluster_colors[name], lw=1.6)
ax.set_xlabel("Tick (days)")
ax.set_ylabel("Infectious agents")
ax.set_title("Single-simulation ABM at TRUE (seed=42) — does C invade?")
ax.legend(frameon=False)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# **Stochastic invasion in action.** Whether you see a C wave depends
# on the particular stochastic realization — the design point is that
# **B_far is subcritical** thanks to its SIA, so chain transmission to
# B_near (and onwards to C) only happens sometimes. Re-running the
# simulation under a different RNG seed integer will produce a
# different outcome.
#
# This *simulation-to-simulation variability* is what motivates the entire
# methodology that follows. A single trajectory isn't a meaningful
# calibration target; we need an **ensemble**.

# %% [markdown]
# ## 7. The synthetic reference
#
# The reference dataset is **20 independent ABM simulations** at TRUE
# parameters for 1095 ticks (each with a distinct RNG seed), saved as
# per-patch I and R trajectories. Generating it takes about 10 minutes
# on a 16-core machine, which
# is too long for a live notebook cell. We load the pre-computed arrays
# and metadata instead.

# %%
REF_DIR = SANDBOX / "reference"
ref_I = np.load(REF_DIR / "I_by_patch.npy")  # (n_seeds, n_ticks, n_patches)
ref_R = np.load(REF_DIR / "R_by_patch.npy")
with (REF_DIR / "reference_meta.json").open() as f:
    ref_meta = json.load(f)

print(f"Reference: {ref_I.shape[0]} simulations × {ref_I.shape[1]} ticks × {ref_I.shape[2]} patches")
print()
print("Calibration targets (the 6 summary statistics the calibrator sees):")
T = ref_meta["calibration_targets"]
print(f"  c_inv_frac (fraction of simulations that invade C) : {T['c_inv_frac']['mean']:.3f}")
print(f"  mean AR_A                                    : {T['AR_A']['mean']:.3f}")
print(f"  mean AR_B_near                               : {T['AR_B_near']['mean']:.3f}")
print(f"  std AR_C (bimodality fingerprint)            : {T['AR_C']['std']:.3f}")
print(f"  mean peak_A (tick of cluster A peak)         : {T['peak_A']['mean']:.1f}")
print(f"  std peak_A                                   : {T['peak_A']['std']:.1f}")

# %% [markdown]
# ### Why these six statistics?
#
# - `c_inv_frac` — the **bottleneck signal**. Only ~45% of simulations get
#   past the B_far SIA to invade C. This pins ε_far implicitly (since
#   we're not calibrating it) and is sensitive to mixing parameters.
# - `mean_AR_A` — within-cluster attack rate. Pins β.
# - `mean_AR_BN` — cluster-coupling. Pins (β, k) jointly.
# - **`std_AR_C` ≈ 0.50** — the **bimodality fingerprint**. Across the
#   20 simulations, AR_C is bimodal: either ~0 (C never invaded) or ~1
#   (full epidemic in C). A deterministic model **cannot** reproduce
#   `std(AR_C) ≈ 0.5` — only a stochastic ensemble can.
# - `mean_peak_A`, `std_peak_A` — epidemic timing in A; pins β and k
#   jointly with cross-cluster timing constraints.
#
# Note that `mean_AR_C` is deliberately **not** a target — the mean of
# a bimodal distribution is meaningless. And `mean_AR_BF` is **not** a
# target because the B_far SIA pins it almost independent of (β, k, c)
# — including it would make the loss redundant rather than informative.

# %% [markdown]
# ### The bimodality fingerprint visualized
#
# Across the 20 reference simulations, plot final cluster-C attack rate
# (R_C(T) / N_C). You should see a clean bimodal distribution with
# peaks near 0 and near 1.

# %%
N_A = pops[a_idx].sum()
N_BF = pops[bf_idx].sum()
N_BN = pops[bn_idx].sum()
N_C = pops[c_idx].sum()

AR_C_per_seed = ref_R[:, -1, c_idx].sum(axis=1) / N_C  # (n_seeds,)
print(f"AR_C per simulation: {np.round(AR_C_per_seed, 2)}")
print(f"  → mean = {AR_C_per_seed.mean():.3f}  (unphysical — it's the mean of a bimodal)")
print(f"  → std  = {AR_C_per_seed.std(ddof=1):.3f}  (the bimodality fingerprint)")

fig, ax = plt.subplots(figsize=(7, 3.5))
ax.hist(AR_C_per_seed, bins=np.linspace(0, 1, 21), color="#4CAF50", edgecolor="k", alpha=0.85)
ax.set_xlabel("Final AR_C  (R_C(T) / N_C)")
ax.set_ylabel("Number of simulations (out of 20)")
ax.set_title("Bimodal C-invasion across reference simulations")
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 8. Stage 0 — identifiability sweeps before any calibration
#
# > The loss function is a weighted sum of squared deviations from the
# > six summary statistics described above (and in Section 7). See
# > Section 9 (`compute_cmp_loss`) and Section 10 (`compute_abm_loss`)
# > for the full definitions. The sweeps below just call this loss at
# > each grid point and plot it alongside the underlying statistics.
#
# Before launching any optimizer, sweep each parameter against the loss
# function and the summary statistics. This catches two classes of
# problem **before** you waste budget on calibration:
#
# 1. **Unidentifiable parameters** — those that don't move the loss
#    enough across their plausible range. (`c` turns out to be one such
#    in CMP here: the chain mixer has already zeroed the long-distance
#    routes that `c` would control.)
# 2. **Structural cross-model bias** — e.g. CMP at TRUE peaks 17 ticks
#    *later* than the ABM ensemble mean. CMP cannot match the ABM
#    timing without inflating `k`. We diagnose that here, so the
#    `k`-bias in Stage 1 isn't a surprise.
#
# The full sweeps are too expensive for a live cell (45 patches × ABM ×
# many parameter grid points; each sweep takes ~5–10 minutes). The
# figures below were pre-computed from one-dimensional and two-
# dimensional parameter scans over (β, k, c) and are bundled in the
# cached artifact set.

# %%
from IPython.display import Image

# CMP sweep — note c's flatness (bottom row)
Image(SANDBOX / "cmp_identifiability.png")

# %% [markdown]
# **Reading the CMP identifiability figure above:**
#
# - **Rows** sweep each free parameter: β (top), k (middle), c (bottom).
# - **Column 1 (loss vs param)** — total CMP loss as the parameter
#   varies; vertical green dashed line marks TRUE. A clean minimum at
#   TRUE means the parameter is identifiable.
# - **Column 2 (AR vs param)** — final attack rate in each cluster as
#   the parameter varies. The four colored lines are
#   `AR_A = R_A(T)/N_A`, `AR_BF = R_B_far(T)/N_B_far`, `AR_BN`, `AR_C`.
#   Horizontal dotted lines mark reference values from the 20-simulation
#   ABM ensemble.
# - **Column 3 (peak timing vs param)** — tick of the cluster-A
#   epidemic peak.
# - **Column 4 (2D heatmaps over (β, k) at c=c_true)** — three different
#   2D surfaces stacked vertically. Top row: overall `log(loss)`.
#   Middle row: `AR_BF` with its red iso-contour at the reference value
#   0.85. Bottom row: `peak_A` with its cyan iso-contour at the
#   reference value 97. The TRUE point is marked in each panel.
#
# Notice especially how `c` (bottom row, column 1) has a nearly flat
# loss curve — CMP's deterministic dynamics through the chain mixer can't
# distinguish between c values across [0.5, 3.0]. That's the "c is
# unidentifiable in CMP" finding the next markdown cell calls out.

# %%
# ABM 2D sweep — four (β, k) landscapes at c=c_true, each showing one
# calibration statistic with its reference iso-contour. The TRUE point
# sits where all three statistic iso-contours pass close to one another.
Image(SANDBOX / "abm_identifiability_2d.png")

# %% [markdown]
# **Reading the ABM identifiability figure above:** Four horizontal
# panels, each a 2D heatmap over (β, k) at c=c_true, all marked with
# the TRUE point (red star).
#
# - **Panel 1**: overall `log10(loss)` on the β × k grid — note the
#   basin near TRUE.
# - **Panel 2**: `c_inv_frac` (fraction of simulations invading C),
#   with the red iso-contour at ref=0.45. Points along that contour
#   match the reference invasion frequency exactly.
# - **Panel 3**: `mean peak_A`, with the cyan iso-contour at ref=97.
# - **Panel 4**: `mean AR_A`, with the red iso-contour at ref=0.98.
#
# Read this figure for **target-ridge intersections**: each statistic's
# iso-contour traces a 1D ridge in (β, k) space where the model matches
# that statistic. The point where multiple ridges intersect (visible
# here because they all pass near the TRUE star) is what the Stage 2
# optimizer is trying to find. If two ridges crossed far from each
# other, that would mean the statistics weren't jointly constraining
# enough — and you'd need additional summary statistics in the loss.

# %% [markdown]
# **Two findings shape every stage that follows:**
#
# 1. **`c` is essentially unidentifiable in CMP** — loss varies <30%
#    across c ∈ [0.5, 3.0] because the chain mixer has already collapsed
#    the long-distance routes that `c` would otherwise control.
#    **Decision: hold `c = 1.5` throughout Stage 1.**
#
# 2. **CMP at TRUE peaks 17 ticks late** vs the ABM ensemble mean. The
#    deterministic limit is slower than the stochastic mean. The only
#    knob CMP has to compensate is `k`. **This is a structural
#    cross-model bias** — diagnosed up front so we don't chase it
#    later.
#
# > *"The sweep is the science; calibration is the finishing touch."*

# %% [markdown]
# ## 9. Stage 1 — cheap deterministic prior (CMP cold-start)
#
# Strategy: use a CompartmentalModel (deterministic SEIR, daily ticks)
# with the same chain mixer to find a useful (β, k) basin
# cheaply (~30–60 s for 30 Optuna trials on an M4 Max with 36 GB RAM). The CMP
# can't reproduce the bimodality (it's deterministic), but it can match
# the **timing** and **A-cluster attack rate** — which is enough to
# land in the right neighborhood.
#
# **Cold start, no warm-start at TRUE.** That's important: it's a
# synthetic recovery test, so we have to play fair.
#
# The CMP loss function uses landmark-crossing times on the
# R_A(t)/N_A curve plus peak_A timing plus final AR_A — the parts of
# the dynamics that a deterministic model *can* match.

# %% [markdown]
# ### Build the CMP equivalent
#
# Same scenario, same chain mixer, same SIA campaigns — but
# CompartmentalModel instead of ABMModel. The biggest practical
# difference: CMP uses `mixer=` on `InfectionParams` natively, no
# adapter or monkey-patch needed.

# %%
def build_cmp_model(beta: float, k: float, c: float = 1.5) -> CompartmentalModel:
    params = CompartmentalParams(num_ticks=N_TICKS, seed=42, start_time=START_TIME, show_progress=False)
    model = CompartmentalModel(scenario=scenario, params=params)

    chain_mixer = make_chain_mixer(
        scenario,
        [a_idx, bf_idx, bn_idx, c_idx],
        k=k,
        c=c,
    )

    inf_params = cmp_components.InfectionParams(
        beta=beta,
        seasonality=0.0,
        mixer=chain_mixer,
    )
    seed_params = cmp_components.InfectionSeedingParams(
        target_patches=seed_patches,
        infections_per_patch=N_SEED_INF,
    )
    # CMP's SIACalendarProcess does a `str.strptime(..., "%Y-%m-%d")` on the
    # date column at construction, so it requires String dates (unlike ABM,
    # which keeps them as date objects). Pass ISO strings here.
    sia_d = tick_to_date(SIA_TICK).isoformat()
    bf_sia = cmp_components.SIACalendarParams(
        sia_efficacy=TRUE["eps_far"],
        aggregation_level=2,
        filter_fn=lambda x: x.startswith("cluster_b:far"),
        sia_schedule=pl.DataFrame({"id": ["cluster_b:far"], "date": [sia_d]}),
        date_column="date",
        group_column="id",
    )
    bn_sia = cmp_components.SIACalendarParams(
        sia_efficacy=TRUE["eps_near"],
        aggregation_level=2,
        filter_fn=lambda x: x.startswith("cluster_b:near"),
        sia_schedule=pl.DataFrame({"id": ["cluster_b:near"], "date": [sia_d]}),
        date_column="date",
        group_column="id",
    )

    # CMP doesn't expose a NoBirthsProcess — it doesn't need any vital-dynamics
    # component when births/deaths are off; the SEIR loop in InfectionProcess
    # updates the state arrays directly. (ABM does require NoBirthsProcess.)
    model.components = [
        create_component(cmp_components.InfectionSeedingProcess, seed_params),
        create_component(cmp_components.InfectionProcess, inf_params),
        create_component(cmp_components.SIACalendarProcess, bf_sia),
        create_component(cmp_components.SIACalendarProcess, bn_sia),
        create_component(
            cmp_components.StateTracker,
            cmp_components.StateTrackerParams(aggregation_level=2),
        ),
    ]
    return model


# %% [markdown]
# ### Loss function for CMP
#
# Three terms — A-attack-rate match, A-peak-tick match, and a
# normalized R_A trajectory match (root mean square of differences from
# the reference R_A(t)/N_A curve at landmark thresholds).

# %%
REF_AR_A_MEAN = T["AR_A"]["mean"]
REF_PEAK_A_MEAN = T["peak_A"]["mean"]
# R_A(t)/N_A reference trajectory (ensemble mean across 20 simulations)
ref_RA_per_N_A = ref_R[:, :, a_idx].sum(axis=2).mean(axis=0) / N_A  # (n_ticks,)


def compute_cmp_loss(st: np.ndarray) -> float:
    R_A_t = st[R_IDX, :, a_idx].sum(axis=0) / N_A  # (n_ticks,)
    I_A_t = st[I_IDX, :, a_idx].sum(axis=0)
    AR_A_final = R_A_t[-1]
    peak_A = int(np.argmax(I_A_t))
    # landmark crossings of R_A(t)/N_A at 0.1, 0.3, 0.5, 0.7, 0.9
    landmark_loss = 0.0
    for lvl in (0.1, 0.3, 0.5, 0.7, 0.9):
        ref_t = np.searchsorted(ref_RA_per_N_A, lvl)
        mod_t = np.searchsorted(R_A_t, lvl)
        landmark_loss += ((mod_t - ref_t) / 30.0) ** 2
    ar_loss = ((AR_A_final - REF_AR_A_MEAN) / 0.01) ** 2
    peak_loss = ((peak_A - REF_PEAK_A_MEAN) / 5.0) ** 2
    return landmark_loss + ar_loss + peak_loss


# %% [markdown]
# ### Run the CMP study
#
# 30 trials live, ~30–60 s total on an M4 Max with 36 GB RAM. The original research
# run did 100 trials and plateaued around trial 31 — 30 here is enough
# to land in the same basin while keeping
# notebook runtime reasonable. **No warm-start at TRUE.**

# %%
def cmp_objective(trial: optuna.Trial) -> float:
    beta = trial.suggest_float("beta", 0.1, 1.5)
    k = trial.suggest_float("k", 1e-4, 0.1, log=True)
    # c held at 1.5 (Stage 0 said it's unidentifiable in CMP)
    model = build_cmp_model(beta=beta, k=k, c=1.5)
    st = run_and_extract(model)
    return compute_cmp_loss(st)


sampler = optuna.samplers.TPESampler(seed=20260423)
cmp_study = optuna.create_study(direction="minimize", sampler=sampler)
cmp_study.optimize(cmp_objective, n_trials=30, show_progress_bar=False)

live_best = cmp_study.best_params
live_loss = cmp_study.best_value
print("Live 30-trial CMP cold-start:")
print(f"  beta = {live_best['beta']:.4f}  (× TRUE = {live_best['beta'] / TRUE['beta']:.2f})")
print(f"  k    = {live_best['k']:.4f}  (× TRUE = {live_best['k'] / TRUE['k']:.2f})")
print(f"  loss = {live_loss:.4f}")
print(f"  trials = {len(cmp_study.trials)}")

# %% [markdown]
# Quick convergence view — running-best loss vs trial number. TPE should
# settle into the basin within the first ~10 trials and then refine.

# %%
trial_values = np.array([t.value for t in cmp_study.trials if t.value is not None])
running_best = np.minimum.accumulate(trial_values)

fig, ax = plt.subplots(figsize=(7, 3.5))
ax.plot(trial_values, "o-", color="#90A4AE", alpha=0.7, label="trial loss")
ax.plot(running_best, "-", color="#D32F2F", lw=1.8, label="running best")
ax.set_xlabel("trial #")
ax.set_ylabel("loss (log scale)")
ax.set_yscale("log")
ax.set_title("Stage 1 CMP cold-start convergence (30 trials, live)")
ax.legend(frameon=False)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# ### Loading the full-precision Stage 1 result
#
# The live 30-trial run above lands in the right basin but uses a fresh
# TPE seed and fewer trials than a fully-converged sweep would. For the
# rest of the tutorial we load a **pre-computed 100-trial Stage 1
# result** as `cmp_result` and use it for all downstream Stage-2
# comparisons, so the rest of the notebook stays deterministic across
# reruns. The 100-trial best is `beta = 0.5294 (1.06× TRUE)`,
# `k = 0.0259 (2.59× TRUE — biased high)`. **The k bias is by design** —
# CMP cannot match the ABM ensemble peak timing at the TRUE k. The
# `k`-inflation is the deterministic-vs-stochastic structural mismatch
# we diagnosed in Stage 0.

# %%
with (SANDBOX / "cmp_coldstart_result.json").open() as f:
    cmp_result = json.load(f)

print(f"Stage 1 best: beta = {cmp_result['best_params']['beta']:.4f}  (× TRUE = {cmp_result['best_params']['beta'] / TRUE['beta']:.2f})")
print(f"             k    = {cmp_result['best_params']['k']:.4f}  (× TRUE = {cmp_result['best_params']['k'] / TRUE['k']:.2f})")
print(f"             loss = {cmp_result['best_loss']:.4f}")
print(f"             trials = {cmp_result.get('n_trials', '?')}")

# %% [markdown]
# Stage 1 cost: under a minute of live compute on an M4 Max with 36 GB RAM. That
# cheapness is the whole reason it's the first stage. Its role isn't
# to recover TRUE — it's to deliver a *useful prior* point to seed
# Stage 2 with.

# %%
Image(SANDBOX / "cmp_coldstart_diagnostics.png")

# %% [markdown]
# ## 10. Stage 2 — stochastic refinement (and the M-vs-trials lesson)
#
# Stage 2 is where the story actually plays out. Optuna is **warm-
# started at the Stage 1 best** (CMP cold-best, **not** TRUE) and runs
# **M-simulation ABM ensembles per trial** under a summary-statistics loss
# that includes the bimodality term `std(AR_C)`.
#
# The interesting question is **how to spend a fixed compute budget**:
# more trials at lower M, or fewer trials at higher M? Four cascade
# variants were run at the same total-compute scale, all warm-started
# from the CMP cold-best, with the result table below:

# %%
# Load cached trial summaries for all four variants
def load_cascade_summary(name: str) -> dict:
    path = SANDBOX / f"abm_cascade_{name}_result.json"
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


# The four cascade variants
cascade_summary = {
    "original (24×M=12)": load_cascade_summary("") or load_cascade_summary("default"),
    "A  (60×M=12)": load_cascade_summary("A"),
    "B  (24×M=20)": load_cascade_summary("B"),
    "F  (20×M=60, cumulative)": load_cascade_summary("F"),
}

# %% [markdown]
# | variant | trials × M | total ABM runs | loss(M=20) | β recovery | k recovery | c recovery |
# |---|---:|---:|---:|---:|---:|---:|
# | original           | 24 × 12  | 288   | 65.4  | 1.17× | **0.21×** ❌ | 0.59× |
# | A (more trials)    | 60 × 12  | 720   | 16.3  | 1.30× | **0.16×** ❌ | 0.47× |
# | B (more sims/trial)| 24 × 20  | 480   | 1.29  | 1.06× | 0.70× | 0.77× |
# | **F (cumulative)** | 20 × 60  | 1,200 | **0.568** | **0.99×** | **0.91×** | 0.72× |
#
# **A failed despite 50% more compute than B.**
#
# Why? It's the **noise floor on the loss function**. The binomial std
# on `c_inv_frac` at M samples is `sqrt(p(1-p)/M)` ≈ `sqrt(0.45·0.55/M)`:
#
# - M=12: std ≈ **0.144**, which is **larger** than the loss-function
#   scale of 0.15 → optimizer can't tell signal from noise.
# - M=20: std ≈ 0.111 ≈ scale → borderline; B succeeds.
# - M=60: std ≈ 0.064 → comfortable signal margin.
#
# More trials at insufficient M **let the optimizer overfit to
# favorable noise** — it doesn't converge faster, it converges to
# whichever happy-accident set of simulations produced an artificially low loss.

# %%
Image(SANDBOX / "cascade_compare.png")

# %% [markdown]
# **Lesson, internalize this:** When per-trial loss measurement is
# noisier than the loss differences between candidate points, spend
# your compute budget on **M (simulations per trial) first**, then on
# `n_trials`. The rule of thumb: push M until the per-trial noise is
# noticeably smaller than the loss differences you're trying to
# resolve.

# %% [markdown]
# ### Each Stage 2 step is cumulative
#
# This is the second methodological move worth emphasizing. Variant F
# launches with **all 108 prior cascade trials pre-loaded into the TPE
# study via `study.add_trial()`**. The search history accumulates
# across runs:
#
# - CMP cold-start gave Stage 2 its initial warm-start point.
# - The original 24-trial cascade told us where M=12 fails.
# - Variant A confirmed the M-not-trials diagnosis.
# - Variant B (24 × M=20) found the basin within ~30%.
# - Variant F (20 × M=60, with 108 prior trials seeded) reached
#   **0.99× × 0.91× × 0.72× recovery** with `loss(M=20) = 0.568`.
#
# **Cumulative TPE preserves every previous evaluation as prior
# knowledge**, including ones at lower M. Each new run sharpens the
# answer rather than restarting the search. A new practitioner
# shouldn't re-discover the same low-loss basins from scratch every
# time they re-run an experiment.

# %%
Image(SANDBOX / "abm_cascade_F_diagnostics.png")

# %% [markdown]
# ### Demonstrating the Stage 2 ABM evaluation API
#
# Re-running variant F would take ~2 hours. Instead, here's a tiny
# demonstration of the **per-trial evaluation pattern** that Optuna
# would call inside `objective(trial)`: build the model at a (β, k, c),
# run an M-simulation ensemble, compute summary stats, score.
#
# Tutorial scale: M=3 simulations at TRUE, ~30 s on an M4 Max with 36 GB RAM. **This is
# not a calibration trial — it's a demonstration of what one trial does
# internally.**

# %%
REF = {
    "c_inv_frac": T["c_inv_frac"]["mean"],
    "mean_AR_A": T["AR_A"]["mean"],
    "mean_AR_BN": T["AR_B_near"]["mean"],
    "std_AR_C": T["AR_C"]["std"],
    "mean_peak_A": T["peak_A"]["mean"],
    "std_peak_A": T["peak_A"]["std"],
}
SCALES = {
    "c_inv_frac": 0.15,  # binomial-noise-aware
    "mean_AR_A": 0.005,
    "mean_AR_BN": 0.05,
    "std_AR_C": 0.08,
    "mean_peak_A": 3.0,
    "std_peak_A": 1.5,
}


def run_abm_ensemble(beta: float, k: float, c: float, seeds: list[int]) -> dict:
    AR_A, AR_BN, AR_C, peak_A, invaded_C = [], [], [], [], []
    for s in seeds:
        st = run_and_extract(build_abm_model(beta, k, c, s))
        R_A_T = st[R_IDX, -1, a_idx].sum()
        R_BN_T = st[R_IDX, -1, bn_idx].sum()
        R_C_T = st[R_IDX, -1, c_idx].sum()
        I_A_t = st[I_IDX, :, a_idx].sum(axis=0)
        I_C_t = st[I_IDX, :, c_idx].sum(axis=0)
        R_C_t = st[R_IDX, :, c_idx].sum(axis=0)
        AR_A.append(R_A_T / N_A)
        AR_BN.append(R_BN_T / N_BN)
        AR_C.append(R_C_T / N_C)
        peak_A.append(int(np.argmax(I_A_t)) if I_A_t.max() > 0 else N_TICKS)
        invaded_C.append(bool((I_C_t > 0).any() or (R_C_t > 0).any()))
    return {
        "c_inv_frac": float(np.mean(invaded_C)),
        "mean_AR_A": float(np.mean(AR_A)),
        "mean_AR_BN": float(np.mean(AR_BN)),
        "std_AR_C": float(np.std(AR_C, ddof=1)) if len(AR_C) > 1 else 0.0,
        "mean_peak_A": float(np.mean(peak_A)),
        "std_peak_A": float(np.std(peak_A, ddof=1)) if len(peak_A) > 1 else 0.0,
    }


def compute_abm_loss(stats: dict) -> float:
    return sum(((stats[key] - REF[key]) / SCALES[key]) ** 2 for key in REF)


# %%
# Demo: one "trial" at TRUE, M=3
demo_stats = run_abm_ensemble(
    beta=TRUE["beta"],
    k=TRUE["k"],
    c=TRUE["c"],
    seeds=[42, 43, 44],
)
demo_loss = compute_abm_loss(demo_stats)

print("Per-trial summary statistics at TRUE (M=3 simulations):")
for key, ref_val in REF.items():
    print(f"  {key:14s}: model = {demo_stats[key]:.3f}   ref = {ref_val:.3f}   (scale {SCALES[key]})")
print(f"\nLoss at TRUE, M=3: {demo_loss:.3f}")
print(f"  → For comparison, Stage 2 variant F best loss at M=20 = {cascade_summary['F  (20×M=60, cumulative)']['best_loss_at_M20']:.3f}")
print("  → Single-simulation noise dominates at M=3 — this is why a calibration")
print("     trial needs M=20+ for the loss to actually mean something.")

# %% [markdown]
# **Note** how the M=3 loss at *exactly TRUE* is not small. That's the
# whole noise-floor argument made concrete: at low M, even the right
# answer has a loss in the tens. That's why you can't use M=3 for
# calibration — you'd be optimizing noise.

# %% [markdown]
# ## 11. Validation against the reference
#
# After Stage 2 finishes, validate by running a **fresh** 50-simulation
# ensemble at the calibrated parameters and comparing to the 20-simulation
# reference at every level — trajectories, per-cluster distributions,
# and summary scalars.
#
# Cached figure from the validation run (50 simulations at the calibrated parameters,
# compared to the 20-simulation reference):

# %%
Image(SANDBOX / "calibration_validation.png")

# %% [markdown]
# **Validation summary (variant F's best at β=0.4963, k=0.00910, c=1.087):**
#
# - **Per-cluster I/N and R/N bands overlap.** Calibrated ensemble
#   (50 simulations, dashed) falls within the reference band (20 simulations,
#   solid) across all four clusters.
# - **Per-cluster AR distributions match shape.** Calibrated AR_C is
#   bimodal with peaks near 0 and 1 — the part no deterministic model
#   can produce.
# - **Bimodality preserved**: `std(AR_C) = 0.488` vs reference 0.500
#   (within ~3%).
# - **peak_A**: 97.65 vs 96.65 — within one tick.
# - **β = 0.4963 (0.99× TRUE)**, **k = 0.00910 (0.91× TRUE)** — the
#   load-bearing result, achieved **without TRUE leakage**.

# %% [markdown]
# ### Optional: reproduce the validation live (~1–2 min, opt-in)
#
# The cached figure above shows a **50-simulation** ABM ensemble at the
# calibrated `(β, k, c)` (variant F's best from cascade Stage 2)
# compared against the 20-simulation reference. The cell below reruns
# that comparison live with a smaller **10-simulation** ensemble —
# enough simulations to resolve `std(AR_C)`, but half the 20-simulation
# reference's count. It's gated behind `RUN_VALIDATION = False` because
# it adds ~1–2 minutes to the notebook runtime on an M4 Max with
# 36 GB RAM. Flip the flag below to run it.
#
# The output is a side-by-side comparison of the 6 calibration-target
# summary statistics — calibrated ensemble vs reference, with each
# deviation expressed in units of the loss-function scale (so values
# near 0 mean agreement within the loss's noise floor).

# %%
RUN_VALIDATION = False  # flip to True to run a 10-simulation ABM ensemble at the calibrated params (~1–2 min)

if RUN_VALIDATION:
    cal = cascade_summary["F  (20×M=60, cumulative)"]["best_params"]
    val_seeds = list(range(1000, 1010))  # 10 fresh RNG seeds (one per simulation), distinct from the reference's
    print(f"Running 10-simulation validation at calibrated params (β={cal['beta']:.4f}, k={cal['k']:.5f}, c={cal['c']:.3f})...")
    print("  expected runtime ~1–2 minutes on an M4 Max with 36 GB RAM")

    val_stats = run_abm_ensemble(beta=cal["beta"], k=cal["k"], c=cal["c"], seeds=val_seeds)
    val_loss = compute_abm_loss(val_stats)

    print()
    print(f"{'statistic':14s}  {'calibrated':>10s}  {'reference':>10s}  {'deviation':>10s}")
    print("-" * 52)
    for key, ref_val in REF.items():
        cal_val = val_stats[key]
        dev = (cal_val - ref_val) / SCALES[key]
        print(f"{key:14s}  {cal_val:>10.3f}  {ref_val:>10.3f}  {dev:>+10.2f}")
    print(f"\nLoss at calibrated params (M=10): {val_loss:.3f}")
    print(f"  (For comparison, variant F best at M=20: {cascade_summary['F  (20×M=60, cumulative)']['best_loss_at_M20']:.3f})")
else:
    print("RUN_VALIDATION is False — skipping live validation.")
    print("Flip the flag above to run a 10-simulation ABM ensemble at the calibrated")
    print("parameters (~1–2 min on an M4 Max with 36 GB RAM).")

# %% [markdown]
# ## 12. What the cascade did *not* fully recover
#
# For an honest write-up, residual bias matters:
#
# - **`c` is biased low: 1.087 vs TRUE 1.5** (0.72×). This shows up
#   in the validation as `c_inv_frac ≈ 0.68` in the 50-simulation calibrated
#   ensemble vs 0.45 in the reference — a real ~3-σ overshoot, not
#   noise. Weaker distance decay → stronger A→B_far→B_near coupling →
#   more frequent C invasion.
# - The summary-stats loss didn't punish this hard enough, because the
#   `c_inv_frac` term is scaled at 0.15 (matching its irreducible
#   binomial noise floor at M=12). Tightening the scale or **adding a
#   per-patch spatial loss term** — e.g. arrival-time differences for
#   patches invaded in ≥50% of simulations — would constrain `c` better.
# - **Resolution is finite, not infinite.** The noise floor at TRUE
#   under M=10 ranged from 2.92 to 61.21 across replicas; a 1D β
#   profile shows that values in [0.48, 0.52] are statistically
#   indistinguishable from TRUE.
#
# **Practical resolution at this loss design and compute budget:
# β within ~5%, k within ~10%, c within ~25%.**

# %%
Image(SANDBOX / "loss_curves.png")

# %% [markdown]
# ## 13. Lessons to carry forward
#
# 1. **Sweep before you calibrate.** Identifiability sweeps catch
#    unidentifiable parameters and cross-model bias *before* you waste
#    optimizer budget. The biennial-calibration adage holds: *the
#    sweep is the science; calibration is the finishing touch.*
#
# 2. **Multi-model cascades work** — a fast deterministic prior gets
#    you into the right basin; the stochastic refinement step needs
#    sufficient M to distinguish gradient from noise.
#
# 3. **Cross-model calibration biases mixing parameters.** Don't be
#    surprised when a CMP-fit k is 2-3× off the ABM-fit k. β is
#    robust because it's set by within-patch dynamics that both
#    models share; mixing parameters live in the cross-cluster
#    coupling, which CMP and ABM disagree about.
#
# 4. **For stochastic calibration, M is the limiting resource,
#    not n_trials.** Push M until per-trial noise is much smaller
#    than the loss differences between candidate points, *then*
#    spend trials.
#
# 5. **Include a bimodality target if the reference is bimodal.**
#    `std(AR_C) ≈ 0.5` is a target only a stochastic model can meet —
#    it's both a forcing function for the right machinery and a
#    diagnostic for whether your fit actually reproduces simulation-to-simulation
#    variability.
#
# 6. **Cumulative TPE.** Don't throw away trial history. Pre-load
#    previous runs into new studies via `study.add_trial()`; each new
#    run sharpens the answer rather than restarting the search.
#
# 7. **Be honest about precision.** Don't quote point estimates
#    without uncertainty bounds. The noise-floor study + 1D parameter
#    profile is the load-bearing way to claim "β recovered within
#    ~5%" rather than just "β recovered."

# %% [markdown]
# ## 14. Where to go from here
#
# - **Deeper methodology background.** The wiki page
#   *Synthetic-Spatial-Multi-Modal-Calibration-for-Documentation*
#   covers honest-precision claims, dead-end cascade variants, and
#   additional methodological detail that this tutorial doesn't expand
#   on.
# - **A natural extension** for pushing `c` recovery: add a per-patch
#   spatial loss term — e.g. `sum((arrival_tick_p_model -
#   arrival_tick_p_ref)^2)` for patches invaded in ≥50% of simulations. `c`
#   controls *which* patches in B_far the chain reaches first; that
#   signal washes out in cluster-aggregate summary statistics.
# - **Other custom mixing patterns** are worth studying when stock
#   gravity/radiation models don't fit your geography. The chain
#   mixer here is one example. The transferable pattern is
#   *function-for-the-logic + minimal `BaseMixing` adapter for the
#   OOP contract* — see `chain_migration_matrix` and
#   `_PrecomputedMixer` in Section 4. The
#   [Chain mixing visualizer](tut_chain_mixing.ipynb) companion
#   notebook walks through the same pattern with visualizations.
