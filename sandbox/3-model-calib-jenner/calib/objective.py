# calib/objective.py
from __future__ import annotations

import os
from dataclasses import dataclass
import numpy as np
import math
import polars as pl
import optuna

@dataclass(frozen=True)
class ObjectiveConfig:
    reference_csv: str = "truth_reference/biweekly_region_reference.csv"
    years: int = 3

    # A small noise floor (cases) so early near-zero periods don’t dominate
    sd_floor: float = 10.0

    # Use a fixed seed for the model during calibration (fast + stable objective).
    model_seed: int = 202

    # beta search range (log-scale); biweekly and compartmental need different scales
    beta_lo: float = 0.1
    beta_hi: float = 2.0

    # import_rate search range; reference truth uses 0.05, allow 0 as lower bound
    # so optimizer can distinguish transmission-driven from importation-dominated regimes
    import_rate_lo: float = 0.0
    import_rate_hi: float = 0.3

    # Progressive multi-seed ensemble: start with n_seeds for fast exploration, then switch to
    # n_seeds_refined once the best-value improvement plateaus. Set both equal to disable.
    n_seeds: int = 1
    n_seeds_refined: int = 1
    plateau_window: int = 30       # number of recent completed trials to inspect
    plateau_min_improvement: float = 1.0  # loss must drop by at least this over the window

    # Weight for harmonic (seasonal amplitude) loss term.
    # Use lower values (~100) for stochastic models (ABM) to prevent noise domination.
    harmonic_weight: float = 1000.0


def _detect_plateau(study: optuna.Study, window: int, min_improvement: float) -> bool:
    """Return True if the best loss hasn't improved by min_improvement over the last `window` trials."""
    completed = sorted(
        [t for t in study.trials if t.state.name == "COMPLETE"],
        key=lambda t: t.number,
    )
    if len(completed) < window:
        return False
    recent = completed[-window:]
    half = window // 2
    first_best = min(t.value for t in recent[:half])
    second_best = min(t.value for t in recent[half:])
    return (first_best - second_best) < min_improvement


def _run_ensemble(run_model_fn, n_seeds: int, base_seed: int, **kwargs) -> pl.DataFrame:
    """Run model n_seeds times and return the mean cases across seeds."""
    dfs = [run_model_fn(seed=base_seed + i, **kwargs) for i in range(n_seeds)]
    if n_seeds == 1:
        return dfs[0]
    return (
        pl.concat(dfs)
        .group_by(["region", "biweek"])
        .agg(pl.col("cases").mean().alias("cases"))
        .sort(["region", "biweek"])
    )


def _resolve_n_seeds(trial: optuna.Trial, cfg: ObjectiveConfig) -> int:
    """
    Determine how many seeds to use for this trial.
    Once the plateau is detected the switch is stored permanently in study user_attrs
    so it survives restarts and never reverts even if loss briefly improves again.
    """
    if cfg.n_seeds_refined <= cfg.n_seeds:
        return cfg.n_seeds
    # Already permanently switched?
    if trial.study.user_attrs.get("refined_seeds_active", False):
        return cfg.n_seeds_refined
    # Check for plateau
    if _detect_plateau(trial.study, cfg.plateau_window, cfg.plateau_min_improvement):
        trial.study.set_user_attr("refined_seeds_active", True)
        print(
            f"[Trial {trial.number}] Plateau detected — switching to {cfg.n_seeds_refined} seeds permanently."
        )
        return cfg.n_seeds_refined
    return cfg.n_seeds


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
    loss_{region} = weight_amp * ((amp_sim - amp_ref) / amp_ref)^2 + weight_phase * circular_phase_diff^2

    Amplitude error is normalized by amp_ref so all regions contribute equally regardless
    of their absolute case counts (prevents metro from dominating or periphery from being
    crushed by absolute-scale differences).
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
        # relative amplitude penalty: normalized by amp_ref so regions of all sizes contribute equally
        denom = max(amp_ref, 1.0)  # floor at 1 to avoid div-by-zero for flat series
        a_loss = ((amp_sim - amp_ref) / denom) ** 2
        # phase penalty (circular distance) if you want to include it
        if weight_phase > 0:
            dphi = np.angle(np.exp(1j*(phase_sim - phase_ref)))  # wrap to [-pi,pi]
            p_loss = (dphi) ** 2
        else:
            p_loss = 0.0
        losses.append(weight_amp * a_loss + weight_phase * p_loss)
    return float(np.mean(losses))

def objective(trial: optuna.Trial, cfg: ObjectiveConfig | None = None, run_model_fn=None) -> float:
    cfg = cfg or ObjectiveConfig()
    if run_model_fn is None:
        from .run_biweekly import run_biweekly_model
        run_model_fn = run_biweekly_model
    ref = _load_reference(cfg)

    # ---- search space ----
    R0_init = trial.suggest_float("R0_init", 3.0, 8.0)
    beta = trial.suggest_float("beta", cfg.beta_lo, cfg.beta_hi, log=True)
    seasonality = trial.suggest_float("seasonality", 0.0, 0.30)
    # season_start=0: fixed to match the ABM that generated the reference data
    season_start = 0

    import_rate = trial.suggest_float("import_rate", cfg.import_rate_lo, cfg.import_rate_hi)  # per 1k per year
    L = trial.suggest_float("L", 0.5, 3.0)
    eps = trial.suggest_float("eps", 0.0, 0.10)

    n_seeds = _resolve_n_seeds(trial, cfg)
    trial.set_user_attr("n_seeds_used", n_seeds)
    sim = _run_ensemble(
        run_model_fn,
        n_seeds=n_seeds,
        base_seed=cfg.model_seed,
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

    harmonic_loss = _harmonic_loss_per_region(ref, sim, weight_amp=cfg.harmonic_weight, weight_phase=0.0)

    # combine (tune the multiplier)
    loss = ts_loss + 0.5 * scalar_loss + harmonic_loss


    trial.set_user_attr("ts_loss", float(ts_loss))
    trial.set_user_attr("scalar_loss", float(scalar_loss))
    trial.set_user_attr("harmonic_loss", float(harmonic_loss))
    return float(loss)
