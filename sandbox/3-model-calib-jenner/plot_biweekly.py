import polars as pl
import matplotlib.pyplot as plt

BIWEEKLY = "truth_outputs/biweekly_seed_123.csv"
df = pl.read_csv(BIWEEKLY)

regions = sorted(df["region"].unique().to_list())

for r in regions:
    sub = df.filter(pl.col("region") == r).sort("biweek")
    plt.plot(sub["biweek"].to_numpy(), sub["cases"].to_numpy(), label=r)

plt.title("Biweekly incidence by region (seed 123)")
plt.xlabel("Biweek")
plt.ylabel("Cases")
plt.legend()
plt.tight_layout()
plt.show()