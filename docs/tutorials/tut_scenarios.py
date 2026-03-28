# %% [markdown]
# # Creating Model Scenarios
#
# The initial conditions of the simulation are dictated by demographics (e.g., population, age distribution, etc.).
# The laser-measles package provides a number of tools to help you generate demographics for your simulation.
# These can be used for the *abm*, *compartmental*, and *biweekly* models.
#
# In this tutorial, we'll download and process a shapefile of Ethiopia at administrative level 1 boundaries
# to estimate intitial populations per patch. We will also show how we can sub-divide each boundary shape
# into roughly equal-area patches.

# %% [markdown]
# ## Setup and plot the shapefile
#
# laser-measles provides some functionality for downloading and plotting GADM shapefiles. Below we will download the data, print it as a dataframe, and then plot it. Note that we have constructed a `DOTNAME` attribute has the format `COUNTRY:REGION`. The data is located in the local directory.

# %%
from pathlib import Path

from IPython.display import display

from laser.measles.demographics import GADMShapefile
from laser.measles.demographics import get_shapefile_dataframe
from laser.measles.demographics import plot_shapefile_dataframe

# Name of the shapefile you want to use
shapefile = Path("ETH/gadm41_ETH_1.shp")

# We will check whether it exists and download it
if not shapefile.exists():
    shp = GADMShapefile.download("ETH", admin_level=1)
    print("Shapefile is now at", shp.shapefile)
else:
    print("Shapefile already exists")
    shp = GADMShapefile(shapefile=shapefile, admin_level=1)

# Access the shapfile and metadata as a polars dataframe
# This looks like geopandas but is more limited.
df = get_shapefile_dataframe(shp.shapefile)
print(df.head(n=2))
# Plot the shapefile
plot_shapefile_dataframe(df, plot_kwargs={"facecolor": "xkcd:sky blue"})

# %% [markdown]
# ## Population calculation
#
# For the simulation we will want to know the initial number of people in each region.
# First we'll download our population file (~5.6MB) from worldpop using standard libraries:

# %%
import requests

url = "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2010/ETH/eth_ppp_2010_1km_Aggregated_UNadj.tif"
output_path = Path("ETH/eth_ppp_2010_1km_Aggregated_UNadj.tif")

if not output_path.exists():
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
    else:
        print(f"Failed to download. Status code: {response.status_code}")

# %% [markdown]
# We use the `RasterPatchGenerator` to sum the population in each of the shapes.
# This is saved into a dataframe that we can use to initialize a simulation.

# %%
import sciris as sc

from laser.measles.demographics import RasterPatchGenerator
from laser.measles.demographics import RasterPatchParams

# Setup demographics generator
config = RasterPatchParams(
    id="ETH_ADM1",
    region="ETH",
    shapefile=shp.shapefile,
    population_raster=output_path,
)
# Create the generator
generator = RasterPatchGenerator(config)
# Time the population calculation
with sc.Timer() as t:
    # Generate the demographics (in this case the population per patch)
    generator.generate_demographics()
    print(f"Total population: {generator.population['pop'].sum() / 1e6:.2f} million")  # Should be ~90.5M
# the result is stored in a polars dataframe and can be accessed via `population`
generator.population.head(n=2)

# %% [markdown]
# laser-measles demographics uses caching to save results.
# Now we will run the calculation again with a new instance of the `RasterPatchGenerator`.

# %%
new_generator = RasterPatchGenerator(config)
with sc.Timer() as t:
    # # Generate the demographics (in this case the population)
    new_generator.generate_demographics()
    print(f"Total population: {new_generator.population['pop'].sum() / 1e6:.2f} million")  # Should be ~90.5M

# Note how the time to run the `generate_demographics` method a second time is greatly improved.

# %% [markdown]
# You can access the cache directory using the associated module

# %%
from laser.measles.demographics import cache

print(f"Cache directory: {cache.get_cache_dir()}")

# %% [markdown]
# ## Sub-divide the regions
#
# Now we will generate roughtly equal area patches of 700 km using the original `shp` shapefile.
# Now each shape has a unique identifier with the form `COUNTRY:REGION:ID`. We will also time how long this takes.

# %%

# Set the patch size
patch_size = 700  # sq km

# Create the GADMShapefile using the original shapefile
new_shp = GADMShapefile(shapefile=shp.shapefile, admin_level=1)

# Subdivide the original shapefile (this is costly)
new_shp.shape_subdivide(patch_size_km=patch_size)
print("Shapefile is now at", new_shp.shapefile)

# Get the results as a polars dataframe
new_df = get_shapefile_dataframe(new_shp.shapefile)
display(new_df.head(n=2))

# Plot the resulting shapes
import matplotlib.pyplot as plt

plt.figure()
ax = plt.gca()
plot_shapefile_dataframe(new_df, plot_kwargs={"facecolor": "xkcd:sky blue", "edgecolor": "gray"}, ax=ax)
plot_shapefile_dataframe(df, plot_kwargs={"fill": False}, ax=ax)
