"""Behaviour tests for bin/hotkey-tally.py. Real files in a temp XDG_STATE_HOME."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "bin" / "hotkey-tally.py"


@pytest.fixture()
def tally(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    spec = importlib.util.spec_from_file_location("hotkey_tally", BIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(module, capsys, *argv):
    code = module.main(list(argv))
    return code, capsys.readouterr().out


def test_record_then_list_counts(tally, capsys):
    assert run(tally, capsys, "record", "--id", "a1", "--key", "SUPER + T", "--label", "Terminal")[0] == 0
    assert run(tally, capsys, "record", "--id", "a1", "--key", "SUPER + T", "--label", "Terminal")[0] == 0
    assert run(tally, capsys, "record", "--id", "b2", "--key", "SUPER + W", "--label", "Close window")[0] == 0

    code, out = run(tally, capsys, "list", "--json")
    assert code == 0
    rows = json.loads(out)
    assert [r["id"] for r in rows] == [tally.binding_id("Terminal", "SUPER + T"), tally.binding_id("Close window", "SUPER + W")]
    assert rows[0]["count"] == 2
    assert rows[0]["label"] == "Terminal"
    assert rows[1]["count"] == 1


def test_list_is_empty_before_any_record(tally, capsys):
    code, out = run(tally, capsys, "list")
    assert code == 0
    assert "no bindings to show" in out


def test_search_filters_key_and_label(tally, capsys):
    run(tally, capsys, "record", "--id", "a1", "--key", "SUPER + T", "--label", "Terminal")
    run(tally, capsys, "record", "--id", "b2", "--key", "SUPER + W", "--label", "Close window")

    _, out = run(tally, capsys, "list", "--json", "--search", "close")
    assert [r["label"] for r in json.loads(out)] == ["Close window"]

    _, out = run(tally, capsys, "list", "--json", "--search", "super + t")
    assert [r["label"] for r in json.loads(out)] == ["Terminal"]


def test_torn_line_does_not_break_reading(tally, capsys):
    run(tally, capsys, "record", "--id", "a1", "--key", "K", "--label", "L")
    path = tally.uses_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "trunc\n')

    _, out = run(tally, capsys, "list", "--json")
    rows = json.loads(out)
    assert len(rows) == 1
    assert rows[0]["label"] == "L"


def test_prune_keeps_newest(tally, capsys):
    for i in range(5):
        run(tally, capsys, "record", "--id", f"id{i}", "--key", "K", "--label", "L")
    code, _ = run(tally, capsys, "prune", "--keep", "2")
    assert code == 0

    _, out = run(tally, capsys, "list", "--json")
    labels = {r["label"] for r in json.loads(out)}
    assert labels == {"L"}


def test_reset_removes_state(tally, capsys):
    run(tally, capsys, "record", "--id", "a1", "--key", "K", "--label", "L")
    run(tally, capsys, "reset")
    assert not tally.uses_path().exists()
    _, out = run(tally, capsys, "list")
    assert "no bindings to show" in out


def test_records_contain_no_free_text_fields(tally, capsys):
    """The row schema is fixed: an accidental extra key would be a privacy leak."""
    run(tally, capsys, "record", "--id", "a1", "--key", "SUPER + T", "--label", "Terminal")
    raw = tally.uses_path().read_text(encoding="utf-8").strip()
    row = json.loads(raw)
    assert set(row) == {"id", "key", "label", "ts"}


def test_legacy_label_id_is_eight_hex(tally):
    assert tally.binding_id("Terminal") == tally.binding_id("Terminal")
    assert len(tally.binding_id("Terminal")) == 8
    int(tally.binding_id("Terminal"), 16)
    assert tally.binding_id("Terminal") != tally.binding_id("Close window")
    # The legacy label-only form is retained for records without a key.
    assert "Terminal" not in tally.binding_id("Terminal")


def test_shared_label_keeps_distinct_shortcut_counts(tally, capsys):
    run(tally, capsys, "record", "--id", "a", "--key", "SUPER + B", "--label", "BrowserOS")
    run(tally, capsys, "record", "--id", "b", "--key", "SUPER + SHIFT + RETURN", "--label", "BrowserOS")
    _, out = run(tally, capsys, "list", "--json")
    rows = json.loads(out)
    assert len(rows) == 2
    assert {row["key"] for row in rows} == {"SUPER + B", "SUPER + SHIFT + RETURN"}
    assert all(row["count"] == 1 for row in rows)


def test_shortcut_identity_normalizes_menu_and_binding_format(tally):
    assert tally.binding_id("Screenshot", "SUPER + XF86AudioMute") != tally.binding_id("Screenshot", "SUPER + F10")
    assert tally.binding_id("File manager", "SUPER + SHIFT + F") == tally.binding_id("File manager", "SUPER SHIFT + F")


def test_menu_only_annotates_the_matching_shortcut(tally, capsys, monkeypatch):
    run(tally, capsys, "record", "--key", "SUPER + B", "--label", "BrowserOS")
    monkeypatch.setattr("sys.stdin", io.StringIO("SUPER + B  → BrowserOS\texec\ta\nSUPER SHIFT + RETURN  → BrowserOS\texec\tb\n"))
    _, out = run(tally, capsys, "annotate")
    lines = out.splitlines()
    assert "×1" in lines[0]
    assert "×1" not in lines[1]


def test_legacy_rows_recover_identity_from_key(tally, capsys):
    tally._append({"id": "legacy", "key": "SUPER + B", "label": "BrowserOS", "ts": 1})
    run(tally, capsys, "record", "--key", "SUPER + B", "--label", "BrowserOS")
    _, out = run(tally, capsys, "list", "--json")
    assert json.loads(out)[0]["count"] == 2


def test_unobserved_binding_is_not_reported_as_zero_usage(tally, monkeypatch):
    monkeypatch.setattr(tally, "_live_binds", lambda: [{"key": "SUPER + T", "label": "Terminal"}])
    assert tally._joined("config")[0]["count"] is None


def test_keycode_binding_retains_its_key(tally):
    assert tally._key_name({"modmask": 64, "key": "", "keycode": 12}) == "SUPER + code:12"


def test_machine_menu_joins_keycode_before_rendering(tally, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    run(tally, capsys, "record", "--key", "SUPER + code:12", "--label", "Switch to workspace 3")
    menu = Path(__file__).resolve().parents[3] / "machine/bin/omarchy-menu-keybindings"
    script = menu.read_text().split('\ncase "${1:-}" in', 1)[0]
    script += '''
HOTKEY_TALLY_BIN="$1"
build_lua_bind_cache() { :; }
dynamic_bindings() { printf 'SUPER\\037code:12\\037Switch to workspace 3\\037exec\\037command\\n'; }
static_bindings() { :; }
keybindings_cache_key() { printf fixed; }
output_binding_records
'''
    result = subprocess.run(["bash", "-c", script, "test", str(BIN)], check=True, capture_output=True, text=True)
    assert "×1" in result.stdout
    assert "code:12" not in result.stdout


def test_machine_menu_survives_missing_tracker():
    menu = Path(__file__).resolve().parents[3] / "machine/bin/omarchy-menu-keybindings"
    script = menu.read_text().split('\ncase "${1:-}" in', 1)[0]
    script += '\nHOTKEY_TALLY_BIN=/does-not-exist\nprintf "SUPER + B → BrowserOS\\texec\\tcommand\\n" | tally_annotate\n'
    result = subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
    assert result.stdout == "SUPER + B → BrowserOS\texec\tcommand\n"


def test_menu_distinguishes_unpressed_tracked_and_untracked(tally, capsys, monkeypatch):
    records = (
        "SUPER + B  → BrowserOS\texec\tpython ./hotkey-tally.py record --key B\n"
        "SUPER + W  → Close\texec\tclose\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(records))
    _, out = run(tally, capsys, "annotate", "--sort", "used")
    lines = out.splitlines()
    assert "BrowserOS  ×0" in lines[0]
    assert "×0" not in lines[1]


def test_focus_launch_keeps_original_dispatcher():
    helper = BIN.parents[1] / "hotkey-tally.lua"
    code = '''
o = { bind = function(_, _, target) assert(type(target) == "table" and target.focus == "app") end }
local tally = dofile(arg[1])
tally.bind("SUPER + T", "App", {launch = "app", focus = "app"})
'''
    subprocess.run(["lua", "-", str(helper)], input=code, text=True, check=True, capture_output=True)


def test_machine_menu_resolves_current_lua_dispatcher():
    menu = Path(__file__).resolve().parents[3] / "machine/bin/omarchy-menu-keybindings"
    script = menu.read_text().split('\ncase "${1:-}" in', 1)[0]
    script += '''
hyprctl() { printf 'bind\\n\\tmodmask: 64\\n\\tkey: B\\n\\tkeycode: 0\\n\\tdescription: BrowserOS\\n\\tdispatcher: HL.Dispatcher(exec_cmd)\\n\\targ: 207\\n'; }
LUA_BIND_DISPATCHER_MAP["64,BrowserOS,B"]=exec
LUA_BIND_ARG_MAP["64,BrowserOS,B"]=browseros
dynamic_bindings
'''
    result = subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
    assert "SUPER\x1fB\x1fBrowserOS\x1fexec\x1fbrowseros" in result.stdout


def test_wrapped_action_runs_with_and_without_recorder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    recorder = tmp_path / ".config/omarchy/plugins/io.github.duketopceo.hotkey-tally/bin/hotkey-tally.py"
    recorder.parent.mkdir(parents=True)
    shutil.copyfile(BIN, recorder)
    helper = BIN.parents[1] / "hotkey-tally.lua"
    lua = 'local t = dofile(arg[1]); print(t.wrap("touch " .. arg[2], "SUPER + B", "BrowserOS"))'
    marker = tmp_path / "action"
    command = subprocess.run(["lua", "-", str(helper), str(marker)], input=lua, check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run(["sh", "-c", command + "; wait"], check=True)
    assert marker.exists()
    rows = (tmp_path / "state/hotkey-tally/uses.jsonl").read_text().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["label"] == "BrowserOS"
    marker.unlink()
    recorder.unlink()
    subprocess.run(["sh", "-c", command + "; wait"], check=True)
    assert marker.exists()
