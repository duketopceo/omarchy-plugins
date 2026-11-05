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


# ---- v4: redesigned tab ----------------------------------------------------

def ts_v4():
    return json.dumps({
        "BackendState": "Running",
        "Self": {"HostName": "laptop", "DNSName": "laptop.example.ts.net.", "TailscaleIPs": ["100.64.0.1"]},
        "Peer": {
            "a": {"HostName": "old-box", "DNSName": "old-box.example.ts.net.", "Online": False, "OS": "windows", "TailscaleIPs": ["100.64.0.9"], "LastSeen": "2026-11-01T00:00:00Z"},
            "b": {"HostName": "zed", "DNSName": "zed.example.ts.net.", "Online": True, "OS": "iOS", "TailscaleIPs": ["100.64.0.2"], "LastSeen": "0001-01-01T00:00:00Z"},
            "c": {"HostName": "relay", "DNSName": "relay.example.ts.net.", "Online": True, "OS": "linux", "TailscaleIPs": ["100.64.0.3"], "ExitNodeOption": True, "ExitNode": True},
            "d": {"HostName": "mac", "DNSName": "mac.example.ts.net.", "Online": True, "OS": "macOS", "TailscaleIPs": ["100.64.0.4"]},
        },
    })


def test_v4_tailscale_dns_exit_and_order():
    t = run(f"N.parseTailscale({json.dumps(ts_v4())})")
    assert t["selfDns"] == "laptop.example.ts.net"
    assert [p["name"] for p in t["peers"]] == ["mac", "relay", "zed", "old-box"]
    assert t["exitNode"] == {"name": "relay", "ip": "100.64.0.3"}
    assert [p["name"] for p in t["exitOptions"]] == ["relay"]


def test_os_icons():
    for os_name, label in [("linux", "Linux"), ("macOS", "macOS"), ("darwin", "macOS"), ("iOS", "iOS"), ("windows", "Windows"), ("android", "Android"), ("", "Device"), ("plan9", "Device")]:
        assert run(f"N.osIcon({json.dumps(os_name)})")["label"] == label
    assert run("N.osIcon('linux').glyph") != run("N.osIcon('windows').glyph")


def test_filter_and_last_seen():
    t = run(f"N.parseTailscale({json.dumps(ts_v4())})")
    assert [p["name"] for p in run(f"N.filterPeers({json.dumps(t['peers'])},'  MAC ')")] == ["mac"]
    assert len(run(f"N.filterPeers({json.dumps(t['peers'])},'100.64.0.')")) == 4
    assert run(f"N.filterPeers({json.dumps(t['peers'])},'')") == t["peers"]
    now = "Date.parse('2026-11-04T00:00:00Z')"
    assert run(f"N.relTime('2026-11-03T22:00:00Z',{now})") == "2h ago"
    assert run(f"N.relTime('2026-11-01T00:00:00Z',{now})") == "3d ago"
    assert run(f"N.relTime('0001-01-01T00:00:00Z',{now})") == ""
    assert run(f"N.peerStatus({json.dumps(t['peers'][3])},{now})") == "3d ago"


def test_exit_node_feasibility_and_args():
    assert run("N.exitNodeFeasible('{\"OperatorUser\":\"luke\"}','luke')") is True
    assert run("N.exitNodeFeasible('{\"OperatorUser\":\"\"}','luke')") is False
    assert run("N.exitNodeFeasible('junk','luke')") is False
    assert run("N.exitNodeNote(true)") == "" and "operator" in run("N.exitNodeNote(false)")
    assert run("N.exitNodeArgs('100.64.0.3')") == ["/usr/bin/tailscale", "set", "--exit-node=100.64.0.3"]
    assert run("N.exitNodeArgs('x; rm -rf')") == ["/usr/bin/tailscale", "set", "--exit-node="]


def test_parse_nord_text():
    text = "Status: Connected\nServer: Canada #1\nHostname: ca1.example.test\nIP: 100.64.9.9\nCountry: Canada\nCity: Calgary\nProtocol: NordLynx\nTransfer: 1 KiB received, 2 KiB sent\nUptime: 5 minutes 3 seconds\n"
    n = run(f"N.parseNordText({json.dumps(text)})")
    assert n["ok"] and n["state"] == "connected" and n["hostname"] == "ca1.example.test"
    assert n["ip"] == "100.64.9.9" and n["country"] == "Canada" and n["uptime"] == "5 minutes 3 seconds"
    off = run("N.parseNordText('Status: Disconnected\\n')")
    assert off["ok"] and off["state"] == "disconnected" and off["ip"] == ""
    assert run("N.parseNordText('Please log in')")["ok"] is False


def test_parse_countries_and_favorites():
    c = run("N.parseCountries('Canada\\nUnited_States\\tChile, Canada\\n--bad--')")
    assert [x["id"] for x in c] == ["Canada", "Chile", "United_States"]
    assert c[2]["label"] == "United States"
    assert run("N.cleanFavorites(null)") == ["United_States", "Canada", "Netherlands", "Switzerland"]
    assert run("N.cleanFavorites(['Japan','Japan','bad name!'])") == ["Japan"]
    assert run("N.toggleFavorite(['Canada'],'Japan')") == ["Canada", "Japan"]
    assert run("N.toggleFavorite(['Canada','Japan'],'Canada')") == ["Japan"]
    assert run("N.favoriteLabel('United_States')") == "US" and run("N.favoriteLabel('Chile')") == "Chile"


def test_nord_connect_args_validate_country():
    a = run("N.nordConnectArgs('/home/x','Canada')")
    assert a[-2:] == ["connect", "Canada"] and a[0] == "/usr/bin/python3"
    assert run("N.nordConnectArgs('/home/x','a; b')")[-1] == "connect"
    assert run("N.nordConnectArgs('/home/x','')")[-1] == "connect"
    assert run("N.nordStatusArgs()") == ["/usr/bin/nordvpn", "status"]
