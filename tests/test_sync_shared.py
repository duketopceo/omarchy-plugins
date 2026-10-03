"""Tests for scripts/sync-shared.py (U4): vendored copy + drift check."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync-shared.py"


def load():
    spec = importlib.util.spec_from_file_location("sync_shared", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_repo(tmp_path: Path, consumers: list[str]) -> Path:
    lib = tmp_path / "shared" / "py" / "_omplug"
    lib.mkdir(parents=True)
    (lib / "__init__.py").write_text('"""lib."""\n')
    (lib / "proc.py").write_text("X = 1\n")
    (tmp_path / "shared" / "VERSION").write_text("0.1.0\n")
    (tmp_path / "shared" / "consumers.txt").write_text(
        "# opt-in list\n" + "".join(c + "\n" for c in consumers)
    )
    for c in consumers:
        (tmp_path / "plugins" / c / "bin").mkdir(parents=True)
    (tmp_path / "plugins" / "lukedaduke.other" / "bin").mkdir(parents=True)
    return tmp_path


def test_zero_consumers_check_passes(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, [])
    assert mod.main(["--root", str(root), "--check"]) == 0
    assert mod.main(["--root", str(root)]) == 0
    assert not (root / "plugins" / "lukedaduke.other" / "bin" / "_omplug").exists()


def test_sync_writes_copy_and_version_then_check_passes(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, ["lukedaduke.demo"])
    assert mod.main(["--root", str(root), "--check"]) == 1  # missing copy
    assert mod.main(["--root", str(root)]) == 0
    vendored = root / "plugins" / "lukedaduke.demo" / "bin" / "_omplug"
    assert (vendored / "proc.py").read_text() == "X = 1\n"
    assert (vendored / "VERSION").read_text() == "0.1.0\n"
    assert not (root / "plugins" / "lukedaduke.other" / "bin" / "_omplug").exists()
    assert mod.main(["--root", str(root), "--check"]) == 0
    # No staging leftovers beside the vendored dir.
    assert sorted(p.name for p in vendored.parent.iterdir()) == ["_omplug"]


def test_one_byte_drift_fails_check(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, ["lukedaduke.demo"])
    assert mod.main(["--root", str(root)]) == 0
    target = root / "plugins" / "lukedaduke.demo" / "bin" / "_omplug" / "proc.py"
    target.write_text("X = 2\n")
    assert mod.main(["--root", str(root), "--check"]) == 1
    problems = mod.check_consumer(root, "lukedaduke.demo")
    assert any("proc.py" in p for p in problems)


def test_extra_file_and_version_drift_fail_check(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, ["lukedaduke.demo"])
    mod.main(["--root", str(root)])
    vendored = root / "plugins" / "lukedaduke.demo" / "bin" / "_omplug"
    (vendored / "stale.py").write_text("")
    assert any("stale.py" in p for p in mod.check_consumer(root, "lukedaduke.demo"))
    (vendored / "stale.py").unlink()
    (vendored / "VERSION").write_text("0.0.9\n")
    assert any("VERSION" in p for p in mod.check_consumer(root, "lukedaduke.demo"))
    # Runtime bytecode caches are not drift.
    (vendored / "VERSION").write_text("0.1.0\n")
    (vendored / "__pycache__").mkdir()
    (vendored / "__pycache__" / "proc.cpython-312.pyc").write_bytes(b"\0")
    assert mod.check_consumer(root, "lukedaduke.demo") == []


def test_resync_replaces_stale_copy(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, ["lukedaduke.demo"])
    mod.main(["--root", str(root)])
    vendored = root / "plugins" / "lukedaduke.demo" / "bin" / "_omplug"
    (vendored / "stale.py").write_text("")
    (root / "shared" / "py" / "_omplug" / "proc.py").write_text("X = 3\n")
    assert mod.main(["--root", str(root)]) == 0
    assert not (vendored / "stale.py").exists()
    assert (vendored / "proc.py").read_text() == "X = 3\n"
    assert mod.main(["--root", str(root), "--check"]) == 0


def test_unknown_consumer_fails(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, [])
    (root / "shared" / "consumers.txt").write_text("lukedaduke.ghost\n")
    assert mod.main(["--root", str(root), "--check"]) == 1
    assert mod.main(["--root", str(root)]) == 1


def test_check_vendored_dir_against_source(tmp_path: Path) -> None:
    mod = load()
    root = make_repo(tmp_path, ["lukedaduke.demo"])
    mod.main(["--root", str(root)])
    vendored = root / "plugins" / "lukedaduke.demo" / "bin" / "_omplug"
    assert mod.main(["--root", str(root), "--check-dir", str(vendored)]) == 0
    (vendored / "__init__.py").write_text("")
    assert mod.main(["--root", str(root), "--check-dir", str(vendored)]) == 1


def test_repo_check_passes() -> None:
    mod = load()
    assert mod.main(["--check"]) == 0
