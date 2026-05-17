# Biweekly model

Compartmental SIR model using biweekly (14-day) timesteps. Recommended for scenario building.

## Example

```python
import polars as pl
from laser.measles.biweekly import BiweeklyModel, BiweeklyParams

scenario = pl.DataFrame({
    "id": ["patch_0", "patch_1", "patch_2"],
    "lat": [0.0, 1.0, 2.0],
    "lon": [0.0, 1.0, 2.0],
    "pop": [10_000, 10_000, 10_000],
    "mcv1": [0.8, 0.8, 0.8],
})

params = BiweeklyParams(num_ticks=130, seed=42, start_time="2000-01")
model = BiweeklyModel(scenario, params)
model.run()
```
