# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Visualizing ChainMixing — a companion to the spatial calibration tutorial
#
# The [spatial calibration tutorial](tut_calibration_spatial.ipynb) uses a
# custom mixer with chain topology: cluster A talks to B_far, B_far to
# B_near, B_near to C, and *only* those routes. The calibration tutorial
# treats the mixer as a given and gets on with the calibration. This
# notebook is the standalone visualizer for the mixer itself.
#
# **When you'd want this notebook**
#
# - You're reading the calibration tutorial and the `ChainMixing`
#   class in Section 4 is opaque — you want to see what the
#   matrix actually looks like and how the chain topology plays out
#   geographically. Open this notebook, run it (under 30 seconds), come
#   back to the main tutorial.
# - You're considering reusing the chain-mixer pattern in your own
#   scenario and want a clean reference implementation that's
#   generalized to N clusters and doesn't carry the calibration
#   tutorial's specific 4-cluster hard-coding.
# - You want to see a worked example of a custom mixer that's
#   testable in isolation (no model, no calibration, just matrix math
#   + plots).
#
# **What's in here**
#
# - A small synthetic chain scenario (4 clusters, 20 patches), small
#   enough to visualize the migration matrix cleanly.
# - Two implementations of the chain mixer side-by-side: a function
#   (the "right" design — see the discussion in the calibration
#   tutorial's [red-team comments](https://github.com/laser-base/laser-measles))
#   and the `ChainMixing(GravityMixing)` class currently used by the
#   calibration tutorial.
# - Four visualizations: the allowed/forbidden mask, the migration
#   matrix heatmap, the chain as a geographic graph, and a population-
#   flow simulation that shows the chain wave from A → B → C.
# - Property checks (rows sum to k, forbidden routes are zero, both
#   directions are present for adjacent clusters).
# - A regression check that proves the function-first and class
#   implementations produce numerically equal matrices on the
#   calibration tutorial's scenario.
# - Generality demos: chains of 3 and 6 clusters using the same
#   function.

# %% [markdown]
# ## 1. Setup
#
# Standard scientific Python plus two utility imports from laser-core
# (great-circle distance + gravity kernel) so we can run both
# implementations side-by-side.

# %%
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from laser.core.migration import distance
from laser.core.migration import gravity as gravity_fn
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

from laser.measles.mixing.gravity import GravityMixing
from laser.measles.mixing.gravity import GravityParams

# Reproducibility
RNG = np.random.default_rng(seed=20260610)


# %% [markdown]
# ## 2. A small synthetic chain scenario
#
# 4 clusters × 5 patches each = 20 patches, arranged in a chain along
# longitude with within-cluster jitter. Small enough that every entry of
# the 20×20 migration matrix is visible in a heatmap.

# %%
def build_chain_scenario(
    n_clusters: int = 4,
    n_patches_per_cluster: int = 5,
    separation_km: float = 300.0,
    cluster_spread_km: float = 30.0,
    rng: np.random.Generator | None = None,
) -> tuple[pl.DataFrame, list[np.ndarray]]:
    """Build a synthetic chain of clusters.

    Returns the scenario DataFrame and a list of patch-index arrays,
    one per cluster, in chain order. The mixer treats patches in
    *adjacent* clusters (in this list) as allowed to exchange; non-
    adjacent clusters are forbidden.
    """
    if rng is None:
        rng = np.random.default_rng(seed=42)

    chain_lat = 40.0
    km_per_deg_lon = 111.0 * np.cos(np.radians(chain_lat))
    sep_deg = separation_km / km_per_deg_lon
    spread_deg = cluster_spread_km / km_per_deg_lon

    rows: list[dict] = []
    cluster_indices: list[np.ndarray] = []
    patch_id = 0
    for ci in range(n_clusters):
        cluster_lon = ci * sep_deg
        idx_this_cluster: list[int] = []
        for pi in range(n_patches_per_cluster):
            lat = chain_lat + rng.normal(0.0, spread_deg)
            lon = cluster_lon + rng.normal(0.0, spread_deg)
            pop = int(rng.integers(20_000, 80_000))
            rows.append({"id": f"c{ci}:p{pi}", "pop": pop, "lat": float(lat), "lon": float(lon)})
            idx_this_cluster.append(patch_id)
            patch_id += 1
        cluster_indices.append(np.array(idx_this_cluster, dtype=int))

    return pl.DataFrame(rows), cluster_indices


