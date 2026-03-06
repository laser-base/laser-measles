# calib/run_compartmental.py
from __future__ import annotations

import polars as pl

from laser.measles.components import create_component
from laser.measles.compartmental import CompartmentalModel, CompartmentalParams
from laser.measles.compartmental import components as comp

from .scenario import build_scenario
from .mixing import ExpKernelMixing, ExpKernelParams


def run_compartmental_model(
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
    Run compartmental (daily) model and return DataFrame(region, biweek, cases).
    Daily ticks are aggregated to biweekly (14-day bins) to match the reference.
    """
    scenario, region_of = build_scenario()

    num_ticks = years * 365

    params = CompartmentalParams(
        num_ticks=num_ticks,
        seed=seed,
        start_time="2000-01",
        verbose=False,
        show_progress=False,
    )

    model = CompartmentalModel(scenario=scenario, params=params, name=f"compartmental_seed_{seed}")

    model.add_component(
        create_component(
            comp.InitializeEquilibriumStatesProcess,
            comp.InitializeEquilibriumStatesParams(R0=R0_init),
        )
    )
    model.add_component(comp.VitalDynamicsProcess)
    model.add_component(
        create_component(
            comp.ImportationPressureProcess,
            comp.ImportationPressureParams(crude_importation_rate=import_rate),
        )
    )

    mixer = ExpKernelMixing(ExpKernelParams(L=L, eps=eps))
    model.add_component(
        create_component(
            comp.InfectionProcess,
            comp.InfectionParams(
                beta=beta,
                seasonality=seasonality,
                season_start=season_start,  # clamped to 0 (ABM truth)
                exp_mu=6.0,                  # clamped to ABM truth
                inf_mu=8.0,                  # clamped to ABM truth (ABM: inf_mean=8.0)
                mixer=mixer,
            ),
        )
    )
    model.add_component(
        create_component(
            comp.CaseSurveillanceTracker,
            comp.CaseSurveillanceParams(detection_rate=1.0),
        )
    )

    model.run()

    tracker = model.get_instance(comp.CaseSurveillanceTracker)[0]
    df = tracker.get_dataframe()
    if not isinstance(df, pl.DataFrame):
        df = pl.DataFrame(df)

    # Aggregate daily ticks -> biweekly (14-day bins) and map patch_id -> region
    df = df.with_columns(
        pl.col("patch_id").replace_strict(region_of).alias("region"),
        (pl.col("tick") // 14).alias("biweek"),
    )

    out = (
        df.group_by(["region", "biweek"])
        .agg(pl.col("cases").sum().alias("cases"))
        .sort(["region", "biweek"])
    )

    return out
