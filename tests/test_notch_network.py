"""Network.js for the notch island (Tailscale + NordVPN), run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NET = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Network.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const N=require({json.dumps(str(NET))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def ts_status(state="Running", peers=None, auth=""):
    return json.dumps({
        "BackendState": state,
        "AuthURL": auth,
        "Self": {"HostName": "laptop", "DNSName": "laptop.example.ts.net.", "TailscaleIPs": ["100.64.0.1", "fd7a:115c:a1e0::1"]},
        "Peer": peers if peers is not None else {
            "a": {"HostName": "zeta", "DNSName": "zeta.example.ts.net.", "Online": False, "OS": "linux", "TailscaleIPs": ["100.64.0.9"]},
            "b": {"HostName": "alpha", "DNSName": "alpha.example.ts.net.", "Online": True, "OS": "macOS", "TailscaleIPs": ["fd7a::2", "100.64.0.2"]},
            "c": {"HostName": "us-nyc-wg-1", "DNSName": "us-nyc-wg-1.mullvad.ts.net.", "Online": True, "TailscaleIPs": ["100.64.0.3"]},
            "d": {"HostName": "localhost", "DNSName": "phone.example.ts.net.", "Online": True, "TailscaleIPs": ["100.64.0.4"]},
        },
    })


def test_tailscale_running_with_peers_sorted_online_first():
    t = run(f"N.parseTailscale({json.dumps(ts_status())})")
    assert t["ok"] and t["running"] and t["state"] == "running"
    assert t["selfName"] == "laptop" and t["selfIp"] == "100.64.0.1"
    assert [p["name"] for p in t["peers"]] == ["alpha", "phone", "zeta"]  # mullvad hidden, localhost -> dns name
    assert [p["online"] for p in t["peers"]] == [True, True, False]
    assert t["peers"][0]["ip"] == "100.64.0.2"  # first IPv4
    assert t["onlineCount"] == 2 and t["peerCount"] == 3


@pytest.mark.parametrize("backend,state", [("Stopped", "stopped"), ("NeedsLogin", "needslogin"), ("Starting", "starting"), ("NoState", "unavailable")])
def test_tailscale_states(backend, state):
    t = run(f"N.parseTailscale({json.dumps(ts_status(backend, {}))})")
    assert t["state"] == state and t["running"] is (state == "running")


def test_tailscale_junk_is_unavailable():
    for text in ("", "nope", "[]", "{}", "null"):
        t = run(f"N.parseTailscale({json.dumps(text)})")
        assert t["ok"] is False and t["state"] == "unavailable" and t["peers"] == []


def test_light_poll_keeps_previous_peers():
    full = run(f"N.parseTailscale({json.dumps(ts_status())})")
    light = f"N.parseTailscale({json.dumps(ts_status(peers={}))})"
    merged = run(f"N.mergePeers({json.dumps(full)},{light})")
    assert merged["peerCount"] == 3 and len(merged["peers"]) == 3
    # A stopped tailnet does not keep stale peers.
    stopped = f"N.parseTailscale({json.dumps(ts_status('Stopped', {}))})"
    assert run(f"N.mergePeers({json.dumps(full)},{stopped})")["peers"] == []


def test_tailscale_commands_are_absolute_and_toggle():
    assert run("N.tailscaleStatusArgs(true)") == ["/usr/bin/tailscale", "status", "--json"]
    assert run("N.tailscaleStatusArgs(false)")[-1] == "--peers=false"
    on = run(f"N.tailscaleToggleCommand(N.parseTailscale({json.dumps(ts_status())}))")
    off = run(f"N.tailscaleToggleCommand(N.parseTailscale({json.dumps(ts_status('Stopped', {}))}))")
    assert on == ["/usr/bin/tailscale", "down"] and off == ["/usr/bin/tailscale", "up"]
    assert run(f"N.tailscaleToggleCommand(N.parseTailscale({json.dumps(ts_status('NeedsLogin', {}))}))") is None
    assert run("N.tailscaleToggleCommand(N.parseTailscale(''))") is None


def nord(state="connected", **kw):
    status = {"state": state, "server": "", "hostname": "xx1.example.test", "country": "United_States", "city": "New_York"}
    status.update(kw)
    return json.dumps({"ok": True, "cli": True, "logged_in": True, "status": status})


def test_nord_parse_and_toggle():
    n = run(f"N.parseNord({json.dumps(nord())})")
    assert n["ok"] and n["state"] == "connected" and n["country"] == "United States" and n["detail"] == "United States, New York"
    assert n["server"] == "xx1.example.test"
    assert run(f"N.nordToggleVerb(N.parseNord({json.dumps(nord())}))") == "disconnect"
    assert run(f"N.nordToggleVerb(N.parseNord({json.dumps(nord('disconnected'))}))") == "connect"
    assert run(f"N.nordToggleVerb(N.parseNord({json.dumps(nord('connecting'))}))") == "disconnect"


def test_nord_unavailable_cases():
    for text in ("", "junk", json.dumps({"cli": False}), json.dumps({"cli": True, "logged_in": False, "status": {"state": "connected"}}),
                 json.dumps({"cli": True, "logged_in": True, "status": {"state": "weird"}})):
        n = run(f"N.parseNord({json.dumps(text)})")
        assert n["ok"] is False and n["state"] == "unavailable"
        assert run(f"N.nordToggleVerb(N.parseNord({json.dumps(text)}))") is None


def test_nord_args_use_absolute_paths_and_only_known_verbs():
    a = run("N.nordArgs('/home/x','connect')")
    assert a[0] == "/usr/bin/python3" and a[1] == "/home/x/.config/omarchy/plugins/io.github.duketopceo.nordvpn/bin/probe_nordvpn.py" and a[2] == "connect"
    assert run("N.nordArgs('/home/x','killswitch')")[2] == "status"
    assert run("N.nordArgs('/home/x')")[2] == "status"


def test_idle_dot_and_summaries():
    on = f"N.parseTailscale({json.dumps(ts_status())})"
    off = f"N.parseTailscale({json.dumps(ts_status('Stopped', {}))})"
    nd = f"N.parseNord({json.dumps(nord())})"
    nc = f"N.parseNord({json.dumps(nord('connecting'))})"
    nx = "N.parseNord('')"
    assert run(f"N.idleDot({on},{nx})") == "on"
    assert run(f"N.idleDot({off},{nd})") == "on"
    assert run(f"N.idleDot({off},{nc})") == "busy"
    assert run(f"N.idleDot({off},{nx})") == ""
    assert run(f"N.tailscaleSummary({on})") == "2 of 3 online"
    assert run(f"N.tailscaleSummary({off})") == "Off"
    assert run(f"N.nordSummary({nd})") == "Connected" and run(f"N.nordSummary({nx})") == "Unavailable"
