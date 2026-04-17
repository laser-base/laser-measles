"""
Raster patch generator for demographic data.
You can use this to generate initial conditions (e.g, population, MCV1 coverage) for a
laser-measles scenario.
"""

# from datetime import UTC # reinstate this when we drop support for Python 3.10
from datetime import datetime
from datetime import timezone  # remove this when we drop support for Python 3.10
from pathlib import Path

import alive_progress
import numpy as np
import polars as pl
from PIL import Image
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from rastertoolkit import raster_clip
from rastertoolkit import raster_clip_weighted

from laser.measles.demographics import cache
from laser.measles.demographics import shapefiles
from laser.measles.demographics.gadm import GADMShapefile


class RasterPatchParams(BaseModel):
    id: str = Field(..., description="Unique identifier for the scenario")
    region: str = Field(..., description="Country identifier (ISO3 code)")
    shapefile: str | Path = Field(..., description="Path to the shapefile")
    population_raster: str | Path | None = Field(default=None, description="Path to the population raster")
    mcv1_raster: str | Path | None = Field(default=None, description="Path to the MCV1 raster")
    mcv2_raster: str | Path | None = Field(default=None, description="Path to the MCV2 raster")

    @field_validator("shapefile")
    def shapefile_exists(cls, v, info):
        path = Path(v) if isinstance(v, str) else v
        if not path.exists():
            raise ValueError(f"Shapefile does not exist: {path}")
        return v


