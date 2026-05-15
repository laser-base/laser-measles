# Spatial mixing

Measles spreads between communities. In laser-measles, the landscape is divided into discrete patches (administrative units, districts, or grid cells), and spatial mixing models control how much transmission pressure each patch exerts on every other patch. This page explains the four spatial mixing models available and the concepts behind them.

## Why spatial mixing matters

Without spatial mixing, each patch in a simulation is an isolated population — an epidemic in one district has no effect on neighboring districts. In reality, people travel for work, trade, healthcare, and social reasons, carrying infections with them. Spatial mixing models translate these movement patterns into a **mixing matrix** that determines what fraction of each patch's transmission pressure reaches every other patch.

The mixing matrix is central to producing realistic spatial dynamics: synchronized outbreaks in well-connected urban areas, delayed spread to remote regions, and geographic patterns of immunity that match surveillance data.

## The mixing matrix

All spatial mixing models in laser-measles produce a square **mixing matrix** of shape `(N, N)` where `N` is the number of patches. Entry `M[i, j]` represents the probability that a person in patch `i` interacts with patch `j` during one timestep.

The mixing matrix is constructed in two steps:

1. **Migration matrix**: A model-specific formula computes the off-diagonal entries — the probability of traveling from patch `i` to patch `j`. These probabilities depend on population sizes, distances, and model parameters.
2. **Diagonal fill**: The diagonal entries are set so that each row sums to 1. Entry `M[i, i]` represents the probability of *staying home* — interacting only within your own patch.

This means the mixing matrix is row-stochastic: for any patch `i`, the fractions of time spent in all patches (including home) sum to 1.

## Available models

laser-measles provides four spatial mixing models, all accessible from `laser.measles.mixing`. Each implements a different theory of human mobility.

### Gravity model

The gravity model is the most widely used spatial mixing model in epidemiology. It is inspired by Newton's law of gravitation: movement between two places increases with their populations and decreases with the distance between them.

$$
M_{i,j} = k \cdot p_i^{a-1} \cdot p_j^b \cdot d_{i,j}^{-c}
$$

Where:

- $p_i$, $p_j$ are the populations of the origin and destination patches
- $d_{i,j}$ is the geographic distance between them
- $k$ controls the overall level of mobility (average trip probability)
- $a$ scales the origin population effect
- $b$ scales the destination population effect
- $c$ controls how steeply movement declines with distance

**When to use it**: The gravity model is a good default choice. It works well when you have population and location data but no direct mobility measurements. The parameters are intuitive and can be calibrated to match known travel patterns.

**Parameters** (`GravityParams`):

| Parameter | Default | Description |
|---|---|---|
| `k` | 0.01 | Scale parameter (average trip probability per timestep) |
| `a` | 1.0 | Origin population exponent (≥ 1.0) |
| `b` | 1.0 | Destination population exponent |
| `c` | 1.5 | Distance decay exponent |

### Radiation model

The radiation model is a parameter-free alternative to the gravity model (aside from the overall scale `k`). Instead of tuning distance and population exponents, it predicts movement based on *intervening opportunities*: a person considers destinations in order of increasing distance, and closer destinations with large populations "absorb" some of the flow that would otherwise reach more distant places.

$$
M_{i,j} = k \cdot \frac{p_i \cdot p_j}{\left(p_i + s_{ij}\right)\left(p_i + p_j + s_{ij}\right)}
$$

Where $s_{ij}$ is the total population in all patches closer to $i$ than $j$ is (the "intervening opportunities").

**When to use it**: The radiation model is useful when you want to avoid calibrating distance-decay parameters, or when you believe that intervening population density (not just raw distance) is the main driver of travel patterns. It tends to produce less long-distance movement than the gravity model.

**Parameters** (`RadiationParams`):

| Parameter | Default | Description |
|---|---|---|
| `k` | 0.01 | Scale parameter (average trip probability) |
| `include_home` | True | Whether to include the home patch in the opportunity set |