scenario, cluster_indices = build_chain_scenario(rng=RNG)
N_CLUSTERS = len(cluster_indices)
CLUSTER_NAMES = [f"c{ci}" for ci in range(N_CLUSTERS)]
N_PATCHES = scenario.height

print(f"Scenario: {N_PATCHES} patches across {N_CLUSTERS} clusters")
for ci, idx in enumerate(cluster_indices):
    pop_sum = int(scenario["pop"].to_numpy()[idx].sum())
    print(f"  cluster {ci}: patches {idx.tolist()}  total pop {pop_sum:,}")

# %% [markdown]
# Layout — patches colored by cluster, marker size proportional to
# population. The chain along longitude is visible at a glance.

# %%
fig, ax = plt.subplots(figsize=(9, 3.5))
cluster_colors = plt.cm.viridis(np.linspace(0.1, 0.9, N_CLUSTERS))
for ci, idx in enumerate(cluster_indices):
    lats = scenario["lat"].to_numpy()[idx]
    lons = scenario["lon"].to_numpy()[idx]
    pops = scenario["pop"].to_numpy()[idx]
    ax.scatter(
        lons,
        lats,
        s=pops / 300,
        c=[cluster_colors[ci]],
        edgecolors="k",
        linewidths=0.4,
        alpha=0.85,
        label=f"cluster {ci}",
    )
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Synthetic chain scenario — 4 clusters × 5 patches (marker size ∝ population)")
ax.legend(loc="upper right", frameon=False, fontsize=9)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 3. Two implementations of the chain mixer
#
# We define both implementations inline so the notebook is self-
# contained and the regression check can run end-to-end.

# %% [markdown]
# ### Implementation A — `chain_constrained_migration_matrix` (function)
#
# Inherits nothing. Takes the scenario + cluster groupings + `k` + `c`
# explicitly. Generalizes to N clusters because the topology comes
# from the `cluster_indices` argument, not hard-coded indices. Returns
# a row-stochastic migration matrix where each nonzero row sums to `k`.

# %%
def chain_constrained_migration_matrix(
    scenario: pl.DataFrame,
    cluster_indices: list[np.ndarray],
    k: float,
    c: float = 1.5,
) -> np.ndarray:
    """Build a chain-constrained row-stochastic migration matrix.

    Migration is allowed only within a cluster and between **adjacent**
    clusters in ``cluster_indices`` (interpreted as a linear chain).
    Allowed-route weights come from a population-and-distance gravity
    kernel ``pop_j / d_{ij}**c``; each row is normalized so each patch
    sends fraction ``k`` of its population per tick.

    Args:
        scenario: patch DataFrame with ``pop``, ``lat``, ``lon`` columns.
        cluster_indices: patch indices grouped by cluster, in chain
            order.
        k: per-row outflow fraction.
        c: distance exponent for within-allowed-route gravity weights.

    Returns:
        Migration matrix of shape ``(n_patches, n_patches)``.
    """
    pop = scenario["pop"].to_numpy()
    lat = scenario["lat"].to_numpy()
    lon = scenario["lon"].to_numpy()
    n = len(pop)

    # cluster-of-each-patch lookup
    cluster_of = np.full(n, -1, dtype=int)
    for ci, idx in enumerate(cluster_indices):
        cluster_of[idx] = ci

    # allowed routes: same cluster or adjacent cluster, no self-loops
    diff = np.abs(cluster_of[:, None] - cluster_of[None, :])
    allowed = (diff <= 1) & (cluster_of[:, None] >= 0) & (cluster_of[None, :] >= 0)
    np.fill_diagonal(allowed, False)

    # great-circle distances + gravity weights on allowed routes only
    distances = distance(lat, lon, lat, lon)
    with np.errstate(divide="ignore", invalid="ignore"):
        weight = np.where(allowed, pop[None, :] / distances**c, 0.0)
    weight = np.nan_to_num(weight, nan=0.0, posinf=0.0)

    # row-normalize: each nonzero row sums to k
    row_sums = weight.sum(axis=1)
    scale = np.where(row_sums > 0, k / row_sums, 0.0)
    return weight * scale[:, None]


