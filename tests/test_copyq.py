"""Tests for lukedaduke.copyq helpers (list + activate + remove + pin)."""

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
BIN = ROOT / "plugins/lukedaduke.copyq/bin"
LIST_HELPER = BIN / "copyq-list.py"
ACTIVATE_HELPER = BIN / "copyq-activate.sh"
REMOVE_HELPER = BIN / "copyq-remove.sh"
PIN_HELPER = BIN / "copyq-pin.sh"


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


def _ok_bytes(data: bytes = b"", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=data, stderr=b"", returncode=returncode)


def _tab_cmd(args: list[str]) -> tuple[str | None, list[str]]:
    """Return (tab_name, rest) when args are [copyq, tab, NAME, ...]."""
    if len(args) >= 3 and args[1] == "tab":
        return args[2], args[3:]
    return None, args[1:]


def _eval_out(pins=None, clips=None) -> str:
    return json.dumps(
        {
            "pins": pins if pins is not None else {"entries": [], "total": 0},
            "clips": clips if clips is not None else {"entries": [], "total": 0},
        }
    )


def _clip_entry(index: int, preview: str, **overrides) -> dict:
    entry = {
        "index": index,
        "tab": "&clipboard",
        "pinned": False,
        "type": "text",
        "text": preview,
        "preview": preview,
        "previewPath": "",
        "mime": "text/plain",
        "imageMime": "",
    }
    entry.update(overrides)
    return entry


def _group(entries: list[dict], total: int | None = None) -> dict:
    return {"entries": entries, "total": len(entries) if total is None else total}


def _is_eval(args: list[str]) -> bool:
    return len(args) >= 2 and args[1] == "eval"