class RasterPatchGenerator:
    def __init__(self, config: RasterPatchParams, verbose: bool = True):
        self.config = config
        self.verbose = verbose
        self.population = None
        self.mcv1 = None
        self.mcv2 = None
        self._validate_config()

    def _get_file_mtime(self, file_path: str | Path) -> float:
        """Get the modification time of a file."""
        return Path(file_path).stat().st_mtime

    def _check_source_files_modified(self, cache_key: str) -> bool:
        """Check if any source files have been modified since cache was created."""
        with cache.load_cache() as c:
            if cache_key not in c:
                return True

            cache_entry = c[cache_key]
            if not isinstance(cache_entry, dict) or "timestamp" not in cache_entry:
                return True

            cache_time = cache_entry["timestamp"]

            # Check shapefile modification time
            if self._get_file_mtime(self.shapefile) > cache_time:
                return True

            # Check population raster modification time
            if self._get_file_mtime(self.config.population_raster) > cache_time:
                return True

            # Check MCV1 raster if it exists
            if cache_key == "mcv1" and self.config.mcv1_raster:
                if self._get_file_mtime(self.config.mcv1_raster) > cache_time:
                    return True

            return False

    def generate_demographics(self) -> None:
        self._validate_shapefile()
        self.population = self.generate_population()
        if self.config.mcv1_raster is not None:
            self.mcv1 = self.generate_mcv1()

    def _validate_config(self) -> None:
        if not shapefiles.check_field(self.config.shapefile, "DOTNAME"):
            raise ValueError(f"Shapefile {self.config.shapefile_path} does not have a DOTNAME field")

        # Validate mcv1_raster_path if provided
        if self.config.mcv1_raster is not None:
            path = Path(self.config.mcv1_raster) if isinstance(self.config.mcv1_raster, str) else self.config.mcv1_raster
            if not path.exists():
                raise FileNotFoundError(f"MCV1 raster path does not exist: {path}")

        self._validate_shapefile()

    def _validate_shapefile(self):
        """ """
        path = Path(self.config.shapefile) if isinstance(self.config.shapefile, str) else self.config.shapefile
        if not path.exists():
            raise FileNotFoundError(f"Shapefile path does not exist: {path}")
        if not shapefiles.check_field(path, "DOTNAME"):
            raise ValueError(f"Shapefile {path} does not have a DOTNAME field")
        self.shapefile = path

    def get_cache_key(self, key) -> str:
        keys = ["shapefile", "population", "mcv1"]
        if key not in keys:
            raise ValueError(f"Invalid key: {key}\nValid keys are: {keys}")
        return f"{self.config.id}" + ":" + key

    def generate_population(self) -> pl.DataFrame:
        """Population, counts"""
        cache_key = self.get_cache_key("population")

        with cache.load_cache() as c:
            if cache_key not in c or self._check_source_files_modified(cache_key):
                # clip the raster to the shapefile
                with alive_progress.alive_bar(title="Clipping population raster to shapefile"):
                    popdict = raster_clip(self.config.population_raster, self.shapefile, include_latlon=True)
                    new_dict = {"dotname": [], "lat": [], "lon": [], "pop": []}
                    for k, v in popdict.items():
                        new_dict["dotname"].append(k)
                        new_dict["lat"].append(v["lat"])
                        new_dict["lon"].append(v["lon"])
                        new_dict["pop"].append(v["pop"])

                    # Store data with timestamp
                    c[cache_key] = {"data": new_dict, "timestamp": datetime.now(timezone.utc).timestamp()}

            return pl.DataFrame(c[cache_key]["data"])

    def generate_mcv1(self) -> pl.DataFrame:
        """MCV1 coverage, population weighted"""
        cache_key = self.get_cache_key("mcv1")

        if self.config.mcv1_raster is None:
            raise ValueError("MCV1 raster path is not provided")

        with cache.load_cache() as c:
            if cache_key not in c or self._check_source_files_modified(cache_key):
                # Value array: Set negative values to zero
                new_values_raster_file = self.config.mcv1_raster.with_name(f"{self.config.mcv1_raster.stem}_zeros.tif")
                with Image.open(self.config.mcv1_raster) as raster:
                    data = np.array(raster)
                    data[data < 0] = 0
                    new_raster = Image.fromarray(data, mode=raster.mode)
                    new_raster.info.update(raster.info)  # Preserve metadata
                    new_raster.save(new_values_raster_file, tiffinfo=raster.tag_v2)

                # Weight array: Set negative values to zero
                new_weight_raster_file = self.config.population_raster.with_name(f"{self.config.population_raster.stem}_zeros.tif")
                with Image.open(self.config.population_raster) as raster:
                    data = np.array(raster)
                    data[data < 0] = np.nan
                    new_raster = Image.fromarray(data, mode=raster.mode)
                    new_raster.info.update(raster.info)  # Preserve metadata
                    new_raster.save(new_weight_raster_file, tiffinfo=raster.tag_v2)

                with alive_progress.alive_bar(title="Clipping MCV1 raster to shapefile"):
                    mcv_dict = raster_clip_weighted(
                        new_weight_raster_file,
                        new_values_raster_file,
                        shape_stem=self.config.shapefile,
                        include_latlon=True,
                        weight_summary_func=np.mean,
                    )

                # remove the rasters
                new_weight_raster_file.unlink()
                new_values_raster_file.unlink()

                # Store data with timestamp
                c[cache_key] = {"data": mcv_dict, "timestamp": datetime.now(timezone.utc).timestamp()}

        mcv_dict = c[cache_key]["data"]
        new_dict = {"dotname": [], "lat": [], "lon": [], "mcv1": []}
        for k, v in mcv_dict.items():
            new_dict["dotname"].append(k)
            new_dict["lat"].append(v["lat"])
            new_dict["lon"].append(v["lon"])
            new_dict["mcv1"].append(v["val"])

        return pl.DataFrame(new_dict)

    def clear_cache(self) -> None:
        with cache.load_cache() as c:
            for k in c.iterkeys():
                if k.startswith(self.config.id):
                    del c[k]

    def generate_birth_rates(self) -> pl.DataFrame: ...

    def generate_mortality_rates(self) -> pl.DataFrame: ...

    def _add_dotname(self) -> None: ...


if __name__ == "__main__":
    gadm = GADMShapefile("NGA")
    gadm.clear_cache()
    gadm.download()
    gadm.add_dotnames()
    config = RasterPatchParams(
        region="NGA",
        start_year=2000,
        end_year=2020,
        granularity="patch",
        patch_size_km=25,
        shapefile=gadm.get_shapefile_path(2),
        population_raster_path=gadm.shapefile_dir,
    )
    generator = RasterPatchGenerator(config)
    generator.generate_demographics()
    # print(generator.generate_population())
