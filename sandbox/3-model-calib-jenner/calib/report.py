"""
3-Stage Measles Calibration Report
Generates a comprehensive multi-panel figure covering:
  - Summary table
  - Loss convergence per stage (by trial)
  - Wall-clock timing: loss vs cumulative CPU time + per-stage cost breakdown
  - Parameter recovery vs ground truth + loss component breakdown
  - Best-fit epidemic curves vs reference (ABM stage)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np
import polars as pl

DB_PATH = "calib.db"
REF_CSV = "truth_reference/biweekly_region_reference.csv"
OUT_PNG = "calib/plots/calibration_report.png"

TRUTH = {
    "R0_init": 5.0,
    "beta": 0.8,
    "seasonality": 0.15,
    "import_rate": 0.05,
    "L": 1.5,
    "eps": 0.05,
}

STAGES = [
    ("calib_v2_biweekly",      "Stage 1\nBiweekly",      "#4C72B0"),
    ("calib_v2_compartmental", "Stage 2\nCompartmental",  "#DD8452"),
    ("calib_v2_abm_v3",        "Stage 3\nABM v3",          "#55A868"),
]

REGION_LABELS = {
    "R0_metro": "Metro (R0)",
    "R1_nw":    "NW (R1)",
    "R2_ne":    "NE (R2)",
    "R3_sw":    "SW (R3)",
    "R4_se":    "SE (R4)",
}
REGION_ORDER = ["R0_metro", "R1_nw", "R2_ne", "R3_sw", "R4_se"]


# ── helpers ──────────────────────────────────────────────────────────────────

def load_study(conn, study_name):
    sid = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=?", (study_name,)
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT t.trial_id, t.number, v.value
           FROM trials t
           JOIN trial_values v ON t.trial_id=v.trial_id
           WHERE t.study_id=? AND t.state='COMPLETE'
           ORDER BY t.number""",
        (sid,),
    ).fetchall()
    return rows


