# calib/run_abm.py
from __future__ import annotations

import polars as pl

from laser.measles.abm import ABMModel, ABMParams, components
from laser.measles.components import create_component

from .mixing import ExpKernelMixing, ExpKernelParams
from .scenario import build_scenario


def run_abm_model(
    *,
    seed: int,
    years: int,
    R0_init: float,
    beta: float,
    seasonality: float,
    season_start: int,
    import_rate: float,
    L: float,
    eps: float,
) -> pl.DataFrame:
    """
    Run ABM (daily) model and return DataFrame(region, biweek, cases).
    Daily ticks are aggregated to biweekly (14-day bins) to match the reference.
    exp_mu and inf_mean are fixed to match ABM reference truth.
    """
    scenario, region_of = build_scenario()

    num_ticks = years * 365

    params = ABMParams(
        num_ticks=num_ticks,
        seed=seed,
        verbose=False,
        show_progress=False,
    )

    model = ABMModel(scenario=scenario, params=params, name=f"abm_seed_{seed}")

    model.add_component(
        create_component(
            components.InitializeEquilibriumStatesProcess,
            components.InitializeEquilibriumStatesParams(R0=R0_init),
        )
    )
    model.add_component(
        create_component(
            components.VitalDynamicsProcess,
            components.VitalDynamicsParams(
                crude_birth_rate=30 / 365,
                crude_death_rate=30 / 365,
            ),
        )
    )
    # Initial spark in metro center — mirrors the reference model
    model.add_component(
        create_component(
            components.InfectionSeedingProcess,
            components.InfectionSeedingParams(
                target_patches=["n_2_2"],
                infections_per_patch=10,
            ),
        )
    )
    model.add_component(
        create_component(
            components.ImportationPressureProcess,
            components.ImportationPressureParams(crude_importation_rate=import_rate),
        )
    )
    mixer = ExpKernelMixing(ExpKernelParams(L=L, eps=eps))
    model.add_component(
        create_component(
            components.InfectionProcess,
            components.InfectionParams(
                beta=beta,
                seasonality=seasonality,
                season_start=season_start,
                mixer=mixer,
                exp_mu=6.0,      # fixed to match ABM reference truth
                inf_mean=8.0,    # fixed to match ABM reference truth
            ),
        )
    )
    model.add_component(
        create_component(
            components.CaseSurveillanceTracker,
            components.CaseSurveillanceParams(detection_rate=1.0),
        )
    )

    model.run()

    tracker = model.get_instance(components.CaseSurveillanceTracker)[0]
    df = tracker.get_dataframe()
    if not isinstance(df, pl.DataFrame):
        df = pl.DataFrame(df)

    # Aggregate daily ticks -> biweekly (14-day bins) and map patch_id -> region
    df = df.with_columns(
        pl.col("patch_id").replace_strict(region_of).alias("region"),
        (pl.col("tick") // 14).alias("biweek"),
    )

    return (
        df.group_by(["region", "biweek"])
        .agg(pl.col("cases").sum().alias("cases"))
        .sort(["region", "biweek"])
    )
