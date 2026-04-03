# aristowrap

## Description

**aristowrap** is an **easy, Docker-first** way to use Harmonic’s [**aristotle**](https://aristotle.harmonic.fun) ([`aristotlelib`](https://pypi.org/project/aristotlelib/)) with **Lean 4** (and **Mathlib** in your own project when you add it)—without installing elan, Lake, or Python toolchains on your machine. Clone the repo, set your API key in a small env file, run **`compose build`** once, then **`compose run … aristowrap submit "…"`** from your project directory. The image ships **Lean 4.28.0**, the **`lake`** toolchain, the **`aristotle`** CLI, and **`aristowrap`**; the repo’s baked Lake project is **tiny** (no Mathlib) so **image builds stay small** and are less likely to exhaust disk during `podman`/`buildah` layer commits. Your real tree (often with Mathlib) lives on the host and is bind-mounted at **`/app`**.

The **`aristowrap`** command is a thin Python wrapper that makes day-to-day use smoother:

1. **`submit`** — Stages only the Lake/Lean files the job needs (skips huge trees like **`.lake`** / **`lake-packages`**), then runs **`aristotle submit`**. By default it **waits** for the job and drops a timestamped **`solution-*.tar.gz`** where you expect—less fiddling than raw `aristotle` flags.
2. **`verify`** — Unpacks a solution archive, finds the Lake root, and runs **`lake build`** so you can quickly check that returned code typechecks.

Prefer running on the host? **`uv run aristowrap`** works too if you already have **`aristotle`** and **`lake`** installed.

**Lake package name:** **`aristowrap`**; root library: **`Aristowrap.lean`** (see [`lakefile.toml`](lakefile.toml)).

If you still see **`AristotleDckr.lean`** or **`aristotle_dckr`** in an old checkout, remove/rename them and align with the files above—those names are obsolete.

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
- **`no space left on device` during `RUN lake …` or when committing layers:** Buildah/Podman may need **several GB free** in **`/var/tmp`** (and image storage) while committing a layer—even for a **small** image, spikes happen. If you previously used a Mathlib-heavy `Dockerfile` step, that layer was **multi‑GB**; this repo’s image build no longer downloads Mathlib (your **mounted** project can still be large). Free disk / grow the Podman machine disk / set **`TMPDIR`** to a roomy filesystem; **`podman system prune`**. On macOS Podman Machine: increase virtual disk in **Podman Desktop → settings**.
- **`--no-wait` and no files:** Expected; read stderr for `Project created`.
- **Compose `env_file` errors:** Create **`aristotle.env`** next to `docker-compose.yml`.
- **Slow or failing `lake build`:** Run `lake exe cache get` again in the container; check network.
- **Root-owned `.lake/` on host:** Adjust ownership if your editor cannot write.
- **`verify` fails:** Archive may be incomplete for a standalone build, or dependencies must be fetched inside the temp tree.
