# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies used across docgen runs and tests.
RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first to leverage Docker layer caching.
COPY requirements/ requirements/

# Allow opting into development tooling at build time.
ARG INSTALL_DEV=false

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements/base.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements/dev.txt; fi

# Copy the remainder of the application code.
COPY . .

# Install docgen in editable mode so local changes are reflected immediately.
RUN pip install --no-cache-dir -e .

# Default command exposes the CLI help text; override in docker run for specific commands.
CMD ["python", "-m", "docgen.cli", "--help"]
