"""Tests for plugins/lukedaduke.standby/bin/standby-data.

Covers the JEV-review crash paths (issue #10): malformed weather.json
values, wrong-shaped remote payloads, corrupt/expired cache, and the
{"error": ...} emission the panel surfaces via root.weatherError.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import signal
import time
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "plugins/lukedaduke.standby/bin/standby-data"


@pytest.fixture()
def mod():
    """Load the extensionless bin/standby-data helper as a fresh module."""
    loader = importlib.machinery.SourceFileLoader("standby_data", str(HELPER))
    spec = importlib.util.spec_from_loader("standby_data", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture()
def _no_alarm(monkeypatch: pytest.MonkeyPatch):
    """main() arms a SIGALRM kill deadline — neutralize it under pytest."""
    monkeypatch.setattr(signal, "alarm", lambda *_: 0)


def _loc_file(tmp_path: Path, mod, monkeypatch, body) -> Path:
    d = tmp_path / "settings"
    d.mkdir(exist_ok=True)
    f = d / "weather.json"
    f.write_text(body if isinstance(body, str) else json.dumps(body))
    monkeypatch.setattr(mod, "LOC_FILE", f)
    return f


def _cache_file(tmp_path: Path, mod, monkeypatch) -> Path:
    f = tmp_path / "cache" / "standby-weather.json"
    monkeypatch.setattr(mod, "CACHE_FILE", f)
    return f


def _meteo_payload() -> dict:
    return {
        "current": {
            "temperature_2m": 10.4,
            "relative_humidity_2m": 55,
            "apparent_temperature": 8.6,
            "weather_code": 3,
            "wind_speed_10m": 12.4,
        },
        "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
        "daily": {
            "sunrise": ["2026-09-17T06:58:00"],
            "sunset": ["2026-09-17T19:22:00"],
            "temperature_2m_max": [15.6],
            "temperature_2m_min": [4.4],
        },
    }


# --- iso_to_hm ----------------------------------------------------------


def test_iso_to_hm(mod) -> None:
    assert mod.iso_to_hm("2026-09-17T07:15:00") == "07:15"
    assert mod.iso_to_hm("") == ""
    assert mod.iso_to_hm(None) == ""
    assert mod.iso_to_hm("no-time-here") == ""
    assert mod.iso_to_hm(12345) == ""


# --- load_weather_location ----------------------------------------------


def test_location_valid(mod, tmp_path, monkeypatch) -> None:
    _loc_file(tmp_path, mod, monkeypatch,
              {"latitude": 12.5, "longitude": -34.25, "name": "Town"})
    assert mod.load_weather_location() == (12.5, -34.25, "Town")


def test_location_numeric_strings(mod, tmp_path, monkeypatch) -> None:
    _loc_file(tmp_path, mod, monkeypatch,
              {"latitude": "12.5", "longitude": "-34.25"})
    lat, lon, _name = mod.load_weather_location()
    assert lat == 12.5 and lon == -34.25


def test_location_non_numeric_coords_do_not_crash(mod, tmp_path, monkeypatch) -> None:
    """dict/list lat/lon used to raise TypeError out of float()."""
    _loc_file(tmp_path, mod, monkeypatch,
              {"latitude": {"deg": 12}, "longitude": [1, 2], "name": "X"})
    assert mod.load_weather_location() == (None, None, "")


def test_location_huge_int_coords_do_not_crash(mod, tmp_path, monkeypatch) -> None:
    """float(10**400) raises OverflowError, which must also be caught."""
    _loc_file(tmp_path, mod, monkeypatch,
              {"latitude": 10 ** 400, "longitude": 2})
    assert mod.load_weather_location() == (None, None, "")


def test_location_non_dict_json(mod, tmp_path, monkeypatch) -> None:
    """A JSON array body has no .get — must not raise AttributeError."""
    _loc_file(tmp_path, mod, monkeypatch, [1, 2, 3])
    assert mod.load_weather_location() == (None, None, "")


def test_location_invalid_json(mod, tmp_path, monkeypatch) -> None:
    _loc_file(tmp_path, mod, monkeypatch, "{not json")
    assert mod.load_weather_location() == (None, None, "")


def test_location_null_name_not_stringified(mod, tmp_path, monkeypatch) -> None:
    """str(None) must not leak the literal 'None' into the location name."""
    _loc_file(tmp_path, mod, monkeypatch, {"name": None})
    assert mod.load_weather_location() == (None, None, "")


def test_location_missing_file(mod, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "LOC_FILE", tmp_path / "nope" / "weather.json")
    assert mod.load_weather_location() == (None, None, "")


# --- cache: validation + TTL --------------------------------------------


def test_cache_roundtrip(mod, tmp_path, monkeypatch) -> None:
    f = _cache_file(tmp_path, mod, monkeypatch)
    payload = {"location": "Town", "temperature": "12°C"}
    mod.write_cache(payload)
    out = mod.read_cache()
    assert out is not None
    assert json.loads(out) == payload
    # envelope carries a fresh fetched_at timestamp
    assert abs(json.loads(f.read_text())["fetched_at"] - time.time()) < 10


def test_read_cache_rejects_truncated_json(mod, tmp_path, monkeypatch) -> None:
    """A corrupt file starting with '{' was previously re-emitted verbatim."""
    f = _cache_file(tmp_path, mod, monkeypatch)
    f.parent.mkdir()
    f.write_text('{"temperature": "12°C"')
    assert mod.read_cache() is None


def test_read_cache_rejects_non_dict(mod, tmp_path, monkeypatch) -> None:
    f = _cache_file(tmp_path, mod, monkeypatch)
    f.parent.mkdir()
    f.write_text("[1, 2, 3]")
    assert mod.read_cache() is None


def test_read_cache_rejects_bare_payload(mod, tmp_path, monkeypatch) -> None:
    """Legacy cache without a fetched_at envelope is discarded."""
    f = _cache_file(tmp_path, mod, monkeypatch)
    f.parent.mkdir()
    f.write_text(json.dumps({"location": "X", "temperature": "1°C"}))
    assert mod.read_cache() is None


def test_read_cache_expired(mod, tmp_path, monkeypatch) -> None:
    _cache_file(tmp_path, mod, monkeypatch)
    mod.write_cache({"location": "X"})
    assert mod.read_cache(now=time.time()) is not None
    assert mod.read_cache(now=time.time() + mod.CACHE_TTL_S + 1) is None


def test_read_cache_far_future_timestamp_rejected(mod, tmp_path, monkeypatch) -> None:
    """A fetched_at far ahead of the clock must not be trusted forever."""
    _cache_file(tmp_path, mod, monkeypatch)
    mod.write_cache({"location": "X"})
    assert mod.read_cache(now=time.time() - 3600) is None


def test_read_cache_missing_file(mod, tmp_path, monkeypatch) -> None:
    _cache_file(tmp_path, mod, monkeypatch)
    assert mod.read_cache() is None


# --- build_result: remote-payload shape assumptions ----------------------


def test_build_result_happy_path(mod) -> None:
    r = mod.build_result(_meteo_payload(), "Town")
    assert r["location"] == "Town"
    assert r["description"] == "Overcast"
    assert r["temperature"] == "10°C"
    assert r["high"] == "16°C"
    assert r["low"] == "4°C"
    assert r["humidity"] == "55%"
    assert r["wind"] == "12 km/h"
    assert r["sunrise"] == "06:58"
    assert r["sunset"] == "19:22"
    json.dumps(r)


def test_build_result_non_dict_body(mod) -> None:
    with pytest.raises(TypeError):
        mod.build_result([1, 2, 3], "X")
    with pytest.raises(TypeError):
        mod.build_result("not a dict", "X")


def test_build_result_non_dict_sections(mod) -> None:
    with pytest.raises(TypeError):
        mod.build_result({"current": [1], "daily": {}, "current_units": {}}, "X")
    with pytest.raises(TypeError):
        mod.build_result({"current": {}, "daily": "nope", "current_units": {}}, "X")


def test_build_result_wrong_member_shapes_degrade(mod) -> None:
    """Garbage members degrade to empty strings instead of crashing."""
    r = mod.build_result(
        {
            "current": {
                "temperature_2m": "hot",
                "apparent_temperature": {"v": 1},
                "relative_humidity_2m": "wet",
                "weather_code": {"code": 3},
                "wind_speed_10m": [1, 2],
            },
            "daily": {
                "sunrise": {"0": "x"},
                "sunset": 12345,
                "temperature_2m_max": "warm",
                "temperature_2m_min": [None],
            },
            "current_units": {"temperature_2m": 42},
        },
        "X",
    )
    assert r["temperature"] == ""
    assert r["feelsLike"] == ""
    assert r["humidity"] == ""
    assert r["wind"] == ""
    assert r["description"] == "Unknown"
    assert r["sunrise"] == "" and r["sunset"] == ""
    assert r["high"] == "" and r["low"] == ""


# --- main(): {"error": ...} emission the panel surfaces -------------------


def test_main_no_location_emits_error(
        mod, tmp_path, monkeypatch, capsys, _no_alarm) -> None:
    monkeypatch.setattr(mod, "LOC_FILE", tmp_path / "none" / "weather.json")
    _cache_file(tmp_path, mod, monkeypatch)
    monkeypatch.setattr(mod, "get_ip_location", lambda: (None, None, ""))
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out["error"] == "unable to determine location"


def test_main_fetch_failure_emits_error(
        mod, tmp_path, monkeypatch, capsys, _no_alarm) -> None:
    monkeypatch.setattr(mod, "load_weather_location", lambda: (10.0, 20.0, "Town"))
    _cache_file(tmp_path, mod, monkeypatch)

    def boom(url, timeout=10):
        raise URLError("offline")

    monkeypatch.setattr(mod, "fetch_json", boom)
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out["error"].startswith("weather fetch failed")


def test_main_fetch_failure_serves_cache(
        mod, tmp_path, monkeypatch, capsys, _no_alarm) -> None:
    monkeypatch.setattr(mod, "load_weather_location", lambda: (10.0, 20.0, "Town"))
    _cache_file(tmp_path, mod, monkeypatch)
    mod.write_cache({"location": "Cached", "temperature": "9°C"})

    def boom(url, timeout=10):
        raise URLError("offline")

    monkeypatch.setattr(mod, "fetch_json", boom)
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out.get("error") is None
    assert out["location"] == "Cached"


def test_main_malformed_remote_emits_error(
        mod, tmp_path, monkeypatch, capsys, _no_alarm) -> None:
    monkeypatch.setattr(mod, "load_weather_location", lambda: (10.0, 20.0, "Town"))
    _cache_file(tmp_path, mod, monkeypatch)
    monkeypatch.setattr(mod, "fetch_json", lambda url, timeout=10: [1, 2, 3])
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out["error"] == "malformed weather payload"


def test_main_malformed_remote_serves_cache(
        mod, tmp_path, monkeypatch, capsys, _no_alarm) -> None:
    monkeypatch.setattr(mod, "load_weather_location", lambda: (10.0, 20.0, "Town"))
    _cache_file(tmp_path, mod, monkeypatch)
    mod.write_cache({"location": "Cached", "temperature": "9°C"})
    monkeypatch.setattr(mod, "fetch_json", lambda url, timeout=10: {"current": "bad"})
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out["location"] == "Cached"


def test_main_success_prints_and_caches(
        mod, tmp_path, monkeypatch, capsys, _no_alarm) -> None:
    monkeypatch.setattr(mod, "load_weather_location", lambda: (10.0, 20.0, "Town"))
    cache = _cache_file(tmp_path, mod, monkeypatch)
    monkeypatch.setattr(mod, "fetch_json", lambda url, timeout=10: _meteo_payload())
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out["temperature"] == "10°C"
    assert out["location"] == "Town"
    assert cache.exists()
    assert json.loads(cache.read_text())["data"]["location"] == "Town"
