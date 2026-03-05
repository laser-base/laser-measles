# calib/objective.py
from __future__ import annotations

import os
from dataclasses import dataclass
import numpy as np
import polars as pl
import optuna

from .run_biweekly import run_biweekly_model


@dataclass(frozen=True)
class ObjectiveConfig:
    reference_csv: str = "truth_reference/biweekly_region_reference.csv"
    years: int = 3

    # A small noise floor (cases) so early near-zero periods don’t dominate
    sd_floor: float = 10.0

    # Use a fixed seed for the biweekly model during calibration (fast + stable objective).
    model_seed: int = 202


def _load_reference(cfg: ObjectiveConfig) -> pl.DataFrame:
    ref = pl.read_csv(cfg.reference_csv)
    # Expected: region, biweek, mean, sd, q10, q50, q90
    # Keep only what we need
    ref = ref.select(["region", "biweek", "mean", "sd"]).sort(["region", "biweek"])
    return ref


def _weighted_sse(joined: pl.DataFrame, sd_floor: float) -> float:
    # joined must have: mean, sd, cases
    df = joined.with_columns(
        (pl.col("sd") + sd_floor).alias("sigma"),
        (pl.col("cases") - pl.col("mean")).alias("err"),
    ).with_columns(
        (pl.col("err") / pl.col("sigma")).alias("z")
    )
    # SSE in z-space
    return float(df.select((pl.col("z") * pl.col("z")).sum()).item())


def objective(trial: optuna.Trial, cfg: ObjectiveConfig | None = None) -> float:
    cfg = cfg or ObjectiveConfig()
    ref = _load_reference(cfg)

    # ---- search space (tweak as you like) ----
    R0_init = trial.suggest_float("R0_init", 5.5, 10.0)
    beta = trial.suggest_float("beta", 0.1, 2.0, log=True)
    seasonality = trial.suggest_float("seasonality", 0.0, 0.30)
    season_start = trial.suggest_int("season_start", 0, 25)

    import_rate = trial.suggest_float("import_rate", 0.0, 2.0)  # per 1k per year
    L = trial.suggest_float("L", 0.5, 3.0)
    eps = trial.suggest_float("eps", 0.0, 0.10)

    sim = run_biweekly_model(
        seed=cfg.model_seed,
        years=cfg.years,
        R0_init=R0_init,
        beta=beta,
        seasonality=seasonality,
        season_start=season_start,
        import_rate=import_rate,
        L=L,
        eps=eps,
    )

    # Join to reference and compute weighted loss
    joined = ref.join(sim, on=["region", "biweek"], how="left").with_columns(
        pl.col("cases").fill_null(0)
    )

    loss = _weighted_sse(joined, cfg.sd_floor)

    # Helpful diagnostics for Optuna dashboards
    trial.set_user_attr("loss", loss)
    return loss