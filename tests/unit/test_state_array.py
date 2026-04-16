"""
Tests for StateArray functionality in utils.py
"""

import numpy as np
import pytest

from laser.measles.utils import StateArray


class TestStateArray:
    """Test cases for StateArray wrapper class."""

    def test_basic_creation(self):
        """Test basic StateArray creation and initialization."""
        data = np.zeros((3, 10))
        state_names = ["S", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        assert isinstance(states, np.ndarray)
        assert states.shape == (3, 10)
        assert states.state_names == (
            "S",
            "I",
            "R",
        )

    def test_attribute_access(self):
        """Test accessing states by attribute names."""
        data = np.zeros((4, 5))
        state_names = ["S", "E", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Test getter access
        assert np.array_equal(states.S, states[0])
        assert np.array_equal(states.E, states[1])
        assert np.array_equal(states.I, states[2])
        assert np.array_equal(states.R, states[3])

    def test_attribute_assignment(self):
        """Test assigning values through attribute access."""
        data = np.zeros((3, 10))
        state_names = ["S", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Test setter access
        states.S[:] = 1000
        states.I[:] = 50
        states.R[:] = 100

        assert np.all(states[0] == 1000)
        assert np.all(states[1] == 50)
        assert np.all(states[2] == 100)

    def test_slicing_operations(self):
        """Test that slicing works with attribute access."""
        data = np.random.rand(3, 10)
        state_names = ["S", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Test slicing with attributes
        patch_indices = [0, 2, 4]
        s_subset = states.S[patch_indices]
        i_subset = states.I[patch_indices]

        assert len(s_subset) == 3
        assert len(i_subset) == 3
        assert np.array_equal(s_subset, states[0, patch_indices])
        assert np.array_equal(i_subset, states[1, patch_indices])

    def test_numpy_operations(self):
        """Test that numpy operations work correctly."""
        data = np.ones((3, 5)) * 100
        state_names = ["S", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Test array operations
        total_pop = states.sum(axis=0)
        assert np.all(total_pop == 300)  # 100 + 100 + 100

        # Test prevalence calculation
        prevalence = states.I / total_pop
        assert np.all(prevalence == 1 / 3)  # 100 / 300

    def test_backward_compatibility(self):
        """Test that numeric indexing still works."""
        data = np.random.rand(4, 8)
        state_names = ["S", "E", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Both should give same results
        assert np.array_equal(states[0], states.S)
        assert np.array_equal(states[1], states.E)
        assert np.array_equal(states[2], states.I)
        assert np.array_equal(states[3], states.R)

    def test_invalid_attribute_access(self):
        """Test that invalid attribute names raise AttributeError."""
        data = np.zeros((3, 5))
        state_names = ["S", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        with pytest.raises(AttributeError):
            _ = states.X  # X is not a valid state name

        with pytest.raises(AttributeError):
            states.Y = 100  # Y is not a valid state name

    def test_different_state_configurations(self):
        """Test StateArray with different state configurations."""
        # Test SIR model (biweekly)
        sir_data = np.zeros((3, 10))
        sir_states = StateArray(source_array=sir_data, state_names=["S", "I", "R"], state_axis=0)

        assert hasattr(sir_states, "S")
        assert hasattr(sir_states, "I")
        assert hasattr(sir_states, "R")
        assert not hasattr(sir_states, "E")

        # Test SEIR model (compartmental)
        seir_data = np.zeros((4, 10))
        seir_states = StateArray(source_array=seir_data, state_names=["S", "E", "I", "R"], state_axis=0)

        assert hasattr(seir_states, "S")
        assert hasattr(seir_states, "E")
        assert hasattr(seir_states, "I")
        assert hasattr(seir_states, "R")

    def test_get_state_index(self):
        """Test the get_state_index utility method."""
        data = np.zeros((4, 5))
        state_names = ["S", "E", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        assert states.get_state_index("S") == 0
        assert states.get_state_index("E") == 1
        assert states.get_state_index("I") == 2
        assert states.get_state_index("R") == 3
        assert states.get_state_index("X") is None  # Invalid state

    # Use pytest to mark this test "skip" as it is no longer applicable
    # Consider re-enabling if __getitem__ can verify that the resulting
    # dimensionality is appropriate to the original StateArray
    @pytest.mark.skip(reason="StateArray slicing now returns a plain ndarray, so finalize is not relevant")
    def test_array_finalize(self):
        """Test that StateArray metadata is preserved during operations."""
        data = np.ones((3, 5))
        state_names = ["S", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Test that slicing preserves StateArray properties
        subset = states[:, :3]
        assert isinstance(subset, StateArray)
        assert subset.state_names == ["S", "I", "R"]

    def test_realistic_epidemiological_operations(self):
        """Test realistic epidemiological operations."""
        # Setup initial SEIR population
        num_patches = 10
        data = np.zeros((4, num_patches))
        state_names = ["S", "E", "I", "R"]
        states = StateArray(source_array=data, state_names=state_names, state_axis=0)

        # Initialize with susceptible population
        initial_pop = np.random.randint(1000, 10000, num_patches)
        states.S[:] = initial_pop

        # Simulate some infections
        new_infections = np.random.randint(0, 50, num_patches)
        states.S -= new_infections
        states.E += new_infections

        # Check conservation of population
        total_pop = states.sum(axis=0)
        assert np.allclose(total_pop, initial_pop)

        # Test prevalence calculation
        prevalence = states.I / np.maximum(total_pop, 1)
        assert np.all(prevalence >= 0)
        assert np.all(prevalence <= 1)


##########

# Additional Tests for StateArray
# Scenario: 6 epidemiological states (S, E, I, R, V, M) across 32 patches/locations.

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAMES = ["S", "E", "I", "R", "V", "M"]
NUM_STATES = len(NAMES)
NUM_PATCHES = 32
NUM_TICKS = 100
NUM_AGES = 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def zero_data() -> np.ndarray:
    """Return a zeroed (6, 32) int64 array."""
    return np.zeros((NUM_STATES, NUM_PATCHES), dtype=np.int64)


@pytest.fixture
def sample_data() -> np.ndarray:
    """Return a (6, 32) int64 array where row i is filled with the value i + 1.

    This makes it trivial to assert correct row selection: ``arr.S`` should be
    all 1s, ``arr.E`` all 2s, and so on.
    """
    data = np.zeros((NUM_STATES, NUM_PATCHES), dtype=np.int64)
    for i in range(NUM_STATES):
        data[i, :] = i + 1
    return data


@pytest.fixture
def tsp_data() -> np.ndarray:
    """Return a (100, 6, 32) int64 array where ``arr[:, i, :]`` is filled with ``i + 1``.

    Used to test the ticks × states × patches layout with states on axis 1.
    """
    data = np.zeros((NUM_TICKS, NUM_STATES, NUM_PATCHES), dtype=np.int64)
    for i in range(NUM_STATES):
        data[:, i, :] = i + 1
    return data


@pytest.fixture
def sap_data() -> np.ndarray:
    """Return a (6, 10, 32) int64 array where ``arr[i, :, :]`` is filled with ``i + 1``.

    Used to test the states × ages × patches layout with states on axis 0.
    """
    data = np.zeros((NUM_STATES, NUM_AGES, NUM_PATCHES), dtype=np.int64)
    for i in range(NUM_STATES):
        data[i, :, :] = i + 1
    return data


@pytest.fixture
def tsap_data() -> np.ndarray:
    """Return a (100, 6, 10, 32) int64 array where ``arr[:, i, :, :]`` is filled with ``i + 1``.

    Used to test the ticks × states × ages × patches layout with states on axis 1.
    """
    data = np.zeros((NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES), dtype=np.int64)
    for i in range(NUM_STATES):
        data[:, i, :, :] = i + 1
    return data


# ===========================================================================
# Construction validation
# ===========================================================================


class TestConstruction:
    """Construction-time guards for the explicit input_array path."""

    def test_valid_construction(self, zero_data):
        """Given a valid 2D array and a matching names list, construction should
        succeed with the correct shape and name registry.

        Failure here means basic construction is broken and every other test
        in this module will also fail.
        """
        # when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.shape == (NUM_STATES, NUM_PATCHES)
        assert arr.state_names == tuple(NAMES)
        assert list(arr._state_to_view.keys()) == NAMES

        return

    def test_rejects_names_shorter_than_states_dimension(self, zero_data):
        """Given a names list shorter than the states dimension of the array,
        construction should raise ValueError.

        Failure means some states have no name, making them unreachable by name
        and silently misaligning named vs. positional access.
        """
        # given - one name too few
        with pytest.raises(ValueError, match="Number of states"):
            StateArray(NAMES[:-1], 0, source_array=zero_data)

        return

    def test_rejects_names_longer_than_states_dimension(self, zero_data):
        """Given a names list longer than the states dimension of the array,
        construction should raise ValueError.

        Failure means phantom names could be registered that point to non-existent
        states.
        """
        # given - one name too many
        with pytest.raises(ValueError, match="Number of states"):
            StateArray([*NAMES, "X"], 0, source_array=zero_data)

        return

    def test_rejects_invalid_python_identifier(self, zero_data):
        """Given a name that is not a valid Python identifier, construction should
        raise ValueError.

        Failure implies the identifier guard is absent; non-identifier names could
        be registered even though attribute access for them would always raise
        AttributeError at use-time rather than at construction.
        """
        # given - "not-valid" contains a hyphen
        bad_names = [*NAMES[:-1], "not-valid"]

        # when / then
        with pytest.raises(ValueError, match="Invalid state name"):
            StateArray(bad_names, 0, source_array=zero_data)

        return

    def test_rejects_ndarray_attribute_collision(self, zero_data):
        """Given a name that shadows an existing ndarray attribute such as 'shape',
        construction should raise ValueError.

        Failure implies the collision guard is absent; the shadowing name would make
        the built-in ndarray attribute unreachable and produce confusing runtime errors.
        """
        # given - "shape" is a built-in ndarray attribute
        colliding_names = [*NAMES[:-1], "shape"]

        # when / then
        with pytest.raises(ValueError, match="collides with ndarray attribute"):
            StateArray(colliding_names, 0, source_array=zero_data)

        return


# ===========================================================================
# Allocation (shape=...)
# ===========================================================================


class TestAllocation:
    """Construction via allocation when dims is provided instead of input_array.

    When no backing array is supplied the class allocates one whose shape matches
    dims, filled with ``default`` and typed as ``dtype``.  All other
    construction-time guarantees (name registry, validation) must hold
    identically to the explicit input_array path.
    """

    def test_allocates_default_dtype_and_value(self):
        """Given shape=(NUM_STATES, NUM_PATCHES) and no other overrides, construction
        should allocate an int32 array filled with zeros.

        Failure implies the allocation path is broken entirely; every other
        allocation test will also fail.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES))

        # then
        assert arr.shape == (NUM_STATES, NUM_PATCHES)
        assert arr.dtype == np.dtype(np.int32)
        assert np.all(arr == 0)

        return

    def test_allocates_with_custom_dtype(self):
        """Given dtype=float64, the allocated array should have float64 elements.

        Failure implies the dtype argument is ignored during allocation, forcing
        callers to cast immediately after construction and breaking type safety.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES), dtype=np.float64)

        # then
        assert arr.dtype == np.dtype(np.float64)
        assert np.all(arr == 0.0)

        return

    def test_allocates_with_custom_default(self):
        """Given default=42, every element of the allocated array should be 42.

        Failure implies the default fill value is ignored; callers relying on a
        non-zero sentinel would receive silently wrong initial state.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES), default_value=42)

        # then
        assert np.all(arr == 42)

        return

    def test_allocates_with_custom_dtype_and_default(self):
        """Given dtype=float32 and default=-1.0, the allocated array should be
        float32 filled with -1.0 throughout.

        Failure implies dtype and default do not compose correctly, breaking
        callers that rely on both being honoured simultaneously.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES), dtype=np.float32, default_value=-1.0)

        # then
        assert arr.dtype == np.dtype(np.float32)
        assert np.all(arr == np.float32(-1.0))

        return

    def test_rejects_missing_dims_and_input_array(self):
        """Given neither input_array nor dims, construction should raise ValueError.

        Failure implies the guard is absent; the class would have no information
        about the required array shape and would crash or produce silently wrong output.
        """
        # when / then
        with pytest.raises(ValueError, match="must specify either source_array or shape"):
            StateArray(NAMES, 0)

        return

    def test_name_registry_populated_on_allocation(self):
        """Given a successful allocation, states and _state_to_view should be
        populated identically to the explicit input_array construction path.

        Failure implies the allocation branch skips or corrupts the name registry,
        making all subsequent named access raise AttributeError.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES))

        # then
        assert arr.state_names == tuple(NAMES)
        assert list(arr._state_to_view.keys()) == NAMES

        return

    def test_named_access_works_on_allocated_array(self):
        """Given an allocated array filled with a known default, named attribute
        access should return a plain ndarray row containing that default value.

        Failure implies the allocation path produces a structurally valid array
        whose named access is somehow broken, e.g. due to a missing finalize step.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES), default_value=5)

        # then
        for name in NAMES:
            row = getattr(arr, name)
            assert isinstance(row, np.ndarray)
            assert not isinstance(row, StateArray)
            assert np.all(row == 5), f"Expected {name} row to be all 5, got {row}"

        return


# ===========================================================================
# Named read access
# ===========================================================================


class TestNamedRead:
    """Named attribute read access: correctness, aliasing, and error behaviour."""

    def test_named_attribute_returns_correct_row(self, sample_data):
        """Given an array where row i is filled with i+1, reading the named attribute
        for each state should return the corresponding row values.

        Failure implies the name-to-view mapping is wrong; all named reads would
        silently return the wrong epidemiological compartment.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when / then
        for i, name in enumerate(NAMES):
            row = getattr(arr, name)
            assert np.all(row == i + 1), f"Expected {name} row (index {i}) to be all {i + 1}, got {row}"

        return

    def test_named_attribute_returns_plain_ndarray(self, sample_data):
        """Given a constructed StateArray, accessing any state name should return
        a plain np.ndarray, not a StateArray instance.

        Failure implies the precomputed views in _state_to_view are not plain
        ndarrays, which would expose callers to StateArray's custom __setattr__
        and __getattr__ on what they expect to be an ordinary array.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when / then - every state name must return a base ndarray, not the subclass
        for name in NAMES:
            row = getattr(arr, name)
            assert isinstance(row, np.ndarray), f"{name}: expected np.ndarray, got {type(row)}"
            assert not isinstance(row, StateArray), f"{name}: returned a StateArray instead of a plain ndarray"

        return

    def test_named_attribute_read_is_a_view(self, zero_data):
        """Given a constructed array, the 1D array returned by a named attribute should
        share memory with the backing store (i.e. be a view, not a copy).

        Failure implies named reads return copies; in-place simulation updates written
        through the named view would not propagate to the backing store, silently
        corrupting model state.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # when - mutate through the named view
        view = arr.S
        view[0] = 99

        # then - change is visible via integer indexing
        assert arr[0, 0] == 99

        return

    def test_unknown_attribute_raises_attribute_error(self, zero_data):
        """Given a constructed array, accessing an attribute not registered as a state
        name should raise AttributeError.

        Failure implies typos in state names return silently wrong data instead of
        failing loudly.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # when / then
        with pytest.raises(AttributeError):
            _ = arr.nonexistent_state

        return


# ===========================================================================
# Named write access
# ===========================================================================


class TestNamedWrite:
    """Named attribute write access: scalars, arrays, and row isolation."""

    def test_named_write_scalar_fills_row(self, zero_data):
        """Given an array initialised to zeros, assigning a scalar to a named attribute
        should broadcast to fill every element of that row.

        Failure implies scalar broadcast assignment via attribute is broken, preventing
        the common pattern of resetting a compartment to a uniform value.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # when
        arr.I = 42

        # then - I row is 42, all other rows unchanged
        i_index = NAMES.index("I")
        assert np.all(arr[i_index, :] == 42)
        for name in NAMES:
            if name != "I":
                assert np.all(getattr(arr, name) == 0), f"Row {name!r} should still be zero after writing to I"

        return

    def test_named_write_array_updates_row(self, zero_data):
        """Given a constructed array, assigning a 1D array to a named attribute should
        replace that row's contents with the provided values.

        Failure implies array assignment via named attribute is broken.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)
        new_values = np.arange(NUM_PATCHES, dtype=np.int64)

        # when
        arr.R = new_values

        # then
        assert np.array_equal(arr.R, new_values)

        return

    def test_named_write_does_not_affect_other_rows(self, zero_data):
        """Given a constructed array, writing to one named row should leave all other
        rows untouched.

        Failure implies named writes bleed into adjacent rows, corrupting compartment
        counts across the whole model.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # when
        arr.V = 7

        # then
        for name in NAMES:
            if name != "V":
                assert np.all(getattr(arr, name) == 0), f"Row {name!r} should be unaffected by writing to V"

        return


# ===========================================================================
# Integer and tuple indexing
# ===========================================================================


class TestIndexing:
    """Direct __getitem__ / __setitem__ access by integer row and (row, col) tuple."""

    def test_getitem_integer_row(self, sample_data):
        """Given distinct per-row values, indexing by integer row should return the
        correct row.

        Failure implies __getitem__ delegation to the underlying ndarray is broken.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when - row 2 is the I compartment, filled with 3
        row = arr[2]

        # then
        assert np.all(row == 3)

        return

    def test_getitem_tuple_returns_scalar(self, sample_data):
        """Given distinct per-row values, 2D tuple indexing should return the correct
        scalar element.

        Failure implies __getitem__ does not correctly delegate tuple indices to the
        underlying array.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when - row 3 (R) is filled with 4; pick patch 7
        value = arr[3, 7]

        # then
        assert value == 4

        return

    def test_setitem_integer_row(self, zero_data):
        """Given a zeroed array, assigning a full row via integer index should update
        the underlying data.

        Failure implies __setitem__ delegation is broken for row-level assignment.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)
        new_row = np.ones(NUM_PATCHES, dtype=np.int64) * 7

        # when
        arr[0] = new_row

        # then
        assert np.all(arr[0] == 7)

        return

    def test_setitem_tuple_updates_single_element(self, zero_data):
        """Given a zeroed array, assigning a scalar via 2D tuple index should update
        only that element, leaving all neighbours unchanged.

        Failure implies __setitem__ does not correctly delegate scalar element
        assignment, or bleeds the write into adjacent cells.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # when
        arr[1, 5] = 99

        # then - target element updated
        assert arr[1, 5] == 99
        # neighbouring elements untouched
        assert arr[1, 4] == 0
        assert arr[1, 6] == 0
        assert arr[0, 5] == 0

        return


# ===========================================================================
# Slice behaviour
# ===========================================================================


class TestSlice:
    """Column slicing returns a plain ndarray, not a StateArray.

    StateArray.__getitem__ delegates directly to the underlying ndarray view,
    so any slice always returns a base ndarray.  Named row access is therefore
    not available on the result.
    """

    def test_column_slice_returns_plain_ndarray(self, sample_data):
        """Given a StateArray, slicing a column range should return a plain
        np.ndarray, not a StateArray.

        Failure implies slicing unexpectedly preserves the StateArray subclass,
        which would give callers false confidence that named access still works on
        the result.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when - take the first half of patches
        sliced = arr[:, : NUM_PATCHES // 2]

        # then - result is a plain ndarray with the correct shape and data
        assert isinstance(sliced, np.ndarray)
        assert not isinstance(sliced, StateArray)
        assert sliced.shape == (NUM_STATES, NUM_PATCHES // 2)
        assert np.array_equal(sliced[0], np.ones(NUM_PATCHES // 2))  # S row filled with 1
        assert np.array_equal(sliced[4], np.full(NUM_PATCHES // 2, 5))  # V row filled with 5

        return


# ===========================================================================
# Protocol surface
# ===========================================================================


class TestProtocol:
    """shape attribute and __array__ protocol."""

    def test_shape_reports_correct_dimensions(self, zero_data):
        """Given a constructed array, the shape attribute should report the underlying
        data's dimensions.

        Failure implies shape reporting is broken; any code that introspects dimensions
        (e.g. to validate patch counts) would receive wrong values.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.shape == (NUM_STATES, NUM_PATCHES)

        return

    def test_asarray_returns_plain_ndarray_with_correct_data(self, sample_data):
        """Given a constructed array, np.asarray() should return a plain ndarray with
        data identical to the source.

        Failure implies the __array__ protocol is broken; the class could not be passed
        transparently to numpy functions that call np.asarray() internally.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when
        plain = np.asarray(arr)

        # then
        assert isinstance(plain, np.ndarray)
        assert np.array_equal(plain, sample_data)

        return

    def test_asarray_respects_dtype_argument(self, sample_data):
        """Given a constructed int64 array, np.asarray(arr, dtype=float64) should return
        a float64 ndarray with the same values.

        Failure implies the dtype argument passed to __array__ is ignored, breaking
        callers that request a specific numeric type.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sample_data)

        # when
        plain = np.asarray(arr, dtype=np.float64)

        # then
        assert plain.dtype == np.float64
        assert np.array_equal(plain, sample_data.astype(np.float64))

        return


# ===========================================================================
# NumPy ndarray built-in attributes
# ===========================================================================


class TestNdarrayAttributes:
    """Built-in ndarray attributes and properties remain intact on StateArray.

    Because StateArray subclasses np.ndarray and overrides __getattr__ and
    __setattr__, there is a risk that custom attribute routing interferes with
    numpy's own attribute machinery.  These tests verify that the most commonly
    used intrinsic attributes are unaffected.
    """

    def test_dtype_reflects_input(self, zero_data):
        """Given a StateArray constructed from an int64 array, dtype should be int64.

        Failure implies dtype is being masked or overridden by the custom __getattr__,
        breaking any code that inspects element type before performing arithmetic.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.dtype == np.dtype(np.int64)

        return

    def test_ndim_is_two(self, zero_data):
        """Given a StateArray wrapping a 2D array, ndim should be 2.

        Failure implies the dimensionality property is being intercepted, which would
        break any generic code that checks array rank before operating on it.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.ndim == 2

        return

    def test_size_is_total_element_count(self, zero_data):
        """Given a StateArray of shape (NUM_STATES, NUM_PATCHES), size should equal
        NUM_STATES * NUM_PATCHES.

        Failure implies the total-element count is inaccessible, breaking any code
        that uses size to validate or allocate buffers.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.size == NUM_STATES * NUM_PATCHES

        return

    def test_itemsize_reflects_dtype(self, zero_data):
        """Given an int64 StateArray, itemsize should be 8 (bytes per element).

        Failure implies per-element byte size is inaccessible, breaking low-level
        memory layout calculations and interop with C extensions.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.itemsize == np.dtype(np.int64).itemsize  # 8 bytes

        return

    def test_nbytes_is_size_times_itemsize(self, zero_data):
        """Given a StateArray, nbytes should equal size * itemsize.

        Failure implies total buffer size is inaccessible, breaking memory-budget
        checks and shared-memory allocation.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.nbytes == NUM_STATES * NUM_PATCHES * arr.itemsize

        return

    def test_strides_are_c_contiguous(self, zero_data):
        """Given a C-contiguous int64 StateArray with states along axis 0, strides
        should be (NUM_PATCHES * itemsize, itemsize).

        Failure implies stride information is wrong or inaccessible, which would
        corrupt any code that uses strides for manual memory navigation or
        passes the array to a C/Fortran extension expecting a specific layout.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)
        itemsize = np.dtype(np.int64).itemsize

        # then
        assert arr.strides == (NUM_PATCHES * itemsize, itemsize)

        return

    def test_transpose_swaps_axes(self, zero_data):
        """Given a (NUM_STATES, NUM_PATCHES) StateArray, the .T attribute should
        return an array with shape (NUM_PATCHES, NUM_STATES).

        Failure implies the transpose property is inaccessible or returns the wrong
        shape, breaking any linear-algebra or matrix operation on the array.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.T.shape == (NUM_PATCHES, NUM_STATES)

        return

    def test_flags_reports_c_contiguous(self, zero_data):
        """Given a StateArray constructed from a standard C-contiguous array, the
        C_CONTIGUOUS flag should be True.

        Failure implies memory-layout flags are inaccessible, which would break code
        that checks contiguity before passing the array to a compiled extension.
        """
        # given / when
        arr = StateArray(NAMES, 0, source_array=zero_data)

        # then
        assert arr.flags["C_CONTIGUOUS"]

        return


# ===========================================================================
# Scenario: ticks × states × patches  (states_dim=1)  — full coverage
# ===========================================================================


class TestTicksStatesPatchesLayout:
    """Full coverage for the ticks × states × patches layout with states_dim=1.

    Named access returns a 2D slice of shape (NUM_TICKS, NUM_PATCHES) rather than
    the 1D row returned by the states × patches layout.  This exercises the
    states_dim=1 code path throughout construction, access, and mutation.
    """

    # --- construction -------------------------------------------------------

    def test_construction_from_input_array(self, tsp_data):
        """Given a (NUM_TICKS, NUM_STATES, NUM_PATCHES) array and states_dim=1,
        construction should succeed with the correct shape and name registry.

        Failure implies the constructor does not handle states on an interior axis.
        """
        # when
        arr = StateArray(NAMES, 1, source_array=tsp_data)

        # then
        assert arr.shape == (NUM_TICKS, NUM_STATES, NUM_PATCHES)
        assert arr.state_names == tuple(NAMES)
        assert list(arr._state_to_view.keys()) == NAMES

        return

    def test_construction_from_dims(self):
        """Given shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES) and states_dim=1,
        construction should allocate a zeroed int32 array of the correct shape.

        Failure implies the allocation path does not work for 3-D dims.
        """
        # when
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))

        # then
        assert arr.shape == (NUM_TICKS, NUM_STATES, NUM_PATCHES)
        assert arr.dtype == np.dtype(np.int32)
        assert np.all(arr == 0)

        return

    def test_rejects_mismatched_states_count(self, tsp_data):
        """Given states_dim=1 and fewer names than elements on axis 1, construction
        should raise ValueError.

        Failure means the name count is not validated against the chosen axis,
        allowing silent misidentification of states.
        """
        # given – one name too few for axis 1
        with pytest.raises(ValueError, match="Number of states"):
            StateArray(NAMES[:-1], 1, source_array=tsp_data)

        return

    # --- named read ---------------------------------------------------------

    def test_named_access_returns_correct_2d_slice(self, tsp_data):
        """Given arr[:, i, :] = i + 1 for each state i, named access should return
        a 2D slice of shape (NUM_TICKS, NUM_PATCHES) with the correct fill value.

        Failure implies the precomputed view for states_dim=1 selects the wrong axis
        or index, causing silent compartment misidentification.
        """
        # given
        arr = StateArray(NAMES, 1, source_array=tsp_data)

        # when / then
        for i, name in enumerate(NAMES):
            slc = getattr(arr, name)
            assert slc.shape == (NUM_TICKS, NUM_PATCHES), f"{name}: expected shape ({NUM_TICKS}, {NUM_PATCHES}), got {slc.shape}"
            assert np.all(slc == i + 1), f"{name}: expected all values {i + 1}"

        return

    def test_named_access_returns_plain_ndarray(self, tsp_data):
        """Given a ticks × states × patches array, named access should return a
        plain np.ndarray, not a StateArray.

        Failure implies the precomputed views in _state_to_view retain the subclass
        type, exposing callers to StateArray internals on what they expect to be
        an ordinary array.
        """
        # given
        arr = StateArray(NAMES, 1, source_array=tsp_data)

        # when / then
        for name in NAMES:
            slc = getattr(arr, name)
            assert isinstance(slc, np.ndarray), f"{name}: expected np.ndarray, got {type(slc)}"
            assert not isinstance(slc, StateArray), f"{name}: returned StateArray instead of ndarray"

        return

    def test_named_access_is_a_view(self):
        """Given a ticks × states × patches array, the 2D slice returned by named
        access should share memory with the backing store.

        Failure implies named access returns copies; in-place updates written through
        the view would not propagate to the backing array, silently corrupting model
        state.
        """
        # given
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))
        s_index = NAMES.index("S")  # 0

        # when – mutate element (tick=0, patch=0) of the S view
        view = arr.S
        view[0, 0] = 99

        # then – change visible at (tick=0, state_S=0, patch=0) via integer indexing
        assert arr[0, s_index, 0] == 99

        return

    def test_unknown_attribute_raises_attribute_error(self):
        """Given a ticks × states × patches array, accessing an unregistered
        attribute should raise AttributeError.

        Failure implies typos in state names return silently wrong data instead of
        failing loudly.
        """
        # given
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))

        # when / then
        with pytest.raises(AttributeError):
            _ = arr.nonexistent_state

        return

    # --- named write --------------------------------------------------------

    def test_named_write_scalar_fills_state_slice(self):
        """Given a zeroed array, assigning a scalar to a named attribute should
        broadcast to fill the entire ticks × patches slice for that state.

        Failure implies scalar broadcast write does not work for 2D state slices.
        """
        # given
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))

        # when
        arr.I = 42

        # then – entire I slice is 42
        assert np.all(arr.I == 42)

        return

    def test_named_write_2d_array_updates_state_slice(self):
        """Given a zeroed array, assigning a 2D array to a named attribute should
        replace the entire ticks × patches slice for that state.

        Failure implies 2D array assignment via named attribute is broken for
        states_dim=1.
        """
        # given
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))
        new_slice = np.arange(NUM_TICKS * NUM_PATCHES, dtype=np.int32).reshape(NUM_TICKS, NUM_PATCHES)

        # when
        arr.R = new_slice

        # then
        assert np.array_equal(arr.R, new_slice)

        return

    def test_named_write_does_not_affect_other_states(self):
        """Given a zeroed array, writing to one named state should leave all other
        states untouched.

        Failure implies writes bleed across the states axis, corrupting compartment
        counts throughout the simulation.
        """
        # given
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))

        # when
        arr.V = 7

        # then
        for name in NAMES:
            if name != "V":
                assert np.all(getattr(arr, name) == 0), f"State {name!r} should be unaffected by writing to V"

        return

    # --- shape --------------------------------------------------------------

    def test_shape_is_ticks_states_patches(self):
        """Given shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES), arr.shape should equal
        that tuple.

        Failure implies shape reporting is broken for 3-D layouts.
        """
        # given / when
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))

        # then
        assert arr.shape == (NUM_TICKS, NUM_STATES, NUM_PATCHES)

        return

    def test_ndim_is_three(self):
        """Given a 3-D layout, ndim should be 3.

        Failure implies the custom __getattr__ intercepts the ndim property, or the
        array is constructed with the wrong number of dimensions.
        """
        # given / when
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_PATCHES))

        # then
        assert arr.ndim == 3

        return


