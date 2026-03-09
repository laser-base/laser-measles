from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
from pathlib import Path

import numpy as np
import polars as pl

import laser.measles as lm
from laser.measles import create_component
from laser.measles.abm import ABMModel, ABMParams
from laser.measles.base import BasePhase

from calib.mixing import ExpKernelMixing, ExpKernelParams


# ----------------------------
# 5x5 grid + 5 regions
# ----------------------------

def node_id(i: int, j: int) -> str:
    return f"n_{i}_{j}"


def build_grid_nodes() -> List[Tuple[int, int]]:
    return [(i, j) for j in range(5) for i in range(5)]


def assign_region(i: int, j: int) -> str:
    # R0 Metro: i==2 or j==2
    if i == 2 or j == 2:
        return "R0_metro"
    # Quadrants on remaining 4x4
    if i < 2 and j < 2:
        return "R1_nw"
    if i > 2 and j < 2:
        return "R2_ne"
    if i < 2 and j > 2:
        return "R3_sw"
    return "R4_se"


def build_population_map() -> Dict[str, int]:
    """
    Deterministic pop map scaled to ~1M total (geometry unchanged).
      - Metro cross: 160k center, 87k inner, 47k outer
      - Quadrants: checkerboard 27k / 11k
    """
    pops: Dict[str, int] = {}
    for i, j in build_grid_nodes():
        nid = node_id(i, j)

        # Metro cross
        if i == 2 and j == 2:
            pops[nid] = 160_000
        elif (i == 2 and j in (1, 3)) or (j == 2 and i in (1, 3)):
            pops[nid] = 87_000
        elif (i == 2 and j in (0, 4)) or (j == 2 and i in (0, 4)):
            pops[nid] = 47_000
        else:
            pops[nid] = 27_000 if ((i + j) % 2 == 0) else 11_000

    return pops


def coverage_map(i: int, j: int) -> float:
    """
    Routine immunization (MCV1) map:
      baseline 0.92 with west->east gradient +/-0.03
      pockets forced to 0.80
    """
    # pockets
    if (i, j) in [(4, 0), (0, 4), (4, 4)]:
        return 0.80

    v0 = 0.92
    g = 0.03
    # i in 0..4 => (i-2)/2 in [-1, 1]
    return float(np.clip(v0 + g * ((i - 2) / 2.0), 0.0, 1.0))


def initial_immune_map(i: int, j: int) -> float:
    """
    Initial immunity fraction:
      baseline 0.85 with west->east gradient +/-0.05 (immune ranges ~0.80..0.90)
      pockets forced to 0.65
    """
    if (i, j) in [(4, 0), (0, 4), (4, 4)]:
        return 0.65

    r0 = 0.85
    g = 0.05
    return float(np.clip(r0 + g * ((i - 2) / 2.0), 0.0, 1.0))


def build_scenario() -> tuple[pl.DataFrame, Dict[str, str], Dict[str, float]]:
    pops = build_population_map()

    rows = []
    region_of: Dict[str, str] = {}
    imm0_of: Dict[str, float] = {}

    # Use (lat,lon) as (j,i) just to give geometry; units are arbitrary
    for i, j in build_grid_nodes():
        nid = node_id(i, j)
        reg = assign_region(i, j)
        mcv1 = coverage_map(i, j)
        imm0 = initial_immune_map(i, j)

        region_of[nid] = reg
        imm0_of[nid] = imm0

        rows.append(
            {
                "id": nid,
                "lat": float(j),
                "lon": float(i),
                "pop": int(pops[nid]),
                "mcv1": float(mcv1),
            }
        )

    scenario = pl.DataFrame(rows)
    return scenario, region_of, imm0_of


