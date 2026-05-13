import shutil
from pathlib import Path

import pytest
from appdirs import user_cache_dir

from laser.measles.demographics import gadm


@pytest.mark.order(1)
def test_clear_cache_dir():
    cache_dir = user_cache_dir("laser.measles", "gadm_test")
    if Path(cache_dir).exists():
        shutil.rmtree(cache_dir)
    assert not Path(cache_dir).exists()


@pytest.mark.slow
@pytest.mark.order(2)
def test_download_gadm_cuba():
    # Download Cuba's shapefile
    cache_dir = user_cache_dir("laser.measles", "gadm_test")
    gadm_shapefile = gadm.GADMShapefile.download("CUB", 0, directory=cache_dir)

    # Verify the path exists and is a file
    assert Path(gadm_shapefile.shapefile).exists()
    assert Path(gadm_shapefile.shapefile).is_file()

    # Check for expected shapefile components
    base_path = Path(gadm_shapefile.shapefile).parent
    expected_files = ["gadm41_CUB_0.shp", "gadm41_CUB_0.shx", "gadm41_CUB_0.dbf", "gadm41_CUB_0.prj"]

    for file in expected_files:
        assert (base_path / file).exists(), f"Expected file {file} not found"
