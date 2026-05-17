from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.patches import Polygon
from shapefile import Reader
from shapefile import Writer


def check_field(path: str | Path, field_name: str) -> bool:
    """Check whether a shapefile contains a named attribute field.

    Args:
        path: Path to the ``.shp`` file.
        field_name: Field name to look for (e.g. ``"DOTNAME"``).

    Returns:
        ``True`` if the field exists in the shapefile's DBF schema.
    """
    path = Path(path) if isinstance(path, str) else path
    with Reader(path) as sf:
        fields = [field[0] for field in sf.fields[1:]]
        if field_name in fields:
            return True
        return False


def add_dotname(
    path: str | Path,
    dot_name_fields: list[str],
    dotname_symbol: str = ":",
    append_suffix: str = "dotname",
    inplace: bool = False,
    field_name: str = "DOTNAME",
) -> None:
    """
    Add a DOTNAME to the shapefile.
    """

    def make_temp_path(path: Path, append_suffix: str, suffix: str) -> Path:
        """Build a temporary file path by appending a suffix to the stem."""
        return path.with_name(path.stem + "_" + append_suffix + suffix)

    # Resolve shapefile
    path = Path(path) if isinstance(path, str) else path

    # original shapefile
    with Reader(path) as sf:
        fields = [field[0] for field in sf.fields[1:]]
        if not all(field in fields for field in dot_name_fields):
            raise ValueError(f"Dot name fields {dot_name_fields} not found in shapefile {path}. Choices are {fields}")

        if field_name in fields:
            return

        dotnames = [
            dotname_symbol.join([shaperec.record[field].lower() for field in dot_name_fields]) for shaperec in sf.iterShapeRecords()
        ]

        # check that all dotnames are unique
        if len(dotnames) != len(set(dotnames)):
            raise ValueError(f"Dotnames are not unique in shapefile {path}")

        # create a new shapefile
        with Writer(make_temp_path(path, append_suffix=append_suffix, suffix=path.suffix)) as w:
            # add the original fields
            for i, field in enumerate(sf.fields):
                if i > 0:
                    w.field(*field)
            # add the new field
            w.field(field_name, "C", 50)

            record_cnt = 0

            for _, shaperec in enumerate(sf.iterShapeRecords()):
                dotname = dotname_symbol.join([shaperec.record[field].lower() for field in dot_name_fields])
                # add the new field
                w.record(*shaperec.record, dotname)
                # add the shape
                w.shape(shaperec.shape)
                record_cnt += 1

    # copy the new shapefile to the old
    if inplace:
        for suffix in [".shp", ".shx", ".prj", ".cpg", ".prj", ".dbf"]:
            temp_path = make_temp_path(path, append_suffix=append_suffix, suffix=suffix)
            target_path = path.with_suffix(suffix)
            if temp_path.exists():
                if target_path.exists():
                    target_path.unlink()  # Remove existing file first
                temp_path.rename(target_path)


def get_shapefile_dataframe(shapefile_path: str | Path) -> pl.DataFrame:
    """
    Get a DataFrame containing the shapefile data with DOTNAME and shape columns.

    Args:
        shapefile_path: The path to the shapefile.

    Returns:
        A DataFrame with DOTNAME and shape columns.
    """
    shapefile_path = Path(shapefile_path) if isinstance(shapefile_path, str) else shapefile_path
    if not shapefile_path.exists():
        raise FileNotFoundError(f"Shapefile not found at {shapefile_path}")

    with Reader(shapefile_path) as sf:
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


def plot_shapefile_dataframe(df: pl.DataFrame, ax: plt.Axes | None = None, plot_kwargs: dict | None = None) -> plt.Figure:
    """Render shapefile polygons onto a matplotlib axes.

    Args:
        df: DataFrame returned by `get_shapefile_dataframe` containing
            a ``shape`` column.
        ax: Matplotlib axes.  A new figure is created if ``None``.
        plot_kwargs: Additional keyword arguments forwarded to
            `matplotlib.patches.Polygon`.

    Returns:
        The matplotlib `Figure` containing the rendered map.
    """
    if ax is None:
        _fig, ax = plt.subplots()
    if plot_kwargs is None:
        plot_kwargs = {}
    default_plot_kwargs = {
        "closed": True,
        "fill": True,
        "edgecolor": "black",
        "linewidth": 1.0,
        "facecolor": "white",
    }
    default_plot_kwargs.update(plot_kwargs)
    # if "facecolor" in default_plot_kwargs:
    # default_plot_kwargs["fill"] = True
    xlim = [float("inf"), float("-inf")]
    ylim = [float("inf"), float("-inf")]

    def get_data(data: list[tuple[float, float]], index: int) -> list[float]:
        """Extract the *index*-th coordinate from each point in *data*."""
        return [x[index] for x in data]

    for shape in df["shape"]:
        parts = [*shape.parts, len(shape.points)]
        for part in range(len(parts) - 1):  # Only plot first shape?
            polygon = Polygon(shape.points[parts[part] : parts[part + 1]], **default_plot_kwargs)
            ax.add_patch(polygon)
        xlim[0] = min(xlim[0], min(get_data(shape.points, 0)))
        xlim[1] = max(xlim[1], max(get_data(shape.points, 0)))
        ylim[0] = min(ylim[0], min(get_data(shape.points, 1)))
        ylim[1] = max(ylim[1], max(get_data(shape.points, 1)))
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect(1 / np.cos(np.mean(ylim) * np.pi / 180))
    ax.set_axis_off()
    return ax.figure


if __name__ == "__main__":
    df = get_shapefile_dataframe("/home/krosenfeld/code/laser-measles/examples/expanding_kano/gadm41_NGA_shp/gadm41_NGA_2_shp")
    plot_shapefile_dataframe(df)
