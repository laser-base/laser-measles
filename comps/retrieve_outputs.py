"""
Retrieve output.csv from each simulation in the experiment and combine them.

Usage:
    python3.11 retrieve_outputs.py
Reads experiment.id (written by run_comps.py) and writes all_outputs.csv.
"""

import io
import polars as pl
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment


def main():
    platform = Platform("CALCULON")

    exp = Experiment.from_id_file("experiment.id", platform=platform)
    exp.refresh_simulations_status()

    frames = []
    for sim in exp.simulations:
        tags = sim.tags
        assets = platform.get_files(sim, ["output.csv"])
        if "output.csv" not in assets:
            print(f"  sim {sim.id}: output.csv not found")
            continue
        df = pl.read_csv(io.BytesIO(assets["output.csv"]))
        frames.append(df)
        peak_i = df["I"].max()
        beta = tags.get("beta", "?")
        print(f"  beta={beta:>5}  peak_I={peak_i:>8,}  rows={len(df)}")

    combined = pl.concat(frames)
    combined.write_csv("all_outputs.csv")
    print(f"\nCombined {len(frames)} simulations → all_outputs.csv ({len(combined):,} rows)")


if __name__ == "__main__":
    main()
