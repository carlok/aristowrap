#!/usr/bin/env python3
"""Stage essential Lean/Lake files, call Harmonic's `aristotle`, optional verify via `lake build`."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

SKIP_SEGMENTS = frozenset(
    {
        ".git",
        ".lake",
        "lake-packages",
        "aristotle-output",
        "__pycache__",
        ".venv",
        "tmp",
        "build",
        "node_modules",
    }
)

ROOT_COPY_NAMES = (
    "lean-toolchain",
    "lakefile.toml",
    "lake-manifest.json",
    "lakefile.lean",
    "lean.toml",
)

LAKEFILE_NAMES = ("lakefile.toml", "lakefile.lean")


def _should_skip(rel_parts: tuple[str, ...]) -> bool:
    return any(p in SKIP_SEGMENTS for p in rel_parts)


def stage_essential_project(source: Path, dest: Path) -> None:
    """Copy Lake roots and all *.lean, excluding caches and dependency trees."""
    if not source.is_dir():
        raise SystemExit(f"aristowrap: not a directory: {source}")
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name in ROOT_COPY_NAMES:
        src = source / name
        if src.is_file():
            shutil.copy2(src, dest / name)
            copied += 1
    for dirpath, dirnames, filenames in os.walk(source):
        # Prune in place so dependency trees (.lake/packages, ...) are never walked.
        dirnames[:] = [d for d in dirnames if d not in SKIP_SEGMENTS]
        for fn in filenames:
            if not fn.endswith(".lean"):
                continue
            path = Path(dirpath) / fn
            if path.is_symlink():
                # A link could point outside the project and get uploaded.
                continue
            out = dest / path.relative_to(source)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
            copied += 1
    if copied == 0:
        raise SystemExit(
            "aristowrap: nothing to stage (need lean-toolchain / lakefile / manifest and/or .lean files)"
        )


def default_project_dir() -> Path:
    return Path(os.environ.get("ARISTOWRAP_PROJECT_DIR", "/app"))


def default_output_dir() -> Path:
    return Path(os.environ.get("ARISTOWRAP_OUTPUT_DIR", "/app/aristotle-output"))


def _finish(proc: subprocess.Popen[str], tee: TextIO | None = None) -> int:
    """Wait for `proc` (optionally tee-ing its output); stop it cleanly on Ctrl-C."""
    try:
        if tee is not None:
            if proc.stdout is None:
                raise RuntimeError("aristowrap: child stdout was not captured")
            for line in proc.stdout:
                sys.stdout.write(line)
                tee.write(line)
                tee.flush()
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return 130


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    log_path: Path | None = None,
) -> int:
    if shutil.which(cmd[0]) is None:
        print(f"aristowrap: {cmd[0]!r} not found on PATH", file=sys.stderr)
        return 127

    if log_path is None:
        return _finish(subprocess.Popen(cmd, cwd=cwd))

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as lf:
        lf.write(f"\n--- {datetime.now(UTC).isoformat()} ---\n")
        lf.write(f"$ {' '.join(cmd)}\n")
        lf.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        return _finish(proc, tee=lf)


def cmd_submit(args: argparse.Namespace) -> int:
    if args.destination and args.no_wait:
        raise SystemExit(
            "aristowrap submit: --destination needs the result, so it cannot be combined with --no-wait"
        )

    source = Path(args.source_project_dir or default_project_dir()).resolve()
    out_dir = Path(args.output_dir or default_output_dir()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
        if not prompt:
            raise SystemExit("aristowrap: --prompt-file is empty")
    elif args.prompt:
        prompt = args.prompt
    else:
        raise SystemExit("aristowrap submit: pass PROMPT or --prompt-file")

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest_tar = Path(args.destination).resolve() if args.destination else out_dir / f"solution-{ts}.tar.gz"

    log_path = Path(args.log).resolve() if args.log else None

    if not os.environ.get("ARISTOTLE_API_KEY"):
        print(
            "aristowrap: ARISTOTLE_API_KEY is not set; aristotle may fail to authenticate",
            file=sys.stderr,
        )

    with tempfile.TemporaryDirectory(prefix="aristowrap-stage-") as tmp:
        stage = Path(tmp)
        stage_essential_project(source, stage)
        cmd = ["aristotle", "submit", "--project-dir", str(stage)]
        if not args.no_wait:
            dest_tar.parent.mkdir(parents=True, exist_ok=True)
            cmd.extend(["--wait", "--destination", str(dest_tar)])
        # `--` keeps a prompt that starts with "-" from being parsed as an option.
        cmd.extend(["--", prompt])
        return _run(cmd, log_path=log_path)


def find_lake_root(start: Path) -> Path:
    """Return the Lake root: top level, a single wrapper dir, else the shallowest lakefile."""
    if any((start / n).is_file() for n in LAKEFILE_NAMES):
        return start
    dirs = [p for p in start.iterdir() if p.is_dir() and p.name != ".lake"]
    if len(dirs) == 1 and any((dirs[0] / n).is_file() for n in LAKEFILE_NAMES):
        return dirs[0]
    candidates: list[tuple[int, int, Path]] = []
    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = [d for d in dirnames if d != ".lake"]
        here = Path(dirpath)
        depth = len(here.relative_to(start).parts)
        for rank, name in enumerate(LAKEFILE_NAMES):
            if name in filenames:
                candidates.append((depth, rank, here))
    if candidates:
        return min(candidates)[2]
    raise SystemExit("aristowrap verify: no lakefile.toml or lakefile.lean under extracted archive")


def cmd_verify(args: argparse.Namespace) -> int:
    out_base = Path(args.output_dir).resolve() if args.output_dir else default_output_dir()

    if args.tarball:
        tar_path = Path(args.tarball).resolve()
    else:
        if not out_base.is_dir():
            raise SystemExit(f"aristowrap verify: output dir missing: {out_base}")
        tars = sorted(
            out_base.glob("*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not tars:
            raise SystemExit("aristowrap verify: no .tar.gz in output dir; pass TARBALL path")
        tar_path = tars[0]

    if not tar_path.is_file():
        raise SystemExit(f"aristowrap verify: not a file: {tar_path}")

    if not hasattr(tarfile, "data_filter"):
        raise SystemExit(
            "aristowrap verify: this Python's tarfile has no extraction filters "
            "(need 3.11.4+); refusing to extract an untrusted archive"
        )

    with tempfile.TemporaryDirectory(prefix="aristowrap-verify-") as tmp:
        root = Path(tmp)
        with tarfile.open(tar_path, "r:*") as tf:
            try:
                tf.extractall(root, filter="data")
            except tarfile.FilterError as exc:
                raise SystemExit(f"aristowrap verify: unsafe archive rejected: {exc}") from exc
        lake_root = find_lake_root(root)
        print(f"aristowrap verify: using lake root {lake_root}", file=sys.stderr)
        print(f"aristowrap verify: tarball {tar_path}", file=sys.stderr)
        return _run(["lake", "build"], cwd=lake_root)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aristowrap",
        description="Wrapper around Harmonic's aristotle CLI with lean staging and verify.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser(
        "submit",
        help="Stage essential Lean/Lake files and run aristotle submit",
    )
    sp.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Prompt string (optional if --prompt-file is set)",
    )
    sp.add_argument(
        "--prompt-file",
        type=Path,
        help="Read prompt from file (UTF-8)",
    )
    sp.add_argument(
        "--source-project-dir",
        type=Path,
        default=None,
        help="Project to stage (default: ARISTOWRAP_PROJECT_DIR or /app)",
    )
    sp.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for default solution-*.tar.gz (default: .../aristotle-output)",
    )
    sp.add_argument(
        "--destination",
        type=Path,
        default=None,
        help="Explicit path for solution .tar.gz when waiting (default: timestamped under output-dir)",
    )
    sp.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait or download; same as aristotle default",
    )
    sp.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Append full command log (stdout+stderr)",
    )
    sp.set_defaults(func=cmd_submit)

    vp = sub.add_parser(
        "verify",
        help="Extract a solution .tar.gz and run lake build (Lean acceptance check)",
    )
    vp.add_argument(
        "tarball",
        nargs="?",
        default=None,
        help="Path to solution archive (default: newest *.tar.gz under output dir)",
    )
    vp.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to look for newest .tar.gz when TARBALL omitted",
    )
    vp.set_defaults(func=cmd_verify)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
