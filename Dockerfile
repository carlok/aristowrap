# Lean 4.28 + Lake (minimal smoke lib) + uv + aristotlelib CLI. No API keys in image.
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

ENV ELAN_HOME=/root/.elan
ENV PATH="${ELAN_HOME}/bin:/root/.local/bin:${PATH}"

RUN curl -fsSL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none

WORKDIR /app

COPY lean-toolchain lakefile.toml lake-manifest.json Aristowrap.lean ./

# Single `lake build` only — no Mathlib in lakefile.toml, no `lake exe cache get`.
# If your build log still shows "lake exe cache get" or "8007 file(s)" from mathlib,
# you are on an old tree: `git pull` (see README).
RUN lake build

# Unit tests + coverage for scripts/aristowrap.py (fails build if tests or threshold fail)
WORKDIR /tmp/aristowrap-pytest
COPY pyproject.toml ./
COPY scripts ./scripts
COPY tests ./tests
RUN pip install --no-cache-dir pytest pytest-cov setuptools \
    && pip install --no-cache-dir -e . \
    && pytest tests/ -q --cov=scripts.aristowrap --cov-report=term-missing --cov-fail-under=55

WORKDIR /app

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv tool install aristotlelib

COPY scripts/aristowrap.py /usr/local/bin/aristowrap
RUN chmod +x /usr/local/bin/aristowrap

CMD ["bash"]