def test_list_two_text_rows(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py", "80"])

    def fake_run(args, **kwargs):
        if _is_eval(args):
            return _ok(
                _eval_out(
                    clips=_group(
                        [_clip_entry(0, "alpha"), _clip_entry(1, "beta")],
                        total=2,
                    )
                )
            )
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert payload["entries"][0]["preview"] == "alpha"
    assert payload["entries"][0]["tab"] == "&clipboard"
    assert payload["entries"][0]["pinned"] is False
    assert payload["entries"][1]["preview"] == "beta"


def test_list_pins_before_clipboard(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    pin = _clip_entry(0, "pinned", tab="Pins", pinned=True)

    def fake_run(args, **_kwargs):
        if _is_eval(args):
            return _ok(
                _eval_out(
                    pins=_group([pin], total=1),
                    clips=_group([_clip_entry(0, "clip")], total=1),
                )
            )
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert [e["preview"] for e in payload["entries"]] == ["pinned", "clip"]
    assert payload["entries"][0]["pinned"] is True
    assert payload["entries"][1]["pinned"] is False


def test_list_image_row(list_mod, monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    image = _clip_entry(
        0,
        "Image",
        type="image",
        text="",
        imageMime="image/png",
        mime="image/png",
    )

    def fake_run(args, **kwargs):
        if _is_eval(args):
            return _ok(_eval_out(clips=_group([image], total=1)))
        tab, rest = _tab_cmd(args)
        if tab == "&clipboard" and rest == ["read", "image/png", "0"]:
            assert kwargs.get("text") is False
            return _ok_bytes(b"\x89PNG\r\n", returncode=0)
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"][0]["type"] == "image"
    assert payload["entries"][0]["preview"] == "Image"
    assert payload["entries"][0]["previewPath"].endswith("preview-clip-0.png")
    assert Path(payload["entries"][0]["previewPath"]).is_file()


def test_list_skips_whitespace_and_keeps_indexes(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    entries = [
        _clip_entry(0, "   \n  "),
        _clip_entry(1, "keep"),
        _clip_entry(2, "also"),
    ]

    def fake_run(args, **_kwargs):
        if _is_eval(args):
            return _ok(_eval_out(clips=_group(entries, total=3)))
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert [e["index"] for e in payload["entries"]] == [1, 2]
    assert [e["text"] for e in payload["entries"]] == ["keep", "also"]


def test_list_eval_failure(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    def fake_run(args, **_kwargs):
        if _is_eval(args):
            return _ok("boom", returncode=1)
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"].startswith("copyq_eval")
    assert payload["entries"] == []


def test_list_bad_eval_json(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    def fake_run(args, **_kwargs):
        if _is_eval(args):
            return _ok("not json at all")
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"].startswith("copyq_eval_json")
    assert payload["entries"] == []


def test_eval_collect_substitutes_limit(list_mod, monkeypatch) -> None:
    captured: list[list[str]] = []

    def fake_run(args, **_kwargs):
        captured.append(args)
        return _ok(_eval_out())

    monkeypatch.setattr(list_mod, "_run", fake_run)
    list_mod._eval_collect(7)
    assert len(captured) == 1
    script = captured[0][2]
    assert "var __limit = 7;" in script
    assert "__LIMIT__" not in script


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


def _write_fake_bin(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _fake_copyq(tmp_path: Path) -> Path:
    return _write_fake_bin(tmp_path, "fake-copyq", 'echo "$@" >> "$LOG"\n')


def _activate_env(tmp_path: Path, log: Path, **extra: str) -> tuple[dict, Path]:
    wtype_log = tmp_path / "wtype.log"
    wtype = _write_fake_bin(
        tmp_path, "fake-wtype", f'echo "$@" >> "{wtype_log}"\n'
    )
    hyprctl_json = extra.pop("HYPRCTL_JSON", '{"tags":[]}')
    hyprctl = _write_fake_bin(
        tmp_path, "fake-hyprctl", f"cat <<'EOF'\n{hyprctl_json}\nEOF\n"
    )
    env = {
        **os.environ,
        "COPYQ_BIN": str(_fake_copyq(tmp_path)),
        "WTYPE_BIN": str(wtype),
        "HYPRCTL_BIN": str(hyprctl),
        "JQ_BIN": "/usr/bin/jq",
        "COPYQ_PASTE_DELAY": "0",
        "LOG": str(log),
        **extra,
    }
    return env, wtype_log


def test_activate_paste_nonterminal(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    env, wtype_log = _activate_env(tmp_path, log)
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "1", "--tab", "&clipboard"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["tab &clipboard select 1"]
    assert wtype_log.read_text().splitlines() == ["-M ctrl -k v -m ctrl"]


def test_activate_paste_terminal(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    env, wtype_log = _activate_env(
        tmp_path, log, HYPRCTL_JSON='{"tags":["terminal","floating"]}'
    )
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "1"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["select 1"]
    assert wtype_log.read_text().splitlines() == [
        "-M ctrl -M shift -k v -m shift -m ctrl"
    ]


def test_activate_copy_only(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    env, wtype_log = _activate_env(tmp_path, log)
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "1", "--copy-only"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["select 1"]
    assert not wtype_log.exists()


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


def test_remove_with_tab(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_bin(tmp_path, "fake-copyq", f'echo "$@" >> "{log}"\n')
    env = {**os.environ, "COPYQ_BIN": str(fake), "LOG": str(log)}
    proc = subprocess.run(
        [str(REMOVE_HELPER), "--index", "2", "--tab", "Pins"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["tab Pins remove 2"]


def test_pin_text(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_bin(
        tmp_path,
        "fake-copyq",
        f"""
echo "$@" >> "{log}"
if [[ "$*" == *"read ?"*"0" ]]; then
  echo text/plain
  exit 0
fi
if [[ "$*" == *"read 0" ]]; then
  printf 'hello pin'
  exit 0
fi
exit 0
""",
    )
    env = {**os.environ, "COPYQ_BIN": str(fake)}
    proc = subprocess.run(
        [str(PIN_HELPER), "--index", "0", "--tab", "&clipboard"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    lines = log.read_text().splitlines()
    assert any("tab &clipboard read ?" in " ".join(lines) or "read ?" in ln for ln in lines)
    assert any("tab Pins write 0 text/plain -" == ln for ln in lines)
