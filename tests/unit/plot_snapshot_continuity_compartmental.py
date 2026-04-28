"""
Visual continuity check for the compartmental model snapshot save/load.

Runs a 3-patch scenario in two segments (seg1 → snapshot → seg2) and plots
all tracked channels for each patch with a vertical line at the snapshot
boundary.

Channels plotted
----------------
  Stock channels  (S, E, I, R, N)  — last seg1 dot and first seg2 x should
                                      overlap exactly at the boundary.
  Flow channels   (births, deaths, incidence) — stochastic per-tick counts;
                                      expect smooth trend, no slope jump.

Components used
---------------
  VitalDynamicsProcess - adds patches.births, patches.deaths
  InfectionSeedingProcess - seeds initial infections (seg1 only)
  InfectionProcess - adds patches.incidence

Run directly:
    python3.11 tests/unit/plot_snapshot_continuity_compartmental.py
    # → tests/unit/snapshot_continuity_compartmental.png
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
from laser.measles.compartmental import load_snapshot
from laser.measles.compartmental import save_snapshot
from laser.measles.compartmental.components import InfectionProcess
from laser.measles.compartmental.components import InfectionSeedingProcess
from laser.measles.compartmental.components import StateTracker
from laser.measles.compartmental.components import VitalDynamicsProcess
from laser.measles.components import BaseStateTrackerParams

# ── Scenario ──────────────────────────────────────────────────────────────────

SNAP_TICKS = 60  # at epidemic peak (total I peaks ~tick 60)
SEG2_TICKS = 55  # full post-peak decline visible
SEED = 42

PATCH_NAMES = ["urban", "rural_a", "rural_b"]

COMP_SEG1 = [VitalDynamicsProcess, InfectionSeedingProcess, InfectionProcess]
COMP_SEG2 = [VitalDynamicsProcess, InfectionProcess]


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


# ── Trackers ──────────────────────────────────────────────────────────────────

_TRACKER_PARAMS = BaseStateTrackerParams(aggregation_level=0)


def _state_tracker(model, verbose=False):
    return StateTracker(model, verbose=verbose, params=_TRACKER_PARAMS)


_FLOW_CHANNELS = ["births", "deaths", "incidence"]


class PatchFlowRecorder:
    """Records per-tick values of patch scalar properties (births, deaths, incidence, …)."""

    def __init__(self, model, verbose: bool = False) -> None:
        self._props = [p for p in _FLOW_CHANNELS if hasattr(model.patches, p)]
        self._records: list[tuple] = []

    def __call__(self, model, tick: int) -> None:
        for prop in self._props:
            vals = np.asarray(getattr(model.patches, prop))
            for patch_idx, v in enumerate(vals):
                self._records.append((tick, prop, patch_idx, int(v)))

    def get_dataframe(self) -> pl.DataFrame:
        if not self._records:
            return pl.DataFrame({"tick": [], "channel": [], "patch_idx": [], "value": []})
        ticks, channels, patch_idxs, values = zip(*self._records, strict=True)
        return pl.DataFrame(
            {
                "tick": list(ticks),
                "channel": list(channels),
                "patch_idx": list(patch_idxs),
                "value": list(values),
            }
        )


# ── Run helpers ───────────────────────────────────────────────────────────────


def _run_segment(scenario, params, comp_classes, snap_path=None, load_from=None):
    """Run one segment. Returns (model, seir_df, flow_df)."""
    all_comps = [*comp_classes, _state_tracker, PatchFlowRecorder]
    if load_from is not None:
        model = load_snapshot(load_from, params, components=all_comps, verbose=True)
    else:
        model = lm.CompartmentalModel(scenario, params)
        model.components = all_comps

    model.run()

    if snap_path is not None:
        save_snapshot(model, snap_path, verbose=True)

    tracker = next(inst for inst in model.instances if isinstance(inst, StateTracker))
    seir_df = tracker.get_dataframe()

    recorder = next(inst for inst in model.instances if isinstance(inst, PatchFlowRecorder))
    flow_df = recorder.get_dataframe()

    return model, seir_df, flow_df


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap = Path(tmpdir) / "snap.h5"
        scenario = _scenario()

        # ── Segment 1 ─────────────────────────────────────────────────────────
        p1 = lm.CompartmentalParams(
            num_ticks=SNAP_TICKS,
            seed=SEED,
            start_time="2000-01",
            show_progress=False,
            verbose=False,
        )
        m1, seir1, flow1 = _run_segment(scenario, p1, COMP_SEG1, snap_path=snap)

        # ── Segment 2 (loaded from snapshot) ──────────────────────────────────
        p2 = lm.CompartmentalParams(
            num_ticks=SEG2_TICKS,
            seed=SEED,
            start_time="2000-03",
            show_progress=False,
            verbose=False,
        )
        _, seir2, flow2 = _run_segment(scenario, p2, COMP_SEG2, load_from=snap)

    # Offset seg2 ticks so they continue from where seg1 left off
    seir2 = seir2.with_columns((pl.col("tick") + SNAP_TICKS).alias("tick"))
    flow2 = flow2.with_columns((pl.col("tick") + SNAP_TICKS).alias("tick"))

    seir_df = pl.concat([seir1, seir2])
    flow_df = pl.concat([flow1, flow2])

    # Derive N (total population) from SEIR sum per tick per patch
    n_df = (
        seir_df.group_by(["tick", "patch_id"])
        .agg(pl.col("count").sum().alias("value"))
        .with_columns(pl.lit("N").alias("channel"))
        .rename({"patch_id": "patch_idx"})
    )
    patch_order = {name: i for i, name in enumerate(PATCH_NAMES)}
    n_df = n_df.with_columns(pl.col("patch_idx").replace(patch_order).cast(pl.Int64))

    # ── Plot layout ───────────────────────────────────────────────────────────
    states = m1.params.states  # ["S", "E", "I", "R"]
    flow_channels_present = sorted(flow_df["channel"].unique().to_list())
    all_channels = [*states, "N", *flow_channels_present]
    n_patches = len(PATCH_NAMES)
    n_cols = len(all_channels)

    state_colors = {"S": "#2196F3", "E": "#FF9800", "I": "#F44336", "R": "#4CAF50"}
    flow_colors = {"N": "#607D8B", "births": "#9C27B0", "deaths": "#795548", "incidence": "#E91E63"}

    fig, axes = plt.subplots(
        n_patches,
        n_cols,
        figsize=(2.8 * n_cols, 3 * n_patches),
        sharex=True,
    )

    for pi, patch_name in enumerate(PATCH_NAMES):
        patch_idx = pi

        for ci, channel in enumerate(all_channels):
            ax = axes[pi][ci]
            is_stock = channel in states or channel == "N"

            if channel in states:
                subset = seir_df.filter((pl.col("patch_id") == patch_name) & (pl.col("state") == channel))
                ticks = subset["tick"].to_numpy()
                counts = subset["count"].to_numpy()
            elif channel == "N":
                subset = n_df.filter(pl.col("patch_idx") == patch_idx)
                ticks = subset["tick"].to_numpy()
                counts = subset["value"].to_numpy()
            else:
                subset = flow_df.filter((pl.col("channel") == channel) & (pl.col("patch_idx") == patch_idx))
                ticks = subset["tick"].to_numpy()
                counts = subset["value"].to_numpy()

            order = np.argsort(ticks)
            ticks, counts = ticks[order], counts[order]

            color = state_colors.get(channel, flow_colors.get(channel, "gray"))
            ax.plot(ticks, counts, color=color, lw=1.4)
            ax.axvline(SNAP_TICKS, color="black", lw=1.0, ls="--")

            if is_stock:
                seg1_mask = ticks < SNAP_TICKS
                seg2_mask = ticks >= SNAP_TICKS
                if seg1_mask.any():
                    ax.scatter([ticks[seg1_mask][-1]], [counts[seg1_mask][-1]], color=color, s=30, zorder=5)
                if seg2_mask.any():
                    ax.scatter([ticks[seg2_mask][0]], [counts[seg2_mask][0]], color=color, marker="x", s=50, zorder=5)

            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
            if pi == 0:
                ax.set_title(channel, fontsize=9, fontweight="bold", color=color)
            if ci == 0:
                ax.set_ylabel(patch_name, fontsize=8)
            if pi == n_patches - 1:
                ax.set_xlabel("tick", fontsize=8)

    legend_elements = [
        Line2D([0], [0], color="black", ls="--", lw=1.0, label="snapshot boundary"),
        Line2D([0], [0], marker="o", color="gray", ls="none", ms=5, label="seg1 last tick (stock)"),
        Line2D([0], [0], marker="x", color="gray", ls="none", ms=7, mew=2, label="seg2 first tick (stock)"),
    ]
    fig.legend(handles=legend_elements, loc="upper center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 1.03))

    fig.suptitle(
        f"Compartmental snapshot continuity — all channels by patch\n"
        f"seg1={SNAP_TICKS} ticks, seg2={SEG2_TICKS} ticks, seed={SEED}\n"
        "Stock channels: dots=seg1 last, ×s=seg2 first (should overlap). "
        "Flow channels: smooth trend only.",
        fontsize=9,
        y=1.04,
    )
    fig.tight_layout()

    out = Path(__file__).parent / "snapshot_continuity_compartmental.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
