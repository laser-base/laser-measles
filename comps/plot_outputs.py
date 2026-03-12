"""
Plot SEIR time series from COMPS beta sweep.

Usage:
    python3.11 plot_outputs.py
Reads all_outputs.csv (written by retrieve_outputs.py) and writes beta_sweep.png.
"""

import polars as pl
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

df = pl.read_csv("all_outputs.csv")
beta_values = sorted(df["beta"].unique().to_list())
colors = cm.plasma(np.linspace(0.1, 0.9, len(beta_values)))

fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
compartments = ["S", "E", "I", "R"]
titles = ["Susceptible", "Exposed", "Infectious", "Recovered"]

for ax, comp, title in zip(axes.flat, compartments, titles):
    for beta, color in zip(beta_values, colors):
        sub = df.filter(pl.col("beta") == beta).sort("tick")
        r0_approx = beta * 8  # inf_mu=8 days
        ax.plot(sub["tick"].to_numpy(), sub[comp].to_numpy(), color=color, label=f"β={beta} (R0≈{r0_approx:.0f})")
    ax.set_title(title)
    ax.set_ylabel("Count")
    ax.grid(True, alpha=0.3)

axes[1, 0].set_xlabel("Day")
axes[1, 1].set_xlabel("Day")

handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(1.0, 1.0))
fig.suptitle("COMPS Beta Sweep — naive population, 8-patch linear scenario, seed=42", fontsize=13)
plt.tight_layout()
plt.savefig("beta_sweep.png", dpi=150, bbox_inches="tight")
print("Saved beta_sweep.png")
