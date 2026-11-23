"""Status.js: Home status dots, weather and System page rows (node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Status.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def js(expr: str):
    script = f"const S=require({json.dumps(str(MOD))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


# ---- weather (Omarchy's omarchy-weather-status format) ----
def test_weather_parses_omarchy_status_line():
    line = "Salt lake city  ·  Temp 12°C  ·  Wind ↗10km/h"
    assert js(f"S.weather({json.dumps(line)})") == {"place": "Salt lake city", "temp": "12°C"}


def test_weather_negative_fahrenheit():
    line = "Oslo  ·  Temp -3°F  ·  Wind 5mph"
    assert js(f"S.weather({json.dumps(line)})")["temp"] == "-3°F"


@pytest.mark.parametrize("text", ["Weather unavailable", "", "garbage", None])
def test_weather_unavailable_is_null(text):
    assert js(f"S.weather({json.dumps(text)})") is None


# ---- weather only while Omarchy's weather widget is in the bar ----
def bar(entries, disabled=None):
    return json.dumps({"bar": {"layout": {"left": [], "center": [{"id": "omarchy.clock"}], "right": entries}},
                       "disabledPlugins": disabled or [], "plugins": [{"id": "x", "note": "omarchy.weather"}]})


def test_weather_in_bar_when_widget_placed():
    assert js(f"S.weatherInBar({json.dumps(bar([{'id': 'omarchy.weather'}]))})") is True


def test_weather_not_in_bar_when_absent_or_only_mentioned_elsewhere():
    assert js(f"S.weatherInBar({json.dumps(bar([]))})") is False


def test_weather_not_in_bar_when_disabled():
    text = bar([{"id": "omarchy.weather"}], ["omarchy.weather"])
    assert js(f"S.weatherInBar({json.dumps(text)})") is False


@pytest.mark.parametrize("text", ["", "{bad", "[]", None])
def test_weather_in_bar_junk(text):
    assert js(f"S.weatherInBar({json.dumps(text)})") is False


# ---- Home status dots ----
def home(**over):
    h = {"battery": {"capacity": 80, "status": "Discharging"},
         "tailscale": {"state": "Running", "online": True, "peers": 3},
         "vpn": {"on": False, "name": ""}}
    h.update(over)
    return js(f"S.homeDots({json.dumps(h)})")


def test_home_dots_battery_and_tailscale_up():
    assert home() == [{"id": "battery", "text": "80%", "on": True},
                      {"id": "tailscale", "text": "Tailscale", "on": True}]


def test_home_dots_charging_marked():
    assert home(battery={"capacity": 55, "status": "Charging"})[0]["text"] == "55% charging"


def test_home_dots_tailscale_down_shown_off():
    d = home(tailscale={"state": "Stopped", "online": False, "peers": 0})
    assert d[1] == {"id": "tailscale", "text": "Tailscale", "on": False}


def test_home_dots_vpn_only_when_on():
    assert [x["id"] for x in home(vpn={"on": True, "name": "wg0"})] == ["battery", "tailscale", "vpn"]
    assert home(vpn={"on": True, "name": "wg0"})[2] == {"id": "vpn", "text": "VPN", "on": True}


def test_home_dots_missing_sources_hidden():
    assert home(battery=None, tailscale=None) == []
    assert js("S.homeDots(null)") == []


# ---- System rows ----
SYS = {"battery": {"capacity": 100, "status": "Full"}, "profile": "balanced", "fan": "quiet", "fanPanel": True,
       "cpu": 62, "memory": {"usedPct": 48, "used": 31958302720, "total": 67279405056},
       "network": {"iface": "wlan0", "type": "wifi", "name": "Bartlett SLC"},
       "tailscale": {"state": "Running", "online": True, "peers": 28}}


def rows(s):
    return js(f"S.systemRows({json.dumps(s)})")


def test_system_rows_in_order():
    r = rows(SYS)
    assert [x["id"] for x in r] == ["battery", "profile", "fan", "cpu", "memory", "network", "tailscale"]
    assert r[0]["value"] == "100% · Full"
    assert r[1]["value"] == "Balanced"
    assert r[2]["value"] == "Quiet"
    assert r[3]["value"] == "62%"
    assert r[4]["value"] == "48% · 29.8 of 62.7 GB"
    assert r[5]["value"] == "Wi-Fi · Bartlett SLC"
    assert r[6]["value"] == "Connected · 28 peers"


def test_system_rows_meter_fraction():
    r = {x["id"]: x for x in rows(SYS)}
    assert r["cpu"]["level"] == 0.62
    assert r["memory"]["level"] == 0.48
    assert "level" not in r["network"]


def test_system_rows_skip_null_fields():
    s = dict(SYS, profile=None, fan=None, tailscale=None, network=None)
    assert [x["id"] for x in rows(s)] == ["battery", "cpu", "memory"]


def test_system_rows_network_without_name_shows_iface():
    s = dict(SYS, network={"iface": "eth0", "type": "ethernet", "name": ""})
    assert {x["id"]: x for x in rows(s)}["network"]["value"] == "Ethernet · eth0"


def test_system_rows_tailscale_stopped():
    s = dict(SYS, tailscale={"state": "Stopped", "online": False, "peers": 0})
    assert {x["id"]: x for x in rows(s)}["tailscale"]["value"] == "Stopped"


def test_system_rows_null_input():
    assert rows(None) == []


# ---- Home glance tile ----
def test_glance_battery_cpu_memory_in_order():
    g = js('S.glance({battery:{capacity:62,status:"Charging"},cpu:12,memory:{usedPct:41}})')
    assert [x["id"] for x in g] == ["battery", "cpu", "memory"]
    assert g[0]["value"] == "62% · charging" and g[0]["level"] == 0.62
    assert g[1]["value"] == "12%" and g[2]["value"] == "41%"


def test_glance_full_and_discharging():
    assert js('S.glance({battery:{capacity:100,status:"Full"}})')[0]["value"] == "100% · full"
    assert js('S.glance({battery:{capacity:50,status:"Discharging"}})')[0]["value"] == "50%"


@pytest.mark.parametrize("h", ["null", "{}", '{"cpu":null,"memory":null,"battery":null}'])
def test_glance_missing_sources_empty(h):
    assert js(f"S.glance({h})") == []


# ---- pill temperature ----
@pytest.mark.parametrize("temp,want", [("12°C", "12°"), ("-3°F", "-3°"), ("41°F", "41°"), ("12.5°C", "12°")])
def test_pill_temp_short(temp, want):
    assert js(f"S.pillTemp({{place:'x',temp:{json.dumps(temp)}}})") == want


@pytest.mark.parametrize("w", ["null", "{}", "{temp:'warm'}", "{temp:12}"])
def test_pill_temp_missing_is_empty(w):
    assert js(f"S.pillTemp({w})") == ""
