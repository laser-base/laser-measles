from collections.abc import Callable

import numpy as np
import polars as pl


def pairwise_haversine(df: pl.DataFrame) -> np.ndarray:  # TODO: use angular separation formula instead
    """Pairwise distances for all (lon, lat) points using the Haversine formula.

    Args:
        df (pl.DataFrame): Polars DataFrame with 'lon' and 'lat' columns

    Returns:
        Pairwise distances in kilometers
    """

    # mean earth radius in km
    earth_radius_km = 6367

    # convert from degrees to radians using polars
    data = np.deg2rad(df[["lon", "lat"]].to_numpy())
    lon = data[:, 0]
    lat = data[:, 1]

    # matrices of pairwise differences for latitudes & longitudes
    dlat = lat[:, None] - lat
    dlon = lon[:, None] - lon

    # vectorized haversine distance calculation
    d = np.sin(dlat / 2) ** 2 + np.cos(lat[:, None]) * np.cos(lat) * np.sin(dlon / 2) ** 2
    return 2 * earth_radius_km * np.arcsin(np.sqrt(d))


def get_diffusion_matrix(df: pl.DataFrame, scale: float, func: Callable, f_kwargs: dict, enforce_scale: bool = True) -> np.ndarray:
    if len(df) == 1:
        return np.ones((1, 1))

    # calculate diffusion matrix
    diffusion_matrix = func(**f_kwargs)

    # Normalize to get the base mixing matrix (average row sum = 1)
    normalized_matrix = diffusion_matrix / np.mean(np.sum(diffusion_matrix, axis=1))

    if enforce_scale:
        # Calculate the maximum valid scale that keeps all diagonals non-negative
        max_valid_scale = 1.0 / np.max(np.sum(normalized_matrix, axis=1))

        # Apply the scale factor, but cap it at the maximum valid value
        effective_scale = min(scale, max_valid_scale)
        diffusion_matrix = normalized_matrix * effective_scale
    else:
        diffusion_matrix = normalized_matrix * scale

    # Calculate diagonal to make each row sum to 1
    diagonal = 1 - np.sum(diffusion_matrix, axis=1)  # normalized outbound migration by source
    np.fill_diagonal(diffusion_matrix, diagonal)

    return diffusion_matrix


def init_gravity_diffusion(df: pl.DataFrame, scale: float, dist_exp: float, enforce_scale: bool = True) -> np.ndarray:
    """Initialize a gravity diffusion matrix for population mixing. The diffusion
    matrix is a square matrix where each row represents the outbound migration
    from a given patch to all other patches e.g., [i,j] = [from_i, to_j].

    Args:
        df: DataFrame with 'pop', 'lat', and 'lon' columns
        scale: Scaling factor for the diffusion matrix, i.e., the average total outbound migration
        dist_exp: Distance exponent for the gravity model, i.e., the sensitivity of migration to distance

    Returns:
        Normalized diffusion matrix where each row sums to 1
    """
    if len(df) == 1:
        return np.ones((1, 1))

    # Calculate pairwise distances
    distances = pairwise_haversine(df)

    # scale linearly with target pop
    pops = np.array(df["pop"])
    pops = pops[:, np.newaxis].T
    pops = np.repeat(pops, pops.size, axis=0).astype(np.float64)

    np.fill_diagonal(distances, 100000000)  # Prevent divide by zero errors and self migration
    diffusion_matrix = (
        pops / (distances + 10) ** dist_exp
    )  # TODO: more intelligence setting; minimum distance prevents excessive neighbor migration
    np.fill_diagonal(diffusion_matrix, 0)

    # Normalize to get the base mixing matrix (average row sum = 1)
    normalized_matrix = diffusion_matrix / np.mean(np.sum(diffusion_matrix, axis=1))

    if enforce_scale:
        # Calculate the maximum valid scale that keeps all diagonals non-negative
        max_valid_scale = 1.0 / np.max(np.sum(normalized_matrix, axis=1))

        # Apply the scale factor, but cap it at the maximum valid value
        effective_scale = min(scale, max_valid_scale)
        diffusion_matrix = normalized_matrix * effective_scale
    else:
        diffusion_matrix = normalized_matrix * scale

    # Calculate diagonal to make each row sum to 1
    diagonal = 1 - np.sum(diffusion_matrix, axis=1)  # normalized outbound migration by source
    np.fill_diagonal(diffusion_matrix, diagonal)

    return diffusion_matrix
