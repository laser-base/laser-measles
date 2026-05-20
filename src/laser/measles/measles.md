# Data sources

Reference links for the data sources used by laser-measles.

## Administrative boundaries

- [GADM v4.1](https://gadm.org/) — Global Administrative Areas database, used by
  [`GADMShapefile`](demographics/gadm.py) for country-level shapefiles at admin
  levels 0–2.

## Population data

- [UN World Population Prospects](https://population.un.org/wpp/) — Used by
  [`WPP`](demographics/wpp.py) for population pyramids, mortality rates, and
  birth rates via the `pyvd` library.
- [WorldPop](https://www.worldpop.org/) — Gridded population estimates used by
  [`RasterPatchGenerator`](demographics/raster_patch.py) for sub-national
  population distribution.

## Historical reference data (tutorials and tests)

The following sources were used during early development and appear in tutorials
or test fixtures:

- [Population Pyramid](https://www.populationpyramid.net/) — Visual population
  pyramid reference.
- [National Vital Statistics Reports, Volume 51, Number 3](https://www.cdc.gov/nchs/data/nvsr/nvsr51/nvsr51_03.pdf) — US
  mortality data (Table 1), used in some tutorial examples.
