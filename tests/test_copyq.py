"""Tests for lukedaduke.copyq helpers (list + activate)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIST_HELPER = ROOT / "plugins/lukedaduke.copyq/bin/copyq-list.py"
ACTIVATE_HELPER = ROOT / "plugins/lukedaduke.copyq/bin/copyq-activate.sh"


@pytest.fixture()
def list_mod(monkeypatch: pytest.MonkeyPatch):
    loader = importlib.machinery.SourceFileLoader("copyq_list", str(LIST_HELPER))
    spec = importlib.util.spec_from_loader("copyq_list", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "COPYQ", "/usr/bin/copyq")
    return module


def _ok(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_list_two_text_rows(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py", "80"])

    def fake_run(args, **_kwargs):
        if args[1:] == ["count"]:
            return _ok("2\n")
        if args[1:3] == ["read", "0"]:
            return _ok("alpha")
        if args[1:3] == ["read", "1"]:
            return _ok("beta")
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert payload["entries"] == [
        {
            "index": 0,
            "type": "text",
            "text": "alpha",
            "preview": "alpha",
        },
        {
            "index": 1,
            "type": "text",
            "text": "beta",
            "preview": "beta",
        },
    ]


def test_list_skips_whitespace_and_keeps_indexes(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    def fake_run(args, **_kwargs):
        if args[1:] == ["count"]:
            return _ok("3\n")
        if args[1:3] == ["read", "0"]:
            return _ok("   \n")
        if args[1:3] == ["read", "1"]:
            return _ok("keep")
        if args[1:3] == ["read", "2"]:
            return _ok("also")
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert [e["index"] for e in payload["entries"]] == [1, 2]
    assert [e["text"] for e in payload["entries"]] == ["keep", "also"]


def test_list_skips_nonzero_read(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    def fake_run(args, **_kwargs):
        if args[1:] == ["count"]:
            return _ok("2\n")
        if args[1:3] == ["read", "0"]:
            return _ok("fail", returncode=1)
        if args[1:3] == ["read", "1"]:
            return _ok("ok")
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"] == [
        {"index": 1, "type": "text", "text": "ok", "preview": "ok"}
    ]


def test_list_preview_truncation(list_mod) -> None:
    long = "x" * 200
    preview = list_mod._preview(long)
    assert preview.endswith("…")
    assert len(preview) == 161


def test_list_limit_clamps(list_mod, monkeypatch) -> None:
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py", "0"])
    assert list_mod._limit_from_argv() == 1
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py", "nope"])
    assert list_mod._limit_from_argv() == 80
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py", "999"])
    assert list_mod._limit_from_argv() == 200


def test_list_missing_binary(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: False)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])
    assert list_mod.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ok": False, "error": "copyq_missing", "entries": []}


def test_list_bad_count(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])
    monkeypatch.setattr(list_mod, "_run", lambda *_a, **_k: _ok("not-a-number\n"))
    assert list_mod.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"].startswith("copyq_count:")
    assert payload["entries"] == []


def _write_fake_copyq(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake-copyq"
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_activate_paste(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(
        tmp_path,
        f'echo "$@" >> "{log}"\n',
    )
    env = {**os.environ, "COPYQ_BIN": str(fake)}
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "1"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["select 1", "paste"]


def test_activate_copy_only(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(
        tmp_path,
        f'echo "$@" >> "{log}"\n',
    )
    env = {**os.environ, "COPYQ_BIN": str(fake)}
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "1", "--copy-only"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["select 1"]


def test_activate_bad_index() -> None:
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "x"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2


def test_activate_missing_binary(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-copyq"
    env = {**os.environ, "COPYQ_BIN": str(missing)}
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "0"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