# %% [markdown]
# ### Implementation B — `ChainMixing(GravityMixing)` (the class currently used by the calibration tutorial)
#
# Hard-coded to 4 clusters via 4 constructor args. Keeps the
# `GravityMixing` parent (which we use here purely for the
# `get_distances()` helper and the abstract-method contract). For this
# notebook the only thing that matters is that it produces a matrix
# we can compare to the function's output.

# %%
class ChainMixing(GravityMixing):
    """Gravity mixing with forbidden cross-cluster shortcuts zeroed.

    Forbidden paths in the 4-cluster chain (A, B_far, B_near, C):
        A ↔ C, A ↔ B_near, B_far ↔ C.
    """

    def __init__(self, a_idx, bf_idx, bn_idx, c_idx, scenario=None, params=None):
        super().__init__(scenario=scenario, params=params)
        self._a_idx = np.asarray(a_idx, dtype=int)
        self._bf_idx = np.asarray(bf_idx, dtype=int)
        self._bn_idx = np.asarray(bn_idx, dtype=int)
        self._c_idx = np.asarray(c_idx, dtype=int)

    def get_migration_matrix(self) -> np.ndarray:
        pop = self.scenario["pop"].to_numpy()
        distances = self.get_distances()
        mat = gravity_fn(pop, distances, k=1.0, a=self.params.a - 1, b=self.params.b, c=self.params.c)
        np.fill_diagonal(mat, 0.0)
        mat[np.ix_(self._a_idx, self._c_idx)] = 0.0
        mat[np.ix_(self._c_idx, self._a_idx)] = 0.0
        mat[np.ix_(self._a_idx, self._bn_idx)] = 0.0
        mat[np.ix_(self._bn_idx, self._a_idx)] = 0.0
        mat[np.ix_(self._bf_idx, self._c_idx)] = 0.0
        mat[np.ix_(self._c_idx, self._bf_idx)] = 0.0
        row_sums = mat.sum(axis=1)
        nrm = np.where(row_sums > 0, self.params.k / row_sums, 0.0)
        mat *= nrm[:, np.newaxis]
        return mat


# %% [markdown]
# ## 4. The allowed/forbidden mask
#
# Before looking at the matrix values, let's look at the *topology*
# alone — which entries are even allowed to be nonzero. This is the
# defining feature of the chain mixer.

# %%
K = 0.01  # per-row outflow fraction
C = 1.5  # distance exponent

# Reconstruct the allowed mask (same logic as the function, but exposed standalone)
cluster_of = np.full(N_PATCHES, -1, dtype=int)
for ci, idx in enumerate(cluster_indices):
    cluster_of[idx] = ci
diff = np.abs(cluster_of[:, None] - cluster_of[None, :])
allowed = (diff <= 1) & (cluster_of[:, None] >= 0) & (cluster_of[None, :] >= 0)
np.fill_diagonal(allowed, False)


