# Contributing

Thanks for looking. aristowrap is a small wrapper, so the bar for a change is low and the process is short.

## Set up

```bash
uv sync --extra dev
uv run pytest tests/ -q --cov=scripts.aristowrap --cov-report=term-missing
uv run ruff check . && uv run ruff format --check .
```

Tests use fake `aristotle` / `lake` binaries on `PATH`, so they need no network, no API key and no Lean install. Coverage must stay above the `fail_under` floor in `pyproject.toml`.

To check the image: `docker build -t aristowrap-lean:local .` (the build runs the same tests against `uv.lock`).

## Pull requests

- Branch from `main`, keep one topic per PR.
- Add or update tests for behavior changes. A bug fix should come with a test that fails without it.
- Update `README.md` when a flag, default or exit code changes, and add a line to `CHANGELOG.md` under *Unreleased*.
- Run `ruff format .` before pushing; CI checks it on Python 3.11 to 3.15.

## Reporting problems

Open an issue with the command you ran, the output, and your container runtime (Docker/Podman) and version. Do not paste your `ARISTOTLE_API_KEY`. For security problems, see [SECURITY.md](SECURITY.md).

## Scope

aristowrap stays a thin layer over Harmonic's `aristotle` CLI. Anything that needs Aristotle's API behavior to change belongs upstream.