# ----------------------------
# Run one ABM replicate
# ----------------------------
def run_one(seed: int = 123, years: int = 3):
    scenario, region_of, _ = build_scenario()

    num_ticks = years * 365

    params = ABMParams(
        num_ticks=num_ticks,
        seed=seed,
        start_time="2000-01",
        verbose=True,
        show_progress=True,
    )

    model = ABMModel(scenario, params, name=f"truth_abm_seed_{seed}")

    # -----------------------------
    # Component order matters
    # -----------------------------

    # 1) Initialize equilibrium immunity (initial S/R split)
    model.add_component(
        create_component(
            lm.abm.components.InitializeEquilibriumStatesProcess,
            lm.abm.components.InitializeEquilibriumStatesParams(
                R0=5.0  # ~20% susceptible, ~80% immune
            ),
        )
    )

    # 2) Vital dynamics (enables RI via mcv1 in scenario)
    #model.add_component(lm.abm.components.VitalDynamicsProcess)
    model.add_component(
        create_component(
            lm.abm.components.VitalDynamicsProcess,
            lm.abm.components.VitalDynamicsParams(
                crude_birth_rate=30/365,   # per 1000 per year
                crude_death_rate=30/365,    # per 1000 per year
                )
            )
        )
    # 3) Seed initial infections in metro center
    model.add_component(
        create_component(
            lm.abm.components.InfectionSeedingProcess,
            lm.abm.components.InfectionSeedingParams(
                target_patches=["n_2_2"],
                infections_per_patch=10,
            ),
        )
    )

    # 4) Low background importation — just enough to prevent stochastic extinction
    model.add_component(
        create_component(
            lm.abm.components.ImportationPressureProcess,
            lm.abm.components.ImportationPressureParams(
                crude_importation_rate=0.05  # yearly per 1k pop
            ),
        )
    )

    # 5) Infection process with spatial mixing + seasonality
    mixer = ExpKernelMixing(ExpKernelParams(L=1.5, eps=0.05))

    infection_params = lm.abm.components.InfectionParams(
        beta=0.8,
        seasonality=0.15,
        season_start=0,
        mixer=mixer,
    )

    model.add_component(
        create_component(
            lm.abm.components.InfectionProcess,
            infection_params,
        )
    )

    # 6) Trackers
    model.add_component(lm.abm.components.StateTracker)

    model.add_component(
        create_component(
            lm.abm.components.CaseSurveillanceTracker,
            lm.abm.components.CaseSurveillanceParams(
                detection_rate=1.0
            ),
        )
    )

    # -----------------------------
    # Run model
    # -----------------------------
    model.run()

    # Extract daily detected cases
    case_tracker = model.get_instance(lm.abm.components.CaseSurveillanceTracker)[0]
    cases_df = case_tracker.get_dataframe()

    # ----------------------------------------
    # Convert to Polars if needed
    # ----------------------------------------
    if not isinstance(cases_df, pl.DataFrame):
        cases_df = pl.DataFrame(cases_df)

    # ----------------------------------------
    # Map patch → region
    # ----------------------------------------
    cases_df = cases_df.with_columns(
        pl.col("patch_id").replace_strict(region_of).alias("region")
    )

    # ----------------------------------------
    # Add week + biweek indices
    # ----------------------------------------
    cases_df = cases_df.with_columns(
        (pl.col("tick") // 7).alias("week"),
        (pl.col("tick") // 14).alias("biweek"),
    )

    # ----------------------------------------
    # Weekly aggregation
    # ----------------------------------------
    weekly = (
        cases_df
        .group_by(["region", "week"])
        .agg(pl.col("cases").sum().alias("cases"))
        .sort(["region", "week"])
    )

    # ----------------------------------------
    # Biweekly aggregation
    # ----------------------------------------
    biweekly = (
        cases_df
        .group_by(["region", "biweek"])
        .agg(pl.col("cases").sum().alias("cases"))
        .sort(["region", "biweek"])
    )

    # ----------------------------------------
    # Scalar summaries
    # ----------------------------------------
    peak = (
        biweekly
        .group_by("region")
        .agg(pl.col("cases").max().alias("peak_biweekly"))
    )

    cumulative = (
        biweekly
        .group_by("region")
        .agg(pl.col("cases").sum().alias("cumulative_cases"))
    )

    summary = peak.join(cumulative, on="region")

    # ----------------------------------------
    # Write outputs
    # ----------------------------------------
    outdir = Path("truth_outputs")
    outdir.mkdir(exist_ok=True)

    weekly.write_csv(outdir / f"weekly_seed_{seed}.csv")
    biweekly.write_csv(outdir / f"biweekly_seed_{seed}.csv")
    summary.write_csv(outdir / f"summary_seed_{seed}.csv")

    print("Wrote:")
    print(" -", outdir / f"weekly_seed_{seed}.csv")
    print(" -", outdir / f"biweekly_seed_{seed}.csv")
    print(" -", outdir / f"summary_seed_{seed}.csv")
    return model, cases_df, region_of

#if __name__ == "__main__":
#    model, cases_df, region_of = run_one(seed=123, years=3)
#    print(cases_df.head())

if __name__ == "__main__":

    years = 3
    seeds = range(100, 110)  # 10 replicates

    for seed in seeds:
        print(f"\nRunning seed {seed}")
        run_one(seed=seed, years=years)

    print("\nAll seeds completed.")
