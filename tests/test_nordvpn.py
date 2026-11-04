from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/io.github.duketopceo.nordvpn/bin/probe_nordvpn.py"


def load():
    spec = importlib.util.spec_from_file_location("probe_nordvpn", PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


STATUS_CONNECTED = """\
Status: Connected
Server: United States #12980
Hostname: us12980.nordvpn.com
IP: 187.14.251.226
Country: United States
City: Denver
Current technology: NORDLYNX
Current protocol: UDP
Transfer: 8.59 MiB received, 6.20 MiB sent
Uptime: 5 minutes 12 seconds
"""

STATUS_DISCONNECTED = "Status: Disconnected\n"
STATUS_LOGGED_OUT = "You are not logged in.\n"
SETTINGS = "Technology: NORDLYNX\nKill Switch: enabled\nAuto-connect: disabled\n"


def _stub_run(mapping):
    def run(argv, timeout_s=8.0):
        key = " ".join(argv[1:]) if len(argv) > 1 else ""
        for pat, out in mapping.items():
            if key == pat or key.startswith(pat):
                return out
        return 0, ""
    return run


def test_kv_parses_nordvpn_style():
    mod = load()
    d = mod._kv(STATUS_CONNECTED)
    assert d["hostname"] == "us12980.nordvpn.com"
    assert d["city"] == "Denver"
    assert d["current_technology"] == "NORDLYNX"


def test_status_connected():
    mod = load()
    calls = {"status": (0, STATUS_CONNECTED), "settings": (0, SETTINGS),
             "countries": (0, "Denmark\nFrance\n")}
    mod._run = _stub_run(calls)
    p = mod._status_payload()
    assert p["status"]["state"] == "connected"
    assert p["status"]["hostname"] == "us12980.nordvpn.com"
    assert p["status"]["city"] == "Denver"
    assert p["logged_in"] is True
    assert p["killswitch"] is True
    assert p["countries"] == ["Denmark", "France"]


def test_status_disconnected():
    mod = load()
    mod._run = _stub_run({"status": (0, STATUS_DISCONNECTED),
                          "settings": (0, SETTINGS), "countries": (0, "")})
    p = mod._status_payload()
    assert p["status"]["state"] == "disconnected"
    assert p["status"]["hostname"] == ""


def test_status_logged_out():
    mod = load()
    mod._run = _stub_run({"status": (0, STATUS_LOGGED_OUT),
                          "settings": (1, ""), "countries": (0, "")})
    p = mod._status_payload()
    assert p["logged_in"] is False


def test_countries_falls_back_to_cli(monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_api_get",
                        lambda path: (_ for _ in ()).throw(OSError("offline")))
    mod._run = _stub_run({"countries": (0, "Denmark\nFrance\n")})
    out = mod._api_countries()
    assert out["source"] == "cli"
    assert [c["name"] for c in out["countries"]] == ["Denmark", "France"]
    assert out["countries"][0]["cities"] == []


def test_country_validation():
    mod = load()
    assert mod._COUNTRY_OK.match("United_States")
    assert mod._COUNTRY_OK.match("Bosnia_And_Herzegovina")
    assert not mod._COUNTRY_OK.match("rm -rf /")
    assert not mod._COUNTRY_OK.match("--evil")


def test_server_shortname_validation():
    mod = load()
    assert mod._SERVER_OK.match("us12980")
    assert mod._SERVER_OK.match("jp35")
    assert not mod._SERVER_OK.match("US12980")
    assert not mod._SERVER_OK.match("us12980.nordvpn.com")
    assert not mod._SERVER_OK.match("-f")
