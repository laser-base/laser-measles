# Demographics

The demographics package in laser-measles handles the pipeline from raw geographic data to the scenario DataFrames that all model types consume. Understanding this pipeline helps you prepare scenario data for new countries or regions and troubleshoot data-related issues.

## The data pipeline

Setting up a spatial measles simulation requires answering three questions for every patch in your study area: *where is it?* (coordinates), *how many people live there?* (population), and *what fraction are vaccinated?* (coverage). The demographics package automates this by combining administrative boundary data with population and vaccination rasters.

The pipeline flows through three stages:

```
Administrative boundaries (GADM shapefile)
        │
        ├── Clip population raster → population per patch
        ├── Clip vaccination raster → MCV1 coverage per patch
        │
        ▼
Scenario DataFrame (id, lat, lon, pop, mcv1)
```

### Stage 1: Administrative boundaries

The `GADMShapefile` class downloads and manages shapefiles from the [GADM database](https://gadm.org/), which provides administrative boundary data for every country. GADM organizes boundaries hierarchically:

- **Level 0**: Country outline
- **Level 1**: First-level administrative divisions (states, provinces, regions)
- **Level 2**: Second-level divisions (districts, counties, departments)

Each boundary polygon is identified by a `DOTNAME` field — a dot-separated string like `"Ethiopia.Amhara.North Gondar"` that encodes the administrative hierarchy. This field is used as the patch identifier throughout the pipeline.

### Stage 2: Raster clipping

The `RasterPatchGenerator` takes a shapefile and one or more raster files (GeoTIFF format) and clips the raster data to each administrative boundary. For population rasters, it sums the population within each polygon. For vaccination rasters, it computes a population-weighted average coverage within each polygon.

Results are cached locally to avoid repeating expensive raster operations. The cache is invalidated automatically when source files change.

### Stage 3: Scenario DataFrame

The output is a Polars DataFrame with one row per patch:

| Column | Type | Source |
|---|---|---|
| `id` / `dotname` | str | GADM shapefile (DOTNAME field) |
| `lat` | Float64 | Population centroid from raster clipping |
| `lon` | Float64 | Population centroid from raster clipping |
| `pop` | int | Sum of population raster within boundary |
| `mcv1` | Float64 | Population-weighted MCV1 coverage from vaccination raster |

This DataFrame is passed directly to any model constructor as the `scenario` argument.

## Key classes

### GADMShapefile

Manages administrative boundary data from the GADM database. Provides methods to download shapefiles, add DOTNAME fields, and extract DataFrames.

```python
from laser.measles.demographics import GADMShapefile

# Download admin-level 2 boundaries for Ethiopia
gadm = GADMShapefile.download("ETH", admin_level=2, directory="./data")

# Or load from an existing shapefile
gadm = GADMShapefile(shapefile="./data/gadm41_ETH_2.shp")

# Get a DataFrame of all administrative units
df = gadm.get_dataframe()
```

**Mirror override.** `GADMShapefile.download` fetches from `geodata.ucdavis.edu` by default. If UCDavis is unreachable from your network (corporate firewall, transient outage), set the `LASER_GADM_MIRROR` environment variable to point at an alternate host that mirrors GADM's path layout. The Institute for Disease Modeling maintains a mirror at `https://packages.idmod.org/artifactory/idm-data` (read-only, no auth required); the laser-measles CI workflows use it by default. To opt in locally:

```bash
export LASER_GADM_MIRROR=https://packages.idmod.org/artifactory/idm-data
python -c "from laser.measles.demographics import GADMShapefile; GADMShapefile.download('ETH', admin_level=1, directory='./data')"
```

The override replaces only the host; the path layout (`/gadm/gadm<VERSION>/shp/gadm<VERSION_INT>_<COUNTRY_CODE>_shp.zip`) must match upstream.

### RasterPatchGenerator

Generates patch-level demographic data by clipping rasters to administrative boundaries.

```python
from laser.measles.demographics import RasterPatchGenerator, RasterPatchParams

config = RasterPatchParams(
    id="ethiopia_admin2",
    region="ETH",
    shapefile="./data/gadm41_ETH_2.shp",
    population_raster="./data/eth_population.tif",
    mcv1_raster="./data/eth_mcv1_coverage.tif",
)

generator = RasterPatchGenerator(config)
generator.generate_demographics()

# Access results
population_df = generator.population   # DataFrame with dotname, lat, lon, pop
mcv1_df = generator.mcv1               # DataFrame with dotname, lat, lon, mcv1
```

### WPP

Provides access to UN World Population Prospects data for birth and mortality rates. This is used by vital dynamics components to calibrate demographic processes.

## Working with sparse or missing data

In many LMIC settings, high-resolution population rasters or vaccination coverage maps may not be available for every region. The demographics pipeline is designed to work at any administrative level — if admin-level 2 data is too granular for your available rasters, use admin-level 1 instead. You can also construct the scenario DataFrame manually from census data or survey estimates without using the raster pipeline at all.

If MCV1 coverage data is not available as a raster, you can add coverage values directly to the scenario DataFrame from DHS surveys, WHO/UNICEF estimates, or other sources:

```python
import polars as pl

scenario = pl.DataFrame({
    "id": ["Region.A", "Region.B"],
    "pop": [500000, 300000],
    "lat": [9.0, 8.5],
    "lon": [38.7, 39.1],
    "mcv1": [0.85, 0.72],  # From survey data
})
```

## See also

- [Model types](index.md) — overview of the three model types that consume scenario data
- [Tutorial: Scenarios](../../tutorials/tut_scenarios.py) — hands-on tutorial for constructing scenario data
- [Configuring spatial mixing](configuring-spatial-mixing.md) — how scenario coordinates feed into the mixing matrix
- [Choosing a model type](choosing-a-model.md) — decision guide for selecting the right model for your data
- [API reference](../../reference/laser/measles/demographics/index.md) — full details on demographics classes
