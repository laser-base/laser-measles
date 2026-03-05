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
    args = ap.parse_args()

    storage = args.storage_url or os.environ.get("STORAGE_URL")
    if not storage:
        raise SystemExit("Provide --storage-url or set STORAGE_URL (e.g., sqlite:///calib.db)")

    cfg = ObjectiveConfig()

    study = optuna.create_study(
        study_name=args.study_name,
        storage=storage,
        direction="minimize",
        load_if_exists=True,
    )

    study.optimize(lambda t: objective(t, cfg), n_trials=args.num_trials, n_jobs=args.n_jobs)

    print("\nBest trial:")
    print("  value:", study.best_value)
    print("  params:", study.best_params)


if __name__ == "__main__":
    main()