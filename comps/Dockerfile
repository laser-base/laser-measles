FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    git \
    wget \
    gzip \
    build-essential \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    libffi-dev \
    libssl-dev \
    && apt-get clean

# Install pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Force python3/pip to point to Python 3.11
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/local/bin/pip3.11 /usr/bin/pip && \
    ln -sf /usr/local/bin/pip3.11 /usr/bin/pip3

WORKDIR /app

# Optional — break cache
ARG CACHE_BREAKER=1

# Upgrade pip + install dependencies
RUN pip install --upgrade pip setuptools wheel

COPY requirements-container.txt .
RUN pip install --pre -r requirements-container.txt

# Pre-warm numba JIT by running a tiny ABM — compiled kernels are baked into
# this image layer so COMPS workers skip the ~24-minute first-run compilation.
ENV NUMBA_CACHE_DIR=/app/.numba_cache
RUN python3 - <<'EOF'
import numpy as np
import polars as pl
from laser.measles.abm import ABMModel, ABMParams, components
from laser.measles.components import create_component

scenario = pl.DataFrame({
    "id": ["p0", "p1"], "lat": [0.0, 1.0], "lon": [0.0, 1.0],
    "pop": np.array([5000, 5000]), "mcv1": np.zeros(2),
})
params = ABMParams(num_ticks=10, seed=42, show_progress=False, use_numba=True)
model = ABMModel(scenario=scenario, params=params, name="warmup")
model.add_component(create_component(
    components.InitializeEquilibriumStatesProcess,
    components.InitializeEquilibriumStatesParams(R0=1.0),
))
model.add_component(create_component(
    components.VitalDynamicsProcess,
    components.VitalDynamicsParams(crude_birth_rate=30.0, crude_death_rate=30.0),
))
model.add_component(create_component(
    components.InfectionSeedingProcess,
    components.InfectionSeedingParams(num_infections=10, use_largest_patch=True),
))
model.add_component(create_component(
    components.ImportationPressureProcess,
    components.ImportationPressureParams(crude_importation_rate=0.05),
))
model.add_component(create_component(
    components.InfectionProcess,
    components.InfectionParams(beta=0.8, seasonality=0.15),
))
model.add_component(create_component(
    components.StateTracker,
    components.StateTrackerParams(aggregation_level=-1),
))
model.run()
print("Numba warmup complete.")
EOF
