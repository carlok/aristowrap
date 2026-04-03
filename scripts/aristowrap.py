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
from datetime import datetime, timezone
from pathlib import Path

SKIP_SEGMENTS = frozenset(
    {
        ".git",
        ".lake",
        "lake-packages",
        "aristotle-output",
        "__pycache__",
        ".venv",
    }
)

ROOT_COPY_NAMES = (
    "lean-toolchain",
    "lakefile.toml",
    "lake-manifest.json",
    "lakefile.lean",
    "lean.toml",
)


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
    for path in source.rglob("*.lean"):
        rel = path.relative_to(source)
        if _should_skip(rel.parts):
            continue
        out = dest / rel
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


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    log_path: Path | None = None,
) -> int:
    if log_path is None:
        return subprocess.call(cmd, cwd=cwd)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as lf:
        lf.write(f"\n--- {datetime.now(timezone.utc).isoformat()} ---\n")
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
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            lf.write(line)
            lf.flush()
        return proc.wait()


def cmd_submit(args: argparse.Namespace) -> int:
    source = Path(args.source_project_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
        if not prompt:
            raise SystemExit("aristowrap: --prompt-file is empty")
    elif args.prompt:
        prompt = args.prompt
    else:
        raise SystemExit("aristowrap submit: pass PROMPT or --prompt-file")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_tar = (
        Path(args.destination).resolve()
        if args.destination
        else out_dir / f"solution-{ts}.tar.gz"
    )

    log_path = Path(args.log).resolve() if args.log else None

    with tempfile.TemporaryDirectory(prefix="aristowrap-stage-") as tmp:
        stage = Path(tmp)
        stage_essential_project(source, stage)
        cmd = ["aristotle", "submit", prompt, "--project-dir", str(stage)]
        if not args.no_wait:
            cmd.append("--wait")
            cmd.extend(["--destination", str(dest_tar)])
        return _run(cmd, log_path=log_path)


def find_lake_root(start: Path) -> Path:
    if (start / "lakefile.toml").is_file():
        return start
    dirs = [p for p in start.iterdir() if p.is_dir()]
    if len(dirs) == 1 and (dirs[0] / "lakefile.toml").is_file():
        return dirs[0]
    found = next(start.rglob("lakefile.toml"), None)
    if found is not None:
        return found.parent
    raise SystemExit("aristowrap verify: no lakefile.toml under extracted archive")


def cmd_verify(args: argparse.Namespace) -> int:
    out_base = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else default_output_dir()
    )

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
            raise SystemExit(
                "aristowrap verify: no .tar.gz in output dir; pass TARBALL path"
            )
        tar_path = tars[0]

    if not tar_path.is_file():
        raise SystemExit(f"aristowrap verify: not a file: {tar_path}")

    extract_kw: dict[str, str] = {}
    if sys.version_info >= (3, 12):
        extract_kw["filter"] = "data"

    with tempfile.TemporaryDirectory(prefix="aristowrap-verify-") as tmp:
        root = Path(tmp)
        with tarfile.open(tar_path, "r:*") as tf:
            tf.extractall(root, **extract_kw)
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
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "submit":
        if args.source_project_dir is None:
            args.source_project_dir = default_project_dir()
        if args.output_dir is None:
            args.output_dir = default_output_dir()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
