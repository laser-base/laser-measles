# calib/run_biweekly.py
from __future__ import annotations

from dataclasses import dataclass
import polars as pl

from laser.measles.components import create_component
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
from laser.measles.biweekly import components as bw_components

from .scenario import build_scenario
from .mixing import ExpKernelMixing, ExpKernelParams


@dataclass(frozen=True)
class BiweeklyRunConfig:
    years: int = 3
    start_time: str = "2000-01"
    seed: int = 123


def run_biweekly_model(
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
    Returns: DataFrame(region, biweek, cases)
    """
    scenario, region_of = build_scenario()

    num_ticks = years * 26  # biweekly ticks

    params = BiweeklyParams(
        num_ticks=num_ticks,
        seed=seed,
        start_time="2000-01",
        verbose=False,
        show_progress=False,
    )

    model = BiweeklyModel(scenario=scenario, params=params, name=f"biweekly_seed_{seed}")

    # 1) Initial immunity via equilibrium
    model.add_component(
        create_component(
            bw_components.InitializeEquilibriumStatesProcess,
            bw_components.InitializeEquilibriumStatesParams(R0=R0_init),
        )
    )

    # 2) Vital dynamics (so RI via mcv1 is active)
    # IMPORTANT: biweekly model runs on 14-day ticks; the vital dynamics params are handled internally
    # by the component. If you want synthetic steady demography you can later set explicit params here.
    model.add_component(bw_components.VitalDynamicsProcess)

    # 3) Importation pressure
    model.add_component(
        create_component(
            bw_components.ImportationPressureProcess,
            bw_components.ImportationPressureParams(crude_importation_rate=import_rate),
        )
    )

    # 4) Infection process
    mixer = ExpKernelMixing(ExpKernelParams(L=L, eps=eps))
    infection_params = bw_components.InfectionParams(
        beta=beta,
        seasonality=seasonality,
        season_start=season_start,
        mixer=mixer,
    )
    model.add_component(create_component(bw_components.InfectionProcess, infection_params))

    # 5) Case tracker (detected cases)
    model.add_component(
        create_component(
            bw_components.CaseSurveillanceTracker,
            bw_components.CaseSurveillanceParams(detection_rate=1.0),
        )
    )

    model.run()

    tracker = model.get_instance(bw_components.CaseSurveillanceTracker)[0]
    df = tracker.get_dataframe()
    if not isinstance(df, pl.DataFrame):
        df = pl.DataFrame(df)

    # Expected columns: tick, group_id, cases  (same pattern you saw for ABM)
    df = df.with_columns(
        pl.col("group_id").cast(pl.String).replace_strict(region_of)
        #pl.col("group_id").map_elements(lambda x: region_of[str(x)], return_dtype=pl.Utf8)
        .alias("region"),
        pl.col("tick").alias("biweek"),
    )

    out = (
        df.group_by(["region", "biweek"])
        .agg(pl.col("cases").sum().alias("cases"))
        .sort(["region", "biweek"])
    )

    return out
