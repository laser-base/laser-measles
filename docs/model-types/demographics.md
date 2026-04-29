# Demographics

The demographics package provides comprehensive geographic data handling capabilities for spatial epidemiological modeling.

**Core features:**

- **GADM Integration**: `GADMShapefile` class for administrative boundary management
- **Raster processing**: `RasterPatchGenerator` for population distribution handling
- **Shapefile utilities**: Functions for geographic data visualization and analysis
- **Flexible geographic scales**: Support from national to sub-district administrative levels

**Key classes:**

- `GADMShapefile`: Manages administrative boundaries from GADM database
- `RasterPatchParams`: Configuration for raster-based population patches
- `RasterPatchGenerator`: Creates population patches from raster data
- `get_shapefile_dataframe`: Utility for shapefile data manipulation
- `plot_shapefile_dataframe`: Visualization functions for geographic data

**Example usage:**

```python
from laser.measles.demographics import GADMShapefile, RasterPatchGenerator, RasterPatchParams

# Load administrative boundaries
shapefile = GADMShapefile("ETH", admin_level=1)  # Ethiopia, admin level 1

# Generate population patches
params = RasterPatchParams(
    shapefile_path="path/to/shapefile.shp",
    raster_path="path/to/population.tif",
    patch_size=1000  # 1km patches
)
generator = RasterPatchGenerator(params)
patches = generator.generate_patches()
```

## See also

- [Model types](index.md) — overview of the three model types that consume scenario data
- [API reference](../reference/laser/measles/index.md) — full details on demographics classes
