# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Image base is now `python:3.15-slim-bookworm`; CI tests Python 3.11 to 3.15.

## [0.1.1] - 2026-10-13

### Security

- `verify` applies the tar `data` filter on every Python that supports it (3.11.4+, not only 3.12+) and refuses to extract on interpreters without it. Rejected members are reported as `unsafe archive rejected`.
- `submit` no longer uploads symlinked `.lean` files, which could point outside the project.
- README documents the `verify` trust model and a read-only, key-less way to run it.

### Fixed

- A prompt starting with `-` is no longer parsed as an `aristotle` option (`--` separator).
- `--destination` together with `--no-wait` is rejected instead of silently ignored; the destination's parent directory is created.
- A missing `aristotle` / `lake` gives a one-line error and exit code 127 instead of a traceback; Ctrl-C stops the child process and exits 130.
- `verify` picks the shallowest `lakefile.toml` / `lakefile.lean` (toml first on ties) and never looks inside `.lake/`.
- Staging prunes `.lake`, `tmp`, `build`, `node_modules` etc. while walking instead of scanning the whole tree.
- README no longer references a `--wait` flag, a `tmp/basic.prompt.txt` that is not in the repo, or the old Mathlib cache troubleshooting.

### Added

- Warning on stderr when `ARISTOTLE_API_KEY` is unset (`aristotle` itself exits 0 in that case).
- `examples/basic.prompt.txt`, `CONTRIBUTING.md`, `SECURITY.md`, issue and PR templates.
- CI: test matrix on Python 3.11 / 3.12 / 3.13, ruff lint and format check, Dependabot for Actions, uv and Docker. `:latest` is now also pushed from `main`.
- Package metadata (license, authors, classifiers, URLs).

### Changed

- CI: removed the duplicate `docker-image.yml` workflow that pushed the same tags twice; actions are pinned to commit SHAs.
- Image: elan installed from a pinned, checksummed release asset; uv and `aristotlelib` (2.1.0) pinned; in-image tests run against `uv.lock`.
- Test coverage 66% → 100%; the coverage floor lives in `pyproject.toml` (`fail_under = 90`).
- Lean toolchain stays at v4.28.0, which is what Aristotle's `/version` endpoint reports.

### Later

- A `verify` sandbox mode, non-root container user and read-only Compose profile.
- Move to a `src/aristowrap/` package layout.
- Multi-arch (arm64) published image.
- Strip ANSI progress output from `submit.log`.

## [0.1.0] - 2026-04-03

Initial release: `submit` (staged upload to Aristotle) and `verify` (`lake build` on a returned archive), packaged as a Docker/Podman image.