def load_timing(conn, study_name):
    """
    Return list of (duration_s, loss) sorted by completion order.
    duration_s = elapsed seconds for that individual trial.
    """
    sid = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=?", (study_name,)
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT v.value, t.datetime_start, t.datetime_complete
           FROM trials t
           JOIN trial_values v ON t.trial_id=v.trial_id
           WHERE t.study_id=? AND t.state='COMPLETE'
             AND t.datetime_start IS NOT NULL AND t.datetime_complete IS NOT NULL
           ORDER BY t.datetime_complete""",
        (sid,),
    ).fetchall()
    result = []
    for loss, ts, tc in rows:
        s = datetime.fromisoformat(ts)
        e = datetime.fromisoformat(tc)
        result.append((max(0.0, (e - s).total_seconds()), loss))
    return result


def best_trial(conn, study_name):
    sid = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=?", (study_name,)
    ).fetchone()[0]
    row = conn.execute(
        """SELECT t.trial_id, t.number, v.value
           FROM trials t JOIN trial_values v ON t.trial_id=v.trial_id
           WHERE t.study_id=? AND t.state='COMPLETE'
           ORDER BY v.value LIMIT 1""",
        (sid,),
    ).fetchone()
    params = dict(
        conn.execute(
            "SELECT param_name, param_value FROM trial_params WHERE trial_id=?",
            (row[0],),
        ).fetchall()
    )
    attrs = dict(
        conn.execute(
            """SELECT key, CAST(value_json AS REAL)
               FROM trial_user_attributes
               WHERE trial_id=? AND key IN ('ts_loss','scalar_loss','harmonic_loss')""",
            (row[0],),
        ).fetchall()
    )
    return row[2], params, attrs


def running_best(values):
    best, out = float("inf"), []
    for v in values:
        if v < best:
            best = v
        out.append(best)
    return out


def run_best_abm(params, n_seeds=5):
    from calib.run_abm import run_abm_model

    dfs = []
    for seed in range(300, 300 + n_seeds):
        df = run_abm_model(
            seed=seed,
            years=3,
            R0_init=params["R0_init"],
            beta=params["beta"],
            seasonality=params["seasonality"],
            season_start=0,
            import_rate=params["import_rate"],
            L=params["L"],
            eps=params["eps"],
        )
        dfs.append(df)

    combined = pl.concat(dfs)
    return (
        combined.group_by(["region", "biweek"])
        .agg(
            pl.col("cases").mean().alias("mean"),
            pl.col("cases").std().alias("sd"),
        )
        .sort(["region", "biweek"])
    )


# ── figure ────────────────────────────────────────────────────────────────────

def make_report():
    Path("calib/plots").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    ref = pl.read_csv(REF_CSV)

    # ── collect per-stage data ──
    stage_data = []
    for sname, label, color in STAGES:
        rows = load_study(conn, sname)
        loss, params, attrs = best_trial(conn, sname)
        timing = load_timing(conn, sname)
        stage_data.append(
            dict(
                name=sname, label=label, color=color,
                rows=rows, best_loss=loss, params=params, attrs=attrs,
                timing=timing,
            )
        )

    print("Running best ABM model (5 seeds)…")
    abm_sim = run_best_abm(stage_data[2]["params"], n_seeds=5)
    print("Done.")

    conn.close()

    # ── pre-compute timing series ──
    # Cumulative CPU seconds (sum of individual trial durations) across all stages
    # chain: stage1 → stage2 → stage3
    all_cumtime = []  # seconds from start of stage 1
    all_runbest = []  # running best loss across all stages
    stage_start_s = []   # cumulative CPU-s at the start of each stage
    stage_end_s = []     # cumulative CPU-s at the end of each stage
    stage_total_s = []   # total CPU-s per stage
    stage_mean_s = []    # mean CPU-s per trial per stage

    offset = 0.0
    global_best = float("inf")
    for sd in stage_data:
        stage_start_s.append(offset)
        for dur, loss in sd["timing"]:
            offset += dur
            all_cumtime.append(offset)
            if loss < global_best:
                global_best = loss
            all_runbest.append(global_best)
        stage_end_s.append(offset)
        stage_total_s.append(sum(d for d, _ in sd["timing"]))
        stage_mean_s.append(
            float(np.mean([d for d, _ in sd["timing"]])) if sd["timing"] else 0.0
        )

    total_cpu_s = offset
    stage1_s = stage_total_s[0]
    stage12_s = stage_total_s[0] + stage_total_s[1]

    # ── layout: 5 rows ──
    fig = plt.figure(figsize=(22, 28), facecolor="#FAFAFA")
    fig.suptitle(
        "3-Stage Measles Calibration: Biweekly → Compartmental → ABM",
        fontsize=18, fontweight="bold", y=0.99,
    )

    outer = gridspec.GridSpec(
        5, 1, figure=fig,
        hspace=0.50,
        height_ratios=[0.07, 0.9, 0.85, 1.05, 1.25],
    )

    # ── Row 0: summary table ──────────────────────────────────────────────────
    ax_tbl = fig.add_subplot(outer[0])
    ax_tbl.axis("off")
    col_labels = ["Stage", "Model", "Trials", "CPU time", "s/trial",
                  "Best Loss", "ts_loss", "scalar_loss", "harmonic_loss",
                  "R₀_init", "β", "seas", "import_rate", "L", "ε"]
    truth_row = ["", "Truth", "", "", "", "", "", "", "",
                 "5.00", "0.800", "0.150", "0.050", "1.500", "0.050"]
    rows_tbl = [truth_row]
    for i, sd in enumerate(stage_data):
        n = len(sd["rows"])
        p, a = sd["params"], sd["attrs"]
        tot_s = stage_total_s[i]
        mean_s = stage_mean_s[i]
        if tot_s >= 60:
            time_str = f"{tot_s/60:.1f} min"
        else:
            time_str = f"{tot_s:.0f} s"
        rows_tbl.append([
            sd["label"].replace("\n", " "),
            sd["name"].replace("calib_v2_", ""),
            str(n),
            time_str,
            f"{mean_s:.1f}",
            f"{sd['best_loss']:.2f}",
            f"{a.get('ts_loss', 0):.2f}",
            f"{a.get('scalar_loss', 0):.2f}",
            f"{a.get('harmonic_loss', 0):.2f}",
            f"{p['R0_init']:.3f}",
            f"{p['beta']:.3f}",
            f"{p['seasonality']:.3f}",
            f"{p['import_rate']:.4f}",
            f"{p['L']:.3f}",
            f"{p['eps']:.4f}",
        ])

    tbl = ax_tbl.table(
        cellText=rows_tbl, colLabels=col_labels,
        loc="center", cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.6)
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2C3E50")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    for j in range(len(col_labels)):
        tbl[1, j].set_facecolor("#ECF0F1")
    for i, clr in enumerate(["#D6E4F7", "#FDEBD0", "#D5F5E3"]):
        for j in range(len(col_labels)):
            tbl[i + 2, j].set_facecolor(clr)

    # ── Row 1: per-stage convergence (by trial number) ────────────────────────
    conv_gs = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=outer[1], wspace=0.30
    )
    for i, sd in enumerate(stage_data):
        ax = fig.add_subplot(conv_gs[i])
        trial_nums = [r[1] for r in sd["rows"]]
        losses = [r[2] for r in sd["rows"]]
        rb = running_best(losses)

        step = max(1, len(losses) // 500)
        ax.scatter(trial_nums[::step], losses[::step],
                   s=4, alpha=0.25, color=sd["color"], rasterized=True)
        ax.plot(trial_nums, rb, color=sd["color"], lw=2, label="Running best")
        ax.axhline(sd["best_loss"], color="crimson", lw=1.2, ls="--",
                   label=f"Best = {sd['best_loss']:.2f}")

        # annotate s/trial in corner
        ax.text(0.97, 0.97,
                f"{stage_mean_s[i]:.1f} s/trial\n{stage_total_s[i]/60:.1f} min total",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=8, color="#333333",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7, ec="lightgray"))

        ax.set_yscale("log")
        ax.set_title(sd["label"].replace("\n", " "), fontsize=11, fontweight="bold")
        ax.set_xlabel("Trial number", fontsize=9)
        ax.set_ylabel("Loss (log scale)", fontsize=9)
        ax.legend(fontsize=8)
        ax.set_facecolor("#F8F9FA")
        ax.grid(True, alpha=0.3)

    # ── Row 2: wall-clock timing ───────────────────────────────────────────────
    timing_gs = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[2], wspace=0.35, width_ratios=[2.2, 1]
    )

    # 2a: loss vs cumulative CPU time (the main "time savings" chart)
    ax_time = fig.add_subplot(timing_gs[0])

    # shade each stage region
    stage_shade = ["#D6E4F7", "#FDEBD0", "#D5F5E3"]
    for i, (ss, se) in enumerate(zip(stage_start_s, stage_end_s)):
        ax_time.axvspan(ss / 60, se / 60, alpha=0.18, color=stage_data[i]["color"],
                        label=f"_{i}")  # no legend entry; labels added below

    # draw the combined running-best curve, coloured by stage
    # build per-stage segments
    all_cumtime_min = [t / 60 for t in all_cumtime]
    ax_time.plot(all_cumtime_min, all_runbest, color="#222222", lw=2.5, zorder=5,
                 label="Running best (all stages)")

    # overlay each stage's segment in its own colour
    idx = 0
    for i, sd in enumerate(stage_data):
        n = len(sd["timing"])
        seg_t = all_cumtime_min[idx: idx + n]
        seg_l = all_runbest[idx: idx + n]
        if seg_t:
            ax_time.plot(seg_t, seg_l, color=sd["color"], lw=3.5, zorder=6,
                         label=sd["label"].replace("\n", " "), alpha=0.85)
        idx += n

    # vertical stage-transition lines
    for i, (ss, se) in enumerate(zip(stage_start_s, stage_end_s)):
        if i > 0:
            ax_time.axvline(ss / 60, color="#666666", lw=1.2, ls="--", zorder=4)
            ax_time.text(ss / 60 + total_cpu_s / 60 * 0.005,
                         ax_time.get_ylim()[1] if ax_time.get_ylim()[1] > 1 else 1000,
                         f"Start\nStage {i+1}", fontsize=7.5, va="top", color="#555555")

    # annotate the cheap investment vs expensive ABM
    cheap_end_min = stage12_s / 60
    abm_start_loss = all_runbest[len(stage_data[0]["timing"]) + len(stage_data[1]["timing"]) - 1]
    ax_time.annotate(
        f"Stages 1+2:\n{cheap_end_min:.0f} min,\nloss → {stage_data[1]['best_loss']:.1f}",
        xy=(cheap_end_min, stage_data[1]["best_loss"]),
        xytext=(cheap_end_min + total_cpu_s / 60 * 0.04, stage_data[1]["best_loss"] * 3),
        fontsize=8, color="#444444",
        arrowprops=dict(arrowstyle="->", color="#666", lw=1),
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8, ec="lightgray"),
    )

    ax_time.set_yscale("log")
    ax_time.set_xlabel("Cumulative CPU time (minutes)", fontsize=10)
    ax_time.set_ylabel("Best loss achieved (log scale)", fontsize=10)
    ax_time.set_title("Loss vs. Cumulative Wall-Clock Time\n(stages run sequentially; each point = one completed trial)",
                       fontsize=11, fontweight="bold")
    ax_time.legend(fontsize=8, loc="upper right")
    ax_time.set_facecolor("#F8F9FA")
    ax_time.grid(True, alpha=0.3)

    # 2b: per-stage cost breakdown (time bars + speedup)
    ax_cost = fig.add_subplot(timing_gs[1])

    stage_labels_short = ["Biweekly\n(2000 trials)", "Compart.\n(1000 trials)", "ABM\n(500 trials)"]
    times_min = [t / 60 for t in stage_total_s]
    colors = [sd["color"] for sd in stage_data]

    bars = ax_cost.barh(stage_labels_short, times_min, color=colors, alpha=0.85,
                        edgecolor="white", linewidth=0.8, height=0.5)

    # annotate each bar: time + mean s/trial + speedup vs ABM
    abm_mean = stage_mean_s[2]
    for i, (bar, tm, ms) in enumerate(zip(bars, times_min, stage_mean_s)):
        speedup = abm_mean / ms if ms > 0 else 1
        label = f"  {tm:.1f} min  |  {ms:.1f} s/trial"
        if i < 2:
            label += f"  |  {speedup:.0f}× faster than ABM"
        ax_cost.text(bar.get_width() + times_min[-1] * 0.01,
                     bar.get_y() + bar.get_height() / 2,
                     label, va="center", fontsize=7.5, color="#333333")

    # stacked total line
    ax_cost.axvline(sum(times_min), color="crimson", lw=1.5, ls=":",
                    label=f"Total: {sum(times_min):.0f} min")
    ax_cost.text(sum(times_min) * 1.01, -0.55,
                 f"Total\n{sum(times_min):.0f} min", color="crimson", fontsize=8, va="bottom")

    ax_cost.set_xlabel("Wall-clock CPU time (minutes)", fontsize=9)
    ax_cost.set_title("Per-Stage Cost\n& Speedup vs ABM", fontsize=11, fontweight="bold")
    ax_cost.set_facecolor("#F8F9FA")
    ax_cost.grid(True, alpha=0.3, axis="x")
    ax_cost.set_xlim(0, max(times_min) * 1.55)
    ax_cost.invert_yaxis()

    # ── Row 3: parameter recovery + loss components ───────────────────────────
    row3_gs = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[3], wspace=0.38, width_ratios=[2, 1]
    )

    ax_par = fig.add_subplot(row3_gs[0])
    param_keys = ["R0_init", "beta", "seasonality", "import_rate", "L", "eps"]
    param_display = ["R₀_init", "β", "seasonality", "import_rate", "L", "ε"]
    x = np.arange(len(param_keys))
    width = 0.25

    for i, sd in enumerate(stage_data):
        vals = [
            (sd["params"].get(pk, np.nan) - TRUTH[pk]) / TRUTH[pk] * 100
            for pk in param_keys
        ]
        ax_par.bar(x + (i - 1) * width, vals, width,
                   label=sd["label"].replace("\n", " "),
                   color=sd["color"], alpha=0.85, edgecolor="white", linewidth=0.5)

    ax_par.axhline(0, color="black", lw=1.5, label="Truth (0% error)")
    ax_par.axhspan(-15, 15, alpha=0.08, color="green", label="±15% band")
    ax_par.set_xticks(x)
    ax_par.set_xticklabels(param_display, fontsize=10)
    ax_par.set_ylabel("% error from truth", fontsize=10)
    ax_par.set_title("Parameter Recovery: % Error from Ground Truth", fontsize=11, fontweight="bold")
    ax_par.legend(fontsize=8, loc="upper right")
    ax_par.set_facecolor("#F8F9FA")
    ax_par.grid(True, alpha=0.3, axis="y")
    ax_par.annotate(
        "import_rate systematically\nhigh — equifinality with L\n(import_rate_hi capped at 0.08)",
        xy=(3, (stage_data[2]["params"]["import_rate"] - TRUTH["import_rate"]) / TRUTH["import_rate"] * 100),
        xytext=(3.6, 190), fontsize=7, color="crimson",
        arrowprops=dict(arrowstyle="->", color="crimson", lw=1), ha="center",
    )

    ax_lc = fig.add_subplot(row3_gs[1])
    comp_keys = ["ts_loss", "scalar_loss", "harmonic_loss"]
    comp_colors = ["#3498DB", "#E67E22", "#9B59B6"]
    comp_labels = ["Time-series (ts)", "Scalar", "Harmonic (×w)"]
    stage_labels_lc = ["Biweekly\n(2000)", "Compart.\n(1000)", "ABM v3\n(500)"]
    bottoms = np.zeros(3)
    for ck, cc, cl in zip(comp_keys, comp_colors, comp_labels):
        vals = [sd["attrs"].get(ck, 0) for sd in stage_data]
        ax_lc.bar(stage_labels_lc, vals, bottom=bottoms, color=cc, alpha=0.85,
                  edgecolor="white", linewidth=0.5, label=cl)
        bottoms += np.array(vals)
    for i, sd in enumerate(stage_data):
        ax_lc.text(i, bottoms[i] + 0.5, f"{sd['best_loss']:.1f}",
                   ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax_lc.set_ylabel("Best loss (stacked components)", fontsize=9)
    ax_lc.set_title("Loss Component\nBreakdown", fontsize=11, fontweight="bold")
    ax_lc.legend(fontsize=8, loc="upper right")
    ax_lc.set_facecolor("#F8F9FA")
    ax_lc.grid(True, alpha=0.3, axis="y")

    # ── Row 4: best-fit epidemic curves ──────────────────────────────────────
    curve_gs = gridspec.GridSpecFromSubplotSpec(
        1, 5, subplot_spec=outer[4], wspace=0.25
    )
    biweeks_per_year = 26
    total_biweeks = 3 * biweeks_per_year

    for j, region in enumerate(REGION_ORDER):
        ax = fig.add_subplot(curve_gs[j])
        rref = ref.filter(pl.col("region") == region).sort("biweek")
        bw = rref["biweek"].to_numpy()
        ax.fill_between(bw, rref["q10"].to_numpy(), rref["q90"].to_numpy(),
                        alpha=0.18, color="steelblue", label="Ref 10–90%")
        ax.plot(bw, rref["mean"].to_numpy(), color="steelblue", lw=2, label="Ref mean")

        rsim = abm_sim.filter(pl.col("region") == region).sort("biweek")
        if rsim.shape[0] > 0:
            bw_sim = rsim["biweek"].to_numpy()
            mean_sim = rsim["mean"].to_numpy()
            sd_sim = rsim["sd"].fill_null(0).to_numpy()
            ax.fill_between(bw_sim,
                            np.maximum(0, mean_sim - sd_sim), mean_sim + sd_sim,
                            alpha=0.22, color="#55A868")
            ax.plot(bw_sim, mean_sim, color="#55A868", lw=2, ls="--", label="ABM best fit")

        for yr in range(1, 3):
            ax.axvline(yr * biweeks_per_year, color="gray", lw=0.7, ls=":", alpha=0.6)

        ax.set_title(REGION_LABELS[region], fontsize=10, fontweight="bold")
        ax.set_xlabel("Biweek", fontsize=8)
        if j == 0:
            ax.set_ylabel("Cases per biweek", fontsize=9)
            ax.legend(fontsize=7, loc="upper right")
        ax.set_facecolor("#F8F9FA")
        ax.grid(True, alpha=0.2)
        ax.set_xlim(0, total_biweeks - 1)

    # ── footnote ─────────────────────────────────────────────────────────────
    fig.text(
        0.5, 0.002,
        "Reference: 10-seed ABM ensemble  |  Truth: R₀=5.0, β=0.8, seas=0.15, import=0.05, L=1.5, ε=0.05  |  "
        f"ABM best-fit: 5-seed ensemble  |  Total CPU: {total_cpu_s/60:.0f} min  |  "
        "harmonic_weight=100, import_rate_hi=0.08 for ABM v3 stage",
        ha="center", fontsize=7.5, color="#555555",
    )

    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved: {OUT_PNG}")


if __name__ == "__main__":
    make_report()
