"""Unit tests for scripts.aristowrap (staging, lake root discovery, submit/verify wiring)."""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts import aristowrap as aw
from scripts.aristowrap import (
    _should_skip,
    build_parser,
    default_output_dir,
    default_project_dir,
    find_lake_root,
    stage_essential_project,
)

needs_data_filter = pytest.mark.skipif(
    not hasattr(tarfile, "data_filter"), reason="tarfile extraction filters unavailable"
)


# --- helpers ---------------------------------------------------------------


def make_project(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "lean-toolchain").write_text("leanprover/lean4:v4.28.0\n", encoding="utf-8")
    (path / "lakefile.toml").write_text('name = "t"\n', encoding="utf-8")
    (path / "X.lean").write_text("-- ok\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """PATH holding only fake `aristotle` and `lake` that record how they were called."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_out = tmp_path / "argv.txt"
    cwd_out = tmp_path / "cwd.txt"
    (bin_dir / "aristotle").write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$ARGV_OUT"\necho "aristotle says hi"\nexit "${FAKE_RC:-0}"\n',
        encoding="utf-8",
    )
    (bin_dir / "lake").write_text(
        '#!/bin/sh\npwd > "$CWD_OUT"\nexit "${FAKE_RC:-0}"\n',
        encoding="utf-8",
    )
    for name in ("aristotle", "lake"):
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("ARGV_OUT", str(argv_out))
    monkeypatch.setenv("CWD_OUT", str(cwd_out))
    monkeypatch.setenv("ARISTOTLE_API_KEY", "test-key")
    monkeypatch.delenv("FAKE_RC", raising=False)
    return bin_dir


