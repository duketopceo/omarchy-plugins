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
HOTKEYS_HELPER = BIN / "copyq_hotkeys.py"
ACTIVATE_HELPER = BIN / "copyq-activate.sh"
REMOVE_HELPER = BIN / "copyq-remove.sh"
PIN_HELPER = BIN / "copyq-pin.sh"


@pytest.fixture()
def list_mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(BIN))
    loader = importlib.machinery.SourceFileLoader("copyq_list", str(LIST_HELPER))
    spec = importlib.util.spec_from_loader("copyq_list", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "COPYQ", "/usr/bin/copyq")
    return module


@pytest.fixture()
def hot_mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(BIN))
    loader = importlib.machinery.SourceFileLoader("copyq_hotkeys", str(HOTKEYS_HELPER))
    spec = importlib.util.spec_from_loader("copyq_hotkeys", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "COPYQ", "/usr/bin/copyq")
    return module


def _ok(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def _ok_bytes(data: bytes = b"", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=data, stderr=b"", returncode=returncode)


def _eval_payload(entries: list[dict], *, pin_count: int = 0, clip_count: int | None = None) -> str:
    if clip_count is None:
        clip_count = len([e for e in entries if not e.get("pinned")])
    return json.dumps(
        {
            "ok": True,
            "pinCount": pin_count,
            "clipCount": clip_count,
            "count": pin_count + clip_count,
            "entries": entries,
        }
    )


def test_list_two_text_rows(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py", "80"])

    def fake_run(args, **_kwargs):
        assert args[0] == "/usr/bin/copyq"
        assert args[1] == "eval"
        return _ok(
            _eval_payload(
                [
                    {
                        "index": 0,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": "alpha",
                        "text": "alpha",
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                    {
                        "index": 1,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": "beta",
                        "text": "beta",
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                ],
                clip_count=2,
            )
        )

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

    def fake_run(args, **_kwargs):
        assert args[1] == "eval"
        return _ok(
            _eval_payload(
                [
                    {
                        "index": 0,
                        "tab": "Pins",
                        "pinned": True,
                        "type": "text",
                        "preview": "pinned",
                        "text": "pinned",
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                    {
                        "index": 0,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": "clip",
                        "text": "clip",
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                ],
                pin_count=1,
                clip_count=1,
            )
        )

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

    def fake_run(args, **kwargs):
        text_mode = kwargs.get("text", True)
        if len(args) >= 2 and args[1] == "eval":
            return _ok(
                _eval_payload(
                    [
                        {
                            "index": 0,
                            "tab": "&clipboard",
                            "pinned": False,
                            "type": "image",
                            "preview": "Image",
                            "text": "",
                            "previewPath": "",
                            "mime": "image/png",
                        }
                    ],
                    clip_count=1,
                )
            )
        # Thumbnail fetch after eval.
        if args[1:] == ["tab", "&clipboard", "read", "image/png", "0"]:
            assert text_mode is False
            return _ok_bytes(b"\x89PNG\r\n", returncode=0)
        raise AssertionError(args)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"][0]["type"] == "image"
    assert payload["entries"][0]["preview"] == "Image"
    assert payload["entries"][0]["previewPath"].endswith("preview-clip-0.png")
    assert Path(payload["entries"][0]["previewPath"]).is_file()


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


def test_list_eval_failure(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    def fake_run(args, **_kwargs):
        assert args[1] == "eval"
        return _ok("not-json", returncode=1)

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"].startswith("copyq_eval:")
    assert payload["entries"] == []


def _write_fake_copyq(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake-copyq"
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_activate_paste(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(tmp_path, f'echo "$@" >> "{log}"\n')
    env = {**os.environ, "COPYQ_BIN": str(fake)}
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--index", "1", "--tab", "&clipboard"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == [
        "tab &clipboard select 1",
        "paste",
    ]


def test_activate_copy_only(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(tmp_path, f'echo "$@" >> "{log}"\n')
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


def test_remove_with_tab(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(tmp_path, f'echo "$@" >> "{log}"\n')
    env = {**os.environ, "COPYQ_BIN": str(fake)}
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
    fake = _write_fake_copyq(
        tmp_path,
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


def test_unpin_from_pins_tab(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(tmp_path, f'echo "$@" >> "{log}"\n')
    env = {**os.environ, "COPYQ_BIN": str(fake)}
    proc = subprocess.run(
        [str(PIN_HELPER), "--index", "1", "--tab", "Pins"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == ["tab Pins remove 1"]


def test_classify_openrouter_and_openai(hot_mod) -> None:
    assert hot_mod.classify_secret("sk-or-v1-" + ("a" * 40))[0] == "openrouter"
    assert hot_mod.classify_secret("sk-" + ("b" * 40))[0] == "openai"
    assert hot_mod.classify_secret("not-a-key") is None


def test_hot_vault_roundtrip(hot_mod, tmp_path: Path) -> None:
    secret = "sk-or-v1-" + ("c" * 48)
    item = hot_mod.upsert_secret(secret, ttl_secs=1800)
    assert item is not None
    assert "sk-or-v1-" in item["preview"]
    assert "…" in item["preview"]
    assert secret not in item["preview"]
    store = tmp_path / "lukedaduke.copyq" / "hotkeys.fernet"
    keyf = tmp_path / "lukedaduke.copyq" / "hotkeys.key"
    assert store.is_file()
    assert keyf.is_file()
    assert secret.encode() not in store.read_bytes()
    rows = hot_mod.list_overlay_entries()
    assert len(rows) == 1
    assert rows[0]["hotId"] == item["id"]
    assert hot_mod.get_secret(item["id"]) == secret
    assert hot_mod.drop_secret(item["id"]) is True
    assert hot_mod.list_overlay_entries() == []


def test_hot_vault_expires(hot_mod) -> None:
    secret = "sk-" + ("d" * 40)
    now = 1_700_000_000.0
    hot_mod.upsert_secret(secret, ttl_secs=60, now=now)
    assert len(hot_mod.list_overlay_entries(now=now + 10)) == 1
    assert hot_mod.list_overlay_entries(now=now + 120) == []


def test_list_harvests_api_key(list_mod, monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])
    secret = "sk-or-v1-" + ("e" * 48)

    def fake_run(args, **_kwargs):
        assert args[1] == "eval"
        return _ok(
            _eval_payload(
                [
                    {
                        "index": 0,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": secret,
                        "text": secret,
                        "keyish": True,
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                    {
                        "index": 1,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": "hello",
                        "text": "hello",
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                ],
                clip_count=2,
            )
        )

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hotCount"] == 1
    assert payload["entries"][0]["hot"] is True
    assert "…" in payload["entries"][0]["preview"]
    assert secret not in json.dumps(payload)
    assert payload["entries"][1]["preview"] == "hello"


def test_activate_hot_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(BIN))
    loader = importlib.machinery.SourceFileLoader("copyq_hotkeys_act", str(HOTKEYS_HELPER))
    spec = importlib.util.spec_from_loader("copyq_hotkeys_act", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    secret = "sk-" + ("f" * 40)
    item = module.upsert_secret(secret)
    assert item is not None
    log = tmp_path / "log.txt"
    fake = _write_fake_copyq(
        tmp_path,
        f'''
printf "argv:%s\\n" "$*" >> "{log}"
if [[ "$1" == "copy" || "$1" == "add" ]]; then
  printf "stdin:" >> "{log}"
  cat >> "{log}"
  printf "\\n" >> "{log}"
fi
''',
    )
    env = {
        **os.environ,
        "COPYQ_BIN": str(fake),
        "XDG_RUNTIME_DIR": str(tmp_path),
    }
    proc = subprocess.run(
        [str(ACTIVATE_HELPER), "--hot-id", item["id"], "--copy-only"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert log.read_text().splitlines() == [
        "argv:copy -",
        f"stdin:{secret}",
    ]
    assert secret not in log.read_text().splitlines()[0]


def test_remove_hot_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(BIN))
    loader = importlib.machinery.SourceFileLoader("copyq_hotkeys_drop", str(HOTKEYS_HELPER))
    spec = importlib.util.spec_from_loader("copyq_hotkeys_drop", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    item = module.upsert_secret("sk-" + ("g" * 40))
    assert item is not None
    proc = subprocess.run(
        [str(REMOVE_HELPER), "--hot-id", item["id"]],
        check=False,
        env={**os.environ, "XDG_RUNTIME_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert module.list_overlay_entries() == []
    assert module.upsert_secret("sk-" + ("g" * 40)) is None


def test_expired_secret_is_not_reharvested(hot_mod) -> None:
    secret = "sk-" + ("h" * 40)
    now = 1_700_000_000.0
    assert hot_mod.upsert_secret(secret, ttl_secs=60, now=now) is not None
    assert hot_mod.list_overlay_entries(now=now + 120) == []
    assert hot_mod.upsert_secret(secret, ttl_secs=60, now=now + 120) is None


def test_runtime_dir_rejects_missing_and_shared(hot_mod, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    with pytest.raises(OSError, match="XDG_RUNTIME_DIR"):
        hot_mod._runtime_dir()
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o777)
    shared.chmod(0o777)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(shared))
    with pytest.raises(OSError, match="writable"):
        hot_mod._runtime_dir()


def test_list_keeps_prefix_that_is_not_a_secret(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])

    def fake_run(args, **_kwargs):
        return _ok(
            _eval_payload(
                [
                    {
                        "index": 0,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": "sk-example",
                        "text": "sk-example",
                        "keyish": True,
                        "previewPath": "",
                        "mime": "text/plain",
                    }
                ],
                clip_count=1,
            )
        )

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hotCount"] == 0
    assert payload["entries"][0]["preview"] == "sk-example"
    assert "512" in list_mod._DUMP_SCRIPT
    assert list_mod.DUMP_MAX_BYTES == 512_000


def test_list_reports_vault_unavailable_without_plaintext(list_mod, monkeypatch, capsys) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(list_mod.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr(list_mod.os, "access", lambda _p, _m: True)
    monkeypatch.setattr(list_mod.sys, "argv", ["copyq-list.py"])
    secret = "sk-" + ("k" * 40)

    def fake_run(args, **_kwargs):
        return _ok(
            _eval_payload(
                [
                    {
                        "index": 0,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": secret,
                        "text": secret,
                        "keyish": True,
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                    {
                        "index": 1,
                        "tab": "&clipboard",
                        "pinned": False,
                        "type": "text",
                        "preview": "hello",
                        "text": "hello",
                        "previewPath": "",
                        "mime": "text/plain",
                    },
                ],
                clip_count=2,
            )
        )

    monkeypatch.setattr(list_mod, "_run", fake_run)
    assert list_mod.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["hotError"] == "hot_vault_unavailable"
    assert payload["hotCount"] == 0
    rendered = json.dumps(payload)
    assert secret not in rendered
    assert payload["entries"][0]["preview"] == "Key hidden — vault unavailable"
    assert payload["entries"][0]["text"] == ""
    assert payload["entries"][1]["preview"] == "hello"
