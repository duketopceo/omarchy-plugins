"""Behaviour tests for bin/hotkey-tally.py. Real files in a temp XDG_STATE_HOME."""

from __future__ import annotations

import importlib.util
import json
import os
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
    assert [r["id"] for r in rows] == [tally.binding_id("Terminal"), tally.binding_id("Close window")]
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


def test_binding_id_is_eight_hex_and_label_only(tally):
    assert tally.binding_id("Terminal") == tally.binding_id("Terminal")
    assert len(tally.binding_id("Terminal")) == 8
    int(tally.binding_id("Terminal"), 16)
    assert tally.binding_id("Terminal") != tally.binding_id("Close window")
    # key text is deliberately not part of the id
    assert "Terminal" not in tally.binding_id("Terminal")
