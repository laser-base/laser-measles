"""
Admin level shapefiles
"""

from pathlib import Path

import alive_progress
from rastertoolkit import shape_subdivide

from laser.measles.demographics import shapefiles
from laser.measles.demographics.base import BaseShapefile


class AdminShapefile(BaseShapefile):
    """
    Shapefile of administrative units.

    Attributes:
        admin_level: Admin level of the shapefile.
        dotname_fields: List of fields to use for dotname. e.g., ["ADMIN0", "ADMIN1", "ADMIN2"]

    Examples:

        from laser.measles.demographics.admin_shapefile import AdminShapefile

        shapefile = AdminShapefile("path/to/shapefile.shp")
        df = shapefile.get_dataframe()
    """

    admin_level: int | None = None
    dotname_fields: list[str] | None = None  # List of fields to use for dotname. e.g., []

    def get_shapefile_parent(self) -> Path:
        """Get the parent directory of the shapefile."""
        return self.shapefile.parent

    def add_dotname(self) -> None:
        """Add a DOTNAME to the shapefil (e.g., ADMIN0:ADMIN1:ADMIN2)"""
        shapefiles.add_dotname(self.shapefile, dot_name_fields=self.dotname_fields, inplace=True)

    def shape_subdivide(
        self,
        patch_size_km: int,
    ) -> None:
        """Subdivide the shapefile for a given administrative level into patches of approximately equal area.

        Args:
            patch_size_km (int): Size of the patch in square kilometers.
        """

        out_file = self.shapefile.parent / f"{self.shapefile.stem}_{patch_size_km}km.shp"
        if not out_file.exists():
            # Add dotname if it doesn't exist
            if not shapefiles.check_field(self.shapefile, "DOTNAME"):
                self.add_dotname()
            with alive_progress.alive_bar(
                title=f"Subdividing shapefile {self.shapefile.stem}",
            ) as _:
                shape_subdivide(
                    shape_stem=self.shapefile,
                    out_dir=self.get_shapefile_parent(),
                    out_suffix=f"{patch_size_km}km",
                    box_target_area_km2=patch_size_km,
                )
        self.shapefile = out_file
        return out_file
