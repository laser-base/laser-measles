"""
This module provides utility functions for the laser-measles project.

Functions:
    calc_distances(latitudes: np.ndarray, longitudes: np.ndarray, verbose: bool = False) -> np.ndarray:
        Calculate the pairwise distances between points given their latitudes and longitudes.

    calc_capacity(population: np.uint32, nticks: np.uint32, cbr: np.float32, verbose: bool = False) -> np.uint32:
        Calculate the population capacity after a given number of ticks based on a constant birth rate.

    seed_infections_randomly(model, ninfections: int = 100) -> None:
        Seed initial infections in random locations at the start of the simulation.

    seed_infections_in_patch(model, ipatch: int, ninfections: int = 100) -> None:
        Seed initial infections in a specific location at the start of the simulation.

    set_initial_susceptibility_randomly(model, susc_frac: float = 1.0) -> None:
        Set the population susceptibility level at the start of the simulation.

    set_initial_susceptibility_in_patch(model, ipatch: int, susc_frac: float = 1.0) -> None:
        Set the population susceptibility level at the start of the simulation in a specific patch.
"""

import numpy as np
from laser.core.migration import distance


def calc_distances(latitudes: np.ndarray, longitudes: np.ndarray, verbose: bool = False) -> np.ndarray:
    """
    Calculate the pairwise distances between points given their latitudes and longitudes.

    Parameters:
        latitudes (np.ndarray): A 1-dimensional array of latitudes.
        longitudes (np.ndarray): A 1-dimensional array of longitudes with the same shape as latitudes.
        verbose (bool, optional): If True, prints the upper left corner of the distance matrix. Default is False.

    Returns:
        np.ndarray: A 2-dimensional array where the element at [i, j] represents the distance between the i-th and j-th points.

    Raises:
        AssertionError: If latitudes is not 1-dimensional or if latitudes and longitudes do not have the same shape.
    """

    assert latitudes.ndim == 1, "Latitude array must be one-dimensional"
    assert longitudes.shape == latitudes.shape, "Latitude and longitude arrays must have the same shape"
    npatches = len(latitudes)
    distances = np.zeros((npatches, npatches), dtype=np.float32)
    for i, (lat, long) in enumerate(zip(latitudes, longitudes, strict=False)):
        distances[i, :] = distance(lat, long, latitudes, longitudes)

    if verbose:
        print(f"Upper left corner of distance matrix:\n{distances[0:4, 0:4]}")

    return distances


def calc_capacity(population: np.uint32, nticks: np.uint32, cbr: np.float32, verbose: bool = False) -> np.uint32:
    """
    Calculate the population capacity after a given number of ticks based on a constant birth rate (CBR).

    Args:
        population (np.uint32): The initial population.
        nticks (np.uint32): The number of ticks (time steps) to simulate.
        cbr (np.float32): The constant birth rate per 1000 people per year.
        verbose (bool, optional): If True, prints detailed population growth information. Defaults to False.

    Returns:
        np.uint32: The estimated population capacity after the given number of ticks.
    """

    # We assume a constant birth rate (CBR) for the population growth
    # The formula is: P(t) = P(0) * (1 + CBR)^t
    # where P(t) is the population at time t, P(0) is the initial population, and t is the number of ticks
    # We need to allocate space for the population data for each tick
    # We will use the maximum population growth to estimate the capacity
    # We will use the maximum population growth to estimate the capacity

    # KM we should think about unitization of births, people might want to define it otherwise.  Should we consider using a
    # package that actually handles unitization, like pint?  Probably not, but just wanted to put that here.
    daily_rate = (cbr / 1000) / 365.0  # CBR is per 1000 people per year
    capacity = np.uint32(population * (1 + daily_rate) ** nticks)

    if verbose:
        print(f"Population growth: {population:,} … {capacity:,}")
        alternate = np.uint32(population * (1 + cbr / 1000) ** (nticks / 365))  # KM What is the purpose of this line?
        print(f"Alternate growth:  {population:,} … {alternate:,}")

    return capacity


