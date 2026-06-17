from collections import defaultdict
from pathlib import Path
from typing import Protocol

import polars as pl
from pydantic import BaseModel
from pydantic import field_validator
from shapefile import Reader


class DemographicsGeneratorProtocol(Protocol):
    """Protocol for demographic data generators.

    Implementations provide population counts, birth rates, and mortality
    rates for the *prepare scenario* stage of the researcher workflow.
    See [`RasterPatchGenerator`][laser.measles.demographics.raster_patch.RasterPatchGenerator]
    for the primary implementation.

    Examples:

        from laser.measles.demographics.raster_patch import RasterPatchGenerator, RasterPatchParams
        from laser.measles.demographics.gadm import GADMShapefile

        shapefile = GADMShapefile("NGA")
        generator = RasterPatchGenerator(shapefile, RasterPatchParams(admin_level=2))
        scenario = generator.generate_demographics()
    """

    def generate_population(self) -> pl.DataFrame:
        """Generate a population DataFrame for all patches."""
        ...

    def generate_birth_rates(self) -> pl.DataFrame:
        """Generate birth-rate data for all patches."""
        ...

    def generate_mortality_rates(self) -> pl.DataFrame:
        """Generate mortality-rate data for all patches."""
        ...


class ShapefileProtocol(Protocol):
    """Protocol for shapefile readers used by the demographics pipeline.

    Examples:

        from laser.measles.demographics.gadm import GADMShapefile

        shapefile = GADMShapefile("NGA")  # Nigeria
        df = shapefile.get_dataframe()
    """

    def add_dotname(self) -> None:
        """Add a ``DOTNAME`` field to the shapefile for hierarchical naming."""
        ...

    def get_dataframe(self) -> pl.DataFrame:
        """Return shapefile records as a Polars DataFrame."""
        ...


class BaseShapefile(BaseModel):
    """Pydantic base for shapefile wrappers.

    Validates that the shapefile path exists on disk and provides a
    `get_dataframe` method to read records into a Polars DataFrame.

    Attributes:
        shapefile: Path to a ``.shp`` file.

    Examples:

        from laser.measles.demographics.gadm import GADMShapefile

        shapefile = GADMShapefile("NGA")
        df = shapefile.get_dataframe()
    """

    shapefile: Path

    @classmethod
    @field_validator("shapefile", mode="before")
    def convert_to_path(cls, v):
        """Convert string paths to ``Path`` and verify existence."""
        p = Path(v) if not isinstance(v, Path) else v
        if not p.exists():
            raise FileNotFoundError(f"Shapefile {p} does not exist")
        return p

    def add_dotname(self) -> None:
        """Add a ``DOTNAME`` field — subclasses override with real logic."""

    def get_dataframe(self) -> pl.DataFrame:
        """
        Get a Polars DataFrame containing the shapefile data and fields.

        Returns:
            A Polars DataFrame.
        """

        with Reader(self.shapefile) as sf:
            # Get all records and shapes
            records = []
            shapes = []
            for shaperec in sf.iterShapeRecords():
                records.append(shaperec.record)
                shapes.append(shaperec.shape)

            record_dict = defaultdict(list)
            for record in records:
                for key, value in record.as_dict().items():
                    record_dict[key].append(value)

            # Convert to DataFrame
            df = pl.DataFrame(record_dict)

            # Add shape column
            df = df.with_columns(pl.Series(name="shape", values=shapes))

            return df
