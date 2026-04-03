# aristowrap

Lean **4.28.0** + **Mathlib v4.28.0** with the [Aristotle](https://aristotle.harmonic.fun) CLI ([`aristotlelib`](https://pypi.org/project/aristotlelib/)) in a container, plus **`aristowrap`**: a small Python helper that stages only essential Lake/Lean files for upload, runs **`aristotle submit`**, and can **`verify`** a returned solution archive with **`lake build`**.

The Lake package and root library module are both named **`aristowrap`** / **`Aristowrap`** (see [`lakefile.toml`](lakefile.toml) and [`Aristowrap.lean`](Aristowrap.lean)).

**Podman is the recommended path**; Docker Compose works the same with a command swap.

## Why Podman first

- Rootless-friendly and matches many Linux/macOS setups without Docker Desktop.
- All commands below use **`podman compose`**. If you use Docker, replace that with **`docker compose`** everywhere—the Compose file is unchanged.

If `podman compose` prints a message about executing an external Compose provider (for example `/usr/local/bin/docker-compose`), your install is forwarding to another Compose implementation. That is expected on some setups; see `man podman-compose` to use or tune Podman’s own compose path.

## What you get

| Piece | Notes |
|--------|--------|
| **elan + Lean** | Pinned in [`lean-toolchain`](lean-toolchain) |
| **Mathlib** | Pinned in [`lakefile.toml`](lakefile.toml) |
| **`aristotle` CLI** | Installed with `uv tool install aristotlelib` inside the image |
| **`aristowrap`** | Copied to `/usr/local/bin/aristowrap` in the image; on the host use **`uv run aristowrap`** (see below) |
| **API key** | Loaded from **`aristotle.env`** (gitignored). Copy from [`aristotle.env.example`](aristotle.env.example). Never commit real keys. |

## `aristowrap` CLI (container or host)

### What `submit` uploads (essential-only)

`aristowrap submit` does **not** pass your full bind-mounted tree (with `.lake`, `lake-packages`, etc.) to Harmonic. It builds a **temporary staging directory** containing:

- Root Lake files if present: `lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, `lakefile.lean`, `lean.toml`
- All `**/*.lean` files, skipping any path segment in `.git`, `.lake`, `lake-packages`, `aristotle-output`, `__pycache__`, `.venv`

Then it runs **`aristotle submit PROMPT --project-dir <staging>`**. The solution tarball you get with **`--wait`** still reflects Harmonic’s view of **that staged tree** (plus generated/changed files)—typically much smaller than uploading the whole dev checkout.

### Defaults and environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `ARISTOWRAP_PROJECT_DIR` | `/app` | Source tree to stage (host: your checkout) |
| `ARISTOWRAP_OUTPUT_DIR` | `/app/aristotle-output` | Default parent for `solution-*.tar.gz` when waiting |

**Submit behavior:** by default **`aristowrap submit` adds `--wait`** and **`--destination`** (timestamped `solution-YYYYMMDDTHHMMSSZ.tar.gz` under the output dir unless you pass `--destination`). Use **`--no-wait`** to match raw `aristotle` fire-and-forget behavior (`--destination` is not passed).

```bash
podman compose run --rm app aristowrap submit "Prove that there are infinitely many primes."
# Optional:
podman compose run --rm app aristowrap submit --prompt-file ./prompt.txt --log /app/aristotle-output/submit.log
podman compose run --rm app aristowrap submit "…" --no-wait
```

### `aristowrap verify`

**Purpose:** sanity-check that the **Lean code** in a solution archive typechecks—not informal “math correctness.”

1. Extract the `.tar.gz` (safely: Python 3.12+ uses `tarfile`’s `filter='data'`).
2. Find a directory containing **`lakefile.toml`** (top level, single top-level folder, or search).
3. Run **`lake build`** there and propagate the exit code.

```bash
# Newest *.tar.gz under aristotle-output/ (or ARISTOWRAP_OUTPUT_DIR):
podman compose run --rm app aristowrap verify

# Explicit path:
podman compose run --rm app aristowrap verify /app/aristotle-output/solution-20260101T120000Z.tar.gz
```

**Caveats:** `verify` runs in a **clean temp tree**. If the archive does not contain everything `lake build` needs (or Mathlib must be fetched), you may need network and time comparable to a fresh checkout. For a full offline check, ensure the tarball layout matches what Lake expects after a normal project fetch.

### Host: `uv run aristowrap`

From the repo root (requires **`aristotle`** on your `PATH`, e.g. `uv tool install aristotlelib`; **`lake`**/`elan` for `verify`):

```bash
uv sync
uv run aristowrap --help
uv run aristowrap submit --help
uv run aristowrap verify --help
```

