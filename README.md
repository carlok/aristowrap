# aristowrap

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
# Create tmp/basic.prompt.txt (UTF-8). Example content:
#   Prove that there are infinitely many primes.
podman compose run --rm app aristowrap submit --prompt-file ./tmp/basic.prompt.txt --log /app/aristotle-output/submit.log
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

**Host without Docker:** **`uv run aristowrap`** works if **`aristotle`** and **`lake`** are already on your machine.

**Lake package name in this repo:** **`aristowrap`**; root library **`Aristowrap.lean`** (see [`lakefile.toml`](lakefile.toml)). If an old checkout still has **`AristotleDckr.lean`** / **`aristotle_dckr`**, those names are obsolete—align with the files above.

The shipped image includes **Lean 4.28.0**, **`lake`**, **`aristotle`**, and **`aristowrap`**. The image’s baked Lake project is **minimal** (no Mathlib) so builds stay smaller; your real project (often with Mathlib) lives on the host under **`/app`**.

### Attribution & notifying Harmonic

Harmonic asks that integrations **mention `@Aristotle-Harmonic` on GitHub** (e.g. in a **PR** or **Issue** on this repo or your fork) when you ship or announce work built on Aristotle.

**Maintainers:** In GitHub **About**, add topics such as `lean4`, `lake`, `aristotle`, `docker`, `podman`, `formal-methods`. **Releases:** tag stable commits (e.g. **`v0.1.0`**) for fixed references.

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

**Submit** with a prompt file and a full log under `aristotle-output/` (staged project, wait for tarball). Put your task in **`tmp/basic.prompt.txt`**—for example the single line: **`Prove that there are infinitely many primes.`**

```bash
podman compose run --rm app aristowrap submit --prompt-file ./tmp/basic.prompt.txt --log /app/aristotle-output/submit.log
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
| **`--destination`** *PATH* | No | *(timestamped file under output-dir)* | Explicit path for the solution tarball when **`--wait`** is used (default submit path). |
| **`--no-wait`** | No | off | Do not pass `--wait` / `--destination` to `aristotle` (fire-and-forget). |
| **`--log`** *PATH* | No | — | Append full stdout+stderr of the `aristotle` run (with timestamps). |

**Default submit behavior:** `aristowrap` adds **`--wait`** and **`--destination`** (unless `--no-wait`). Bare `aristotle submit` does not wait unless you opt in.

**What gets staged:** present root files among `lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, `lakefile.lean`, `lean.toml`, plus all `**/*.lean` under the source tree, **excluding** path segments `.git`, `.lake`, `lake-packages`, `aristotle-output`, `__pycache__`, `.venv`.

#### `aristowrap verify`

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| **`TARBALL`** | No | Newest `*.tar.gz` in output dir | Path to the solution archive. |
| **`--output-dir`** *PATH* | No | `ARISTOWRAP_OUTPUT_DIR` or **`/app/aristotle-output`** | When `TARBALL` is omitted, pick newest `*.tar.gz` here. |

**Behavior:** Extracts to a temp directory (Python **3.12+** uses `tarfile.extractall(..., filter='data')`), resolves Lake root (top-level `lakefile.toml`, or single top-level subdirectory containing it, or first `lakefile.toml` found), then runs **`lake build`**. Exit code is that of `lake build`.

**Note:** `verify` checks that Lean builds, not “mathematical correctness.” A minimal archive may still need network/time to fetch Mathlib.

#### Environment variables

| Variable | Default | Used by |
|----------|---------|---------|
| **`ARISTOWRAP_PROJECT_DIR`** | `/app` | `submit` staging source when `--source-project-dir` omitted |
| **`ARISTOWRAP_OUTPUT_DIR`** | `/app/aristotle-output` | `submit` default tarball parent; `verify` default search dir |

### Container details

- **Dockerfile** runs **`lake build`** on a **minimal** Lake package (no Mathlib), then **pytest + coverage** on `scripts/aristowrap.py` (build fails if tests fail or coverage is below **55%**).
- **`.dockerignore`** keeps **`.lake`**, **`aristotle-output`**, **`.git`**, etc. out of build context.
- At **runtime**, **`.:/app`** overlays the image’s `/app`, so you work against your checkout.

### Python tests (host)

```bash
uv sync --extra dev
uv run pytest tests/ -q --cov=scripts.aristowrap --cov-report=term-missing --cov-fail-under=55
```

### Raw `aristotle` vs `aristowrap`

- Without **`--wait`**, `aristotle submit` queues the job and logs a project id; **no** tarball.
- With **`--wait`**, it downloads the solution; **`--destination`** sets the file path.

`aristowrap submit` defaults to **wait + tarball** under **`aristotle-output/`** (or `--destination`).

### Troubleshooting

- **Build log shows `RUN lake exe cache get && lake build` and Mathlib “8007 file(s)”:** Checkout is **out of date**. Current **`Dockerfile`** uses only **`RUN lake build`** on a Mathlib-free skeleton; **`git pull origin main`**, then **`podman compose build --no-cache`** once.
- **`Image aristowrap-lean:local Pulling` → `denied` → `Building`:** **`aristowrap-lean:local`** is a **local** tag, not a Hub repo—Compose’s pull fails, then it builds. Pull **[`carloperassi/aristowrap`](https://hub.docker.com/r/carloperassi/aristowrap)** and tag it **`aristowrap-lean:local`** (see [Without building: pull from Docker Hub](#without-building-pull-from-docker-hub)). **`pull_policy: never`** skips pull once that tag exists locally (Compose v2.23+).
- **Unexpected long rebuild / `COPY lean-toolchain …` without “Using cache”:** Cache invalidated by file changes, **different CPU arch** than last build, or no prior local image.
- **`no space left on device`** (storage under **`/var/lib/containers`** or **`/var/tmp`**): the **engine** building the image needs free space in **its** VM—check **`podman system df`** / **`docker system df`**, prune or grow **Podman Machine** / **Docker Desktop** disk.
- **`no space left on device`** during **`elan`** / **`RUN lake build`** with **`podman compose`** talking to **docker-compose**:** build is on **Docker**—use **`podman build -t aristowrap-lean:local -f Dockerfile .`** or free **Docker Desktop** disk.
- **Debian `apt-get` “invalid signature” / “repository is not signed”:** Often **truncated metadata** from **disk full**—free space, rebuild.
- **`no space left on device` during layer commit:** Lean toolchain is large; prune old images / builders. If Compose builds via Docker, prefer **`podman build`** for the image (see [Building the image: Compose vs `podman build`](#building-the-image-compose-vs-podman-build)).
- **`--no-wait` and no files:** Expected; read stderr for `Project created`.
- **Compose `env_file` errors:** Create **`aristotle.env`** next to `docker-compose.yml`.
- **Slow or failing `lake build`:** Run `lake exe cache get` in the container; check network.
- **Root-owned `.lake/` on host:** Fix ownership if your editor cannot write.
- **`verify` fails:** Archive may be incomplete or deps must be fetched in the temp tree.
- **`git status` not clean after `git pull`:** Inspect with **`git status -sb`** / **`git diff`**. To match **`origin/main`** (destructive): **`git fetch origin && git reset --hard origin/main`**. To keep edits: **`git stash`** then pull, or branch. Untracked **`aristotle-output/`** or **`.lake/`:** this repo ignores **`.lake/`**; use **`git rm -r --cached`** if something was tracked by mistake.
