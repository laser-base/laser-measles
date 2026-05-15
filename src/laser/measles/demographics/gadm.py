"""
GADM shapefiles
"""

import io
import zipfile
from pathlib import Path

import alive_progress
import pycountry
import requests
from pydantic import model_validator

from laser.measles.demographics import shapefiles
from laser.measles.demographics.admin_shapefile import AdminShapefile

VERSION = "4.1"
VERSION_INT = VERSION.replace(".", "")
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm{VERSION}/shp/gadm{VERSION_INT}_{COUNTRY_CODE}_shp.zip"
GADM_SHP_FILE = "gadm{VERSION_INT}_{COUNTRY_CODE}_{LEVEL}.shp"
DOTNAME_FIELDS_DICT = {
    0: ["COUNTRY"],
    1: ["COUNTRY", "NAME_1"],
    2: ["COUNTRY", "NAME_1", "NAME_2"],
}


class GADMShapefile(AdminShapefile):
    """Shapefile reader for GADM (Global Administrative Areas) boundary data.

    Automatically determines the admin level from the GADM filename and
    downloads shapefiles from the GADM servers when needed.  Use
    [`download`][laser.measles.demographics.gadm.GADMShapefile.download] to
    fetch a country's boundaries, or construct directly from a local file.

    **Example:**

        ```python
        gadm = GADMShapefile.download("NGA", admin_level=2, directory="./data")
        df = gadm.get_dataframe()
        ```
    """
    @model_validator(mode="after")
    def check_dotname_fields(self) -> "GADMShapefile":
        """
        Check dotname_fields from shapefile name if not explicitly provided.
        """
        if self.dotname_fields is None:
            shapefile_path = Path(self.shapefile)
            if self.admin_level is None:
                admin_level = self._parse_admin_level_from_shapefile(shapefile_path)
            else:
                admin_level = self.admin_level

            if admin_level is None:
                raise ValueError("Could not determine admin level from shapefile name. Please provide dotname_fields explicitly.")

            self.dotname_fields = DOTNAME_FIELDS_DICT[admin_level]

        # Add dotname if it doesn't exist
        if not shapefiles.check_field(self.shapefile, "DOTNAME"):
            self.add_dotname()

        return self

    @classmethod
    def _parse_admin_level_from_shapefile(cls, shapefile_path: Path) -> int | None:
        """
        Parse the admin level from the GADM shapefile name.

        Args:
            shapefile_path: Path to the shapefile

        Returns:
            The admin level if it can be determined, None otherwise
        """
        try:
            # Extract the level from the filename
            filename = shapefile_path.stem
            parts = filename.split("_")
            if len(parts) >= 3:
                level = int(parts[-1])
                if level in DOTNAME_FIELDS_DICT:
                    return level
        except (ValueError, IndexError):
            print(f"Could not determine admin level from shapefile name: {shapefile_path}")
        return None

    @classmethod
    def download(cls, country_code: str, admin_level: int, directory: str | Path | None = None, timeout: int = 60) -> "GADMShapefile":
        """
        Download the GADM shapefile for a given country code and return a GADMShapefile instance.

        Args:
            country_code: The country code to download the shapefile for.
            admin_level: The admin level to download the shapefile for.
            directory: The directory to download the shapefile to. If None, uses current directory.
            timeout: The timeout for the request.

        Returns:
            A GADMShapefile instance for the downloaded shapefile.
        """
        # Check country_code for correctness
        country = pycountry.countries.get(alpha_3=country_code.upper())
        if not country:
            raise ValueError(f"Invalid country code: {country_code}")
        if directory is None:
            directory = Path.cwd() / country_code.upper()
        download_path = Path(directory) if isinstance(directory, str) else directory
        download_path.mkdir(parents=True, exist_ok=True)

        url = GADM_URL.format(VERSION=VERSION, VERSION_INT=VERSION_INT, COUNTRY_CODE=country_code.upper())
        with alive_progress.alive_bar(
            title=f"Downloading GADM shapefile for {country.name}",
        ) as bar:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            bar.text = f"Extracting GADM shapefile for {country.name}"
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                zip_file.extractall(path=download_path)
            bar.text = f"GADM shapefile for {country.name} downloaded and extracted"

        # Initialize with the downloaded shapefile
        shapefile_path = download_path / GADM_SHP_FILE.format(VERSION_INT=VERSION_INT, COUNTRY_CODE=country_code.upper(), LEVEL=admin_level)
        return cls(shapefile=shapefile_path, dotname_fields=DOTNAME_FIELDS_DICT[admin_level])


if __name__ == "__main__":
    from appdirs import user_cache_dir

    cache_dir = user_cache_dir("laser.measles", "tmp")
    # download to directory
    gadm = GADMShapefile.download("CUB", 2, directory=cache_dir)
    df = gadm.get_dataframe()

    # load from shapefile
    g = GADMShapefile(shapefile=gadm.shapefile)
    print(df.head())
