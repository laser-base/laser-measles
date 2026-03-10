"""
10x10 spatial measles ABM with:
- 8-neighbor diffusion on open boundaries (no wrap)
- weak long-range coupling (Option C)
- total population ~ 1e6 with one metro patch

Requires: laser-measles (ABMModel), polars, numpy, pydantic
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from pydantic import BaseModel, Field

import laser.measles as lm
from laser.measles import create_component
from laser.measles.abm import ABMModel, ABMParams
from laser.measles.base import BasePhase


# -------------------------
# Scenario construction
# -------------------------

def make_grid_scenario(
    n: int = 10,
    total_pop: int = 1_000_000,
    metro_pop: int = 300_000,
    metro_xy: Tuple[int, int] = (5, 5),  # (x, y) in [0..n-1]
    mcv1: float = 0.0,
) -> pl.DataFrame:
    """
    Creates a 10x10 grid scenario with lat=y, lon=x (arbitrary planar coords).
    One patch gets metro_pop, all others share the remainder as evenly as possible.
    """
    assert n > 0
    assert 0 <= metro_xy[0] < n and 0 <= metro_xy[1] < n
    assert 0 <= mcv1 <= 1

    num_patches = n * n
    assert metro_pop < total_pop

    remainder = total_pop - metro_pop
    base = remainder // (num_patches - 1)
    extra = remainder - base * (num_patches - 1)

    pops = np.full(num_patches, base, dtype=np.int64)
    metro_idx = metro_xy[1] * n + metro_xy[0]
    pops[metro_idx] = metro_pop

    # distribute any leftover +1s across non-metro patches
    if extra > 0:
        non_metro = [i for i in range(num_patches) if i != metro_idx]
        for i in non_metro[:extra]:
            pops[i] += 1

    ids = []
    lats = np.zeros(num_patches, dtype=np.float64)
    lons = np.zeros(num_patches, dtype=np.float64)
    mcv1s = np.full(num_patches, mcv1, dtype=np.float64)

    for y in range(n):
        for x in range(n):
            idx = y * n + x
            ids.append(f"patch_x{x}_y{y}")
            lats[idx] = float(y)
            lons[idx] = float(x)

    return pl.DataFrame({"id": ids, "pop": pops, "lat": lats, "lon": lons, "mcv1": mcv1s})


# -------------------------
# Model parameters (custom)
# -------------------------

class GridMeaslesParams(BaseModel):
    # Measles-ish transmission scale; tune to match what you want.
    beta: float = Field(default=20.0, ge=0.0, description="Base transmission scaling.")
    seasonality: float = Field(default=0.0, ge=0.0, le=1.0, description="0..1 sinusoidal amplitude.")
    latent_days: int = Field(default=8, gt=0, description="E duration in days.")
    infectious_days: int = Field(default=6, gt=0, description="I duration in days.")

    # Diffusion (8-neighbor)
    D: float = Field(default=0.03, ge=0.0, description="Per-neighbor diffusion weight.")
    # Long-range mixing blend
    long_range_eps: float = Field(default=0.05, ge=0.0, le=1.0, description="Blend weight for long-range matrix.")
    long_range_rowsum: float = Field(default=0.10, ge=0.0, le=1.0, description="Row-sum scale for long-range matrix.")
    long_range_decay: float = Field(default=2.0, gt=0.0, description="Distance decay exponent for long-range weights.")

    # Initial immunity
    initial_immune_frac: float = Field(default=0.90, ge=0.0, le=1.0, description="Fraction initially immune (R).")

    # Seeding
    seed_infections: int = Field(default=20, ge=0, description="Number of infections to seed at start.")

    # Numerical safety
    max_total_rowsum: float = Field(default=0.50, gt=0.0, le=1.0, description="Max row-sum for combined mixing.")


# -------------------------
# Utility: mixing matrices
# -------------------------

def build_moore_diffusion_matrix(n: int, D: float) -> np.ndarray:
    """
    8-neighbor diffusion on an open n x n grid.
    M[i,j] is weight from origin i to destination j (off-diagonal).
    No wrap. Edges just have fewer neighbors.
    """
    num = n * n
    M = np.zeros((num, num), dtype=np.float32)

    def idx(x: int, y: int) -> int:
        return y * n + x

    for y in range(n):
        for x in range(n):
            i = idx(x, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < n and 0 <= ny < n:
                        j = idx(nx, ny)
                        M[i, j] = D

    # diagonal stays 0; "stay-home" is implicit
    return M


def build_long_range_matrix(
    lat: np.ndarray,
    lon: np.ndarray,
    pop: np.ndarray,
    rowsum: float,
    decay: float,
) -> np.ndarray:
    """
    Simple gravity-like long-range matrix:
      weight(i->j) ∝ pop[j] / dist(i,j)^decay
    then row-normalized to sum to `rowsum`, diagonal set to 0.
    """
    n = pop.size
    M = np.zeros((n, n), dtype=np.float32)

    # pairwise distances (planar)
    dx = lon.reshape(-1, 1) - lon.reshape(1, -1)
    dy = lat.reshape(-1, 1) - lat.reshape(1, -1)
    dist = np.sqrt(dx * dx + dy * dy).astype(np.float32)
    dist[dist == 0] = np.inf  # avoid diagonal singularity

    # raw weights
    w = (pop.reshape(1, -1).astype(np.float32)) / (dist ** decay)
    w[np.isinf(w)] = 0.0
    np.fill_diagonal(w, 0.0)

    row_sums = w.sum(axis=1, keepdims=True)
    # handle isolated rows (shouldn't happen here)
    row_sums[row_sums == 0] = 1.0
    w = w / row_sums

    M = (rowsum * w).astype(np.float32)
    np.fill_diagonal(M, 0.0)
    return M


def cap_rowsums(M: np.ndarray, max_rowsum: float) -> np.ndarray:
    """
    If any row sum exceeds max_rowsum, scale that row down proportionally.
    """
    rs = M.sum(axis=1)
    scale = np.ones_like(rs, dtype=np.float32)
    over = rs > max_rowsum
    scale[over] = (max_rowsum / rs[over]).astype(np.float32)
    return (M.T * scale).T.astype(np.float32)


# -------------------------
# Custom components
# -------------------------

class GridPopulationInitProcess(BasePhase):
    """
    Initialize the people LaserFrame to match scenario populations and set initial immunity.

    Notes:
    - PeopleLaserFrame properties are array-backed and can be resized via ABMModel.initialize_people_capacity(). :contentReference[oaicite:2]{index=2}
    """

    def __init__(self, model: ABMModel, verbose: bool = False, params: GridMeaslesParams | None = None):
        super().__init__(model, verbose)
        self.params = params if params is not None else GridMeaslesParams()

    def _initialize(self, model: ABMModel):
        scenario = model.scenario
        pop = scenario["pop"].to_numpy()
        total_pop = int(pop.sum())
        num_patches = pop.size

        # Over-allocate 20% to accommodate births from VitalDynamicsProcess
        model.initialize_people_capacity(capacity=int(total_pop * 1.2), initial_count=total_pop)

        people = model.people

        # Ensure we have timers (uint16 is what the built-in ABM uses). :contentReference[oaicite:3]{index=3}
        if not hasattr(people, "etimer"):
            people.add_scalar_property("etimer", dtype=np.uint16, default=0)
        if not hasattr(people, "itimer"):
            people.add_scalar_property("itimer", dtype=np.uint16, default=0)

        # Assign patch_id according to scenario pops
        patch_ids = np.repeat(np.arange(num_patches, dtype=np.uint16), pop.astype(np.int64))
        assert patch_ids.size == total_pop

        # Shuffle agents to avoid “all of patch 0 then all of patch 1” ordering artifacts
        rng = model.prng
        perm = rng.permutation(total_pop)
        patch_ids = patch_ids[perm]

        people.patch_id[:total_pop] = patch_ids
        people.state[:total_pop] = 0  # S
        people.susceptibility[:total_pop] = 1.0
        people.etimer[:total_pop] = 0
        people.itimer[:total_pop] = 0

        # Initial immunity: move fraction to R
        immune_frac = self.params.initial_immune_frac
        if immune_frac > 0:
            # Sample immune individuals globally (simpler; you can make it patch-specific if desired)
            n_immune = int(round(total_pop * immune_frac))
            immune_idx = rng.choice(total_pop, size=n_immune, replace=False)
            people.state[immune_idx] = 3  # R
            people.susceptibility[immune_idx] = 0.0

        if self.verbose:
            counts = np.bincount(people.state[:total_pop], minlength=4)
            print(f"[Init] People={total_pop:,}  S/E/I/R = {counts.tolist()}")


class GridInfectionSeedingProcess(BasePhase):
    """
    Seed infections in a chosen target patch at t=0.
    """

    def __init__(
        self,
        model: ABMModel,
        verbose: bool = False,
        params: GridMeaslesParams | None = None,
        target_patch_id: int | None = None,  # numeric patch index
    ):
        super().__init__(model, verbose)
        self.params = params if params is not None else GridMeaslesParams()
        self.target_patch_id = target_patch_id

    def _initialize(self, model: ABMModel):
        people = model.people
        n = len(people)

        # default target: largest-pop patch
        if self.target_patch_id is None:
            pops = model.scenario["pop"].to_numpy()
            self.target_patch_id = int(np.argmax(pops))

        target = np.uint16(self.target_patch_id)

        # find susceptible people in that patch
        in_patch = (people.patch_id[:n] == target)
        susceptible = in_patch & (people.state[:n] == 0)

        sus_idx = np.where(susceptible)[0]
        k = min(self.params.seed_infections, sus_idx.size)
        if k <= 0:
            return

        rng = model.prng
        chosen = rng.choice(sus_idx, size=k, replace=False)
        people.state[chosen] = 2  # I
        people.itimer[chosen] = np.uint16(self.params.infectious_days)
        people.etimer[chosen] = 0
        people.susceptibility[chosen] = 0.0  # infected not susceptible

        if self.verbose:
            print(f"[Seed] Seeded {k} infections in patch index {int(target)}")


class DiffusionPlusLongRangeTransmissionProcess(BasePhase):
    """
    Transmission using a fixed mixing matrix:
      M = (1-eps)*M_diffusion + eps*M_longrange
    with row sums capped at params.max_total_rowsum.

    Then per destination patch j:
      lambda[j] = beta(t) * sum_i prevalence[i] * M[i,j]
    and new infections are sampled per patch (binomial), then applied to random susceptibles in that patch.
    """

    def __init__(self, model: ABMModel, verbose: bool = False, params: GridMeaslesParams | None = None, grid_n: int = 10):
        super().__init__(model, verbose)
        self.params = params if params is not None else GridMeaslesParams()
        self.grid_n = grid_n
        self.M: np.ndarray | None = None
        self.pop: np.ndarray | None = None
        self.patch_agent_indices: list[np.ndarray] | None = None  # constant membership per patch

    def _initialize(self, model: ABMModel):
        # Ensure timer properties exist (may not be added by InitializeEquilibriumStatesProcess)
        people = model.people
        if not hasattr(people, "etimer"):
            people.add_scalar_property("etimer", dtype=np.uint16, default=0)
        if not hasattr(people, "itimer"):
            people.add_scalar_property("itimer", dtype=np.uint16, default=0)

        scenario = model.scenario
        lat = scenario["lat"].to_numpy()
        lon = scenario["lon"].to_numpy()
        pop = scenario["pop"].to_numpy().astype(np.float32)
        self.pop = pop

        num_patches = pop.size
        assert num_patches == self.grid_n * self.grid_n, "grid_n mismatch with scenario patch count"

        M_diff = build_moore_diffusion_matrix(self.grid_n, self.params.D)

        M_lr = build_long_range_matrix(
            lat=lat,
            lon=lon,
            pop=pop,
            rowsum=self.params.long_range_rowsum,
            decay=self.params.long_range_decay,
        )

        eps = self.params.long_range_eps
        M = (1.0 - eps) * M_diff + eps * M_lr
        np.fill_diagonal(M, 0.0)

        # Cap off-diagonal mixing, then set diagonal = 1 - off-diag row sum
        # so local infectious generate local force of infection.
        M = cap_rowsums(M, self.params.max_total_rowsum)
        off_diag_rs = M.sum(axis=1)
        np.fill_diagonal(M, np.maximum(0.0, 1.0 - off_diag_rs))

        self.M = M.astype(np.float32)

        # Precompute constant agent membership arrays by patch (no movement in this model)
        people = model.people
        n_people = len(people)
        patch_ids = people.patch_id[:n_people].astype(np.int64)
        self.patch_agent_indices = [
            np.where(patch_ids == p)[0] for p in range(num_patches)
        ]

        if self.verbose:
            rs = self.M.sum(axis=1)
            print(
                f"[Mix] diffusion D={self.params.D}, eps={eps}, "
                f"row-sum min/mean/max = {rs.min():.3f}/{rs.mean():.3f}/{rs.max():.3f}"
            )

    def __call__(self, model: ABMModel, tick: int):
        # --- Lazy build mixing matrix (works even if initialize() is never called) ---
        if self.M is None or self.pop is None:
            scenario = model.scenario
            lat = scenario["lat"].to_numpy()
            lon = scenario["lon"].to_numpy()
            pop = scenario["pop"].to_numpy().astype(np.float32)
            self.pop = pop

            num_patches = pop.size
            grid_n = int(round(np.sqrt(num_patches)))
            if grid_n * grid_n != num_patches:
                raise ValueError(f"Patch count {num_patches} is not a square grid.")
            self.grid_n = grid_n

            M_diff = build_moore_diffusion_matrix(self.grid_n, self.params.D)

            M_lr = build_long_range_matrix(
                lat=lat,
                lon=lon,
                pop=pop,
                rowsum=self.params.long_range_rowsum,
                decay=self.params.long_range_decay,
            )

            eps = self.params.long_range_eps
            M = (1.0 - eps) * M_diff + eps * M_lr
            np.fill_diagonal(M, 0.0)
            M = cap_rowsums(M, self.params.max_total_rowsum)
            off_diag_rs = M.sum(axis=1)
            np.fill_diagonal(M, np.maximum(0.0, 1.0 - off_diag_rs))

            self.M = M.astype(np.float32)

            if self.verbose:
                rs = self.M.sum(axis=1)
                print(
                    f"[Mix lazy-init @ tick {tick}] D={self.params.D}, eps={eps}, "
                    f"row-sum min/mean/max = {rs.min():.3f}/{rs.mean():.3f}/{rs.max():.3f}"
                )

        # From here on, these must exist
        people = model.people
        n_people = len(people)
        num_patches = self.pop.size

        # Rebuild patch membership if population size changed (births/deaths via VitalDynamics)
        if self.patch_agent_indices is None or n_people != getattr(self, "_last_n_people", -1):
            patch_ids = people.patch_id[:n_people].astype(np.int64)
            self.patch_agent_indices = [
                np.where(patch_ids == p)[0] for p in range(num_patches)
            ]
            self._last_n_people = n_people

        # Count infectious by patch
        is_I = (people.state[:n_people] == 2)
        I_patch = np.bincount(
            people.patch_id[:n_people].astype(np.int64),
            weights=is_I.astype(np.int32),
            minlength=num_patches,
        ).astype(np.float32)
        prevalence = I_patch / self.pop

        # Seasonal beta(t)
        beta = self.params.beta
        if self.params.seasonality > 0:
            beta = beta * (1.0 + self.params.seasonality * np.sin(2.0 * np.pi * (tick / 365.0)))

        # Force of infection per destination patch:
        # lambda[j] = beta * sum_i prevalence[i] * M[i,j]
        lam = beta * (prevalence @ self.M)

        rng = model.prng

        # Hazard -> infection probability
        p = 1.0 - np.exp(-lam)
        p = np.clip(p, 0.0, 1.0)

        newly_exposed_total = 0

        for patch in range(num_patches):
            idxs = self.patch_agent_indices[patch]
            if idxs.size == 0:
                continue

            # susceptibles in this patch
            sus_mask = (people.state[idxs] == 0)
            s = int(sus_mask.sum())
            if s == 0:
                continue

            k = rng.binomial(n=s, p=float(p[patch]))
            if k <= 0:
                continue

            sus_idxs = idxs[np.where(sus_mask)[0]]
            if k > sus_idxs.size:
                k = sus_idxs.size

            chosen = rng.choice(sus_idxs, size=k, replace=False)

            # S -> E
            people.state[chosen] = 1  # E
            people.etimer[chosen] = np.uint16(self.params.latent_days)
            people.itimer[chosen] = 0
            people.susceptibility[chosen] = 0.0

            newly_exposed_total += k

        # Optional: track incidence per tick on patches LaserFrame if present
        if hasattr(model, "patches") and hasattr(model.patches, "incidence"):
            model.patches.incidence[:] = 0

        if self.verbose and (tick % 30 == 0):
            print(f"[Tx] Day {tick}: new E = {newly_exposed_total:,}")

    def infect(self, model: ABMModel, indices: np.ndarray) -> None:
        """Move agents at given indices S -> E (called by ImportationPressureProcess)."""
        people = model.people
        sus = indices[people.state[indices] == 0]
        if sus.size == 0:
            return
        people.state[sus] = 1  # E
        people.etimer[sus] = np.uint16(self.params.latent_days)
        people.susceptibility[sus] = 0.0


class PatchStateAggregator(BasePhase):
    """
    Aggregates agent-level states into model.patches.states each tick so that
    StateTracker (which reads the patches frame) reflects the actual population.
    """

    def _initialize(self, model: ABMModel):
        pass

    def __call__(self, model: ABMModel, tick: int):
        people = model.people
        n = len(people)
        num_patches = len(model.scenario)
        # Filter to active agents only — VitalDynamicsProcess marks dead agents
        # as inactive (active=False) but leaves them in the array.
        if hasattr(people, "active"):
            alive = people.active[:n]
        else:
            alive = np.ones(n, dtype=bool)
        patch_ids = people.patch_id[:n][alive].astype(np.int64)
        state_vals = people.state[:n][alive].astype(np.int64)
        for state_idx, attr in enumerate(("S", "E", "I", "R")):
            counts = np.bincount(patch_ids[state_vals == state_idx], minlength=num_patches)
            getattr(model.patches.states, attr)[:] = counts


class DiseaseProgressionProcess(BasePhase):
    """
    Simple daily progression:
      E: etimer--, if hits 0 -> I with itimer = infectious_days
      I: itimer--, if hits 0 -> R
    """

    def __init__(self, model: ABMModel, verbose: bool = False, params: GridMeaslesParams | None = None):
        super().__init__(model, verbose)
        self.params = params if params is not None else GridMeaslesParams()

    def __call__(self, model: ABMModel, tick: int):
        people = model.people
        n = len(people)

        # Exposed
        E = (people.state[:n] == 1)
        if np.any(E):
            # decrement timers (avoid underflow by checking >0)
            et = people.etimer[:n]
            dec = E & (et > 0)
            et[dec] = et[dec] - 1

            to_I = E & (et == 0)
            if np.any(to_I):
                people.state[to_I] = 2
                people.itimer[to_I] = np.uint16(self.params.infectious_days)
                people.susceptibility[to_I] = 0.0

        # Infectious
        I = (people.state[:n] == 2)
        if np.any(I):
            it = people.itimer[:n]
            dec = I & (it > 0)
            it[dec] = it[dec] - 1

            to_R = I & (it == 0)
            if np.any(to_R):
                people.state[to_R] = 3
                people.susceptibility[to_R] = 0.0


# -------------------------
# Run it
# -------------------------

def run_grid_measles_abm(
    grid_n: int = 10,
    total_pop: int = 1_000_000,
    metro_pop: int = 300_000,
    metro_xy: Tuple[int, int] = (5, 5),
    num_ticks: int = 365 * 3,
    seed: int = 42,
    verbose: bool = True,
):
    scenario = make_grid_scenario(
        n=grid_n,
        total_pop=total_pop,
        metro_pop=metro_pop,
        metro_xy=metro_xy,
        mcv1=0.0,
    )

    abm_params = ABMParams(
        num_ticks=num_ticks,
        seed=seed,
        start_time="2000-01",
        verbose=False,
    )

    model = ABMModel(scenario=scenario, params=abm_params)
    p = GridMeaslesParams(
        beta=10.0,
        seasonality=0.05,
        latent_days=8,
        infectious_days=6,
        D=0.06,
        long_range_eps=0.01,
        long_range_rowsum=0.03,
        long_range_decay=2.0,
        initial_immune_frac=0.82,  # used only by GridPopulationInitProcess (fallback)
        seed_infections=50,
        max_total_rowsum=0.6,
    )

    R0_init = 15.0   # used by InitializeEquilibriumStatesProcess to set S≈1/R0

    # 1. Equilibrium initialization: sets S≈1/R0, R≈1-1/R0 per patch,
    #    assigns patch_id and state to every agent.
    model.add_component(
        create_component(
            lm.abm.components.InitializeEquilibriumStatesProcess,
            lm.abm.components.InitializeEquilibriumStatesParams(R0=R0_init),
        )
    )

    # 2. Vital dynamics: births replenish susceptibles; crude rates in per-1000-per-year.
    #    Use 30/365 (the correct per-1000-per-year form for this component).
    model.add_component(
        create_component(
            lm.abm.components.VitalDynamicsProcess,
            lm.abm.components.VitalDynamicsParams(
                crude_birth_rate=30,   # 30 per 1000 per year
                crude_death_rate=30,
            ),
        )
    )

    # 3. Custom disease progression (E->I->R timers)
    model.add_component(create_component(DiseaseProgressionProcess, p))

    # 4. Sync agent states -> patches.states so StateTracker reads correctly
    model.add_component(create_component(PatchStateAggregator, p))

    # 5. Spatial transmission (diffusion + long-range mixing)
    model.add_component(
        create_component(DiffusionPlusLongRangeTransmissionProcess, p)
    )

    # 6. Small importation into metro to spark waves after inter-epidemic troughs
    metro_patch = int(np.argmax(scenario["pop"].to_numpy()))
    metro_name = scenario["id"][metro_patch]
    model.add_component(
        create_component(
            lm.abm.components.ImportationPressureProcess,
            lm.abm.components.ImportationPressureParams(
                crude_importation_rate=1.0,   # per 1000 per year into metro
                target_patches=[metro_name],
            ),
        )
    )

    # Global tracker (index 0)
    model.add_component(lm.abm.components.StateTracker)

    # Patch-level tracker (index 1)
    model.add_component(
        create_component(
            lm.abm.components.StateTracker,
            lm.abm.components.StateTrackerParams(aggregation_level=0),
        )
    )

    model.run()

    trackers = model.get_instance("StateTracker")
    global_tracker = trackers[0]
    patch_tracker = trackers[1]

    # patch_tracker.I shape: (num_ticks, num_patches)
    I_ts = np.array(patch_tracker.I)
    metro_idx = int(np.argmax(scenario["pop"].to_numpy()))
    print(f"I_ts shape: {I_ts.shape}, metro_idx: {metro_idx}")

    # crude monthly grouping (trim to multiple of 30)
    n_full_months = I_ts.shape[0] // 30
    I_ts_trim = I_ts[:n_full_months * 30]
    monthly_I = I_ts_trim.reshape(-1, 30, I_ts.shape[1]).sum(axis=1)
    metro_monthly = monthly_I[:, metro_idx]
    print("Months with nonzero I in metro:", np.count_nonzero(metro_monthly))
    print("Peak monthly I in metro:", int(metro_monthly.max()))

    # save plot to file
    plotdir = Path("plots")
    plotdir.mkdir(exist_ok=True)
    plt.figure(figsize=(12, 4))
    plt.plot(I_ts[:, metro_idx], label="metro")
    # also plot a few neighbor patches for comparison
    for pi in range(min(5, I_ts.shape[1])):
        if pi != metro_idx:
            plt.plot(I_ts[:, pi], alpha=0.4, lw=0.8)
    plt.title("Infectious by patch over time")
    plt.xlabel("Day")
    plt.ylabel("Infectious agents")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plotdir / "infectious_timeseries.png")
    plt.close()
    print(f"Saved plot to {plotdir}/infectious_timeseries.png")

    return model, scenario, global_tracker, patch_tracker


if __name__ == "__main__":
    model, scenario, global_tracker, patch_tracker = run_grid_measles_abm()
    print("Done.")
    print("Total infections (approx):", int(global_tracker.R[-1] - global_tracker.R[0]))
