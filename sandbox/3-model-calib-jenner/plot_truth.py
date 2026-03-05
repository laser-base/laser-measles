import polars as pl
import matplotlib.pyplot as plt

WEEKLY = "truth_outputs/weekly_seed_123.csv"
df = pl.read_csv(WEEKLY)

regions = sorted(df["region"].unique().to_list())

for r in regions:
    sub = df.filter(pl.col("region") == r).sort("week")
    plt.plot(sub["week"].to_numpy(), sub["cases"].to_numpy(), label=r)

plt.title("Weekly incidence by region (seed 123)")
plt.xlabel("Week")
plt.ylabel("Cases")
plt.legend()
plt.tight_layout()
plt.show()