### Competing destinations model

The competing destinations model extends the gravity model by accounting for the effect of *other destinations* near the target. If patch `j` is surrounded by many other attractive destinations, it receives less flow than its population and distance alone would predict — travelers are "siphoned off" by the competing alternatives.

$$
M_{i,j} = k \cdot \frac{p_i^{a-1} \cdot p_j^b}{d_{i,j}^c} \cdot \left(\sum_{k \ne i,j} \frac{p_k^b}{d_{ik}^c}\right)^{\delta}
$$

The additional parameter $\delta$ controls the strength of the competition effect. When $\delta = 0$, this reduces to the standard gravity model.

**When to use it**: Use the competing destinations model when modeling regions with uneven spatial structure — for example, when several large cities are clustered together and you want to capture the competition between them for travelers from rural areas.

**Parameters** (`CompetingDestinationsParams`):

| Parameter | Default | Description |
|---|---|---|
| `k` | 0.01 | Scale parameter |
| `a` | 1.0 | Origin population exponent (≥ 1.0) |
| `b` | 1.0 | Destination population exponent |
| `c` | 1.5 | Distance decay exponent |
| `delta` | 0.0 | Destination competition exponent (0 = standard gravity) |

### Stouffer model

The Stouffer model (also called the intervening opportunities model) predicts that the probability of traveling to a destination depends not on absolute distance but on how many *opportunities* (people, in this context) lie between the origin and destination. It is related to the radiation model but uses a different functional form.

$$
M_{i,j} = k \cdot p_i^a \cdot \sum_j \left(\frac{p_j}{\sum_{k \in \Omega(i,j)} p_k}\right)^b
$$

Where $\Omega(i,j)$ is the set of patches closer to $i$ than $j$.

**When to use it**: The Stouffer model is useful when distance is a poor proxy for accessibility — for example, in regions where travel routes follow rivers, roads, or terrain rather than straight-line distance. The intervening-opportunities framework captures the idea that what matters is not how far away a place is, but how many alternatives are closer.

**Parameters** (`StoufferParams`):

| Parameter | Default | Description |
|---|---|---|
| `k` | 0.01 | Scale parameter |
| `a` | 1.0 | Origin population exponent |
| `b` | 1.0 | Destination population exponent |
| `include_home` | True | Whether to include home in the opportunity set |

## How mixing models connect to infection

Spatial mixing models are not standalone — they are attached to infection components via the infection parameters. When an infection component computes transmission for a given timestep, it uses the mixing matrix to distribute infectious pressure across patches.

The mixer is instantiated separately and passed to the infection component's parameters. The model automatically provides the scenario data (populations, coordinates) to the mixer before the first timestep, so you do not need to pass the scenario explicitly.

## The scale parameter `k`

All four models share a `k` parameter that controls the overall level of mobility. Conceptually, `k` represents the average probability that a person in any given patch travels to *any* other patch during one timestep. The model-specific formula determines *where* travelers go; `k` determines *how many* travelers there are.

- `k = 0.01` means roughly 1% of each patch's population travels per timestep.
- Larger `k` produces more inter-patch transmission and faster spatial spread.
- Smaller `k` produces more isolated patches and slower spatial spread.

The right value of `k` depends on your timestep length, the geographic scale of your patches, and the mobility patterns of your study population.

## See also

- [How to configure spatial mixing](configuring-spatial-mixing.md) — step-by-step guide to setting up a mixer
- [Model types](index.md) — overview of the three model types that use spatial mixing
- [Demographics](demographics.md) — how scenario data (populations, coordinates) flows into the mixing matrix
- [Tutorial: Spatial mixing](../../tutorials/tut_spatial_mixing.py) — hands-on tutorial on spatial mixing
- [API reference](../../reference/laser/measles/mixing/index.md) — full class and parameter details
