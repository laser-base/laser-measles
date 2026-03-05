import polars as pl
import numpy as np
import matplotlib.pyplot as plt

df = pl.read_csv("truth_outputs/weekly_seed_123.csv")
regions = sorted(df["region"].unique().to_list())

# pivot to matrix (rows=regions, cols=week)
piv = (
    df.pivot(values="cases", index="region", columns="week", aggregate_function="first")
    .sort("region")
)

# extract numeric weeks in sorted order
week_cols = [c for c in piv.columns if c != "region"]
week_cols = sorted(week_cols, key=lambda x: int(x))
mat = piv.select(week_cols).to_numpy()

plt.imshow(mat, aspect="auto")
plt.yticks(range(len(regions)), regions)
plt.colorbar(label="Weekly cases")
plt.title("Weekly incidence heatmap (seed 123)")
plt.xlabel("Week")
plt.ylabel("Region")
plt.tight_layout()
plt.show()