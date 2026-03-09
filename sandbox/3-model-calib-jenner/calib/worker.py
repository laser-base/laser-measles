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
        "--model-type", default="biweekly", choices=["biweekly", "compartmental", "abm"],
        help="Which model to calibrate against",
    )
    ap.add_argument(
        "--warm-start-study", default=None,
        help="Load best params from this study and enqueue as first trial",
    )
    ap.add_argument(
        "--import-rate-hi", type=float, default=None,
        help="Override import_rate upper bound (e.g. 0.08 to constrain near truth=0.05)",
    )
    args = ap.parse_args()

    storage = args.storage_url or os.environ.get("STORAGE_URL")
    if not storage:
        raise SystemExit("Provide --storage-url or set STORAGE_URL (e.g., sqlite:///calib.db)")

    if args.model_type == "compartmental":
        from .run_compartmental import run_compartmental_model
        run_model_fn = run_compartmental_model
        cfg = ObjectiveConfig(
            beta_lo=0.05, beta_hi=2.0,
            import_rate_hi=args.import_rate_hi or 0.15,
            n_seeds=1, n_seeds_refined=3,
        )
    elif args.model_type == "abm":
        from .run_abm import run_abm_model
        run_model_fn = run_abm_model
        # ABM is stochastic and expensive; switch to 3-seed ensemble after plateau.
        # Lower harmonic_weight (100 vs default 1000) prevents stochastic amplitude noise
        # from dominating the loss landscape on single-seed runs.
        cfg = ObjectiveConfig(
            beta_lo=0.05, beta_hi=2.0,
            import_rate_hi=args.import_rate_hi or 0.3,
            n_seeds=1, n_seeds_refined=3,
            harmonic_weight=100.0,
        )
    else:
        from .run_biweekly import run_biweekly_model
        run_model_fn = run_biweekly_model
        cfg = ObjectiveConfig(
            import_rate_hi=args.import_rate_hi or 0.3,
        )

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
        if args.model_type in ("compartmental", "abm"):
            # import_rate has different mechanistic meaning across model types:
            # biweekly/compartmental rely on it to spark epidemics (no seeding);
            # ABM has InfectionSeedingProcess so import_rate is purely background noise.
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