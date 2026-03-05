# calib/plot_fit_best.py
import json
from pathlib import Path
import polars as pl
import matplotlib.pyplot as plt

from calib.run_biweekly import run_biweekly_model

BAD_BEST = {
  "R0_init": 6.407312036675342,
  "beta": 0.2797172355425265,
  "seasonality": 0.08798488066951987,
  "season_start": 16,
  "import_rate": 1.8867630360725798,
  "L": 2.631357163176375,
  "eps": 0.06514743430271358,
}
BEST = {'R0_init': 7.8385612718871815, 'beta': 0.3370427715165416, 'seasonality': 0.2197966005023035, 'season_start': 19, 'import_rate': 1.8442774331127594, 'L': 2.7256798032095166, 'eps': 0.012724883745133562}

ref_weekly = pl.read_csv("truth_reference/biweekly_region_reference.csv")  # biweek, region, mean, sd

sim = run_biweekly_model(
    seed=999,
    years=3,
    R0_init=BEST["R0_init"],
    beta=BEST["beta"],
    seasonality=BEST["seasonality"],
    season_start=BEST["season_start"],
    import_rate=BEST["import_rate"],
    L=BEST["L"],
    eps=BEST["eps"],
)

# sim: region, biweek, cases  (case counts)
# join to ref for plotting
plotdir = Path("calib/plots")
plotdir.mkdir(exist_ok=True, parents=True)

regions = sorted(ref_weekly["region"].unique().to_list())
for r in regions:
    ref_r = ref_weekly.filter(pl.col("region") == r).sort("biweek")
    sim_r = sim.filter(pl.col("region") == r).sort("biweek")

    """
    t = ref_r["biweek"].to_numpy()
    mean = ref_r["mean"].to_numpy()
    sd = ref_r["sd"].to_numpy()
    sim_cases = sim_r["cases"].to_numpy()
    """
    joined = (
        ref_r.join(sim_r, on="biweek", how="inner")
             .sort("biweek")
    )

    t = joined["biweek"].to_numpy()
    mean = joined["mean"].to_numpy()
    sd = joined["sd"].to_numpy()
    sim_cases = joined["cases"].to_numpy()

    plt.figure(figsize=(8,3))
    plt.plot(t, mean, color="C0", lw=2, label="Truth mean")
    plt.fill_between(t, mean - sd, mean + sd, color="C0", alpha=0.25, label="Truth ±1 sd")
    plt.plot(t, sim_cases, color="C1", lw=1.25, linestyle="--", label="Biweekly best-fit")
    plt.title(f"Region {r}")
    plt.xlabel("Biweek")
    plt.ylabel("Cases")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plotdir / f"biweekly_fit_{r}.png")
    plt.close()

print("Saved plots to", plotdir)
