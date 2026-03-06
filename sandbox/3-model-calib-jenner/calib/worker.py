# calib/worker.py
from __future__ import annotations

import argparse
import os
import optuna

from .objective import objective, ObjectiveConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study-name", default="measles_biweekly_calib")
    ap.add_argument("--num-trials", type=int, default=50)
    ap.add_argument("--storage-url", default=None, help="e.g. sqlite:///calib.db (or set STORAGE_URL)")
    ap.add_argument("--n-jobs", type=int, default=1)
    ap.add_argument(
        "--model-type", default="biweekly", choices=["biweekly", "compartmental"],
        help="Which model to calibrate against",
    )
    ap.add_argument(
        "--warm-start-study", default=None,
        help="Load best params from this study and enqueue as first trial",
    )
    args = ap.parse_args()

    storage = args.storage_url or os.environ.get("STORAGE_URL")
    if not storage:
        raise SystemExit("Provide --storage-url or set STORAGE_URL (e.g., sqlite:///calib.db)")

    if args.model_type == "compartmental":
        from .run_compartmental import run_compartmental_model
        run_model_fn = run_compartmental_model
        # beta must be re-fit (different effective scaling vs biweekly); use wide log range
        # import_rate: compartmental applies importation ~8-15x stronger than biweekly,
        # so tighten range to [0, 0.30] to prevent importation dominating transmission
        # n_seeds_refined=3: switch to 3-seed ensemble after plateau to reduce stochastic noise
        cfg = ObjectiveConfig(
            beta_lo=0.05, beta_hi=2.0,
            import_rate_hi=0.30,
            n_seeds=1, n_seeds_refined=3,
        )
    else:
        from .run_biweekly import run_biweekly_model
        run_model_fn = run_biweekly_model
        cfg = ObjectiveConfig()

    study = optuna.create_study(
        study_name=args.study_name,
        storage=storage,
        direction="minimize",
        load_if_exists=True,
    )

    # Warm-start: enqueue best params from a prior study.
    # Excluded params differ by model type:
    #   beta: different effective scaling between biweekly (SIR, 14-day tick) and compartmental (SEIR, daily tick)
    #   import_rate (compartmental only): mechanistically different — biweekly adds FOI pressure while
    #     compartmental creates direct S->E case chains, so the values are not transferable
    if args.warm_start_study:
        prior = optuna.load_study(study_name=args.warm_start_study, storage=storage)
        best = prior.best_params
        exclude = {"beta"}
        if args.model_type == "compartmental":
            exclude.add("import_rate")
        warm_params = {k: v for k, v in best.items() if k not in exclude}
        study.enqueue_trial(warm_params)
        print(f"Warm-started from '{args.warm_start_study}' (best loss={prior.best_value:.4f}), excluded: {exclude}")

    study.optimize(
        lambda t: objective(t, cfg, run_model_fn=run_model_fn),
        n_trials=args.num_trials,
        n_jobs=args.n_jobs,
    )

    print("\nBest trial:")
    print("  value:", study.best_value)
    print("  params:", study.best_params)


if __name__ == "__main__":
    main()