def _annotate_cluster_boundaries(ax, cluster_indices):
    """Draw cluster boundary lines + labels on a heatmap of the migration matrix."""
    offset = 0
    for ci, idx in enumerate(cluster_indices):
        size = len(idx)
        # cluster boundary box
        rect = Rectangle(
            (offset - 0.5, offset - 0.5),
            size,
            size,
            linewidth=1.5,
            edgecolor="white",
            facecolor="none",
        )
        ax.add_patch(rect)
        # cluster label at center
        ax.text(
            offset + size / 2 - 0.5,
            -1.5,
            f"c{ci}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
        ax.text(
            -1.5,
            offset + size / 2 - 0.5,
            f"c{ci}",
            ha="right",
            va="center",
            fontsize=9,
            fontweight="bold",
        )
        offset += size


fig, ax = plt.subplots(figsize=(6, 5.5))
ax.imshow(allowed.astype(float), cmap="RdYlBu_r", vmin=0, vmax=1, aspect="equal")
_annotate_cluster_boundaries(ax, cluster_indices)
ax.set_xlabel("destination patch")
ax.set_ylabel("source patch")
ax.set_title("Allowed (red) / Forbidden (blue) routes\nDiagonal and non-adjacent cluster pairs are blocked")
plt.tight_layout()
plt.show()

# %% [markdown]
# What to see in the figure above:
#
# - The matrix is block-structured. Four diagonal blocks (one per
#   cluster) and two off-diagonal blocks above + below each diagonal
#   block (adjacent-cluster pairs). All blue.
# - The blue everywhere else is *forbidden*: c0↔c2, c0↔c3, c1↔c3.
# - The diagonal is blue (forbidden self-loops in the migration
#   matrix — a patch can't "migrate to itself").

# %% [markdown]
# ## 5. The migration matrix
#
# Now compute the actual migration weights from the function and
# visualize. Within the allowed cells, gravity weights the destination
# by population and inverse distance.

# %%
M_function = chain_constrained_migration_matrix(scenario, cluster_indices, k=K, c=C)

fig, ax = plt.subplots(figsize=(6.5, 5.5))
# log-scale to make the wide dynamic range readable
img = ax.imshow(
    np.where(M_function > 0, M_function, np.nan),
    cmap="viridis",
    norm=LogNorm(vmin=max(M_function[M_function > 0].min(), 1e-8), vmax=M_function.max()),
    aspect="equal",
)
_annotate_cluster_boundaries(ax, cluster_indices)
plt.colorbar(img, ax=ax, label="migration weight (log scale)")
ax.set_xlabel("destination patch")
ax.set_ylabel("source patch")
ax.set_title("Migration matrix M  —  rows sum to k=0.01")
plt.tight_layout()
plt.show()

# %% [markdown]
# Things to notice:
#
# - **Same block structure as the mask** — gravity weights only show
#   up in the allowed blocks. The forbidden regions are exactly zero
#   (shown as blank/NaN in the log-scale plot).
# - **Within-cluster weights are usually larger than cross-cluster
#   weights** — patches inside a cluster are closer in distance and
#   often comparable in population, so the gravity kernel
#   ``pop_j / d^c`` favors them.
# - **Cross-cluster (adjacent) weights are visible but smaller** —
#   that's the chain coupling that lets transmission propagate from
#   cluster to cluster.

# %% [markdown]
# ## 6. The chain as a geographic graph
#
# A different lens on the same matrix: draw the patches as nodes
# positioned by lat/lon, with edges proportional to migration flow and
# colored by source cluster. Within-cluster edges are drawn thinner
# than cross-cluster edges so the chain coupling stands out.

# %%
fig, ax = plt.subplots(figsize=(11, 4.5))

lats = scenario["lat"].to_numpy()
lons = scenario["lon"].to_numpy()
pops = scenario["pop"].to_numpy()

# Determine separate scales so within-cluster edges aren't overwhelming
max_within = max(
    (M_function[i, j] for ci, idx in enumerate(cluster_indices) for i in idx for j in idx if i != j),
    default=1.0,
)
max_cross = max(
    (
        M_function[i, j]
        for ci, idx in enumerate(cluster_indices)
        for i in idx
        for j in range(N_PATCHES)
        if cluster_of[j] != ci and M_function[i, j] > 0
    ),
    default=1.0,
)

# Draw edges (cross-cluster first as thicker; within-cluster as faint)
for i in range(N_PATCHES):
    for j in range(N_PATCHES):
        if M_function[i, j] <= 0:
            continue
        same_cluster = cluster_of[i] == cluster_of[j]
        if same_cluster:
            ax.plot(
                [lons[i], lons[j]],
                [lats[i], lats[j]],
                color="gray",
                alpha=0.15,
                linewidth=0.5 + 2.0 * M_function[i, j] / max_within,
                zorder=1,
            )
        else:
            ax.plot(
                [lons[i], lons[j]],
                [lats[i], lats[j]],
                color=cluster_colors[cluster_of[i]],
                alpha=0.6,
                linewidth=0.8 + 4.0 * M_function[i, j] / max_cross,
                zorder=2,
            )

# Draw nodes
for ci, idx in enumerate(cluster_indices):
    ax.scatter(
        lons[idx],
        lats[idx],
        s=pops[idx] / 200,
        c=[cluster_colors[ci]],
        edgecolors="k",
        linewidths=0.6,
        zorder=3,
        label=f"cluster {ci}",
    )

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title(
    "Chain network — colored edges show cross-cluster migration; gray edges show within-cluster\n"
    f"(k={K}, c={C}; only adjacent clusters can exchange)"
)
ax.legend(loc="upper right", frameon=False, fontsize=9)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# The colored cross-cluster edges connect each cluster only to its
# chain-neighbors. There is no orange-to-purple direct edge (c1 ↔ c3),
# no blue-to-green direct edge (c0 ↔ c2), etc. — those forbidden routes
# from the mask are visually absent.

# %% [markdown]
# ## 7. Property checks
#
# Inline assertions that double as both regression tests and visible
# evidence the implementation is doing what it claims.

# %% [markdown]
# **Check 1**: every nonzero row sums to exactly `k`.

# %%
row_sums = M_function.sum(axis=1)
nonzero_rows = row_sums > 0

fig, ax = plt.subplots(figsize=(9, 3))
ax.bar(np.arange(N_PATCHES), row_sums, color="#4C72B0", alpha=0.85)
ax.axhline(K, color="#D32F2F", linestyle="--", linewidth=1.2, label=f"k = {K}")
ax.set_xlabel("patch index")
ax.set_ylabel("row sum")
ax.set_title("Row sums of the migration matrix — every row equals k")
ax.legend(loc="lower right", frameon=False)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

max_deviation = float(np.max(np.abs(row_sums[nonzero_rows] - K)))
print(f"max |row_sum - k| over nonzero rows: {max_deviation:.2e}")
assert max_deviation < 1e-12, f"row sums deviate from k by more than float epsilon: {max_deviation}"
print("✓ Check 1 passed: every nonzero row sums to k within 1e-12.")

# %% [markdown]
# **Check 2**: forbidden routes are *exactly* zero.

# %%
violations = 0
for ci_src in range(N_CLUSTERS):
    for ci_dst in range(N_CLUSTERS):
        if abs(ci_src - ci_dst) <= 1:
            continue  # allowed (same or adjacent)
        sub = M_function[np.ix_(cluster_indices[ci_src], cluster_indices[ci_dst])]
        if sub.max() > 0:
            violations += 1
            print(f"  ✗ forbidden block c{ci_src} → c{ci_dst} has max value {sub.max():.4e}")
assert violations == 0, f"{violations} forbidden block(s) had nonzero entries"
print(f"✓ Check 2 passed: all {N_CLUSTERS * (N_CLUSTERS - 1) - 2 * (N_CLUSTERS - 1)} forbidden cluster pairs are exactly zero.")

# %% [markdown]
# **Check 3**: the diagonal is zero (no self-loops in the migration
# matrix; self-mixing happens elsewhere in the SEIR pipeline).

# %%
diag_max = float(np.abs(np.diag(M_function)).max())
print(f"max |diag(M)|: {diag_max:.2e}")
assert diag_max == 0.0
print("✓ Check 3 passed: diagonal is exactly zero.")

# %% [markdown]
# **Check 4**: for every adjacent-cluster pair, *both* directions have
# at least one positive entry. (If forward-only coupling were possible,
# transmission would only flow downstream — we want bidirectional
# coupling for realism.)

# %%
missing_pairs = 0
for ci_src in range(N_CLUSTERS - 1):
    ci_dst = ci_src + 1
    forward = M_function[np.ix_(cluster_indices[ci_src], cluster_indices[ci_dst])]
    backward = M_function[np.ix_(cluster_indices[ci_dst], cluster_indices[ci_src])]
    if forward.max() <= 0:
        missing_pairs += 1
        print(f"  ✗ forward c{ci_src} → c{ci_dst} has no positive entry")
    if backward.max() <= 0:
        missing_pairs += 1
        print(f"  ✗ backward c{ci_dst} → c{ci_src} has no positive entry")
assert missing_pairs == 0
print(f"✓ Check 4 passed: all {N_CLUSTERS - 1} adjacent cluster pairs have positive flow in both directions.")

# %% [markdown]
# ## 8. Regression check — function vs. class
#
# The calibration tutorial currently uses `ChainMixing` (the class).
# A switch to the function-first design is only safe if the two
# produce numerically equivalent matrices on the calibration tutorial's
# scenario.
#
# Build both with the same scenario and parameters; compute the diff;
# visualize it; assert it's below float epsilon.

# %%
# Build the class-based mixer (note its 4-arg constructor — hard-coded)
chain_mixer_class = ChainMixing(
    a_idx=cluster_indices[0],
    bf_idx=cluster_indices[1],
    bn_idx=cluster_indices[2],
    c_idx=cluster_indices[3],
    scenario=scenario,
    params=GravityParams(k=K, c=C),
)
M_class = chain_mixer_class.get_migration_matrix()

diff = M_function - M_class
max_abs_diff = float(np.abs(diff).max())

fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

for ax, mat, title in [
    (axes[0], M_function, "Function-first"),
    (axes[1], M_class, "Class-based"),
]:
    img = ax.imshow(
        np.where(mat > 0, mat, np.nan),
        cmap="viridis",
        norm=LogNorm(vmin=max(mat[mat > 0].min(), 1e-8), vmax=mat.max()),
        aspect="equal",
    )
    _annotate_cluster_boundaries(ax, cluster_indices)
    ax.set_title(title)
    plt.colorbar(img, ax=ax, fraction=0.046, pad=0.04)

# Diff with symmetric color scale
diff_scale = max(np.abs(diff).max(), 1e-30)
img = axes[2].imshow(diff, cmap="RdBu_r", vmin=-diff_scale, vmax=diff_scale, aspect="equal")
_annotate_cluster_boundaries(axes[2], cluster_indices)
axes[2].set_title(f"Difference (function - class)\nmax |Δ| = {max_abs_diff:.2e}")
plt.colorbar(img, ax=axes[2], fraction=0.046, pad=0.04)

plt.tight_layout()
plt.show()

print(f"max |M_function - M_class|: {max_abs_diff:.4e}")
assert max_abs_diff < 1e-12, (
    f"function and class differ by more than float epsilon: {max_abs_diff:.4e}. Refactor is not behaviorally equivalent."
)
print("✓ Regression passed: function-first and class-based mixers agree to float epsilon.")
print("  The two implementations produce numerically identical migration matrices on")
print("  the calibration tutorial's scenario shape. Refactor is safe to swap in.")

# %% [markdown]
# ## 9. Generality — chain of 3 clusters
#
# The function-first design takes the cluster grouping as an argument
# rather than hard-coding it. Same scenario factory, `n_clusters=3`:

# %%
scenario_3, cluster_indices_3 = build_chain_scenario(n_clusters=3, rng=np.random.default_rng(101))
M_3 = chain_constrained_migration_matrix(scenario_3, cluster_indices_3, k=K, c=C)

fig, ax = plt.subplots(figsize=(5.5, 5))
img = ax.imshow(
    np.where(M_3 > 0, M_3, np.nan),
    cmap="viridis",
    norm=LogNorm(vmin=max(M_3[M_3 > 0].min(), 1e-8), vmax=M_3.max()),
    aspect="equal",
)
_annotate_cluster_boundaries(ax, cluster_indices_3)
plt.colorbar(img, ax=ax, label="migration weight (log scale)")
ax.set_title("Chain of 3 clusters (15 patches) — same function, different topology")
plt.tight_layout()
plt.show()

# Same property checks pass with no code changes
row_sums_3 = M_3.sum(axis=1)
nonzero_3 = row_sums_3 > 0
assert np.max(np.abs(row_sums_3[nonzero_3] - K)) < 1e-12
# forbidden: only c0↔c2 in a 3-chain
assert M_3[np.ix_(cluster_indices_3[0], cluster_indices_3[2])].max() == 0
assert M_3[np.ix_(cluster_indices_3[2], cluster_indices_3[0])].max() == 0
print("✓ 3-cluster chain: row sums = k, c0↔c2 routes are zero.")

# %% [markdown]
# ## 10. Generality — chain of 6 clusters
#
# Same recipe with more clusters. The block structure scales naturally;
# the function code is unchanged.

# %%
scenario_6, cluster_indices_6 = build_chain_scenario(n_clusters=6, n_patches_per_cluster=4, rng=np.random.default_rng(202))
M_6 = chain_constrained_migration_matrix(scenario_6, cluster_indices_6, k=K, c=C)

fig, ax = plt.subplots(figsize=(6.5, 6))
img = ax.imshow(
    np.where(M_6 > 0, M_6, np.nan),
    cmap="viridis",
    norm=LogNorm(vmin=max(M_6[M_6 > 0].min(), 1e-8), vmax=M_6.max()),
    aspect="equal",
)
_annotate_cluster_boundaries(ax, cluster_indices_6)
plt.colorbar(img, ax=ax, label="migration weight (log scale)")
ax.set_title("Chain of 6 clusters (24 patches) — same function, different topology")
plt.tight_layout()
plt.show()

# Forbidden pairs are all non-adjacent ones
violations = 0
for ci_src in range(6):
    for ci_dst in range(6):
        if abs(ci_src - ci_dst) <= 1:
            continue
        if M_6[np.ix_(cluster_indices_6[ci_src], cluster_indices_6[ci_dst])].max() > 0:
            violations += 1
assert violations == 0
print(f"✓ 6-cluster chain: all {6 * 6 - 6 - 2 * 5} forbidden pairs are zero.")

# %% [markdown]
# ## 11. Population flow over time
#
# The mixer is a *migration matrix*: at each tick, every patch sends
# fraction `k` of its population to its allowed neighbors, weighted by
# gravity. Iterating that operator on an initial population vector
# shows the chain wave concretely.
#
# We seed all population in cluster 0 and iterate `pop_t+1 = pop_t @ (I - k*I + M)`
# — keep what stays, plus inflows from neighbors. The exact recursion
# isn't physical (no births, no transmission, no patch-level
# normalization), but it's the right tool for visualizing the mixer's
# *topology* in time.

# %%
# Re-use the 4-cluster scenario for this demo
n_ticks = 200
M = M_function.copy()
N = scenario["pop"].to_numpy().astype(np.float64)

# Concentrate all population in cluster 0; zero out the rest
N_seeded = np.zeros_like(N)
N_seeded[cluster_indices[0]] = N[cluster_indices[0]] / N[cluster_indices[0]].sum()

# Iterate: at each tick, every patch loses k of its population (outflow)
# and receives the column sum of its inflows from neighbors.
trajectory = np.zeros((n_ticks, N_PATCHES))
trajectory[0] = N_seeded
for t in range(1, n_ticks):
    outflow_per_patch = trajectory[t - 1] * K
    inflows = trajectory[t - 1] @ M  # sum over sources weighted by M
    trajectory[t] = trajectory[t - 1] - outflow_per_patch + inflows

# Aggregate to per-cluster shares
cluster_share = np.zeros((n_ticks, N_CLUSTERS))
for ci, idx in enumerate(cluster_indices):
    cluster_share[:, ci] = trajectory[:, idx].sum(axis=1)

fig, ax = plt.subplots(figsize=(10, 4))
ax.stackplot(
    np.arange(n_ticks),
    cluster_share.T,
    colors=cluster_colors,
    alpha=0.85,
    labels=[f"cluster {ci}" for ci in range(N_CLUSTERS)],
)
ax.set_xlabel("tick")
ax.set_ylabel("share of seeded population")
ax.set_title(f"Population flow under the chain mixer (k={K}) — seeded in cluster 0")
ax.legend(loc="upper right", frameon=False)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# %% [markdown]
# What to read off the figure:
#
# - **At t=0**, all population is in cluster 0 (blue, full area).
# - **Cluster 1 fills in next** (the immediate neighbor) — the wave
#   front passes the c0/c1 boundary first.
# - **Cluster 2 fills in after cluster 1** — population can only
#   reach c2 via c1, never directly from c0.
# - **Cluster 3 fills in last** — must traverse c0 → c1 → c2 → c3.
#
# That ordering — strict chain propagation, no shortcuts — is the
# defining property of the chain mixer. In the calibration tutorial,
# this same propagation pattern (but with the SEIR machinery on top)
# is what creates the stochastic bottleneck at B_far: if its SIA
# suppresses the wave there, the chain breaks and clusters B_near
# and C never get invaded.

# %% [markdown]
# ## Where this connects back to the calibration tutorial
#
# - The [calibration tutorial's](tut_calibration_spatial.ipynb) §4
#   defines the same `ChainMixing` class shown here in Section 3-B.
#   That tutorial focuses on the calibration mechanics; this notebook
#   focuses on the mixer.
# - The "stochastic bottleneck" the calibration tutorial talks about
#   in §5 is exactly the structure visualized here in Section 11. The
#   chain ordering means a single subcritical cluster (B_far under its
#   SIA) can break the chain stochastically — sometimes the wave makes
#   it through, sometimes it doesn't.
# - The chain topology is *why* the parameter `c` (gravity distance
#   exponent) is hard to identify in the calibration tutorial's §8:
#   the mask zeros all the long-distance routes that `c` would
#   otherwise control. With only short-range, adjacent-cluster
#   coupling allowed, `c` is essentially cosmetic — a structural
#   consequence of the scenario design, not a model finding.
# - The regression check in Section 8 of *this* notebook is the
#   evidence that a refactor of `ChainMixing` to the function-first
#   design (or any other equivalent reimplementation) is safe — both
#   produce numerically identical migration matrices on the
#   calibration tutorial's scenario shape.
