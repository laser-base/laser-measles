"""
Visual continuity check for the ABM snapshot save/load.

Runs a 3-patch scenario in two segments (seg1 → snapshot → seg2), collects
per-tick SEIR timeseries with a StateTracker, and plots all four channels
for each patch with a vertical line at the snapshot boundary.

Run directly:
    python3.11 tests/unit/plot_snapshot_continuity.py
    # → tests/unit/snapshot_continuity.png
"""

import tempfile
from pathlib import Path

import matplotlib
from matplotlib.lines import Line2D

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import polars as pl

import laser.measles as lm
from laser.measles.abm.components import InfectionProcess
from laser.measles.abm.components import InfectionSeedingProcess
from laser.measles.abm.components import StateTracker
from laser.measles.abm.snapshot import load_snapshot
from laser.measles.abm.snapshot import save_snapshot
from laser.measles.components import BaseStateTrackerParams

# ── Scenario ──────────────────────────────────────────────────────────────────

SNAP_TICKS = 55  # at epidemic peak (total I across all patches peaks ~tick 56)
SEG2_TICKS = 50  # full post-peak decline visible
SEED = 42
COMP_CLS = [InfectionSeedingProcess, InfectionProcess]

PATCH_NAMES = ["urban", "rural_a", "rural_b"]


def _scenario() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": PATCH_NAMES,
            "pop": [50_000, 20_000, 10_000],
            "lat": [0.0, 1.0, -1.0],
            "lon": [0.0, 1.0, 1.0],
            "mcv1": [0.5, 0.4, 0.3],
        }
    )


# ── Per-patch tracker params ──────────────────────────────────────────────────

# aggregation_level=0 with flat IDs → one row per (tick, patch, state)
_TRACKER_PARAMS = BaseStateTrackerParams(aggregation_level=0)


def _tracker_comp(model, verbose=False):
    return StateTracker(model, verbose=verbose, params=_TRACKER_PARAMS)


def _run_segment(scenario, params, snap_path=None, load_from=None):
    """
    Run one segment.  Returns (model, dataframe).

    * If load_from is set, load from that snapshot file.
    * If snap_path is set, save a snapshot at the end.
    """
    if load_from is not None:
        model = load_snapshot(load_from, params, components=[*COMP_CLS, _tracker_comp], verbose=True)
    else:
        model = lm.ABMModel(scenario, params)
        model.components = [*COMP_CLS, _tracker_comp]

    model.run()

    if snap_path is not None:
        save_snapshot(model, snap_path, verbose=True)

    # Find the StateTracker instance
    tracker = next(inst for inst in model.instances if isinstance(inst, StateTracker))
    df = tracker.get_dataframe()
    return model, df


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap = Path(tmpdir) / "snap.h5"
        scenario = _scenario()

        # ── Segment 1 ─────────────────────────────────────────────────────────
        p1 = lm.ABMParams(
            num_ticks=SNAP_TICKS,
            seed=SEED,
            start_time="2000-01",
            show_progress=False,
            verbose=False,
        )
        m1, df1 = _run_segment(scenario, p1, snap_path=snap)

        # ── Segment 2 (loaded from snapshot) ──────────────────────────────────
        p2 = lm.ABMParams(
            num_ticks=SEG2_TICKS,
            seed=SEED,
            start_time="2000-02",
            show_progress=False,
            verbose=False,
        )
        _, df2 = _run_segment(scenario, p2, load_from=snap)

    # Offset seg2 ticks so they continue from where seg1 left off
    df2 = df2.with_columns((pl.col("tick") + SNAP_TICKS).alias("tick"))

    df = pl.concat([df1, df2])

    # ── Plot ──────────────────────────────────────────────────────────────────
    states = m1.params.states  # ["S", "E", "I", "R"]
    # Preserve scenario order (not alphabetical)
    all_ids = PATCH_NAMES
    patches = [p for p in all_ids if p in df["patch_id"].unique().to_list()]
    n_patches = len(patches)
    n_states = len(states)

    colors = {"S": "#2196F3", "E": "#FF9800", "I": "#F44336", "R": "#4CAF50"}
    fig, axes = plt.subplots(
        n_patches,
        n_states,
        figsize=(4 * n_states, 3 * n_patches),
        sharex=True,
    )
    if n_patches == 1:
        axes = [axes]

    for pi, patch in enumerate(patches):
        for si, state in enumerate(states):
            ax = axes[pi][si]
            subset = df.filter((pl.col("patch_id") == patch) & (pl.col("state") == state))
            ticks = subset["tick"].to_numpy()
            counts = subset["count"].to_numpy()

            # Sort by tick
            order = np.argsort(ticks)
            ticks, counts = ticks[order], counts[order]

            ax.plot(ticks, counts, color=colors[state], lw=1.5, label=state)
            ax.axvline(SNAP_TICKS, color="black", lw=1.2, ls="--", label="snapshot" if si == 0 else None)

            # Mark boundary values explicitly
            if len(ticks) > 0:
                # last tick of seg1 and first tick of seg2
                seg1_mask = ticks < SNAP_TICKS
                seg2_mask = ticks >= SNAP_TICKS
                if seg1_mask.any():
                    t_end = ticks[seg1_mask][-1]
                    c_end = counts[seg1_mask][-1]
                    ax.scatter([t_end], [c_end], color=colors[state], s=40, zorder=5)
                if seg2_mask.any():
                    t_start = ticks[seg2_mask][0]
                    c_start = counts[seg2_mask][0]
                    ax.scatter([t_start], [c_start], color=colors[state], marker="x", s=60, zorder=5)

            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
            if pi == 0:
                ax.set_title(state, fontsize=11, fontweight="bold", color=colors[state])
            if si == 0:
                ax.set_ylabel(patch, fontsize=9)
            if pi == n_patches - 1:
                ax.set_xlabel("tick")

    # Legend for boundary markers
    legend_elements = [
        Line2D([0], [0], color="black", ls="--", lw=1.2, label="snapshot boundary"),
        Line2D([0], [0], marker="o", color="gray", ls="none", ms=6, label="seg1 last tick"),
        Line2D([0], [0], marker="x", color="gray", ls="none", ms=8, mew=2, label="seg2 first tick"),
    ]
    fig.legend(handles=legend_elements, loc="upper center", ncol=3, fontsize=9, bbox_to_anchor=(0.5, 1.03))

    fig.suptitle(
        f"Snapshot continuity — SEIR by patch\n"
        f"seg1={SNAP_TICKS} ticks, seg2={SEG2_TICKS} ticks, seed={SEED}\n"
        "Dots = seg1 last tick | ×s = seg2 first tick (should overlap exactly at boundary)",
        fontsize=10,
        y=1.04,
    )
    fig.tight_layout()

    out = Path(__file__).parent / "snapshot_continuity.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
