"""
Plot best-fit simulation vs reference for the best trial in an Optuna study.

Usage (from sandbox/3-model-calib-jenner/):
    python3.11 calib/plot_best_fit.py
    python3.11 calib/plot_best_fit.py --study-name measles_biweekly_calib
    python3.11 calib/plot_best_fit.py --storage-url sqlite:///calib.db
"""
import argparse
import os
from pathlib import Path

import optuna
import polars as pl
import matplotlib.pyplot as plt

from .objective import ObjectiveConfig

DEFAULT_STUDY = "measles_biweekly_calib_with_harmonic_scoring"
DEFAULT_STORAGE = "sqlite:///calib.db"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study-name", default=DEFAULT_STUDY)
    ap.add_argument("--storage-url", default=None)
    ap.add_argument("--seed", type=int, default=None, help="Override model seed (default: ObjectiveConfig.model_seed)")
    ap.add_argument("--model-type", default="biweekly", choices=["biweekly", "compartmental"])
    args = ap.parse_args()

    storage = args.storage_url or os.environ.get("STORAGE_URL", DEFAULT_STORAGE)

    study = optuna.load_study(study_name=args.study_name, storage=storage)
    best = study.best_trial

    print(f"Study: {args.study_name}")
    print(f"Best trial #{best.number}  loss={best.value:.4f}")
    for k in ("ts_loss", "scalar_loss", "harmonic_loss"):
        if k in best.user_attrs:
            print(f"  {k}={best.user_attrs[k]:.4f}")
    print(f"  params={best.params}")

    if args.model_type == "compartmental":
        from .run_compartmental import run_compartmental_model
        run_model_fn = run_compartmental_model
    else:
        from .run_biweekly import run_biweekly_model
        run_model_fn = run_biweekly_model

    from .objective import _run_ensemble
    cfg = ObjectiveConfig()
    seed = args.seed if args.seed is not None else cfg.model_seed
    n_seeds = best.user_attrs.get("n_seeds_used", 1)
    p = best.params

    print(f"  n_seeds_used={n_seeds} (averaging {n_seeds} seed(s) starting from {seed})")
    sim = _run_ensemble(
        run_model_fn,
        n_seeds=n_seeds,
        base_seed=seed,
        years=cfg.years,
        R0_init=p["R0_init"],
        beta=p["beta"],
        seasonality=p["seasonality"],
        season_start=p.get("season_start", 0),
        import_rate=p["import_rate"],
        L=p["L"],
        eps=p["eps"],
    )

    ref = pl.read_csv(cfg.reference_csv)

    plotdir = Path("calib/plots")
    plotdir.mkdir(exist_ok=True, parents=True)

    regions = sorted(ref["region"].unique().to_list())
    for r in regions:
        ref_r = ref.filter(pl.col("region") == r).sort("biweek")
        sim_r = sim.filter(pl.col("region") == r).sort("biweek")

        joined = ref_r.join(sim_r, on="biweek", how="inner").sort("biweek")

        t = joined["biweek"].to_numpy()
        mean = joined["mean"].to_numpy()
        sd = joined["sd"].to_numpy()
        sim_cases = joined["cases"].to_numpy()

        plt.figure(figsize=(8, 3))
        plt.plot(t, mean, color="C0", lw=2, label="Truth mean")
        plt.fill_between(t, mean - sd, mean + sd, color="C0", alpha=0.25, label="Truth ±1 sd")
        plt.plot(t, sim_cases, color="C1", lw=1.25, linestyle="--", label="Biweekly best-fit")
        plt.title(f"Region {r}  |  trial #{best.number}  loss={best.value:.2f}")
        plt.xlabel("Biweek")
        plt.ylabel("Cases")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plotdir / f"biweekly_fit_{r}.png")
        plt.close()

    print(f"Saved plots to {plotdir}/")


if __name__ == "__main__":
    main()
