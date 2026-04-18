"""Unit tests for scripts.aristowrap (staging, lake root discovery, CLI wiring)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.aristowrap import (
    _should_skip,
    build_parser,
    default_output_dir,
    default_project_dir,
    find_lake_root,
    stage_essential_project,
)


def test_should_skip_detects_cache_segments() -> None:
    assert _should_skip((".lake", "Foo.lean"))
    assert _should_skip(("src", "lake-packages", "x.lean"))
    assert _should_skip(("a", ".git", "b"))
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


def test_find_lake_root_missing_raises(tmp_path: Path) -> None:
    root = tmp_path / "none"
    root.mkdir()
    with pytest.raises(SystemExit, match="no lakefile"):
        find_lake_root(root)


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


def test_cmd_submit_requires_prompt_or_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARISTOWRAP_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("ARISTOWRAP_OUTPUT_DIR", str(tmp_path / "out"))
    (tmp_path / "lean-toolchain").write_text("x\n", encoding="utf-8")
    (tmp_path / "lakefile.toml").write_text('name = "t"\n', encoding="utf-8")
    (tmp_path / "X.lean").write_text("--\n", encoding="utf-8")
    (tmp_path / "out").mkdir()

    from scripts import aristowrap as aw

    args = build_parser().parse_args(
        ["submit", "--source-project-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]
    )
    with pytest.raises(SystemExit, match="prompt"):
        aw.cmd_submit(args)


def test_cmd_submit_empty_prompt_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARISTOWRAP_PROJECT_DIR", str(tmp_path))
    pf = tmp_path / "p.txt"
    pf.write_text("  \n", encoding="utf-8")
    (tmp_path / "lean-toolchain").write_text("x\n", encoding="utf-8")
    (tmp_path / "lakefile.toml").write_text('name = "t"\n', encoding="utf-8")
    (tmp_path / "X.lean").write_text("--\n", encoding="utf-8")

    from scripts import aristowrap as aw

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
    (tmp_path / "o").mkdir()
    with pytest.raises(SystemExit, match="empty"):
        aw.cmd_submit(args)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="tarfile filter='data' only exercised on 3.12+")
def test_cmd_verify_extract_uses_data_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: verify path reaches extractall with filter when tarball exists."""
    import tarfile

    from scripts import aristowrap as aw

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
