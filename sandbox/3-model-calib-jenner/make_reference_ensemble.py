from pathlib import Path
import polars as pl
import numpy as np
import glob
import math

OUTDIR = Path("truth_outputs")
REFDIR = Path("truth_reference")
REFDIR.mkdir(exist_ok=True)


# ---------------------------------------------------------
# Utility: aggregate ensemble stats
# ---------------------------------------------------------

def ensemble_stats(dfs, group_cols, value_col="cases"):
    stacked = pl.concat(
        [df.with_columns(pl.lit(i).alias("replicate")) for i, df in enumerate(dfs)],
        how="vertical",
    )

    return (
        stacked
        .group_by(group_cols)
        .agg(
            pl.col(value_col).mean().alias("mean"),
            pl.col(value_col).std().alias("sd"),
            pl.col(value_col).quantile(0.10).alias("q10"),
            pl.col(value_col).quantile(0.50).alias("q50"),
            pl.col(value_col).quantile(0.90).alias("q90"),
        )
        .sort(group_cols)
    )


# ---------------------------------------------------------
# Annual harmonic (1-year frequency) for weekly series
# ---------------------------------------------------------

def annual_harmonic(df_weekly):
    """
    df_weekly must have:
        region, week, mean
    """

    results = []

    for region in df_weekly["region"].unique():
        sub = df_weekly.filter(pl.col("region") == region).sort("week")

        y = sub["mean"].to_numpy()
        t = np.arange(len(y))

        # Weekly series → 52 weeks per year
        omega = 2 * math.pi / 52.0

        sin_term = np.sin(omega * t)
        cos_term = np.cos(omega * t)

        # Linear regression: y ≈ a*sin + b*cos
        A = np.vstack([sin_term, cos_term]).T
        coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
        a, b = coeffs

        amplitude = np.sqrt(a**2 + b**2)
        phase = np.arctan2(b, a)

        results.append(
            {
                "region": region,
                "annual_amp": amplitude,
                "annual_phase": phase,
            }
        )

    return pl.DataFrame(results)


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    weekly_files = sorted(glob.glob(str(OUTDIR / "weekly_seed_*.csv")))
    biweekly_files = sorted(glob.glob(str(OUTDIR / "biweekly_seed_*.csv")))
    summary_files = sorted(glob.glob(str(OUTDIR / "summary_seed_*.csv")))

    if len(weekly_files) == 0:
        raise RuntimeError("No weekly_seed_*.csv files found.")

    print(f"Found {len(weekly_files)} replicate seeds.")

    weekly_reps = [pl.read_csv(f) for f in weekly_files]
    biweekly_reps = [pl.read_csv(f) for f in biweekly_files]
    summary_reps = [pl.read_csv(f) for f in summary_files]

    # ---------------------------------------------------------
    # Weekly reference
    # ---------------------------------------------------------
    weekly_ref = ensemble_stats(
        weekly_reps,
        group_cols=["region", "week"],
        value_col="cases",
    )

    weekly_ref.write_csv(REFDIR / "weekly_region_reference.csv")

    # ---------------------------------------------------------
    # Biweekly reference
    # ---------------------------------------------------------
    biweekly_ref = ensemble_stats(
        biweekly_reps,
        group_cols=["region", "biweek"],
        value_col="cases",
    )

    biweekly_ref.write_csv(REFDIR / "biweekly_region_reference.csv")

    # ---------------------------------------------------------
    # Scalar summaries
    # ---------------------------------------------------------
    summary_stacked = pl.concat(
        [df.with_columns(pl.lit(i).alias("replicate")) for i, df in enumerate(summary_reps)],
        how="vertical",
    )

    scalar_ref = (
        summary_stacked
        .group_by("region")
        .agg(
            pl.col("peak_biweekly").mean().alias("peak_mean"),
            pl.col("peak_biweekly").std().alias("peak_sd"),
            pl.col("cumulative_cases").mean().alias("cum_mean"),
            pl.col("cumulative_cases").std().alias("cum_sd"),
        )
        .sort("region")
    )

    scalar_ref.write_csv(REFDIR / "scalar_region_reference.csv")

    # ---------------------------------------------------------
    # Annual harmonic from weekly mean
    # ---------------------------------------------------------
    harmonic_ref = annual_harmonic(weekly_ref)
    harmonic_ref.write_csv(REFDIR / "annual_harmonic_reference.csv")

    print("\nWrote reference files to:")
    for f in REFDIR.glob("*.csv"):
        print(" -", f)


if __name__ == "__main__":
    main()