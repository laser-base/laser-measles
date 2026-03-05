# calib/mixing.py
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from laser.measles.mixing.base import BaseMixing


@dataclass(frozen=True)
class ExpKernelParams:
    L: float = 1.5
    eps: float = 0.05


class ExpKernelMixingWrong(BaseMixing):
    """
    exp(-d/L) migration kernel with background mixing.
    Compatible with biweekly + compartmental models.
    """

    def __init__(self, params: ExpKernelParams):
        super().__init__(scenario=None, params=params)
        self._mixing_matrix = None

    def set_scenario(self, scenario):
        self._scenario = scenario
        self._mixing_matrix = None

    def get_migration_matrix(self):
        if self._mixing_matrix is not None:
            return self._mixing_matrix

        if self._scenario is None:
            raise RuntimeError("Scenario not set on mixer.")

        scenario = self._scenario
        coords = np.column_stack(
            [scenario["lat"].to_numpy(), scenario["lon"].to_numpy()]
        )

        n = coords.shape[0]
        d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(axis=2))

        # Raw kernel
        K = np.exp(-d / self.params.L)

        # Zero out diagonal for migration component
        np.fill_diagonal(K, 0.0)

        # Normalize off-diagonal rows to sum to 1
        row_sums = K.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        K = K / row_sums

        # Scale total outward migration probability
        # eps controls how much of population migrates (not stays)
        eps = self.params.eps
        K = eps * K

        # Now construct full matrix including "stay home"
        M = K.copy()
        stay_prob = 1.0 - M.sum(axis=1)

        # Put stay probability on diagonal
        np.fill_diagonal(M, stay_prob)

        # Final sanity: enforce <= 1 numerically
        M = np.minimum(M, 1.0)
        self._mixing_matrix = M.astype(np.float32)

        return self._mixing_matrix

class ExpKernelMixing(BaseMixing):
    """
    exp(-d/L) migration kernel for biweekly/compartmental models.

    Off-diagonal entries represent migration probability.
    Diagonal must be zero.
    Row sums must be <= 1.
    """

    def __init__(self, params: ExpKernelParams):
        super().__init__(scenario=None, params=params)
        self._mixing_matrix = None

    def set_scenario(self, scenario):
        self._scenario = scenario
        self._mixing_matrix = None

    def get_migration_matrix(self):
        if self._mixing_matrix is not None:
            return self._mixing_matrix

        if self._scenario is None:
            raise RuntimeError("Scenario not set on mixer.")

        scenario = self._scenario
        coords = np.column_stack(
            [scenario["lat"].to_numpy(), scenario["lon"].to_numpy()]
        )

        n = coords.shape[0]
        d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(axis=2))

        # Kernel
        K = np.exp(-d / self.params.L)

        # Remove self-migration
        np.fill_diagonal(K, 0.0)

        # Normalize off-diagonal rows
        row_sums = K.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        K = K / row_sums

        # Scale by eps (total outward migration fraction)
        eps = self.params.eps
        K = eps * K

        # Enforce strictly <= 1 row sum
        row_sums = K.sum(axis=1)
        assert np.all(row_sums <= 1.0 + 1e-8)

        self._mixing_matrix = K.astype(np.float32)
        return self._mixing_matrix
