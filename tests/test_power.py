from __future__ import annotations

import importlib.util
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
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
    assert "75–80%" in chart
    assert spark


def test_update_history_state_dir_denied_returns_empty(
    helper, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _deny():
        raise PermissionError("state dir is not a user-owned real directory")

    monkeypatch.setattr(helper, "_open_state_dir", _deny)
    assert helper.update_history(50, "Discharging") == []


def test_missing_battery_is_reported_without_synthetic_history(
    helper, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(helper.os.path, "exists", lambda _path: False)
    capacity, status = helper.get_current_battery()
    assert capacity is None
    assert status == "Battery unavailable"
    assert helper.update_history(capacity, status) == []
    assert not (helper.STATE_DIR / HISTORY_NAME).exists()


def test_history_update_serializes_concurrent_writers(helper) -> None:
    original = helper.time.time
    try:
        helper.time.time = lambda: 1000
        capacities = [40, 41, 42, 43, 44]
        with ThreadPoolExecutor(max_workers=len(capacities)) as pool:
            list(pool.map(lambda capacity: helper.update_history(capacity, "Discharging"), capacities))
    finally:
        helper.time.time = original

    history = _read(helper)
    assert len(history) == len({point["cap"] for point in history}) == 5


# ---------- make_ascii_graph ----------


def test_make_ascii_graph_empty_history(helper) -> None:
    chart, spark = helper.make_ascii_graph([], 80)
    lines = chart.split("\n")
    assert len(lines) == 2
    assert "80–80%" in chart
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
    assert "40–68%" in chart


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


# ---------- write amplification ----------
# The bar ticks every few seconds; rewriting (and fsyncing) an unchanged
# 17 KB history file on each tick was ~17k pointless writes a day.


def test_update_history_does_not_write_when_nothing_changed(helper, monkeypatch) -> None:
    now = int(time.time())
    _seed(tmp_path := helper.STATE_DIR, [{"time": now, "cap": 80, "status": "Discharging"}])

    calls = []
    monkeypatch.setattr(helper, "_write_history", lambda dirfd, history: calls.append(history))

    helper.update_history(80, "Discharging")

    assert calls == []


def test_update_history_writes_once_when_appending(helper, monkeypatch) -> None:
    now = int(time.time())
    _seed(tmp_path := helper.STATE_DIR, [{"time": now, "cap": 80, "status": "Discharging"}])

    calls = []
    monkeypatch.setattr(helper, "_write_history", lambda dirfd, history: calls.append(history))

    helper.update_history(79, "Discharging")

    assert len(calls) == 1
    assert calls[0][-1]["cap"] == 79


def test_update_history_repairs_malformed_even_without_new_sample(helper, monkeypatch) -> None:
    """A corrupt point must still get scrubbed on a no-op tick."""
    now = int(time.time())
    _seed(
        tmp_path := helper.STATE_DIR,
        [{"time": now, "cap": 80, "status": "Discharging"}, {"bogus": True}],
    )

    calls = []
    monkeypatch.setattr(helper, "_write_history", lambda dirfd, history: calls.append(history))

    helper.update_history(80, "Discharging")

    assert len(calls) == 1
    assert all(e.get("bogus") is None for e in calls[0])


# ---------- get_telemetry ----------

# A real macsmc-battery snapshot: bq40z651 in a MacBookPro18,2.
BAT = {
    "capacity": "40",
    "status": "Discharging",
    "cycle_count": "269",
    "energy_now": "31130000",
    "energy_full": "84500000",
    "energy_full_design": "99111600",
    "charge_now": "2731000",
    "charge_full": "7412000",
    "charge_full_design": "8694000",
    "charge_counter": "9875107",
    "current_now": "-988000",
    "power_now": "-11080000",
    "voltage_now": "11140000",
    "voltage_min": "8611000",
    "voltage_max": "13005000",
    "temp": "332",
    "time_to_empty_now": "8340",
    "time_to_full_now": "0",
    "charge_control_start_threshold": "75",
    "charge_control_end_threshold": "80",
    "charge_behaviour": "[auto] inhibit-charge",
    "health": "Good",
    "model_name": "bq40z651",
    "manufacture_year": "2022",
    "manufacture_month": "7",
    "manufacture_day": "9",
}


def _telemetry(helper, monkeypatch, overrides=None, drop=()):
    attrs = {k: v for k, v in BAT.items() if k not in drop}
    attrs.update(overrides or {})
    monkeypatch.setattr(helper, "_read_battery_attrs", lambda: attrs)
    return helper.get_telemetry()


def test_telemetry_state_of_health(helper, monkeypatch) -> None:
    # 84.5 Wh of a 99.1116 Wh design pack.
    assert _telemetry(helper, monkeypatch)["health_pct"] == 85.3


def test_telemetry_health_falls_back_to_coulomb_pair(helper, monkeypatch) -> None:
    tele = _telemetry(helper, monkeypatch, drop=("energy_full", "energy_full_design"))
    # 7.412 Ah of an 8.694 Ah design pack.
    assert tele["health_pct"] == 85.3


def test_telemetry_health_clamped_at_100(helper, monkeypatch) -> None:
    tele = _telemetry(
        helper, monkeypatch, {"energy_full": "99900000", "energy_full_design": "99111600"}
    )
    assert tele["health_pct"] == 100.0


def test_telemetry_counts_are_whole_numbers(helper, monkeypatch) -> None:
    """269.0 in a UI is a bug; these are counts, not measurements."""
    tele = _telemetry(helper, monkeypatch)
    assert tele["cycle_count"] == 269
    assert tele["charge_limit_pct"] == 80
    assert tele["charge_resume_pct"] == 75
    assert tele["time_to_empty_s"] == 8340
    assert all(isinstance(tele[k], int) for k in ("cycle_count", "charge_limit_pct", "time_to_empty_s"))


def test_telemetry_electrical_units(helper, monkeypatch) -> None:
    tele = _telemetry(helper, monkeypatch)
    # uWh/uW/uA/uV and tenths-of-a-degree are divided exactly once.
    assert tele["energy_wh"] == 31.13
    assert tele["energy_full_wh"] == 84.5
    assert tele["power_w"] == -11.08
    assert tele["current_a"] == -0.988
    assert tele["voltage_v"] == 11.14
    assert tele["temp_c"] == 33.2


def test_telemetry_charge_reported_in_mah(helper, monkeypatch) -> None:
    """uAh -> mAh is /1e3. Reporting 7.4 "mAh" for a 7412 mAh pack was the bug."""
    tele = _telemetry(helper, monkeypatch)
    assert tele["charge_now_mah"] == 2731
    assert tele["charge_full_mah"] == 7412
    assert tele["charge_design_mah"] == 8694


def test_telemetry_flow_follows_power_sign(helper, monkeypatch) -> None:
    assert _telemetry(helper, monkeypatch)["flow"] == "out"
    charging = _telemetry(helper, monkeypatch, {"power_now": "45200000", "status": "Charging"})
    assert charging["flow"] == "in"


def test_telemetry_idle_power_snapped_to_zero(helper, monkeypatch) -> None:
    """Sub-1.0 W is gauge noise; a live decimal there just flickers."""
    idle = _telemetry(helper, monkeypatch, {"power_now": "-120000", "status": "Not charging"})
    assert idle["power_w"] == 0.0
    assert idle["flow"] == "idle"


def test_telemetry_gauged_dither_does_not_contradict_charging(helper, monkeypatch) -> None:
    """A real capture: the gauge read -0.57 W while UPower said Charging.

    Rendered verbatim that printed "-0.57 W out" directly under a charging
    header, which looks like a fault. It has to snap to idle instead.
    """
    tele = _telemetry(helper, monkeypatch, {"power_now": "-570000", "status": "Charging"})
    assert tele["power_w"] == 0.0
    # Direction falls back to the status string once the sign is snapped away.
    assert tele["flow"] == "in"


def test_telemetry_descriptive_fields(helper, monkeypatch) -> None:
    tele = _telemetry(helper, monkeypatch)
    assert tele["health"] == "Good"
    assert tele["model"] == "bq40z651"
    assert tele["manufactured"] == "2022-07-09"
    # "[auto] inhibit-charge" -> the driver policy, not the supply's mode word.
    assert tele["charge_behaviour"] == "inhibit-charge"


def test_telemetry_absent_battery_is_empty(helper, monkeypatch) -> None:
    monkeypatch.setattr(helper, "_read_battery_attrs", lambda: {})
    assert helper.get_telemetry() == {}


def test_telemetry_survives_unparsable_attribute(helper, monkeypatch) -> None:
    tele = _telemetry(helper, monkeypatch, {"temp": "not-a-number", "cycle_count": "???"})
    assert tele["temp_c"] is None
    assert tele["cycle_count"] is None
    # Everything else still reports.
    assert tele["health_pct"] == 85.3


# ---------- analyze_history ----------


def test_analyze_history_needs_two_points(helper) -> None:
    assert helper.analyze_history([], 50)["drain_pct_per_h"] is None
    assert helper.analyze_history([{"time": 100, "cap": 50}], 50)["drain_pct_per_h"] is None


def test_analyze_history_recovers_known_drain_rate(helper) -> None:
    """9 points of fall over 90 minutes is 6%/hour."""
    now = 1_000_000
    history = [
        {"time": now - (9 - i) * 600, "cap": 90 - i, "status": "Discharging"} for i in range(10)
    ]
    out = helper.analyze_history(history, 81)
    assert out["drain_pct_per_h"] == 6.0
    assert out["window_min"] == 90.0


def test_analyze_history_slope_is_directionless(helper) -> None:
    """Charging yields a negative drain; the panel should still show a number."""
    now = 1_000_000
    history = [
        {"time": now - (9 - i) * 600, "cap": 40 + i, "status": "Charging"} for i in range(10)
    ]
    assert helper.analyze_history(history, 49)["drain_pct_per_h"] == -6.0


def test_analyze_history_ignores_malformed_points(helper) -> None:
    now = 1_000_000
    history = [
        {"time": now - 1200, "cap": 70},
        "garbage",
        {"nope": 1},
        {"time": now - 600, "cap": 65},
        {"time": now, "cap": 60},
    ]
    assert helper.analyze_history(history, 60)["drain_pct_per_h"] == 30.0


def test_analyze_history_projected_runtime_prefers_gauge_estimate(helper) -> None:
    out = helper.analyze_history(
        [{"time": 0, "cap": 50}, {"time": 600, "cap": 45}],
        45,
        {"time_to_empty_s": 8340, "energy_wh": 31.1, "power_w": -11.0},
    )
    assert out["projected_runtime_min"] == 139


def test_analyze_history_projected_runtime_falls_back_to_energy_over_power(helper) -> None:
    """At full charge the kernel reports 0s, so W and Wh have to carry it."""
    out = helper.analyze_history(
        [{"time": 0, "cap": 50}, {"time": 600, "cap": 45}],
        45,
        {"time_to_empty_s": 0, "energy_wh": 44.0, "power_w": 11.0},
    )
    assert out["projected_runtime_min"] == 240


def test_analyze_history_no_runtime_without_power(helper) -> None:
    out = helper.analyze_history(
        [{"time": 0, "cap": 50}, {"time": 600, "cap": 45}], 45, {"time_to_empty_s": 0}
    )
    assert out["projected_runtime_min"] is None


def test_graph_caption_carries_drain_rate(helper) -> None:
    now = 1_000_000
    history = [
        {"time": now - (9 - i) * 600, "cap": 90 - i, "status": "Discharging"} for i in range(10)
    ]
    insights = helper.analyze_history(history, 81)
    chart, _ = helper.make_ascii_graph(history, 81, None, insights)
    assert "6.0%/h down" in chart
    assert "1h 30m" in chart
    # The header owns the current charge; repeating it here only ever put two
    # different percentages on one screen.
    assert "now" not in chart


def test_graph_caption_marks_a_charging_slope_as_up(helper) -> None:
    now = 1_000_000
    history = [
        {"time": now - (9 - i) * 600, "cap": 50 + i, "status": "Charging"} for i in range(10)
    ]
    insights = helper.analyze_history(history, 59)
    chart, _ = helper.make_ascii_graph(history, 59, None, insights)
    # A rising window yields a negative slope; it must read as a gain, not as
    # a bare "-6.0%/h" the reader has to decode.
    assert insights["drain_pct_per_h"] < 0
    assert "6.0%/h up" in chart
    assert "-6.0" not in chart


def test_graph_caption_omits_drain_when_unknown(helper) -> None:
    chart, _ = helper.make_ascii_graph([], 80, None, {"drain_pct_per_h": None})
    assert "/h" not in chart


# ---------- consumers cache ----------

_PS_BODY = b"COMMAND %CPU %MEM\nchromium 30.0 10.0\ndevin 4.0 1.0\n"


def test_consumers_are_cached_within_ttl(helper, monkeypatch) -> None:
    scans = []

    def fake_scan():
        scans.append(1)
        return [{"name": "chromium", "cpu": "30.0%", "cpu_num": 30.0, "mem": "10.0%", "bar": "#"}]

    monkeypatch.setattr(helper, "_scan_top_consumers", fake_scan)

    first = helper.get_top_consumers()
    second = helper.get_top_consumers()
    third = helper.get_top_consumers()

    assert first == second == third
    assert len(scans) == 1, "ps must be walked once per TTL, not once per call"


def test_consumers_cache_rescans_after_ttl(helper, monkeypatch) -> None:
    scans = []

    def fake_scan():
        scans.append(1)
        return [{"name": "x", "cpu": "1.0%", "cpu_num": 1.0, "mem": "0.0%", "bar": "-"}]

    monkeypatch.setattr(helper, "_scan_top_consumers", fake_scan)

    helper.get_top_consumers()
    # Pretend the cached rows are older than the TTL.
    dirfd = helper._open_state_dir()
    try:
        helper._write_consumers_cache(dirfd, [])
        payload = json.loads((helper.STATE_DIR / helper.CACHE_NAME).read_text())
        payload["at"] -= helper.CONSUMERS_TTL_S + 1
        (helper.STATE_DIR / helper.CACHE_NAME).write_text(json.dumps(payload))
    finally:
        os.close(dirfd)

    helper.get_top_consumers()
    assert len(scans) == 2


def test_consumers_force_bypasses_cache(helper, monkeypatch) -> None:
    scans = []

    def fake_scan():
        scans.append(1)
        return [{"name": "x", "cpu": "1.0%", "cpu_num": 1.0, "mem": "0.0%", "bar": "-"}]

    monkeypatch.setattr(helper, "_scan_top_consumers", fake_scan)

    helper.get_top_consumers()
    helper.get_top_consumers(force=True)
    assert len(scans) == 2


def test_consumers_exclude_this_interpreter(helper, monkeypatch) -> None:
    """The helper must never list its own python process as a top consumer."""
    body = b"COMMAND %CPU %MEM\npython3 99.0 5.0\nchromium 2.0 1.0\n"
    monkeypatch.setattr(helper, "_run", lambda argv, **kw: body.decode())
    names = [row["name"] for row in helper._scan_top_consumers()]
    assert "python3" not in names
    assert "chromium" in names


def test_consumers_survive_ps_failure(helper, monkeypatch) -> None:
    monkeypatch.setattr(helper, "_run", lambda argv, **kw: None)
    assert helper._scan_top_consumers()[0]["name"] == "unavailable"
