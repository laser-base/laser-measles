import numpy as np
import pyvd
from scipy.interpolate import make_interp_spline


class WPP:
    """World Population Prospects (WPP) population data access and processing.

    This class provides access to United Nations World Population Prospects data
    for population trajectories, demographic estimates, and population pyramids.
    It uses the pyvd library to retrieve and process population data for specific
    countries, including mortality rates, birth rates, and age-structured population
    data.

    The class supports interpolation of population pyramids for any year within
    the available data range, making it useful for demographic modeling and
    population projection analysis.

    Attributes:
        country_code (str): The ISO country code for the selected country.
        year_vec (np.ndarray): Vector of years available in the WPP dataset.
        pop_mat (np.ndarray): Population matrix with shape (age_bins, years).
        vd_tup (tuple): Demographic vital data tuple containing:
            - mort_year: Mortality year reference
            - mort_mat: Mortality matrix
            - birth_rate: Birth rate data
            - br_mult_x: Birth rate multiplier x values
            - br_mult_y: Birth rate multiplier y values
        age_vec (np.ndarray): Age vector in days, representing age bins.
        pyramid_spline: Interpolating spline for population pyramid data.

    Examples:

        >>> wpp = WPP("USA")
        >>> pyramid_2020 = wpp.get_population_pyramid(2020)
        >>> print(f"Population pyramid shape: {pyramid_2020.shape}")
    """

    def __init__(self, country_code: str):
        """Initialize WPP data access for a specific country.

        Args:
            country_code (str): ISO country code (e.g., "USA", "GBR", "CHN").
                The code will be converted to uppercase automatically.

        Raises:
            ValueError: If the country code is invalid or data is unavailable.

        Note:
            Population data is adjusted by adding 0.1 to avoid zero values
            that could cause issues in demographic calculations.
        """
        # Get WPP population information from pyvd
        pop_input = pyvd.make_pop_dat(country_code.upper())
        self.country_code = country_code
        self.year_vec = pop_input[0, :]
        self.pop_mat = pop_input[1:, :] + 0.1  # age_bins x years
        self.vd_tup = pyvd.demog_vd_calc(
            self.year_vec, self.year_vec[0], self.pop_mat
        )  # ('mort_year', 'mort_mat', 'birth_rate', 'br_mult_x', 'br_mult_y')
        self.age_vec = np.concatenate([np.array(pyvd.constants.MORT_XVAL)[::2], [pyvd.constants.MORT_XVAL[-1]]])  # in days
        self.pyramid_spline = make_interp_spline(self.year_vec, self.pop_mat, axis=1)

    def get_population_pyramid(self, year: int) -> np.ndarray:
        """Get the population pyramid for a given year.

        Retrieves the age-structured population data for the specified year
        using spline interpolation. The population pyramid represents the
        distribution of population across different age groups.

        Args:
            year (int): The target year for population pyramid data.
                Must be within the available data range.

        Returns:
            np.ndarray: Population pyramid array with shape (age_bins,),
                representing population counts for each age group.

        Raises:
            AssertionError: If the requested year is outside the available
                data range (before first year or after last year).

        Examples:

            >>> wpp = WPP("USA")
            >>> pyramid_2020 = wpp.get_population_pyramid(2020)
            >>> print(f"Age groups: {len(pyramid_2020)}")
            >>> print(f"Total population: {pyramid_2020.sum():.0f}")
        """
        assert year >= self.year_vec[0], "Year is before the first year in the WPP data"
        assert year <= self.year_vec[-1], "Year is after the last year in the WPP data"
        return self.pyramid_spline(year)