# ===========================================================================
# Scenario: states × ages × patches  (states_dim=0) — basic coverage
# ===========================================================================


class TestStatesAgesPatchesLayout:
    """Basic coverage for the states × ages × patches layout with states_dim=0.

    Named access returns a 2D slice of shape (NUM_AGES, NUM_PATCHES).
    """

    def test_construction_from_input_array(self, sap_data):
        """Given a (NUM_STATES, NUM_AGES, NUM_PATCHES) array and states_dim=0,
        construction should succeed with the correct shape and name registry.

        Failure implies 3-D construction with states_dim=0 is broken.
        """
        # when
        arr = StateArray(NAMES, 0, source_array=sap_data)

        # then
        assert arr.shape == (NUM_STATES, NUM_AGES, NUM_PATCHES)
        assert arr.state_names == tuple(NAMES)

        return

    def test_construction_from_dims(self):
        """Given shape=(NUM_STATES, NUM_AGES, NUM_PATCHES) and states_dim=0,
        construction should allocate a zeroed int32 array of the correct shape.

        Failure implies the allocation path does not work for this 3-D layout.
        """
        # when
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_AGES, NUM_PATCHES))

        # then
        assert arr.shape == (NUM_STATES, NUM_AGES, NUM_PATCHES)
        assert arr.dtype == np.dtype(np.int32)
        assert np.all(arr == 0)

        return

    def test_named_access_returns_correct_2d_slice(self, sap_data):
        """Given arr[i, :, :] = i + 1, named access should return a 2D slice of
        shape (NUM_AGES, NUM_PATCHES) containing the correct values.

        Failure implies named access is broken for states_dim=0 in a 3-D array.
        """
        # given
        arr = StateArray(NAMES, 0, source_array=sap_data)

        # when / then
        for i, name in enumerate(NAMES):
            slc = getattr(arr, name)
            assert slc.shape == (NUM_AGES, NUM_PATCHES), f"{name}: expected shape ({NUM_AGES}, {NUM_PATCHES}), got {slc.shape}"
            assert np.all(slc == i + 1), f"{name}: expected all values {i + 1}"

        return

    def test_named_write_scalar_fills_state_slice(self):
        """Given a zeroed states × ages × patches array, assigning a scalar to a
        named attribute should fill the entire ages × patches slice for that state.

        Failure implies scalar write does not broadcast correctly in this layout.
        """
        # given
        arr = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_AGES, NUM_PATCHES))

        # when
        arr.I = 42

        # then
        assert np.all(arr.I == 42)
        for name in NAMES:
            if name != "I":
                assert np.all(getattr(arr, name) == 0), f"State {name!r} should be unaffected by writing to I"

        return


