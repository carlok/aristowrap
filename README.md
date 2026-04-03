# aristowrap

> **Unofficial** helper for [Aristotle](https://aristotle.harmonic.fun) (Harmonic). **Not affiliated** with Harmonic. Using the API is subject to Harmonic’s [Terms of Use](https://aristotle.harmonic.fun/terms) and [Privacy Policy](https://aristotle.harmonic.fun/privacy).

## Description

**aristowrap** is an **easy, Docker-first** way to use Harmonic’s [**aristotle**](https://aristotle.harmonic.fun) ([`aristotlelib`](https://pypi.org/project/aristotlelib/)) with **Lean 4** (and **Mathlib** in your own project when you add it)—without installing elan, Lake, or Python toolchains on your machine. Clone the repo, set your API key in a small env file, run **`compose build`** once, then **`compose run … aristowrap submit "…"`** from your project directory. The image ships **Lean 4.28.0**, the **`lake`** toolchain, the **`aristotle`** CLI, and **`aristowrap`**; the repo’s baked Lake project is **tiny** (no Mathlib) so **image builds stay small** and are less likely to exhaust disk during `podman`/`buildah` layer commits. Your real tree (often with Mathlib) lives on the host and is bind-mounted at **`/app`**.

The **`aristowrap`** command is a thin Python wrapper that makes day-to-day use smoother:

1. **`submit`** — Stages only the Lake/Lean files the job needs (skips huge trees like **`.lake`** / **`lake-packages`**), then runs **`aristotle submit`**. By default it **waits** for the job and drops a timestamped **`solution-*.tar.gz`** where you expect—less fiddling than raw `aristotle` flags.
2. **`verify`** — Unpacks a solution archive, finds the Lake root, and runs **`lake build`** so you can quickly check that returned code typechecks.

Prefer running on the host? **`uv run aristowrap`** works too if you already have **`aristotle`** and **`lake`** installed.

**Lake package name:** **`aristowrap`**; root library: **`Aristowrap.lean`** (see [`lakefile.toml`](lakefile.toml)).

If you still see **`AristotleDckr.lean`** or **`aristotle_dckr`** in an old checkout, remove/rename them and align with the files above—those names are obsolete.

### Attribution & notifying Harmonic

Harmonic asks that integrations **mention `@Aristotle-Harmonic` on GitHub** (for example in a **Pull Request** or **Issue** on this repository or your fork) when you ship or announce work that builds on Aristotle, so the team is notified.

**Repository metadata (maintainers):** In GitHub **About**, add a short description and **Topics** such as: `lean4`, `lake`, `aristotle`, `docker`, `podman`, `formal-methods`.

**Releases:** Tag stable commits (e.g. **`v0.1.0`**) so links and citations point at a fixed revision.

---

## Requirements

- **Container workflow:** [Podman](https://podman.io/) or Docker with Compose v2, network when **`lake`** / Mathlib must be fetched (e.g. your mounted project or a **`verify`** tarball) and (when submitting) the Aristotle API.
- **Host `uv run aristowrap`:** Python ≥3.11, `aristotle` on `PATH` (e.g. `uv tool install aristotlelib`), and **`lake`** for `verify`.

---

## Quick start (container)

From the repo root:

```bash
cp aristotle.env.example aristotle.env
# Set ARISTOTLE_API_KEY in aristotle.env (never commit real keys).

podman compose build
podman compose run --rm app aristowrap --help
```

Use **`docker compose`** instead of **`podman compose`** if you use Docker. Compose bind-mounts **`.:/app`**; image name **`aristowrap-lean:local`**.

### Building the image: Compose vs `podman build`

On some installs, **`podman compose build`** prints that it is **Executing external compose provider `/usr/local/bin/docker-compose`**. That means the build talks to **Docker Desktop**, not Podman’s storage. **`docker system df`** can look fine on the host while **`RUN lake build`** still fails with **no space left on device**: **`elan`** unpacks the **Lean 4.28** toolchain under **`/root/.elan/`** and needs **several gigabytes free inside that engine’s VM** during extract and layer commit.

**Workaround (recommended when Compose keeps hitting Docker):** build with Podman only, then use Compose for **`run`**:

```bash
podman build -t aristowrap-lean:local -f Dockerfile .
podman compose run --rm app aristowrap --help
```

To stop delegating to Docker for **`compose build`**, see **`podman-compose(1)`** or **`podman compose --help`** on your system (provider / env / config varies by version).

---

## Basic usage

**Submit** (staged project, wait for tarball under `aristotle-output/`):

```bash
podman compose run --rm app aristowrap submit "Prove that there are infinitely many primes."
```

**Submit** with prompt file and log:

```bash
podman compose run --rm app aristowrap submit --prompt-file ./prompt.txt --log /app/aristotle-output/submit.log
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

---

## `aristowrap` CLI reference

### Commands

| Command | Purpose |
|--------|---------|
| **`submit`** | Stage essential Lean/Lake files, then `aristotle submit …` |
| **`verify`** | Extract a `.tar.gz`, locate Lake root, run `lake build` |

### `aristowrap submit`

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| **`PROMPT`** | One of PROMPT or `--prompt-file` | — | Prompt string passed to `aristotle submit`. |
| **`--prompt-file`** *PATH* | One of PROMPT or `--prompt-file` | — | Read prompt from UTF-8 file (must be non-empty after strip). |
| **`--source-project-dir`** *PATH* | No | `ARISTOWRAP_PROJECT_DIR` or **`/app`** | Directory to stage (Lake root + `*.lean`). |
| **`--output-dir`** *PATH* | No | `ARISTOWRAP_OUTPUT_DIR` or **`/app/aristotle-output`** | Where default timestamped `solution-*.tar.gz` is written when waiting. |
| **`--destination`** *PATH* | No | *(timestamped file under output-dir)* | Explicit path for the solution tarball when **`--wait`** is used (default submit path). |
| **`--no-wait`** | No | off | Do not pass `--wait` / `--destination` to `aristotle` (fire-and-forget). |
| **`--log`** *PATH* | No | — | Append full stdout+stderr of the `aristotle` run (with timestamps). |

**Default submit behavior:** `aristowrap` adds **`--wait`** and **`--destination`** (unless `--no-wait`). That differs from bare `aristotle submit`, which does not wait unless you opt in.

**What gets staged:** copies present root files among `lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, `lakefile.lean`, `lean.toml`, plus all `**/*.lean` under the source tree, **excluding** any path segment in `.git`, `.lake`, `lake-packages`, `aristotle-output`, `__pycache__`, `.venv`.

### `aristowrap verify`

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| **`TARBALL`** | No | Newest `*.tar.gz` in output dir | Path to the solution archive. |
| **`--output-dir`** *PATH* | No | `ARISTOWRAP_OUTPUT_DIR` or **`/app/aristotle-output`** | When `TARBALL` is omitted, pick newest `*.tar.gz` here. |

**Behavior:** Extracts to a temp directory (Python **3.12+** uses `tarfile.extractall(..., filter='data')`), resolves Lake root (top-level `lakefile.toml`, or single top-level subdirectory containing it, or first `lakefile.toml` found), then runs **`lake build`** there. Exit code is that of `lake build`.

**Note:** `verify` does not prove “mathematical correctness”—only that Lean builds. A minimal archive may still need network/time to fetch Mathlib.

### Environment variables

| Variable | Default | Used by |
|----------|---------|---------|
| **`ARISTOWRAP_PROJECT_DIR`** | `/app` | `submit` staging source when `--source-project-dir` omitted |
| **`ARISTOWRAP_OUTPUT_DIR`** | `/app/aristotle-output` | `submit` default tarball parent; `verify` default search dir |

---

## Container details

- **Dockerfile** runs **`lake build`** on a **minimal** Lake package (no Mathlib) during image build, then **pytest + coverage** on `scripts/aristowrap.py` (fails build if tests fail or coverage is below **55%**).
- **`.dockerignore`** excludes **`.lake`**, **`aristotle-output`**, **`.git`**, etc., so **`docker build`** does not upload hundreds of MB of context (without it, Compose can look like it is “rebuilding everything” slowly for no reason).
- At **runtime**, **`.:/app`** overlays the image’s `/app`, so you develop against your checkout, not only the image layer.

---

## Python tests (host)

```bash
uv sync --extra dev
uv run pytest tests/ -q --cov=scripts.aristowrap --cov-report=term-missing --cov-fail-under=55
```

---

## Raw `aristotle` vs `aristowrap`

- Without **`--wait`**, `aristotle submit` queues the job and logs a project id; **no** tarball.
- With **`--wait`**, it downloads the solution; **`--destination`** sets the file path.

`aristowrap submit` defaults to **wait + tarball** under **`aristotle-output/`** (or `--destination`).

---

## Troubleshooting

- **Build log shows `RUN lake exe cache get && lake build` and Mathlib “8007 file(s)”:** Your checkout is **out of date**. Current **`Dockerfile`** uses only **`RUN lake build`** on a **Mathlib-free** skeleton; update with **`git pull origin main`**. Then **`podman compose build --no-cache`** once so old cached layers are not reused.
- **`Image aristowrap-lean:local Pulling` → `denied` → `Building`:** Compose treats **`image:`** as a registry reference and tries **`docker pull`** first. There is no image on Docker Hub with that name, so the pull fails and Compose builds from **`Dockerfile`** instead. This is normal—not an Aristotle API change. This repo sets **`pull_policy: never`** on the **`app`** service so that pull is skipped (requires Docker Compose v2.23+ / a provider that honors the Compose spec).
- **Unexpected long rebuild / `COPY lean-toolchain …` without “Using cache”:** Build cache is invalidated when those files change, when you build on a **different architecture** (e.g. `linux/amd64` vs `linux/arm64`) than last time, or when there is **no** prior local image. Harmonic does not control your image build.
- **`no space left on device`** (often under **`/var/lib/containers/storage`** or **`/var/tmp`**): the **container engine** that is actually building has **no** spare bytes in **its** VM/disk (not necessarily what macOS Activity Monitor shows). **`podman compose build --no-cache`** needs free space for every layer from scratch—**free disk first** (`df -h`, **`podman system df`** / **`docker system df`**, remove unused images, **`podman system prune -a`** / **`docker system prune -a`** if safe, grow **Podman Machine** or **Docker Desktop** virtual disk). Until that store has headroom, builds will keep failing at random steps.
- **`no space left on device`** while **`elan`** unpacks Lean (**`libLean.a`**, **`.elan/...tmp`**) during **`RUN lake build`**, and you use **`podman compose`** with the **docker-compose** provider: the build is running on **Docker**, not Podman—pruning Podman alone will not help. Use **`podman build -t aristowrap-lean:local -f Dockerfile .`** (see [Quick start](#building-the-image-compose-vs-podman-build)) or free space / grow **Docker Desktop**’s disk limit.
- **Debian `apt-get` errors: “invalid signature” / “repository is not signed” on `RUN apt-get update`:** Usually the same as **disk full**: `Release` / `InRelease` files or indexes are **truncated**, so GPG checks fail. Fix storage space, then rebuild—**not** a broken Debian mirror in the `Dockerfile`.
- **`no space left on device` during `RUN lake …` or when committing layers:** the active engine (**Podman** or **Docker**) may need **several GB free** in its VM for **`elan`** extract plus layer commit—even for a **small** Lake package, the **Lean toolchain** is large. If you previously used a Mathlib-heavy `Dockerfile` step, old cached layers could still be **multi‑GB**; this repo’s **`Dockerfile`** no longer downloads Mathlib (your **mounted** project can still be large). Free disk, **`podman system prune`** / **`docker builder prune`**, grow **Podman Machine** or **Docker Desktop** virtual disk. If Compose builds via Docker, prefer **`podman build`** for the image (see [above](#building-the-image-compose-vs-podman-build)).
- **`--no-wait` and no files:** Expected; read stderr for `Project created`.
- **Compose `env_file` errors:** Create **`aristotle.env`** next to `docker-compose.yml`.
- **Slow or failing `lake build`:** Run `lake exe cache get` again in the container; check network.
- **Root-owned `.lake/` on host:** Adjust ownership if your editor cannot write.
- **`verify` fails:** Archive may be incomplete for a standalone build, or dependencies must be fetched inside the temp tree.
- **`git status` not clean after `git pull`:** See what changed: **`git status -sb`** and **`git diff`**. To **throw away** all local edits and match **`origin/main`** (destructive): **`git fetch origin && git reset --hard origin/main`**. To **keep** them: **`git stash push -u -m "wip"`** then **`git pull`**, then **`git stash pop`**, or commit on a branch. If **`aristotle-output/`** or **`.lake/`** show as untracked and you do not want them listed, add them to **`.gitignore`** (this repo already ignores **`.lake/`**); remove accidentally tracked trees with **`git rm -r --cached <path>`** once.
