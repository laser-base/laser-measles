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

# Install laser-measles (pre-release) and its dependencies from PyPI
RUN pip install --upgrade --pre laser_measles