# ===========================================================================
# Scenario: ticks × states × ages × patches  (states_dim=1) — basic coverage
# ===========================================================================


class TestTicksStatesAgesPatchesLayout:
    """Basic coverage for the ticks × states × ages × patches layout with states_dim=1.

    Named access returns a 3D slice of shape (NUM_TICKS, NUM_AGES, NUM_PATCHES).
    """

    def test_construction_from_input_array(self, tsap_data):
        """Given a (NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES) array and
        states_dim=1, construction should succeed with the correct shape and registry.

        Failure implies 4-D construction with states_dim=1 is broken.
        """
        # when
        arr = StateArray(NAMES, 1, source_array=tsap_data)

        # then
        assert arr.shape == (NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES)
        assert arr.state_names == tuple(NAMES)

        return

    def test_construction_from_dims(self):
        """Given shape=(NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES) and states_dim=1,
        construction should allocate a zeroed int32 array of the correct shape.

        Failure implies the allocation path does not work for 4-D dims.
        """
        # when
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES))

        # then
        assert arr.shape == (NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES)
        assert arr.dtype == np.dtype(np.int32)
        assert np.all(arr == 0)

        return

    def test_named_access_returns_correct_3d_slice(self, tsap_data):
        """Given arr[:, i, :, :] = i + 1, named access should return a 3D slice of
        shape (NUM_TICKS, NUM_AGES, NUM_PATCHES) with the correct values.

        Failure implies named access is broken for states_dim=1 in a 4-D array.
        """
        # given
        arr = StateArray(NAMES, 1, source_array=tsap_data)

        # when / then
        for i, name in enumerate(NAMES):
            slc = getattr(arr, name)
            assert slc.shape == (NUM_TICKS, NUM_AGES, NUM_PATCHES), (
                f"{name}: expected shape ({NUM_TICKS}, {NUM_AGES}, {NUM_PATCHES}), got {slc.shape}"
            )
            assert np.all(slc == i + 1), f"{name}: expected all values {i + 1}"

        return

    def test_named_write_scalar_fills_state_slice(self):
        """Given a zeroed ticks × states × ages × patches array, assigning a scalar
        to a named attribute should fill the entire ticks × ages × patches slice.

        Failure implies scalar broadcast write does not work for 3D state slices.
        """
        # given
        arr = StateArray(NAMES, 1, shape=(NUM_TICKS, NUM_STATES, NUM_AGES, NUM_PATCHES))

        # when
        arr.I = 42

        # then
        assert np.all(arr.I == 42)
        for name in NAMES:
            if name != "I":
                assert np.all(getattr(arr, name) == 0), f"State {name!r} should be unaffected by writing to I"

        return


