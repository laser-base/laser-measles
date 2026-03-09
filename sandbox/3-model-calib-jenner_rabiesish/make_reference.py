"""
Generate reference ensemble outputs for the 10x10 grid measles ABM.

Runs N_SEEDS independent replicates of run_grid_measles_abm(), then:
  - Computes per-patch daily incidence (approx from ΔS)
  - Aggregates to biweekly bins
  - Saves mean/SD/quantile statistics as CSVs (calibration targets)
  - Saves spatial metrics: attack rate, onset day per patch
  - Generates diagnostic plots

Usage (from sandbox/3-model-calib-jenner_rabiesish/):
    python3.11 make_reference.py
    python3.11 make_reference.py --n-seeds 20
    python3.11 make_reference.py --n-seeds 5 --base-seed 100
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import polars as pl

from reference import run_grid_measles_abm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_incidence_from_S(S_ts: np.ndarray) -> np.ndarray:
    """
    Approximate daily new infections from decrease in S.
    S_ts shape: (num_ticks, num_patches).
    Returns incidence shape: (num_ticks, num_patches); tick 0 = S[0]-S[1] etc.
    """
    diff = np.diff(S_ts, axis=0, prepend=S_ts[:1])   # (num_ticks, P)
    inc = np.maximum(0, -diff)                         # S can only fall from infection
    # tick 0 has no predecessor -> set to 0
    inc[0] = 0
    return inc.astype(np.float64)


def aggregate_biweekly(daily: np.ndarray, ticks_per_day: int = 1) -> np.ndarray:
    """
    Sum daily data (ticks, patches) into 14-day bins.
    Returns (n_biweeks, patches).
    """
    n_ticks, n_patches = daily.shape
    biweek_len = 14 * ticks_per_day
    n_full = (n_ticks // biweek_len) * biweek_len
    trimmed = daily[:n_full]
    return trimmed.reshape(-1, biweek_len, n_patches).sum(axis=1)


def onset_day(I_ts: np.ndarray) -> np.ndarray:
    """
    First tick with I > 0 per patch. NaN if never infectious.
    I_ts shape: (ticks, patches).
    """
    ticks, patches = I_ts.shape
    result = np.full(patches, np.nan)
    for p in range(patches):
        idxs = np.where(I_ts[:, p] > 0)[0]
        if idxs.size > 0:
            result[p] = idxs[0]
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-seeds", type=int, default=10)
    ap.add_argument("--base-seed", type=int, default=42)
    ap.add_argument("--years", type=int, default=3)
    args = ap.parse_args()

    N_SEEDS = args.n_seeds
    BASE_SEED = args.base_seed
    NUM_TICKS = 365 * args.years

    out_dir = Path("reference_outputs")
    plot_dir = Path("reference_plots")
    out_dir.mkdir(exist_ok=True)
    plot_dir.mkdir(exist_ok=True)

    print(f"Running {N_SEEDS} seeds × {NUM_TICKS} ticks each …")

    # Collect raw per-seed arrays
    all_S: list[np.ndarray] = []   # each (ticks, 100)
    all_I: list[np.ndarray] = []
    all_R: list[np.ndarray] = []
    all_inc: list[np.ndarray] = []
    scenario = None

    for s_i in range(N_SEEDS):
        seed = BASE_SEED + s_i
        print(f"  seed {seed} ({s_i + 1}/{N_SEEDS})", flush=True)
        model, scen, gt, pt = run_grid_measles_abm(
            num_ticks=NUM_TICKS,
            seed=seed,
            verbose=False,
        )
        if scenario is None:
            scenario = scen

        S_ts = np.array(pt.S, dtype=np.float64)   # (ticks, 100)
        I_ts = np.array(pt.I, dtype=np.float64)
        R_ts = np.array(pt.R, dtype=np.float64)
        inc = compute_incidence_from_S(S_ts)

        all_S.append(S_ts)
        all_I.append(I_ts)
        all_R.append(R_ts)
        all_inc.append(inc)
        model.cleanup()

    # Stack: (N_SEEDS, ticks, patches)
    S_stack = np.stack(all_S)
    I_stack = np.stack(all_I)
    R_stack = np.stack(all_R)
    inc_stack = np.stack(all_inc)

    pops = scenario["pop"].to_numpy().astype(float)
    total_pop = pops.sum()
    n_patches = pops.size
    n_ticks = S_stack.shape[1]
    ticks = np.arange(n_ticks)

    print("Computing summary statistics …")

    # ------------------------------------------------------------------
    # 1. Biweekly per-patch incidence reference  (main calibration CSV)
    # ------------------------------------------------------------------
    bw_per_seed = np.stack([aggregate_biweekly(inc_stack[s]) for s in range(N_SEEDS)])  # (seeds, bw, patches)
    bw_mean = bw_per_seed.mean(axis=0)    # (bw, patches)
    bw_sd   = bw_per_seed.std(axis=0)
    bw_q10  = np.quantile(bw_per_seed, 0.10, axis=0)
    bw_q50  = np.quantile(bw_per_seed, 0.50, axis=0)
    bw_q90  = np.quantile(bw_per_seed, 0.90, axis=0)

    n_bw = bw_mean.shape[0]
    patch_ids = scenario["id"].to_list()
    rows = []
    for bw in range(n_bw):
        for p in range(n_patches):
            rows.append({
                "patch_id": patch_ids[p],
                "patch_idx": p,
                "biweek": bw,
                "mean": float(bw_mean[bw, p]),
                "sd":   float(bw_sd[bw, p]),
                "q10":  float(bw_q10[bw, p]),
                "q50":  float(bw_q50[bw, p]),
                "q90":  float(bw_q90[bw, p]),
            })
    df_bw = pl.DataFrame(rows)
    df_bw.write_csv(out_dir / "biweekly_patch_incidence.csv")
    print(f"  Saved {out_dir}/biweekly_patch_incidence.csv  ({len(df_bw)} rows)")

    # ------------------------------------------------------------------
    # 2. Attack rate per patch
    # ------------------------------------------------------------------
    ar_per_seed = R_stack[:, -1, :] / pops   # (seeds, patches)
    ar_mean = ar_per_seed.mean(axis=0)
    ar_sd   = ar_per_seed.std(axis=0)
    df_ar = pl.DataFrame({
        "patch_id":  patch_ids,
        "patch_idx": list(range(n_patches)),
        "pop":       pops.tolist(),
        "lat":       scenario["lat"].to_list(),
        "lon":       scenario["lon"].to_list(),
        "mean_attack_rate": ar_mean.tolist(),
        "sd_attack_rate":   ar_sd.tolist(),
    })
    df_ar.write_csv(out_dir / "attack_rate_by_patch.csv")
    print(f"  Saved {out_dir}/attack_rate_by_patch.csv")

    # ------------------------------------------------------------------
    # 3. Onset day per patch
    # ------------------------------------------------------------------
    onset_per_seed = np.stack([onset_day(I_stack[s]) for s in range(N_SEEDS)])  # (seeds, patches)
    onset_mean = np.nanmean(onset_per_seed, axis=0)
    onset_sd   = np.nanstd(onset_per_seed, axis=0)
    df_onset = pl.DataFrame({
        "patch_id":       patch_ids,
        "patch_idx":      list(range(n_patches)),
        "lat":            scenario["lat"].to_list(),
        "lon":            scenario["lon"].to_list(),
        "mean_onset_day": onset_mean.tolist(),
        "sd_onset_day":   onset_sd.tolist(),
    })
    df_onset.write_csv(out_dir / "onset_day_by_patch.csv")
    print(f"  Saved {out_dir}/onset_day_by_patch.csv")

    # ------------------------------------------------------------------
    # 4. Global SEIR reference
    # ------------------------------------------------------------------
    # Sum across patches → (seeds, ticks)
    gS = S_stack.sum(axis=2)
    gI = I_stack.sum(axis=2)
    gR = R_stack.sum(axis=2)
    df_global = pl.DataFrame({
        "day":    list(ticks),
        "mean_S": gS.mean(axis=0).tolist(),
        "sd_S":   gS.std(axis=0).tolist(),
        "mean_I": gI.mean(axis=0).tolist(),
        "sd_I":   gI.std(axis=0).tolist(),
        "mean_R": gR.mean(axis=0).tolist(),
        "sd_R":   gR.std(axis=0).tolist(),
    })
    df_global.write_csv(out_dir / "global_seir.csv")
    print(f"  Saved {out_dir}/global_seir.csv")

    # ------------------------------------------------------------------
    # 5. Key scalar metrics
    # ------------------------------------------------------------------
    metro_idx = int(np.argmax(pops))
    total_inc_per_seed = inc_stack.sum(axis=(1, 2))  # (seeds,)
    total_ar_per_seed  = R_stack[:, -1, :].sum(axis=1) / total_pop

    peak_I_global_per_seed = I_stack.sum(axis=2).max(axis=1)
    peak_day_per_seed = I_stack.sum(axis=2).argmax(axis=1)

    metrics = {
        "n_seeds": N_SEEDS,
        "n_ticks": int(n_ticks),
        "n_patches": int(n_patches),
        "total_pop": int(total_pop),
        "metro_idx": int(metro_idx),
        "total_attack_rate_mean": float(total_ar_per_seed.mean()),
        "total_attack_rate_sd":   float(total_ar_per_seed.std()),
        "peak_global_I_mean":     float(peak_I_global_per_seed.mean()),
        "peak_global_I_sd":       float(peak_I_global_per_seed.std()),
        "peak_day_mean":          float(peak_day_per_seed.mean()),
        "peak_day_sd":            float(peak_day_per_seed.std()),
        "metro_attack_rate_mean": float(ar_per_seed[:, metro_idx].mean()),
        "metro_attack_rate_sd":   float(ar_per_seed[:, metro_idx].std()),
        "metro_onset_day_mean":   float(np.nanmean(onset_per_seed[:, metro_idx])),
        "n_patches_reached_mean": float((onset_per_seed < np.inf).sum(axis=1).mean()),
    }
    import json
    with open(out_dir / "scalar_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Saved {out_dir}/scalar_metrics.json")
    print("\n  Key metrics:")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"    {k}: {v:.3f}")
        else:
            print(f"    {k}: {v}")

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------
    print("\nGenerating plots …")
    lats = scenario["lat"].to_numpy()
    lons = scenario["lon"].to_numpy()
    n_grid = int(round(np.sqrt(n_patches)))

    def to_grid(values_flat):
        """Reshape flat patch array → (n_grid, n_grid) with origin at bottom-left."""
        g = values_flat.reshape(n_grid, n_grid)  # rows=y, cols=x
        return g  # imshow will flip; we'll use origin='lower'

    # --- Plot 1: Global SEIR ensemble ---
    fig, ax = plt.subplots(figsize=(11, 4))
    mean_S = gS.mean(axis=0); sd_S = gS.std(axis=0)
    mean_I = gI.mean(axis=0); sd_I = gI.std(axis=0)
    mean_R = gR.mean(axis=0); sd_R = gR.std(axis=0)
    for mean, sd, color, label in [
        (mean_S, sd_S, "C0", "S"),
        (mean_I, sd_I, "C1", "I"),
        (mean_R, sd_R, "C2", "R"),
    ]:
        ax.plot(ticks, mean, color=color, lw=2, label=label)
        ax.fill_between(ticks, mean - sd, mean + sd, color=color, alpha=0.2)
    ax.set_xlabel("Day"); ax.set_ylabel("Agents"); ax.set_title(f"Global SEIR  (n={N_SEEDS} seeds)")
    ax.legend(); fig.tight_layout()
    fig.savefig(plot_dir / "global_seir.png", dpi=120)
    plt.close(fig)

    # --- Plot 2: Metro + 4 nearest-neighbor patches incidence ---
    # Find 4 patches nearest metro
    dist_from_metro = np.sqrt((lons - lons[metro_idx])**2 + (lats - lats[metro_idx])**2)
    nearest = np.argsort(dist_from_metro)[:6]   # metro + 5 closest

    inc_mean = inc_stack.mean(axis=0)  # (ticks, patches)
    inc_sd   = inc_stack.std(axis=0)

    fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharey=False)
    for ax, pi in zip(axes.flat, nearest):
        m = inc_mean[:, pi]; s = inc_sd[:, pi]
        ax.plot(ticks, m, lw=1.5, color="C1")
        ax.fill_between(ticks, m - s, m + s, alpha=0.3, color="C1")
        dist = dist_from_metro[pi]
        label = "METRO" if pi == metro_idx else f"d={dist:.1f}"
        ax.set_title(f"Patch {patch_ids[pi]}  ({label})")
        ax.set_xlabel("Day"); ax.set_ylabel("Daily incidence")
    fig.suptitle("Incidence: metro + nearest neighbors  (mean ± 1 SD)")
    fig.tight_layout()
    fig.savefig(plot_dir / "incidence_metro_neighbors.png", dpi=120)
    plt.close(fig)

    # --- Plot 3: Attack rate spatial heatmap ---
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(to_grid(ar_mean), origin="lower", cmap="hot_r", vmin=0, vmax=1)
    ax.scatter([lons[metro_idx]], [lats[metro_idx]], marker="*", s=200, c="cyan", zorder=5)
    plt.colorbar(im, ax=ax, label="Mean attack rate")
    ax.set_title("Attack rate by patch (mean across seeds)")
    ax.set_xlabel("x (lon)"); ax.set_ylabel("y (lat)")
    fig.tight_layout()
    fig.savefig(plot_dir / "attack_rate_heatmap.png", dpi=120)
    plt.close(fig)

    # --- Plot 4: Onset day spatial heatmap ---
    fig, ax = plt.subplots(figsize=(7, 6))
    vmax = np.nanpercentile(onset_mean, 95)
    im = ax.imshow(to_grid(onset_mean), origin="lower", cmap="viridis_r", vmin=0, vmax=vmax)
    ax.scatter([lons[metro_idx]], [lats[metro_idx]], marker="*", s=200, c="red", zorder=5)
    plt.colorbar(im, ax=ax, label="Mean onset day")
    ax.set_title("Epidemic onset day by patch (mean across seeds)")
    ax.set_xlabel("x (lon)"); ax.set_ylabel("y (lat)")
    fig.tight_layout()
    fig.savefig(plot_dir / "onset_day_heatmap.png", dpi=120)
    plt.close(fig)

    # --- Plot 5: All 100 patches — biweekly incidence grid ---
    fig, axes = plt.subplots(n_grid, n_grid, figsize=(20, 18), sharex=True, sharey=True)
    bw_ticks = np.arange(n_bw)
    for yi in range(n_grid):
        for xi in range(n_grid):
            pi = yi * n_grid + xi
            ax = axes[n_grid - 1 - yi][xi]   # flip y so row 0 = bottom
            m = bw_mean[:, pi]; s = bw_sd[:, pi]
            ax.plot(bw_ticks, m, lw=0.8, color="C1")
            ax.fill_between(bw_ticks, m - s, m + s, alpha=0.25, color="C1")
            if pi == metro_idx:
                ax.set_facecolor("#eef8ff")
            ax.tick_params(labelsize=4)
    fig.suptitle("Biweekly incidence per patch (all 100 patches, mean ± 1 SD)", fontsize=12)
    fig.text(0.5, 0.01, "Biweek", ha="center", fontsize=9)
    fig.text(0.01, 0.5, "Incidence", va="center", rotation="vertical", fontsize=9)
    fig.tight_layout(rect=[0.02, 0.02, 1, 0.98])
    fig.savefig(plot_dir / "all_patches_biweekly.png", dpi=80)
    plt.close(fig)

    # --- Plot 6: Biweekly by distance ring ---
    # Group patches by Chebyshev distance from metro
    metro_x = int(lons[metro_idx]); metro_y = int(lats[metro_idx])
    cheby = np.maximum(np.abs(lons.astype(int) - metro_x), np.abs(lats.astype(int) - metro_y))
    rings = sorted(set(cheby.tolist()))

    fig, axes = plt.subplots(1, len(rings), figsize=(3 * len(rings), 3.5), sharey=True)
    for ax, ring in zip(axes, rings):
        pix = np.where(cheby == ring)[0]
        bw_ring = bw_per_seed[:, :, pix].sum(axis=2)  # (seeds, bw)
        m = bw_ring.mean(axis=0); s = bw_ring.std(axis=0)
        ax.plot(bw_ticks, m, lw=1.5, color="C1")
        ax.fill_between(bw_ticks, m - s, m + s, alpha=0.3, color="C1")
        ax.set_title(f"Ring {ring}  (n={len(pix)})")
        ax.set_xlabel("Biweek")
    axes[0].set_ylabel("Sum incidence")
    fig.suptitle("Biweekly incidence by Chebyshev ring from metro")
    fig.tight_layout()
    fig.savefig(plot_dir / "biweekly_by_ring.png", dpi=120)
    plt.close(fig)

    print(f"\nPlots saved to {plot_dir}/")
    print("Done.")


if __name__ == "__main__":
    main()