def recorded_argv(tmp_path: Path) -> list[str]:
    return (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()


def write_tar(path: Path, members: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


# --- staging ---------------------------------------------------------------


def test_should_skip_detects_cache_segments() -> None:
    assert _should_skip((".lake", "Foo.lean"))
    assert _should_skip(("src", "lake-packages", "x.lean"))
    assert _should_skip(("a", ".git", "b"))
    assert _should_skip(("tmp", "scratch.lean"))
    assert not _should_skip(("Aristowrap.lean",))
    assert not _should_skip(("src", "Proof.lean"))


def test_stage_essential_project_copies_roots_and_lean(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    src.mkdir()
    (src / "lean-toolchain").write_text("leanprover/lean4:v4.28.0\n", encoding="utf-8")
    (src / "lakefile.toml").write_text('name = "x"\n', encoding="utf-8")
    (src / "lake-manifest.json").write_text("{}\n", encoding="utf-8")
    nested = src / "Sub" / "Proof.lean"
    nested.parent.mkdir(parents=True)
    nested.write_text("-- ok\n", encoding="utf-8")

    dest = tmp_path / "out"
    stage_essential_project(src, dest)

    assert (dest / "lean-toolchain").is_file()
    assert (dest / "lakefile.toml").is_file()
    assert (dest / "Sub" / "Proof.lean").read_text(encoding="utf-8") == "-- ok\n"


def test_stage_essential_project_skips_under_dot_lake(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    src.mkdir()
    (src / "lean-toolchain").write_text("x\n", encoding="utf-8")
    (src / "lakefile.toml").write_text('name = "x"\n', encoding="utf-8")
    bad = src / ".lake" / "cache" / "bad.lean"
    bad.parent.mkdir(parents=True)
    bad.write_text("oops\n", encoding="utf-8")
    good = src / "Good.lean"
    good.write_text("-- ok\n", encoding="utf-8")

    dest = tmp_path / "out"
    stage_essential_project(src, dest)
    assert not (dest / ".lake").exists()
    assert (dest / "Good.lean").is_file()


def test_stage_essential_project_skips_tmp_build_and_node_modules(tmp_path: Path) -> None:
    src = make_project(tmp_path / "proj")
    for d in ("tmp", "build", "node_modules"):
        (src / d).mkdir()
        (src / d / "Junk.lean").write_text("--\n", encoding="utf-8")

    dest = tmp_path / "out"
    stage_essential_project(src, dest)
    assert (dest / "X.lean").is_file()
    for d in ("tmp", "build", "node_modules"):
        assert not (dest / d).exists()


def test_stage_essential_project_does_not_walk_pruned_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_project(tmp_path / "proj")
    deep = src / ".lake" / "packages" / "mathlib" / "Mathlib"
    deep.mkdir(parents=True)
    (deep / "Big.lean").write_text("--\n", encoding="utf-8")

    walked: list[str] = []
    real_walk = os.walk

    def spy(top, *a, **kw):  # type: ignore[no-untyped-def]
        for dirpath, dirnames, filenames in real_walk(top, *a, **kw):
            walked.append(dirpath)
            yield dirpath, dirnames, filenames

    monkeypatch.setattr(aw.os, "walk", spy)
    stage_essential_project(src, tmp_path / "out")
    assert not any(".lake" in p for p in walked)


def test_stage_essential_project_skips_symlinked_lean(tmp_path: Path) -> None:
    src = make_project(tmp_path / "proj")
    outside = tmp_path / "secret.lean"
    outside.write_text("-- secret\n", encoding="utf-8")
    (src / "Link.lean").symlink_to(outside)

    dest = tmp_path / "out"
    stage_essential_project(src, dest)
    assert (dest / "X.lean").is_file()
    assert not (dest / "Link.lean").exists()


def test_stage_essential_project_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="not a directory"):
        stage_essential_project(f, tmp_path / "out")


def test_stage_essential_project_empty_raises(tmp_path: Path) -> None:
    src = tmp_path / "empty"
    src.mkdir()
    with pytest.raises(SystemExit, match="nothing to stage"):
        stage_essential_project(src, tmp_path / "out")


# --- find_lake_root --------------------------------------------------------


def test_find_lake_root_at_top_level(tmp_path: Path) -> None:
    root = tmp_path / "x"
    root.mkdir()
    (root / "lakefile.toml").touch()
    assert find_lake_root(root) == root


def test_find_lake_root_single_wrapped_dir(tmp_path: Path) -> None:
    outer = tmp_path / "archive"
    outer.mkdir()
    inner = outer / "solution"
    inner.mkdir()
    (inner / "lakefile.toml").touch()
    assert find_lake_root(outer) == inner


def test_find_lake_root_search_nested(tmp_path: Path) -> None:
    root = tmp_path / "a"
    (root / "b" / "c").mkdir(parents=True)
    (root / "b" / "c" / "lakefile.toml").touch()
    assert find_lake_root(root) == root / "b" / "c"


def test_find_lake_root_accepts_lakefile_lean(tmp_path: Path) -> None:
    root = tmp_path / "x"
    root.mkdir()
    (root / "lakefile.lean").touch()
    assert find_lake_root(root) == root

    outer = tmp_path / "archive"
    inner = outer / "solution"
    inner.mkdir(parents=True)
    (inner / "lakefile.lean").touch()
    assert find_lake_root(outer) == inner


def test_find_lake_root_prefers_shallowest(tmp_path: Path) -> None:
    root = tmp_path / "a"
    (root / "x" / "y" / "z").mkdir(parents=True)
    (root / "x" / "y" / "z" / "lakefile.toml").touch()
    (root / "p" / "q").mkdir(parents=True)
    (root / "p" / "q" / "lakefile.lean").touch()
    assert find_lake_root(root) == root / "p" / "q"


def test_find_lake_root_prefers_toml_on_same_depth(tmp_path: Path) -> None:
    root = tmp_path / "a"
    (root / "one" / "k").mkdir(parents=True)
    (root / "two" / "k").mkdir(parents=True)
    (root / "one" / "k" / "lakefile.lean").touch()
    (root / "two" / "k" / "lakefile.toml").touch()
    assert find_lake_root(root) == root / "two" / "k"


def test_find_lake_root_ignores_dot_lake(tmp_path: Path) -> None:
    root = tmp_path / "a"
    vendored = root / "sol" / ".lake" / "packages" / "dep"
    vendored.mkdir(parents=True)
    (vendored / "lakefile.toml").touch()
    (root / "other").mkdir()
    with pytest.raises(SystemExit, match="no lakefile"):
        find_lake_root(root)

    (root / "sol" / "lakefile.toml").touch()
    assert find_lake_root(root) == root / "sol"


def test_find_lake_root_missing_raises(tmp_path: Path) -> None:
    root = tmp_path / "none"
    root.mkdir()
    with pytest.raises(SystemExit, match="no lakefile"):
        find_lake_root(root)


# --- defaults and parser ---------------------------------------------------


def test_default_project_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ARISTOWRAP_PROJECT_DIR", raising=False)
    assert default_project_dir() == Path("/app")
    monkeypatch.setenv("ARISTOWRAP_PROJECT_DIR", str(tmp_path))
    assert default_project_dir() == tmp_path


def test_default_output_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ARISTOWRAP_OUTPUT_DIR", raising=False)
    assert default_output_dir() == Path("/app/aristotle-output")
    monkeypatch.setenv("ARISTOWRAP_OUTPUT_DIR", str(tmp_path))
    assert default_output_dir() == tmp_path


def test_build_parser_submit_and_verify() -> None:
    p = build_parser()
    a = p.parse_args(["submit", "hello world"])
    assert a.command == "submit"
    assert a.prompt == "hello world"
    assert a.func.__name__ == "cmd_submit"

    b = p.parse_args(["verify", "/tmp/x.tar.gz"])
    assert b.command == "verify"
    assert str(b.tarball) == "/tmp/x.tar.gz"
    assert b.func.__name__ == "cmd_verify"


# --- _run / _finish --------------------------------------------------------


def test_run_missing_binary_returns_127(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", "")
    assert aw._run(["definitely-not-a-real-binary"]) == 127
    assert "not found on PATH" in capsys.readouterr().err


def test_run_without_log_returns_exit_code(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert aw._run(["aristotle", "x"]) == 0
    monkeypatch.setenv("FAKE_RC", "7")
    assert aw._run(["aristotle", "x"]) == 7


def test_run_with_log_tees_output(
    fake_bin: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "logs" / "submit.log"
    assert aw._run(["aristotle", "x"], log_path=log) == 0
    assert "aristotle says hi" in capsys.readouterr().out
    text = log.read_text(encoding="utf-8")
    assert "$ aristotle x" in text
    assert "aristotle says hi" in text


class _FakeProc:
    def __init__(self, waits: list[object]) -> None:
        self._waits = waits
        self.stdout = None
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        item = self._waits.pop(0)
        if isinstance(item, BaseException):
            raise item
        return int(item)  # type: ignore[call-overload]

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_finish_interrupt_terminates_child() -> None:
    proc = _FakeProc([KeyboardInterrupt(), 0])
    assert aw._finish(proc) == 130  # type: ignore[arg-type]
    assert proc.terminated and not proc.killed


def test_finish_interrupt_kills_stubborn_child() -> None:
    proc = _FakeProc([KeyboardInterrupt(), subprocess.TimeoutExpired("x", 10), 0])
    assert aw._finish(proc) == 130  # type: ignore[arg-type]
    assert proc.terminated and proc.killed


def test_finish_tee_without_stdout_raises() -> None:
    proc = _FakeProc([0])
    with pytest.raises(RuntimeError, match="not captured"):
        aw._finish(proc, tee=io.StringIO())  # type: ignore[arg-type]


# --- cmd_submit ------------------------------------------------------------


def test_cmd_submit_requires_prompt_or_file(tmp_path: Path) -> None:
    make_project(tmp_path)
    (tmp_path / "out").mkdir()

    args = build_parser().parse_args(
        ["submit", "--source-project-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]
    )
    with pytest.raises(SystemExit, match="prompt"):
        aw.cmd_submit(args)


def test_cmd_submit_empty_prompt_file(tmp_path: Path) -> None:
    make_project(tmp_path)
    pf = tmp_path / "p.txt"
    pf.write_text("  \n", encoding="utf-8")

    args = build_parser().parse_args(
        [
            "submit",
            "--prompt-file",
            str(pf),
            "--source-project-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "o"),
        ]
    )
    with pytest.raises(SystemExit, match="empty"):
        aw.cmd_submit(args)


def test_cmd_submit_waits_by_default(fake_bin: Path, tmp_path: Path) -> None:
    proj = make_project(tmp_path / "proj")
    out = tmp_path / "out"
    args = build_parser().parse_args(
        ["submit", "prove it", "--source-project-dir", str(proj), "--output-dir", str(out)]
    )
    assert aw.cmd_submit(args) == 0

    argv = recorded_argv(tmp_path)
    assert argv[0] == "submit"
    assert "--wait" in argv
    dest = argv[argv.index("--destination") + 1]
    assert Path(dest).parent == out.resolve()
    assert Path(dest).name.startswith("solution-") and dest.endswith(".tar.gz")
    assert argv[-2:] == ["--", "prove it"]
    assert argv[argv.index("--project-dir") + 1] != str(proj)  # a staged copy, not the source


def test_cmd_submit_no_wait(fake_bin: Path, tmp_path: Path) -> None:
    proj = make_project(tmp_path / "proj")
    args = build_parser().parse_args(
        [
            "submit",
            "--no-wait",
            "hi",
            "--source-project-dir",
            str(proj),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert aw.cmd_submit(args) == 0
    argv = recorded_argv(tmp_path)
    assert "--wait" not in argv and "--destination" not in argv
    assert argv[-2:] == ["--", "hi"]


def test_cmd_submit_prompt_file_and_dash_prompt(fake_bin: Path, tmp_path: Path) -> None:
    proj = make_project(tmp_path / "proj")
    pf = tmp_path / "p.txt"
    pf.write_text("--not-an-option please\n", encoding="utf-8")
    args = build_parser().parse_args(
        [
            "submit",
            "--prompt-file",
            str(pf),
            "--source-project-dir",
            str(proj),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert aw.cmd_submit(args) == 0
    assert recorded_argv(tmp_path)[-2:] == ["--", "--not-an-option please"]


def test_cmd_submit_destination_creates_parent(fake_bin: Path, tmp_path: Path) -> None:
    proj = make_project(tmp_path / "proj")
    dest = tmp_path / "deep" / "er" / "sol.tar.gz"
    args = build_parser().parse_args(
        [
            "submit",
            "go",
            "--source-project-dir",
            str(proj),
            "--output-dir",
            str(tmp_path / "out"),
            "--destination",
            str(dest),
        ]
    )
    assert aw.cmd_submit(args) == 0
    assert dest.parent.is_dir()
    argv = recorded_argv(tmp_path)
    assert argv[argv.index("--destination") + 1] == str(dest.resolve())


def test_cmd_submit_destination_with_no_wait_rejected(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        ["submit", "go", "--no-wait", "--destination", str(tmp_path / "x.tar.gz")]
    )
    with pytest.raises(SystemExit, match="--no-wait"):
        aw.cmd_submit(args)


def test_cmd_submit_logs_to_file(fake_bin: Path, tmp_path: Path) -> None:
    proj = make_project(tmp_path / "proj")
    log = tmp_path / "s.log"
    args = build_parser().parse_args(
        [
            "submit",
            "go",
            "--source-project-dir",
            str(proj),
            "--output-dir",
            str(tmp_path / "out"),
            "--log",
            str(log),
        ]
    )
    assert aw.cmd_submit(args) == 0
    assert "aristotle says hi" in log.read_text(encoding="utf-8")


def test_cmd_submit_propagates_exit_code(
    fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj = make_project(tmp_path / "proj")
    monkeypatch.setenv("FAKE_RC", "4")
    args = build_parser().parse_args(
        ["submit", "go", "--no-wait", "--source-project-dir", str(proj), "--output-dir", str(tmp_path / "o")]
    )
    assert aw.cmd_submit(args) == 4


def test_cmd_submit_warns_without_api_key(
    fake_bin: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    proj = make_project(tmp_path / "proj")
    monkeypatch.delenv("ARISTOTLE_API_KEY")
    args = build_parser().parse_args(
        ["submit", "go", "--no-wait", "--source-project-dir", str(proj), "--output-dir", str(tmp_path / "o")]
    )
    assert aw.cmd_submit(args) == 0
    assert "ARISTOTLE_API_KEY is not set" in capsys.readouterr().err


def test_main_fills_submit_defaults_from_env(
    fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj = make_project(tmp_path / "proj")
    out = tmp_path / "out"
    monkeypatch.setenv("ARISTOWRAP_PROJECT_DIR", str(proj))
    monkeypatch.setenv("ARISTOWRAP_OUTPUT_DIR", str(out))
    monkeypatch.setattr("sys.argv", ["aristowrap", "submit", "go"])

    assert aw.main() == 0
    argv = recorded_argv(tmp_path)
    assert Path(argv[argv.index("--destination") + 1]).parent == out.resolve()


# --- cmd_verify ------------------------------------------------------------


@needs_data_filter
def test_cmd_verify_extract_uses_data_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: verify path reaches extractall with filter when tarball exists."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "lakefile.toml").write_text('name = "t"\n', encoding="utf-8")
    tar_path = tmp_path / "s.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(proj, arcname="proj")

    calls: list[dict] = []

    real_open = tarfile.open

    def wrapped_open(name, mode: str = "r", **kwargs):  # type: ignore[no-untyped-def]
        tf_obj = real_open(name, mode, **kwargs)
        orig_extractall = tf_obj.extractall

        def capture_extractall(path, **kw):  # type: ignore[no-untyped-def]
            calls.append(kw)
            return orig_extractall(path, **kw)

        tf_obj.extractall = capture_extractall  # type: ignore[method-assign]
        return tf_obj

    monkeypatch.setattr(aw.tarfile, "open", wrapped_open)
    monkeypatch.setattr(aw, "_run", lambda *a, **k: 0)

    args = build_parser().parse_args(["verify", str(tar_path)])
    assert aw.cmd_verify(args) == 0
    assert calls and calls[0].get("filter") == "data"


def test_cmd_verify_refuses_without_extraction_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tar_path = write_tar(tmp_path / "s.tar.gz", {"lakefile.toml": b"x"})
    monkeypatch.delattr(aw.tarfile, "data_filter", raising=False)
    args = build_parser().parse_args(["verify", str(tar_path)])
    with pytest.raises(SystemExit, match="extraction filters"):
        aw.cmd_verify(args)


@needs_data_filter
def test_cmd_verify_runs_lake_in_lake_root(fake_bin: Path, tmp_path: Path) -> None:
    tar_path = write_tar(tmp_path / "s.tar.gz", {"sol/lakefile.toml": b'name = "t"\n'})
    args = build_parser().parse_args(["verify", str(tar_path)])
    assert aw.cmd_verify(args) == 0
    cwd = (tmp_path / "cwd.txt").read_text(encoding="utf-8").strip()
    assert cwd.endswith("sol")


@needs_data_filter
def test_cmd_verify_propagates_lake_failure(
    fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tar_path = write_tar(tmp_path / "s.tar.gz", {"lakefile.toml": b"x"})
    monkeypatch.setenv("FAKE_RC", "3")
    args = build_parser().parse_args(["verify", str(tar_path)])
    assert aw.cmd_verify(args) == 3


@needs_data_filter
def test_cmd_verify_picks_newest_tarball(
    fake_bin: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    old = write_tar(out / "old.tar.gz", {"lakefile.toml": b"x"})
    new = write_tar(out / "new.tar.gz", {"lakefile.toml": b"x"})
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))

    args = build_parser().parse_args(["verify", "--output-dir", str(out)])
    assert aw.cmd_verify(args) == 0
    assert str(new) in capsys.readouterr().err


def test_cmd_verify_default_output_dir_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARISTOWRAP_OUTPUT_DIR", str(tmp_path / "missing"))
    args = build_parser().parse_args(["verify"])
    with pytest.raises(SystemExit, match="output dir missing"):
        aw.cmd_verify(args)


def test_cmd_verify_no_tarballs(tmp_path: Path) -> None:
    args = build_parser().parse_args(["verify", "--output-dir", str(tmp_path)])
    with pytest.raises(SystemExit, match="no .tar.gz"):
        aw.cmd_verify(args)


def test_cmd_verify_tarball_not_a_file(tmp_path: Path) -> None:
    args = build_parser().parse_args(["verify", str(tmp_path / "nope.tar.gz")])
    with pytest.raises(SystemExit, match="not a file"):
        aw.cmd_verify(args)


@needs_data_filter
def test_cmd_verify_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tar_path = write_tar(tmp_path / "evil.tar.gz", {"../escaped.txt": b"pwned"})
    monkeypatch.setattr(aw, "_run", lambda *a, **k: 0)
    args = build_parser().parse_args(["verify", str(tar_path)])
    with pytest.raises(SystemExit, match="unsafe archive"):
        aw.cmd_verify(args)


@needs_data_filter
def test_cmd_verify_rejects_escaping_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tar_path = tmp_path / "evil.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        tf.addfile(link)
    monkeypatch.setattr(aw, "_run", lambda *a, **k: 0)
    args = build_parser().parse_args(["verify", str(tar_path)])
    with pytest.raises(SystemExit, match="unsafe archive"):
        aw.cmd_verify(args)


@needs_data_filter
def test_cmd_verify_absolute_member_stays_inside_extract_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The data filter strips leading slashes, so an absolute name cannot escape."""
    tar_path = write_tar(tmp_path / "abs.tar.gz", {"/abs/lakefile.toml": b'name = "t"\n'})
    seen: list[Path] = []

    def fake_run(cmd, *, cwd=None, log_path=None):  # type: ignore[no-untyped-def]
        assert (cwd / "lakefile.toml").is_file()
        seen.append(cwd)
        return 0

    monkeypatch.setattr(aw, "_run", fake_run)
    args = build_parser().parse_args(["verify", str(tar_path)])
    assert aw.cmd_verify(args) == 0
    assert seen and "aristowrap-verify-" in str(seen[0])
    assert not Path("/abs/lakefile.toml").exists()