# Want to think about the ways to seed infections.  Not all infections have a timer!
def seed_infections_randomly_SI(model, ninfections: int = 100) -> None:
    """
    Seed initial infections in random locations at the start of the simulation.
    This function randomly selects individuals from the population and seeds
    them with an infection, based on the specified number of initial infections.

    Args:
        model: The simulation model containing the population and parameters.
        ninfections (int, optional): The number of initial infections to seed.
                                     Defaults to 100.

    Returns:
        None
    """

    # Seed initial infections in random locations at the start of the simulation
    cinfections = 0
    while cinfections < ninfections:
        index = model.prng.integers(0, model.population.count)
        if model.population.susceptibility[index] > 0:
            model.population.susceptibility[index] = 0
            cinfections += 1

    return


def seed_infections_randomly(model, ninfections: int = 100) -> np.ndarray:
    """
    Seed initial infections in random locations at the start of the simulation.
    This function randomly selects individuals from the population and seeds
    them with an infection, based on the specified number of initial infections.

    Args:
        model: The simulation model containing the population and parameters.
        ninfections (int, optional): The number of initial infections to seed.
                                     Defaults to 100.

    Returns:
        np.ndarray: The nodeids of the individuals seeded with an infection.
    """

    # Seed initial infections in random locations at the start of the simulation
    myinds = np.where(model.population.susceptibility > 0)[0]
    if len(myinds) > ninfections:
        myinds = np.random.choice(myinds, ninfections, replace=False)
    model.population.itimer[myinds] = model.params.inf_mean
    model.population.susceptibility[myinds] = 0
    inf_nodeids = model.population.nodeid[myinds]

    return np.array(inf_nodeids, dtype=np.uint16)


def seed_infections_in_patch(model, ipatch: int, ninfections: int = 1) -> None:
    """
    Seed initial infections in a specific patch of the population at the start of the simulation.
    This function randomly selects individuals from the specified patch and sets their infection timer
    to the mean infection duration, effectively marking them as infected. The process continues until
    the desired number of initial infections is reached.

    Args:
        model: The simulation model containing the population and parameters.
        ipatch (int): The identifier of the patch where infections should be seeded.
        ninfections (int, optional): The number of initial infections to seed. Defaults to 100.

    Returns:
        None
    """

    # Seed initial infections in a specific location at the start of the simulation
    myinds = np.where((model.population.susceptibility > 0) & (model.population.nodeid == ipatch))[0]
    if len(myinds) > ninfections:
        myinds = np.random.choice(myinds, ninfections, replace=False)
    model.population.itimer[myinds] = model.params.inf_mean
    model.population.susceptibility[myinds] = 0

    return


def set_initial_susceptibility_in_patch(model, ipatch: int, susc_frac: float = 1.0) -> None:
    """
    Set the population susceptibility level at the start of the simulation, in a specific patch.
    This function randomly selects individuals from the patch and changes
    their susceptibility to zero, according to the parameter susc_frac.

    Args:
        model: The simulation model containing the population and parameters.
        ipatch: The patch to set susceptibility in
        susc_frac (float, optional): The fraction of individuals to keep susceptible.

    Returns:
        None
    """

    # Seed initial infections in random locations at the start of the simulation
    indices = np.squeeze(np.where(model.population.nodeid == ipatch))
    patch_indices = model.prng.choice(indices, int(len(indices) * (1 - susc_frac)), replace=False)
    model.population.susceptibility[patch_indices] = 0

    return


def set_initial_susceptibility_randomly(model, susc_frac: float = 1.0) -> None:
    """
    Set the population susceptibility level at the start of the simulation.
    This function randomly selects individuals from the population and changes
    their susceptibility to zero, according to the parameter susc_frac.

    Args:
        model: The simulation model containing the population and parameters.
        susc_frac (float, optional): The fraction of individuals to keep susceptible.

    Returns:
        None
    """

    # Seed initial infections in random locations at the start of the simulation
    indices = model.prng.choice(model.population.count, int(model.population.count * (1 - susc_frac)), replace=False)
    model.population.susceptibility[indices] = 0

    return


def add_at(A: np.ndarray, indices: np.ndarray, B: np.ndarray) -> None:
    """Accumulate rows of *B* into *A* at the given indices (scatter-add).

    Args:
        A: Destination array that is updated in-place.
        indices: Index into *A* for each row of *B*.
        B: Source values to accumulate.
    """
    sorted_indices = np.argsort(indices)
    uniques, run_lengths = np.unique(indices[sorted_indices], return_counts=True)
    for i, length, end in zip(uniques, run_lengths, run_lengths.cumsum(), strict=False):
        A[i] += B[sorted_indices[end - length : end]].sum(axis=0)
