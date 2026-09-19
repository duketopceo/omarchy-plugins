from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "plugins/lukedaduke.power/battery_helper.py"
HISTORY_NAME = "battery_history.json"


def load():
    spec = importlib.util.spec_from_file_location("battery_helper", HELPER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Helper module with STATE_DIR redirected into a temp dir."""
    mod = load()
    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    return mod


def _seed(tmp_path: Path, payload) -> None:
    (tmp_path / HISTORY_NAME).write_text(json.dumps(payload))


def _read(helper) -> list:
    dirfd = helper._open_state_dir()
    try:
        return helper._read_history(dirfd)
    finally:
        os.close(dirfd)


def _read_file(tmp_path: Path):
    return json.loads((tmp_path / HISTORY_NAME).read_text())


# ---------- _read_history ----------


def test_read_history_missing_file_returns_empty(helper) -> None:
    assert _read(helper) == []


def test_read_history_invalid_json_returns_empty(helper, tmp_path: Path) -> None:
    (tmp_path / HISTORY_NAME).write_text("{not json")
    assert _read(helper) == []


def test_read_history_non_list_payload_returns_empty(helper, tmp_path: Path) -> None:
    _seed(tmp_path, {"time": 1, "cap": 50})
    assert _read(helper) == []
    _seed(tmp_path, 42)
    assert _read(helper) == []


def test_read_history_skips_malformed_entries(helper, tmp_path: Path) -> None:
    _seed(
        tmp_path,
        [
            {"time": 100, "cap": 80, "status": "Discharging"},
            "garbage",
            42,
            ["cap", 50],
            {"cap": 70},  # missing time
            {"time": 200},  # missing cap
            {"time": "soon", "cap": 60},  # non-numeric time
            {"time": 300, "cap": "full"},  # non-numeric cap
            {"time": 400, "cap": "55"},  # numeric-string cap is kept
        ],
    )
    assert _read(helper) == [
        {"time": 100, "cap": 80, "status": "Discharging"},
        {"time": 400, "cap": 55, "status": ""},
    ]


def test_read_history_all_malformed_returns_empty(helper, tmp_path: Path) -> None:
    _seed(tmp_path, ["x", 7, None, {"bogus": True}])
    assert _read(helper) == []


# ---------- update_history append/trim rules ----------


def test_update_history_appends_first_point(helper, tmp_path: Path) -> None:
    history = helper.update_history(80, "Discharging")
    assert len(history) == 1
    assert history[0]["cap"] == 80
    assert history[0]["status"] == "Discharging"
    assert isinstance(history[0]["time"], int)
    assert _read_file(tmp_path) == history


def test_update_history_no_duplicate_within_60s_same_cap(helper, tmp_path: Path) -> None:
    now = int(time.time())
    _seed(tmp_path, [{"time": now, "cap": 80, "status": "Discharging"}])
    history = helper.update_history(80, "Discharging")
    assert len(history) == 1


def test_update_history_appends_on_cap_change(helper, tmp_path: Path) -> None:
    now = int(time.time())
    _seed(tmp_path, [{"time": now, "cap": 80, "status": "Discharging"}])
    history = helper.update_history(75, "Discharging")
    assert len(history) == 2
    assert history[-1]["cap"] == 75


def test_update_history_appends_after_60s(helper, tmp_path: Path) -> None:
    now = int(time.time())
    _seed(tmp_path, [{"time": now - 61, "cap": 80, "status": "Discharging"}])
    history = helper.update_history(80, "Discharging")
    assert len(history) == 2


def test_update_history_trims_to_240(helper, tmp_path: Path) -> None:
    now = int(time.time())
    seeded = [
        {"time": now - 60 * (241 - i), "cap": 50 + (i % 10), "status": "Discharging"}
        for i in range(240)
    ]
    _seed(tmp_path, seeded)
    history = helper.update_history(33, "Charging")
    assert len(history) == 240
    assert history[-1]["cap"] == 33
    # Oldest point was dropped to make room.
    assert history[0] == seeded[1]


def test_update_history_malformed_entries_not_fatal(helper, tmp_path: Path) -> None:
    """A corrupt entry must not zero the whole output — the JEV finding."""
    now = int(time.time())
    _seed(
        tmp_path,
        [
            {"time": now - 120, "cap": 80, "status": "Discharging"},
            "garbage",
            {"nope": 1},
            7,
        ],
    )
    history = helper.update_history(75, "Discharging")
    assert history[-1]["cap"] == 75
    assert all(isinstance(p, dict) for p in history)
    # File is rewritten clean — malformed entries are gone for good.
    assert _read_file(tmp_path) == history
    # And downstream rendering doesn't choke on the recovered data.
    chart, spark = helper.make_ascii_graph(history, 75)
    assert "now 75%" in chart
    assert spark


def test_update_history_state_dir_denied_returns_empty(
    helper, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _deny():
        raise PermissionError("state dir is not a user-owned real directory")

    monkeypatch.setattr(helper, "_open_state_dir", _deny)
    assert helper.update_history(50, "Discharging") == []


# ---------- make_ascii_graph ----------


def test_make_ascii_graph_empty_history(helper) -> None:
    chart, spark = helper.make_ascii_graph([], 80)
    lines = chart.split("\n")
    assert len(lines) == 2
    assert "now 80%" in chart
    assert len(spark) == 1


def test_make_ascii_graph_decimates_to_width(helper) -> None:
    now = int(time.time())
    history = [
        {"time": now - (100 - i) * 60, "cap": 40 + (i % 30), "status": "Discharging"}
        for i in range(100)
    ]
    chart, spark = helper.make_ascii_graph(history, 55)
    spark_line = chart.split("\n")[0]
    assert len(spark_line) == helper.GRAPH_WIDTH == 24
    assert len(spark) == helper.GRAPH_WIDTH
    assert "now 55%" in chart


def test_make_ascii_graph_short_history_not_padded(helper) -> None:
    now = int(time.time())
    history = [
        {"time": now - 120, "cap": 50, "status": "Discharging"},
        {"time": now - 60, "cap": 55, "status": "Discharging"},
        {"time": now, "cap": 60, "status": "Discharging"},
    ]
    chart, spark = helper.make_ascii_graph(history, 60)
    assert len(chart.split("\n")[0]) == 3
    assert len(spark) == 3
    # 2-minute span renders with an "m" label.
    assert "2m" in chart


def test_make_ascii_graph_hour_span_label(helper) -> None:
    now = int(time.time())
    history = [
        {"time": now - 3700, "cap": 30, "status": "Discharging"},
        {"time": now, "cap": 80, "status": "Charging"},
    ]
    chart, _ = helper.make_ascii_graph(history, 80)
    assert "1h" in chart