### Python unit tests and coverage (host)

Install dev dependencies and run **`pytest`** with coverage on **`scripts/aristowrap.py`**:

```bash
uv sync --extra dev
uv run pytest tests/ -q --cov=scripts.aristowrap --cov-report=term-missing --cov-fail-under=55
```

The **Docker image build** runs the same suite after `lake build`: if any test fails or coverage drops below **55%**, **`docker compose build`** / **`podman compose build`** fails. That keeps the small wrapper script exercised in CI-like builds without a separate stage name.

## Prerequisites

- [Podman](https://podman.io/) and a working `podman compose` (or Docker + Compose v2)
- Network access for Mathlib cache and, when you submit jobs, the Aristotle API

## One-time setup

From the repository root:

```bash
cp aristotle.env.example aristotle.env
# Edit aristotle.env and set ARISTOTLE_API_KEY to your real key.

podman compose build
podman compose run --rm app lake exe cache get
podman compose run --rm app lake build
podman compose run --rm app aristotle --help
podman compose run --rm app aristowrap --help
```

[`docker-compose.yml`](docker-compose.yml) bind-mounts **`.:/app`** so Lake and Mathlib artifacts live on your host under `.lake/` and `lake-packages/`. Image name: **`aristowrap-lean:local`**.

## Bind mount vs image build

The **Dockerfile** runs `lake exe cache get && lake build` during **`podman compose build`** as a smoke test inside the image. At **runtime**, the volume **`.:/app`** overlays `/app` with your checkout, so normal development always builds the **mounted** tree—not a stale layer from the image alone.

## Submit: raw `aristotle` vs `aristowrap`

`aristotle submit` behaves in two different ways:

1. **Without `--wait` (default for `aristotle`)**  
   The job is queued. The CLI logs a line like `INFO - Project created: <project_id>` on **stderr**.  
   **No tarball**; `--destination` is ignored without **`--wait`**.

2. **With `--wait`**  
   The CLI polls, then downloads the solution archive. **`--destination`** selects the path.

**`aristowrap submit`** defaults to **`--wait`** and a timestamped tarball under **`aristotle-output/`** unless you pass **`--no-wait`** or **`--destination`**.

Example matching classic “save tarball to repo” flow:

```bash
mkdir -p aristotle-output
podman compose run --rm app aristowrap submit \
  "Prove that there are infinitely many primes." \
  --destination /app/aristotle-output/solution.tar.gz
```

## Daily workflow

1. Edit `*.lean`, `lakefile.toml`, etc. on the host.
2. Build in the same environment you use for Aristotle:

   ```bash
   podman compose run --rm app lake build
   ```

3. Submit with **`aristowrap submit`** (staged upload) or raw **`aristotle`** if you prefer.

4. Optional interactive shell:

   ```bash
   podman compose run --rm -it app bash
   ```

## Using Docker instead of Podman

Replace `podman compose` with `docker compose` in every command above.

## When to rebuild the image

```bash
podman compose build
# Full clean rebuild:
podman compose build --no-cache
```

Rebuild when you change the **Dockerfile**, base image, or toolchain/Mathlib/aristotle expectations. You do **not** need to rebuild for ordinary `.lean` edits.

## Verification

```bash
podman compose build
podman compose run --rm app aristowrap --help
podman compose run --rm app aristowrap submit --help
podman compose run --rm app aristowrap verify --help
podman compose run --rm app aristotle --help
podman compose run --rm app lake build
# Requires a valid ARISTOTLE_API_KEY in aristotle.env.
# Fire-and-forget (stderr: "Project created"):
podman compose run --rm app aristowrap submit "Prove that there are infinitely many primes." --no-wait
# Wait and save solution tarball:
mkdir -p aristotle-output
podman compose run --rm app aristowrap submit "Prove that there are infinitely many primes." \
  --destination /app/aristotle-output/solution.tar.gz
```

## Troubleshooting

- **`submit` seems to do nothing / no new files:** With **`--no-wait`**, that is expected; check **stderr** for `Project created: …`. For a tarball, omit **`--no-wait`** or use explicit **`--wait`** via raw `aristotle`.
- **`env_file` / compose errors:** `aristotle.env` must exist next to `docker-compose.yml`.
- **Slow `lake build`:** Run `podman compose run --rm app lake exe cache get` again; check network from the container.
- **Root-owned `.lake/` or `lake-packages/`:** The container often runs as root; use `chown` on the host if your editor cannot write those directories.
- **`verify` fails after extract:** The archive may be incomplete for a standalone `lake build`, or Mathlib must be downloaded inside the temp dir; see [aristowrap verify](#aristowrap-verify).
