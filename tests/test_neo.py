from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/io.github.duketopceo.neo/bin/probe_neo.py"


def load():
    spec = importlib.util.spec_from_file_location("probe_neo", PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


SHOW_OUT = """\
Id=browserclaw-chromium.service
ActiveState=active
SubState=running
MainPID=1234

Id=browserclaw-shim.service
ActiveState=inactive
SubState=dead
MainPID=0

Id=browserclaw-server.service
ActiveState=active
SubState=running
MainPID=5678
"""


def test_unit_states_parses_show_output():
    mod = load()
    mod._run = lambda argv, **kw: SHOW_OUT
    st = mod._unit_states()
    assert st["chromium"] == {"active": True, "sub": "running", "pid": 1234}
    assert st["shim"] == {"active": False, "sub": "dead", "pid": 0}
    assert st["server"]["pid"] == 5678


def test_unit_states_survive_systemctl_failure():
    mod = load()
    mod._run = lambda argv, **kw: None
    st = mod._unit_states()
    assert all(v["active"] is False for v in st.values())
    assert set(st) == {"chromium", "shim", "server"}


def test_listening_ports_shape():
    mod = load()
    ports = mod._listening_ports()
    assert set(ports) == {"9211", "49337", "49338"}
    assert all(isinstance(v, bool) for v in ports.values())


def test_status_payload_is_bounded_and_typed(monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_unit_states", lambda: {
        "chromium": {"active": True, "sub": "running", "pid": 1},
        "shim": {"active": True, "sub": "running", "pid": 2},
        "server": {"active": True, "sub": "running", "pid": 3}})
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": True, "49337": True, "49338": True})
    monkeypatch.setattr(mod, "_mcp_health",
                        lambda: (True, "browseros-neo", "0.0.60"))
    data = mod._status()
    assert data["ok"] is True
    assert data["mcp"]["server"] == "browseros-neo"
    assert data["endpoint"].endswith("/mcp")
    json.dumps(data)


def test_status_skips_mcp_when_asked(monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_unit_states", lambda: {k: {"active": False,
        "sub": "dead", "pid": 0} for k in mod.UNITS})
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": False, "49337": False, "49338": False})

    def _boom():
        raise AssertionError("mcp check must be skipped")
    monkeypatch.setattr(mod, "_mcp_health", _boom)
    data = mod._status(check_mcp=False)
    assert data["mcp"]["up"] is False


def test_control_rejects_bad_verb_and_bounds_calls(monkeypatch):
    mod = load()
    bad = mod._control("shellcode")
    assert bad["ok"] is False and bad["error"] == "bad_verb"

    calls = []
    monkeypatch.setattr(mod, "_run",
                        lambda argv, **kw: calls.append(list(argv)) or "")
    monkeypatch.setattr(mod, "_unit_states",
                        lambda: {k: {"active": True, "sub": "running", "pid": 1}
                                 for k in mod.UNITS})
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": True, "49337": True, "49338": True})
    ok = mod._control("restart")
    assert ok["ok"] is True
    assert calls == [["/usr/bin/systemctl", "--user", "restart",
                      "browserclaw-chromium", "browserclaw-shim",
                      "browserclaw-server"]]
    assert ok["status"]["units"]["server"]["active"] is True
