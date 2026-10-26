# Lean + Lake (minimal smoke lib; version comes from ./lean-toolchain) + uv + aristotlelib CLI.
# No API keys in the image. Base: Debian bookworm, Python 3.14.
FROM python:3.15-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

ENV ELAN_HOME=/root/.elan
ENV PATH="${ELAN_HOME}/bin:/root/.local/bin:${PATH}"

# elan-init.sh always fetches the *latest* elan, so install a pinned release asset instead.
# Digests come from the GitHub release API (`gh api repos/leanprover/elan/releases/tags/<tag>`).
ARG ELAN_VERSION=v4.2.4
ARG ELAN_SHA256_AMD64=42b94d4244e8353142c456ec0e4ca6528fd898a6c604d4059f494e706e431f63
ARG ELAN_SHA256_ARM64=05febd124d84ebf994b2e7479922a5650b1e950c17ae3bd1ddd776b65bb72bf9
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
      amd64) triple=x86_64-unknown-linux-gnu;  sha="${ELAN_SHA256_AMD64}" ;; \
      arm64) triple=aarch64-unknown-linux-gnu; sha="${ELAN_SHA256_ARM64}" ;; \
      *) echo "unsupported architecture" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/elan.tar.gz \
      "https://github.com/leanprover/elan/releases/download/${ELAN_VERSION}/elan-${triple}.tar.gz"; \
    echo "${sha}  /tmp/elan.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/elan.tar.gz -C /tmp; \
    /tmp/elan-init -y --default-toolchain none; \
    rm -f /tmp/elan.tar.gz /tmp/elan-init

# Pinned uv (Dependabot's docker ecosystem keeps this tag current).
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY lean-toolchain lakefile.toml lake-manifest.json Aristowrap.lean ./

# Single `lake build` only: no Mathlib in lakefile.toml, so nothing to cache-fetch.
RUN lake build

# Unit tests + coverage for scripts/aristowrap.py against uv.lock
# (fails the build if a test fails or coverage drops below fail_under in pyproject.toml).
WORKDIR /tmp/aristowrap-pytest
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY scripts ./scripts
COPY tests ./tests
RUN UV_PROJECT_ENVIRONMENT=/tmp/aristowrap-venv uv sync --extra dev --frozen \
    && UV_PROJECT_ENVIRONMENT=/tmp/aristowrap-venv uv run --frozen pytest tests/ -q \
       --cov=scripts.aristowrap --cov-report=term-missing \
    && rm -rf /tmp/aristowrap-venv

WORKDIR /app

# The `aristotle` CLI is what the wrapper shells out to; pin it so flag changes upstream
# show up as a reviewed bump rather than a silent break.
ARG ARISTOTLELIB_VERSION=2.1.0
RUN uv tool install "aristotlelib==${ARISTOTLELIB_VERSION}"

COPY scripts/aristowrap.py /usr/local/bin/aristowrap
RUN chmod +x /usr/local/bin/aristowrap

CMD ["bash"]
