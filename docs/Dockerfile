# laser-measles documentation build image.
#
# Pins the full mkdocs-jupyter + Jupyter + scientific-python toolchain so doc
# builds are reproducible and immune to upstream resolver drift. The image
# does NOT contain laser-measles itself — workflows check out the repo into
# the container at run time and `pip install --no-deps -e .` to wire up the
# package without re-resolving any dependencies.
#
# Build + publish locally (GHA workflows pull from Artifactory):
#
#   docker login packages.idmod.org
#   docker buildx build --platform linux/amd64 \
#       -t packages.idmod.org/docker-public/laser/laser-docs:latest \
#       -t packages.idmod.org/docker-public/laser/laser-docs:$(git rev-parse --short HEAD) \
#       -f docs/Dockerfile --push .
#
# `--platform linux/amd64` is important: GHA runners that consume this image
# are linux/amd64, so build for that explicitly even if your local machine
# is something else (e.g. Apple Silicon — without --platform you'd push an
# arm64 image and the consumer workflows would fail to pull).
#
# Rebuild whenever this Dockerfile, the [docs]/[examples] extras in
# pyproject.toml, or docs/requirements.txt change.

FROM python:3.12-slim

# System libraries that the scientific-python wheels need at runtime, plus
# build-essential as a fallback for any package that has no manylinux wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
        libgdal-dev \
        libgeos-dev \
        libhdf5-dev \
        libproj-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# uv handles the actual install. Pin major versions of both pip and uv so
# resolver behavior doesn't drift between image builds.
RUN pip install --no-cache-dir 'pip<26' 'uv<1'

# Docs + notebook-execution deps. Inlined (rather than COPYing requirements
# files) so the image is self-contained — anyone pulling the image gets the
# same closure regardless of which checkout they're consuming it from.
#
# Keep these lists aligned with:
#   - laser-measles' [docs] / [examples] extras in pyproject.toml
#   - docs/requirements.txt (used by the tox docs env)
#
# Split across four `RUN` invocations on purpose — the single 940 MB combined
# layer trips a server-side 500 on push to the IDM Artifactory at certain
# transfer sizes, and tooling like `crane` falls into a chunked-upload code
# path that triggers an unrelated Artifactory NPE on the same monolithic
# blob. Four ~150-300 MB layers push cleanly via `docker push` without
# chunking, and rebuilds get better cache reuse when one group's pin moves.
#
# Key constraints:
#   - numba>=0.60 because laser-core leaves numba unpinned, which lets uv
#     backtrack to numba==0.53.1 (Python<=3.9 only) on a 3.12 base.
#   - pyarrow is required by polars.DataFrame.to_pandas(), which
#     mkdocs-jupyter triggers when rendering polars frames in tutorials.

# Numeric stack — heaviest, most cache-stable (~250 MB).
RUN uv pip install --system --no-cache \
        'numpy>=1.26,<3' \
        'numba>=0.60' \
        pyarrow

# Scientific stack + laser-core (~250 MB).
RUN uv pip install --system --no-cache \
        matplotlib \
        polars \
        seaborn \
        'laser-core>=1.0.2,<2.0'

# Jupyter execution (~150 MB).
RUN uv pip install --system --no-cache \
        notebook \
        ipykernel \
        jupytext

# MkDocs + plugins (~100 MB) — smallest, most likely to churn.
RUN uv pip install --system --no-cache \
        'mkdocs-material~=9.7' \
        mkdocs-include-markdown-plugin \
        mkdocs-autorefs \
        mkdocs-api-autonav \
        mkdocs-gen-files \
        mkdocs-literate-nav \
        python-markdown-math \
        pymdown-extensions \
        mkdocs-jupyter \
        mkdocstrings \
        mkdocstrings-python \
        mkdocs-table-reader-plugin \
        mkdocs-exclude \
        markdownify

WORKDIR /repo
