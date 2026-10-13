# aristowrap

[![Docker Image CI](https://github.com/carlok/aristowrap/actions/workflows/docker.yml/badge.svg)](https://github.com/carlok/aristowrap/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/github/license/carlok/aristowrap)](LICENSE)

> **Unofficial** helper for [Aristotle](https://aristotle.harmonic.fun) (Harmonic). **Not affiliated** with Harmonic. API use is subject to Harmonic’s [Terms of Use](https://aristotle.harmonic.fun/terms) and [Privacy Policy](https://aristotle.harmonic.fun/privacy).

## Description

**aristowrap** is a small CLI that runs **Lean 4** + Harmonic’s **`aristotle`** tool inside **Docker** (or **Podman**), so you do not install elan, Lake, or Python on the host. Your project is bind-mounted at **`/app`**; **`submit`** sends a staged copy of your Lake/Lean tree to Aristotle and (by default) waits for a **`solution-*.tar.gz`**; **`verify`** unpacks an archive and runs **`lake build`**.

---

## TL;DR

| | |
|--|--|
| **Goal** | Submit formal tasks to Aristotle and optionally typecheck returned archives, without a local Lean toolchain. |
| **Need** | [Docker](https://docs.docker.com/) or [Podman](https://podman.io/) with **Compose v2**, this repo cloned, and **`aristotle.env`** with **`ARISTOTLE_API_KEY`**. |
| **Image** | Pull **[`carloperassi/aristowrap` on Docker Hub](https://hub.docker.com/r/carloperassi/aristowrap)** *or* **`compose build`** from the `Dockerfile`. |

**Fast path (Hub image + Compose):**

[`docker-compose.yml`](docker-compose.yml) names the service **`app`** and the image **`aristowrap-lean:local`**. After **`docker tag carloperassi/aristowrap:latest aristowrap-lean:local`** (or the Podman equivalents below), **`compose run --rm app …`** uses that local tag—no mismatch. **`pull_policy: never`** stops Compose from trying to pull a registry image under that name.

```bash
# From the repo root:
cp aristotle.env.example aristotle.env
# Put ARISTOTLE_API_KEY in aristotle.env (never commit real keys).

podman pull carloperassi/aristowrap:latest
podman tag carloperassi/aristowrap:latest aristowrap-lean:local
# examples/basic.prompt.txt is a ready-made one-line prompt; point --prompt-file at your own file for real work.
podman compose run --rm app aristowrap submit --prompt-file ./examples/basic.prompt.txt --log /app/aristotle-output/submit.log
```

Same steps with **`docker`** / **`docker compose`** instead of **`podman`** / **`podman compose`** if you use Docker. Replace **`latest`** with another Hub tag if you pin versions.

**One-liners:**

- **Help:** `podman compose run --rm app aristowrap --help`
- **Verify** newest tarball under `aristotle-output/`: `podman compose run --rm app aristowrap verify`
- **No Compose:** `podman run --rm -it -v "$(pwd):/app" --env-file aristotle.env -w /app carloperassi/aristowrap:latest aristowrap --help`

**Build locally instead of Hub:** `podman compose build` then `podman compose run --rm app aristowrap --help`.

---

## Details

### What the wrapper does

The **`aristowrap`** command is a thin Python layer on top of **`aristotle`**:

1. **`submit`** — Stages only the Lake/Lean files the job needs (skips **`.lake`**, **`lake-packages`**, etc.), then runs **`aristotle submit`**. By default it **waits** and writes a timestamped **`solution-*.tar.gz`** under **`aristotle-output/`** (or your **`--destination`**).
2. **`verify`** — Unpacks a solution archive, finds the Lake root, and runs **`lake build`** so you can check that returned code typechecks.

**Host without Docker:** **`uv run aristowrap`** works if **`aristotle`** and **`lake`** are already on your machine. The defaults point at **`/app`**, so on a bare host pass **`--source-project-dir`** / **`--output-dir`** (or set **`ARISTOWRAP_PROJECT_DIR`** / **`ARISTOWRAP_OUTPUT_DIR`**).

**Lake package name in this repo:** **`aristowrap`**; root library **`Aristowrap.lean`** (see [`lakefile.toml`](lakefile.toml)).

The shipped image includes the Lean toolchain pinned in [`lean-toolchain`](lean-toolchain) (currently **4.28.0**, the version Aristotle itself reports), **`lake`**, a pinned **`aristotle`** CLI, and **`aristowrap`**. The image’s baked Lake project is **minimal** (no Mathlib) so builds stay smaller; your real project (often with Mathlib) lives on the host under **`/app`**.

### Attribution & notifying Harmonic

Harmonic asks that integrations **mention `@Aristotle-Harmonic` on GitHub** (e.g. in a **PR** or **Issue** on this repo or your fork) when you ship or announce work built on Aristotle.

**Releases:** see the [changelog](CHANGELOG.md) and the GitHub releases page; image tags follow the release tags (`v0.1.1`, …), plus `main` and `latest`.

### Security notes

- **`verify` builds code you did not write.** The archive comes from a remote service, and Lean can run arbitrary code while building (`#eval`, macros, `lakefile.lean`, git dependencies). Treat the archive as untrusted.
- **The Compose setup is permissive.** The container runs as root, mounts your project read-write at `/app`, and `env_file` puts `ARISTOTLE_API_KEY` into every command, `verify` included.
- **Safer `verify`:** run it without the key and with a read-only mount, since it only needs to read the archive:

  ```bash
  podman run --rm -v "$(pwd):/app:ro" -w /app carloperassi/aristowrap:latest aristowrap verify
  ```

- Archives are extracted with `tarfile`'s `data` filter (Python 3.11.4+). Members that would land outside the temp directory abort the run with `unsafe archive rejected`.
- `submit` uploads only Lake root files and `*.lean` files, and skips symlinked `.lean` files so a link cannot pull in files from outside the project.

### Requirements

- **Container workflow:** Podman or Docker with Compose v2; network when **`lake`** / Mathlib must be fetched and (for submit) the Aristotle API.
- **Host `uv run aristowrap`:** Python ≥3.11, `aristotle` on `PATH` (e.g. `uv tool install aristotlelib`), and **`lake`** for `verify`.

### Quick start (container)

From the repo root:

```bash
cp aristotle.env.example aristotle.env
# Set ARISTOTLE_API_KEY in aristotle.env (never commit real keys).
```

Then either **pull** (no local build) or **build** (from this repo’s `Dockerfile`).

#### Without building: pull from Docker Hub

**[`carloperassi/aristowrap`](https://hub.docker.com/r/carloperassi/aristowrap)** is tagged as **`aristowrap-lean:local`** so this repo’s **`docker-compose.yml`** matches (`pull_policy: never` avoids a useless pull for that local name).

**Docker:**

```bash
docker pull carloperassi/aristowrap:latest
docker tag carloperassi/aristowrap:latest aristowrap-lean:local
docker compose run --rm app aristowrap --help
```

**Podman:**

```bash
podman pull carloperassi/aristowrap:latest
podman tag carloperassi/aristowrap:latest aristowrap-lean:local
podman compose run --rm app aristowrap --help
```

**Without Compose:**

```bash
docker run --rm -it \
  -v "$(pwd):/app" \
  --env-file aristotle.env \
  -w /app \
  carloperassi/aristowrap:latest \
  aristowrap --help
```

Use **`podman run`** the same way if you use Podman.

#### Build locally (from this repository)

```bash
podman compose build
podman compose run --rm app aristowrap --help
```

Use **`docker compose`** instead of **`podman compose`** if you use Docker. Compose bind-mounts **`.:/app`**; image name **`aristowrap-lean:local`**.

#### Building the image: Compose vs `podman build`

On some installs, **`podman compose build`** uses an external **docker-compose** provider, so the build runs on **Docker Desktop**, not Podman’s disk. **`RUN lake build`** can then fail with **no space left on device** while **`elan`** unpacks Lean under **`/root/.elan/`**—the engine’s VM needs **several GB** free.

**Workaround:** build only with Podman, then use Compose for **`run`**:

```bash
podman build -t aristowrap-lean:local -f Dockerfile .
podman compose run --rm app aristowrap --help
```

See **`podman compose --help`** / **`podman-compose(1)`** to avoid delegating **`compose build`** to Docker if your setup allows it.

### Basic usage

**Submit** with a prompt file and a full log under `aristotle-output/` (staged project, wait for tarball). Use your own file, or the bundled **`examples/basic.prompt.txt`** (the single line **`Prove that there are infinitely many primes.`**).

```bash
podman compose run --rm app aristowrap submit --prompt-file ./examples/basic.prompt.txt --log /app/aristotle-output/submit.log
```

**Submit** with an inline prompt string:

```bash
podman compose run --rm app aristowrap submit "Prove that there are infinitely many primes."
```

**Submit** without waiting (no tarball; check stderr for `Project created: …`):

```bash
podman compose run --rm app aristowrap submit "Your task." --no-wait
```

**Verify** newest `*.tar.gz` in the default output directory:

```bash
podman compose run --rm app aristowrap verify
```

**Verify** a specific archive:

```bash
podman compose run --rm app aristowrap verify /app/aristotle-output/solution-20260101T120000Z.tar.gz
```

**Host** (repo root, after `uv sync`):

```bash
uv run aristowrap --help
uv run aristowrap submit --help
uv run aristowrap verify --help

# Outside the container the /app defaults do not exist, so say where things are:
uv run aristowrap submit --prompt-file examples/basic.prompt.txt \
  --source-project-dir ~/my-lean-project --output-dir ~/my-lean-project/aristotle-output
```

### `aristowrap` CLI reference

#### Commands

| Command | Purpose |
|--------|---------|
| **`submit`** | Stage essential Lean/Lake files, then `aristotle submit …` |
| **`verify`** | Extract a `.tar.gz`, locate Lake root, run `lake build` |

#### `aristowrap submit`

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| **`PROMPT`** | One of PROMPT or `--prompt-file` | — | Prompt string passed to `aristotle submit`. |
| **`--prompt-file`** *PATH* | One of PROMPT or `--prompt-file` | — | Read prompt from UTF-8 file (must be non-empty after strip). |
| **`--source-project-dir`** *PATH* | No | `ARISTOWRAP_PROJECT_DIR` or **`/app`** | Directory to stage (Lake root + `*.lean`). |
| **`--output-dir`** *PATH* | No | `ARISTOWRAP_OUTPUT_DIR` or **`/app/aristotle-output`** | Where default timestamped `solution-*.tar.gz` is written when waiting. |
| **`--destination`** *PATH* | No | *(timestamped file under output-dir)* | Explicit path for the solution tarball (parent directories are created). Not allowed with **`--no-wait`**. |
| **`--no-wait`** | No | off | Do not pass `--wait` / `--destination` to `aristotle` (fire-and-forget). Without it, `aristowrap` waits by default. |
| **`--log`** *PATH* | No | — | Append full stdout+stderr of the `aristotle` run (with timestamps). |

**Default submit behavior:** `aristowrap` adds **`--wait`** and **`--destination`** (unless `--no-wait`). Bare `aristotle submit` does not wait unless you opt in.

**What gets staged:** present root files among `lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, `lakefile.lean`, `lean.toml`, plus all `**/*.lean` under the source tree, **excluding** directories named `.git`, `.lake`, `lake-packages`, `aristotle-output`, `__pycache__`, `.venv`, `tmp`, `build`, `node_modules` (pruned while walking) and symlinked `.lean` files.

**Prompt handling:** the prompt is passed after a `--` separator, so a prompt that starts with `-` is not read as an `aristotle` option.

**Exit codes:** the wrapped command's own code; `127` if `aristotle` / `lake` is not on `PATH`; `130` after Ctrl-C (the child process is stopped first).

#### `aristowrap verify`

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| **`TARBALL`** | No | Newest `*.tar.gz` in output dir | Path to the solution archive. |
| **`--output-dir`** *PATH* | No | `ARISTOWRAP_OUTPUT_DIR` or **`/app/aristotle-output`** | When `TARBALL` is omitted, pick newest `*.tar.gz` here. |

**Behavior:** Extracts to a temp directory with `tarfile`'s `data` filter (needs Python **3.11.4+**; older interpreters refuse to extract), resolves the Lake root (top-level `lakefile.toml` / `lakefile.lean`, else a single wrapper directory containing one, else the **shallowest** `lakefile.toml` / `lakefile.lean` found, never looking inside `.lake/`), then runs **`lake build`**. Exit code is that of `lake build`.

**Note:** `verify` checks that Lean builds, not “mathematical correctness.” A minimal archive may still need network/time to fetch Mathlib.

#### Environment variables

| Variable | Default | Used by |
|----------|---------|---------|
| **`ARISTOWRAP_PROJECT_DIR`** | `/app` | `submit` staging source when `--source-project-dir` omitted |
| **`ARISTOWRAP_OUTPUT_DIR`** | `/app/aristotle-output` | `submit` default tarball parent; `verify` default search dir |

### Container details

- **Dockerfile** runs **`lake build`** on a **minimal** Lake package (no Mathlib), then **pytest + coverage** on `scripts/aristowrap.py` (build fails if tests fail or coverage drops below the `fail_under` floor in [`pyproject.toml`](pyproject.toml), currently **90%**). Tools are pinned: elan (release asset with sha256 check), uv (versioned image) and `aristotlelib` (build arg); tests run against `uv.lock`..
- **`.dockerignore`** keeps **`.lake`**, **`aristotle-output`**, **`.git`**, etc. out of build context.
- At **runtime**, **`.:/app`** overlays the image’s `/app`, so you work against your checkout.

### Python tests (host)

```bash
uv sync --extra dev
uv run pytest tests/ -q --cov=scripts.aristowrap --cov-report=term-missing
```

### Raw `aristotle` vs `aristowrap`

- Without **`--wait`**, `aristotle submit` queues the job and logs a project id; **no** tarball.
- With **`--wait`**, it downloads the solution; **`--destination`** sets the file path.

`aristowrap submit` defaults to **wait + tarball** under **`aristotle-output/`** (or `--destination`).

### Troubleshooting

- **`Image aristowrap-lean:local Pulling` → `denied` → `Building`:** **`aristowrap-lean:local`** is a **local** tag, not a Hub repo—Compose’s pull fails, then it builds. Pull **[`carloperassi/aristowrap`](https://hub.docker.com/r/carloperassi/aristowrap)** and tag it **`aristowrap-lean:local`** (see [Without building: pull from Docker Hub](#without-building-pull-from-docker-hub)). **`pull_policy: never`** skips pull once that tag exists locally (Compose v2.23+).
- **Unexpected long rebuild / `COPY lean-toolchain …` without “Using cache”:** Cache invalidated by file changes, **different CPU arch** than last build, or no prior local image.
- **`no space left on device`** (storage under **`/var/lib/containers`** or **`/var/tmp`**): the **engine** building the image needs free space in **its** VM—check **`podman system df`** / **`docker system df`**, prune or grow **Podman Machine** / **Docker Desktop** disk.
- **`no space left on device`** during **`elan`** / **`RUN lake build`** with **`podman compose`** talking to **docker-compose**:** build is on **Docker**—use **`podman build -t aristowrap-lean:local -f Dockerfile .`** or free **Docker Desktop** disk.
- **Debian `apt-get` “invalid signature” / “repository is not signed”:** Often **truncated metadata** from **disk full**—free space, rebuild.
- **`no space left on device` during layer commit:** Lean toolchain is large; prune old images / builders. If Compose builds via Docker, prefer **`podman build`** for the image (see [Building the image: Compose vs `podman build`](#building-the-image-compose-vs-podman-build)).
- **`--no-wait` and no files:** Expected; read stderr for `Project created`.
- **`aristotle` says `API key not found` but the exit code is 0:** That is `aristotle`'s own behavior. `aristowrap` prints a warning on stderr when `ARISTOTLE_API_KEY` is unset; check `aristotle.env` is next to `docker-compose.yml` and has a key.
- **Compose `env_file` errors:** Create **`aristotle.env`** next to `docker-compose.yml`.
- **Slow or failing `lake build` in your own Mathlib project:** run `lake exe cache get` in that project (the image's baked skeleton has no Mathlib); check network.
- **Root-owned `.lake/` on host:** Fix ownership if your editor cannot write.
- **`verify` fails:** Archive may be incomplete or deps must be fetched in the temp tree.
- **`git status` not clean after `git pull`:** Inspect with **`git status -sb`** / **`git diff`**. To match **`origin/main`** (destructive): **`git fetch origin && git reset --hard origin/main`**. To keep edits: **`git stash`** then pull, or branch. Untracked **`aristotle-output/`** or **`.lake/`:** this repo ignores **`.lake/`**; use **`git rm -r --cached`** if something was tracked by mistake.

## Contributing

Issues and PRs are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md). Released under the [MIT License](LICENSE).
