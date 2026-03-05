# calib/objective.py
from __future__ import annotations

import os
from dataclasses import dataclass
import numpy as np
import math
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

def _per_region_timeseries_loss(joined: pl.DataFrame, sd_floor: float) -> float:
    """
    Computes weighted SSE per region, then averages across regions so each region
    has comparable influence (prevents Metro dominance).
    """
    df = joined.with_columns(
        (pl.col("sd") + sd_floor).alias("sigma"),
        (pl.col("cases") - pl.col("mean")).alias("err"),
        ((pl.col("cases") - pl.col("mean")) / (pl.col("sd") + sd_floor)).alias("z"),
    )

    per_region = (
        df.group_by("region")
          .agg((pl.col("z") * pl.col("z")).mean().alias("mse_z"))  # mean over time
    )

    return float(per_region.select(pl.col("mse_z").mean()).item())


def _per_region_scalar_loss(
    joined: pl.DataFrame,
    sd_floor: float,
    w_cum: float = 1.0,
    w_peak: float = 1.0,
    w_tpeak: float = 0.25,
) -> float:
    """
    Adds region-level constraints for:
      - cumulative incidence
      - peak height
      - peak timing (soft)
    Uses sd-weighted z-scores derived from time-series sd (with a floor).
    """
    df = joined.with_columns(
        (pl.col("sd") + sd_floor).alias("sigma"),
    )

    # region-level scalars from truth (mean series) and sim
    scal = (
        df.group_by("region")
          .agg(
              pl.col("mean").sum().alias("truth_cum"),
              pl.col("cases").sum().alias("sim_cum"),
              pl.col("mean").max().alias("truth_peak"),
              pl.col("cases").max().alias("sim_peak"),
              # peak timing: first biweek achieving max
              pl.col("biweek").filter(pl.col("mean") == pl.col("mean").max()).min().alias("truth_tpeak"),
              pl.col("biweek").filter(pl.col("cases") == pl.col("cases").max()).min().alias("sim_tpeak"),
              # an sd proxy for scalars: sqrt(sum sigma^2)) behaves like sd of sum
              (pl.col("sigma") * pl.col("sigma")).sum().sqrt().alias("cum_sigma"),
              pl.col("sigma").max().alias("peak_sigma"),
          )
          .with_columns(
              ((pl.col("sim_cum") - pl.col("truth_cum")) / pl.col("cum_sigma")).alias("z_cum"),
              ((pl.col("sim_peak") - pl.col("truth_peak")) / pl.col("peak_sigma")).alias("z_peak"),
              (pl.col("sim_tpeak") - pl.col("truth_tpeak")).alias("dt_peak"),
          )
    )

    # timing penalty: measured in biweeks; scale by a few biweeks so it's soft
    # (You can tune denom; 2–4 biweeks is reasonable)
    timing_scale = 3.0
    scal = scal.with_columns((pl.col("dt_peak") / timing_scale).alias("z_tpeak"))

    per_region_loss = (
        (w_cum * (pl.col("z_cum") * pl.col("z_cum"))
         + w_peak * (pl.col("z_peak") * pl.col("z_peak"))
         + w_tpeak * (pl.col("z_tpeak") * pl.col("z_tpeak")))
        .alias("scalar_loss")
    )

    scal = scal.with_columns(per_region_loss)

    # average across regions (balanced)
    return float(scal.select(pl.col("scalar_loss").mean()).item())

def _fit_annual_amp_phase(series):
    """
    series: 1D numpy array of weekly/biweekly counts (assumed equally spaced)
    Returns: amplitude, phase
    """
    if len(series) == 0:
        return 0.0, 0.0
    t = np.arange(len(series))
    # for biweekly series, frequency = 2*PI / 26 (26 biweeks per year)
    # If you're using biweeks, use 26; if weeks use 52. Our pipeline uses biweeks.
    omega = 2 * math.pi / 26.0
    sin_term = np.sin(omega * t)
    cos_term = np.cos(omega * t)
    A = np.vstack([sin_term, cos_term]).T
    coeffs, *_ = np.linalg.lstsq(A, series, rcond=None)
    a, b = coeffs
    amp = float(np.sqrt(a*a + b*b))
    phase = float(np.arctan2(b, a))
    return amp, phase

def _harmonic_loss_per_region(ref_df, sim_df, weight_amp=1.0, weight_phase=0.0):
    """
    ref_df: reference DataFrame with columns region, biweek, mean
    sim_df: simulation DataFrame with columns region, biweek, cases
    Returns averaged harmonic loss across regions.
    loss_{region} = weight_amp * (amp_sim - amp_ref)^2 + weight_phase * circular_phase_diff^2
    """
    regions = sorted(ref_df["region"].unique().to_list())
    losses = []
    for r in regions:
        rref = ref_df.filter(pl.col("region") == r).sort("biweek")
        rsim = sim_df.filter(pl.col("region") == r).sort("biweek")
        # inner join on biweek to align
        joined = rref.join(rsim, on="biweek", how="inner")
        if joined.shape[0] == 0:
            losses.append(0.0)
            continue
        ref_series = joined["mean"].to_numpy()
        sim_series = joined["cases"].to_numpy()
        amp_ref, phase_ref = _fit_annual_amp_phase(ref_series)
        amp_sim, phase_sim = _fit_annual_amp_phase(sim_series)
        # amplitude penalty (squared)
        a_loss = (amp_sim - amp_ref) ** 2
        # phase penalty (circular distance) if you want to include it
        if weight_phase > 0:
            dphi = np.angle(np.exp(1j*(phase_sim - phase_ref)))  # wrap to [-pi,pi]
            p_loss = (dphi) ** 2
        else:
            p_loss = 0.0
        losses.append(weight_amp * a_loss + weight_phase * p_loss)
    return float(np.mean(losses))

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

    # Balanced region-wise time-series fit
    ts_loss = _per_region_timeseries_loss(joined, cfg.sd_floor)

    # Region-level scalar constraints
    scalar_loss = _per_region_scalar_loss(
        joined,
        cfg.sd_floor,
        w_cum=1.0,
        w_peak=1.0,
        w_tpeak=0.25,
    )

    # Combine (tune weights)
    #loss = ts_loss + 0.5 * scalar_loss

    harmonic_loss = _harmonic_loss_per_region(ref, sim, weight_amp=10.0, weight_phase=0.0)

    # combine (tune the multiplier)
    loss = ts_loss + 0.5 * scalar_loss + harmonic_loss


    trial.set_user_attr("ts_loss", float(ts_loss))
    trial.set_user_attr("scalar_loss", float(scalar_loss))
    trial.set_user_attr("harmonic_loss", float(harmonic_loss))
    return float(loss)
