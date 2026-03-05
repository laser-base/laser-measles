# calib/export_best.py
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import optuna


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study-name", default="measles_biweekly_calib")
    ap.add_argument("--storage-url", default=None)
    ap.add_argument("--out", default="truth_reference/best_biweekly_params.json")
    args = ap.parse_args()

    storage = args.storage_url or os.environ.get("STORAGE_URL")
    if not storage:
        raise SystemExit("Provide --storage-url or set STORAGE_URL (e.g., sqlite:///calib.db)")

    study = optuna.load_study(study_name=args.study_name, storage=storage)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "study_name": args.study_name,
        "best_value": study.best_value,
        "best_params": study.best_params,
    }

    out.write_text(json.dumps(payload, indent=2))
    print("Wrote", out)


if __name__ == "__main__":
    main()