# Ways to create a StateArray according to NumPy subclassing rules:
# - explicit constructor call StateArray(...)
# - view casting: arr.view(StateArray)  # if arr is a compatible ndarray
# - np.asarray(..., dtype=StateArray)  # if __array__ returns a StateArray instance
# The latter two paths must produce a valid StateArray with the correct name registry, so we test them both here.


class TestConstructionPaths:
    """StateArray construction via explicit constructor, np.asarray with dtype, and view casting."""

    # Well tested in all the cases above.
    # def test_explicit_constructor(self):
    #     return

    def test_view_casting(self, sample_data):
        """
        arr = np.zeros((3,))
        # take a view of it, as our subclass
        state_array = arr.view(StateArray)
        type(state_array)
        """
        # given
        # sample_data

        # when
        state_arr = sample_data.view(StateArray)

        # then
        assert isinstance(state_arr, StateArray)
        assert (
            state_arr.state_names is None
        )  # We don't have the machinery to reconstruct the state names from a view cast, so these should be None.
        assert state_arr.state_axis is None  # Same for state_axis.
        assert state_arr.get_state_index("V") is None  # And the name-to-view mapping should also be None.

        return

    def test_new_from_template(self):
        """
        v = c_arr[1:]
        type(v) # the view is of type 'C'
        v is not c_arr # but it's a new instance
        """
        # given
        sa = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES))

        # when
        # take a view of it, as a new StateArray instance
        new_arr = sa[1:]

        # then
        # The new view should be a plain ndarray, not a StateArray, because slicing
        # should delegate directly to the underlying array and not preserve the
        # subclass type _in our implementation_.
        assert not isinstance(new_arr, StateArray)

        return

    def test_new_from_dtype(self, sample_data):
        """
        np.asarray(state_arr, dtype=StateArray)
        """
        # given
        state_arr = StateArray(NAMES, 0, source_array=sample_data)

        # when
        arr_from_asarray = state_arr.astype(np.float64)

        # then
        assert isinstance(arr_from_asarray, StateArray)
        assert arr_from_asarray.state_names == state_arr.state_names
        assert arr_from_asarray.state_axis == state_arr.state_axis
        assert arr_from_asarray._state_to_view.keys() == state_arr._state_to_view.keys()
        assert np.array_equal(arr_from_asarray, sample_data)

        return

    def test_from_ufunc(self):
        # given
        sa = StateArray(NAMES, 0, shape=(NUM_STATES, NUM_PATCHES))
        sa.S = 10_000
        sa.E = 0
        sa.I = 10
        sa.R = 59_990
        sa.V = 28_000
        sa.M = 2_000

        # when
        normalized = sa / sa.sum(sa.state_axis)

        # then
        assert isinstance(normalized, StateArray)
        assert normalized.state_names == sa.state_names
        assert normalized.state_axis == sa.state_axis
        assert normalized._state_to_view.keys() == sa._state_to_view.keys()

        return


if __name__ == "__main__":
    pytest.main()
