#!/usr/bin/env python3
"""Vendor shared/py/_omplug and shared/qml into opted-in plugins, or check for drift.

A plugin opts in by listing its id in shared/consumers.txt. Sync copies each
library plus shared/VERSION into plugins/<id>/bin/_omplug/ (Python) and
plugins/<id>/lib/ (QML, imported as `import "lib"`), staged in a sibling
directory and renamed into place, so a half-synced copy never exists.

  scripts/sync-shared.py             sync every consumer
  scripts/sync-shared.py --check     exit 1 on any drift or missing copy
  scripts/sync-shared.py --check-dir DIR [--src shared/qml]
                                     compare one vendored dir (e.g. extracted
                                     from a subtree split) against shared/
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB_SRC = Path("shared/py/_omplug")
VERSION_SRC = Path("shared/VERSION")
CONSUMERS = Path("shared/consumers.txt")
VENDOR_DEST = Path("bin/_omplug")
QML_SRC = Path("shared/qml")
QML_DEST = Path("lib")
# (source tree, vendored path inside plugins/<id>/); a source tree that does
# not exist in the repo is simply not vendored.
TARGETS = ((LIB_SRC, VENDOR_DEST), (QML_SRC, QML_DEST))
IGNORED_DIRS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def read_consumers(root: Path) -> list[str]:
    path = root / CONSUMERS
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        item = line.split("#", 1)[0].strip()
        if item and item not in out:
            out.append(item)
    return out


def _files(base: Path) -> dict[str, Path]:
    """Relative path -> file, skipping bytecode caches."""
    out: dict[str, Path] = {}
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if any(part in IGNORED_DIRS for part in rel.parts) or path.suffix in IGNORED_SUFFIXES:
            continue
        if path.is_symlink() or path.is_file():
            out[rel.as_posix()] = path
    return out


def expected_files(root: Path, src: Path = LIB_SRC) -> dict[str, bytes]:
    """The exact vendored tree: library files plus VERSION."""
    files = {rel: p.read_bytes() for rel, p in _files(root / src).items()}
    files["VERSION"] = (root / VERSION_SRC).read_bytes()
    return files


def compare_dir(root: Path, vendored: Path, src: Path = LIB_SRC) -> list[str]:
    """Differences between a vendored directory and shared/ (empty = equal)."""
    try:
        label = vendored.resolve().relative_to(root).as_posix()
    except ValueError:
        label = vendored.as_posix()
    if vendored.is_symlink() or not vendored.is_dir():
        return [f"{label}: missing vendored shared library"]
    expected = expected_files(root, src)
    actual = _files(vendored)
    problems = []
    for rel in sorted(expected.keys() - actual.keys()):
        problems.append(f"{label}/{rel}: missing")
    for rel in sorted(actual.keys() - expected.keys()):
        problems.append(f"{label}/{rel}: not in shared/ (stale)")
    for rel in sorted(expected.keys() & actual.keys()):
        path = actual[rel]
        if path.is_symlink():
            problems.append(f"{label}/{rel}: symlink not allowed")
        elif path.read_bytes() != expected[rel]:
            problems.append(f"{label}/{rel}: differs from shared/")
    return problems


def check_consumer(root: Path, plugin_id: str) -> list[str]:
    plugin = root / "plugins" / plugin_id
    if not plugin.is_dir():
        return [f"{plugin_id}: listed in {CONSUMERS} but plugins/{plugin_id} does not exist"]
    problems = []
    for src, dest in active_targets(root):
        problems.extend(compare_dir(root, plugin / dest, src))
    return problems


def active_targets(root: Path) -> list[tuple[Path, Path]]:
    return [(src, dest) for src, dest in TARGETS if (root / src).is_dir()]


def sync_consumer(root: Path, plugin_id: str) -> None:
    plugin = root / "plugins" / plugin_id
    if not plugin.is_dir():
        raise FileNotFoundError(f"plugins/{plugin_id} does not exist")
    for src, rel_dest in active_targets(root):
        _sync_tree(root, src, plugin / rel_dest)


def _sync_tree(root: Path, src: Path, dest: Path) -> None:
    """Stage the vendored tree beside dest, then rename it into place."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="._omplug.stage-", dir=dest.parent))
    old = None
    try:
        for rel, data in expected_files(root, src).items():
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o644)
        os.chmod(stage, 0o755)
        if dest.is_symlink() or dest.exists():
            old = Path(tempfile.mkdtemp(prefix="._omplug.old-", dir=dest.parent))
            os.rmdir(old)
            os.rename(dest, old)
        os.rename(stage, dest)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        if old is not None and not dest.exists():
            os.rename(old, dest)
        raise
    if old is not None:
        if old.is_symlink() or old.is_file():
            old.unlink()
        else:
            shutil.rmtree(old)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--check-dir", type=Path)
    parser.add_argument("--src", type=Path, default=LIB_SRC,
                        help="shared source tree --check-dir compares against (default shared/py/_omplug)")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.check_dir is not None:
        problems = compare_dir(root, args.check_dir, args.src)
    elif args.check:
        problems = [p for c in read_consumers(root) for p in check_consumer(root, c)]
    else:
        problems = []
        for consumer in read_consumers(root):
            try:
                sync_consumer(root, consumer)
                print(f"synced {consumer}")
            except OSError as exc:
                problems.append(f"{consumer}: {exc}")
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems and (args.check or args.check_dir is not None):
        print("ok: shared library copies match shared/")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
