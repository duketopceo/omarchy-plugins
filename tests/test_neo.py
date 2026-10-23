from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/io.github.duketopceo.neo/bin/probe_neo.py"
PUBLISH = ROOT / "scripts" / "publish.sh"


def load():
    spec = importlib.util.spec_from_file_location("probe_neo", PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


SHOW_OUT = """\
Id=browserclaw-chromium.service
LoadState=loaded
ActiveState=active
SubState=running
MainPID=1234

Id=browserclaw-shim.service
LoadState=loaded
ActiveState=inactive
SubState=dead
MainPID=0

Id=browserclaw-server.service
LoadState=loaded
ActiveState=active
SubState=running
MainPID=5678
"""

SHOW_NOT_FOUND = """\
Id=browserclaw-chromium.service
LoadState=not-found
ActiveState=inactive
SubState=dead
MainPID=0

Id=browserclaw-shim.service
LoadState=not-found
ActiveState=inactive
SubState=dead
MainPID=0

Id=browserclaw-server.service
LoadState=not-found
ActiveState=inactive
SubState=dead
MainPID=0
"""


def test_unit_states_parses_show_output():
    mod = load()
    mod._run = lambda argv, **kw: (0, SHOW_OUT)
    st, ok = mod._unit_states()
    assert ok is True
    assert st["chromium"] == {
        "active": True, "sub": "running", "pid": 1234,
        "load_state": "loaded", "loaded": True}
    assert st["shim"] == {
        "active": False, "sub": "dead", "pid": 0,
        "load_state": "loaded", "loaded": True}
    assert st["server"]["pid"] == 5678
    assert st["server"]["loaded"] is True
    assert st["server"]["load_state"] == "loaded"


def test_unit_states_survive_systemctl_failure():
    mod = load()
    mod._run = lambda argv, **kw: (None, "")
    st, ok = mod._unit_states()
    assert ok is False
    assert all(v["active"] is False for v in st.values())
    assert all(v["loaded"] is False for v in st.values())
    assert all(v["load_state"] is None for v in st.values())
    assert set(st) == {"chromium", "shim", "server"}


def test_unit_states_nonzero_rc_is_not_success():
    mod = load()
    # Nonzero rc with empty/partial output must not count as a successful show.
    mod._run = lambda argv, **kw: (1, "")
    st, ok = mod._unit_states()
    assert ok is False
    assert all(v["load_state"] is None for v in st.values())
    assert mod._sidecar_present(st, ok) is True


def test_listening_ports_shape():
    mod = load()
    ports = mod._listening_ports()
    assert set(ports) == {"9211", "49337", "49338"}
    assert all(isinstance(v, bool) for v in ports.values())


def test_status_payload_is_bounded_and_typed(monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_unit_states", lambda: ({
        "chromium": {"active": True, "sub": "running", "pid": 1, "loaded": True},
        "shim": {"active": True, "sub": "running", "pid": 2, "loaded": True},
        "server": {"active": True, "sub": "running", "pid": 3, "loaded": True}},
        True))
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": True, "49337": True, "49338": True})
    monkeypatch.setattr(mod, "_mcp_health",
                        lambda: (True, "browseros-neo", "0.0.60"))
    monkeypatch.setattr(mod, "_tab_count", lambda: 3)
    data = mod._status()
    assert data["ok"] is True
    assert data["mcp"]["server"] == "browseros-neo"
    assert data["tabs"] == 3
    assert data["endpoint"].endswith("/mcp")
    assert data["capabilities"]["sidecar"] is True
    json.dumps(data)


def test_status_skips_mcp_when_asked(monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_unit_states", lambda: ({
        k: {"active": False, "sub": "dead", "pid": 0, "loaded": True}
        for k in mod.UNITS}, True))
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": False, "49337": False, "49338": False})

    def _boom():
        raise AssertionError("mcp check must be skipped")
    monkeypatch.setattr(mod, "_mcp_health", _boom)
    monkeypatch.setattr(mod, "_tab_count", lambda: None)
    data = mod._status(check_mcp=False)
    assert data["mcp"]["up"] is False
    assert data["tabs"] is None
    assert data["capabilities"]["sidecar"] is True


def test_status_sidecar_false_when_units_not_found(monkeypatch):
    mod = load()
    mod._run = lambda argv, **kw: (0, SHOW_NOT_FOUND)

    def _boom_ports():
        raise AssertionError("ports must be skipped when sidecar absent")
    def _boom_mcp():
        raise AssertionError("mcp must be skipped when sidecar absent")
    def _boom_tabs():
        raise AssertionError("tabs must be skipped when sidecar absent")
    monkeypatch.setattr(mod, "_listening_ports", _boom_ports)
    monkeypatch.setattr(mod, "_mcp_health", _boom_mcp)
    monkeypatch.setattr(mod, "_tab_count", _boom_tabs)
    data = mod._status()
    assert data["capabilities"]["sidecar"] is False
    assert data["ports"] == {"9211": False, "49337": False, "49338": False}
    assert data["tabs"] is None
    assert data["endpoint"] == mod.ENDPOINT
    assert all(u["load_state"] == "not-found" for u in data["units"].values())


def test_status_sidecar_true_when_systemctl_fails(monkeypatch):
    mod = load()
    mod._run = lambda argv, **kw: (None, "")
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": False, "49337": False, "49338": False})
    monkeypatch.setattr(mod, "_mcp_health", lambda: (False, None, None))
    monkeypatch.setattr(mod, "_tab_count", lambda: None)
    data = mod._status()
    assert data["capabilities"]["sidecar"] is True


def test_sidecar_present_true_for_masked_or_error_units():
    mod = load()
    # All units exist but are masked — not "absent".
    masked = {k: {"active": False, "sub": "dead", "pid": 0,
                  "load_state": "masked", "loaded": False}
              for k in mod.UNITS}
    assert mod._sidecar_present(masked, True) is True
    errored = {k: {"active": False, "sub": "dead", "pid": 0,
                   "load_state": "error", "loaded": False}
               for k in mod.UNITS}
    assert mod._sidecar_present(errored, True) is True
    # Missing LoadState after a "successful" parse must not hide either.
    missing = {k: {"active": False, "sub": "unknown", "pid": 0,
                   "load_state": None, "loaded": False}
               for k in mod.UNITS}
    assert mod._sidecar_present(missing, True) is True


def test_sidecar_present_false_only_when_all_explicitly_not_found():
    mod = load()
    absent = {k: {"active": False, "sub": "dead", "pid": 0,
                  "load_state": "not-found", "loaded": False}
              for k in mod.UNITS}
    assert mod._sidecar_present(absent, True) is False
    # One loaded unit among not-found → still present.
    mixed = dict(absent)
    mixed["server"] = {"active": True, "sub": "running", "pid": 1,
                       "load_state": "loaded", "loaded": True}
    assert mod._sidecar_present(mixed, True) is True


def test_control_rejects_bad_verb_and_bounds_calls(monkeypatch):
    mod = load()
    bad = mod._control("shellcode")
    assert bad["ok"] is False and bad["error"] == "bad_verb"

    calls = []
    monkeypatch.setattr(mod, "_run",
                        lambda argv, **kw: (0, calls.append(list(argv)) or ""))
    monkeypatch.setattr(mod, "_unit_states",
                        lambda: ({k: {"active": True, "sub": "running",
                                      "pid": 1, "loaded": True}
                                  for k in mod.UNITS}, True))
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": True, "49337": True, "49338": True})
    # The post-control status pass would otherwise hit 127.0.0.1:49338.
    monkeypatch.setattr(mod, "_tab_count", lambda: 3)
    ok = mod._control("restart")
    assert ok["ok"] is True
    assert calls == [["/usr/bin/systemctl", "--user", "restart",
                      "browserclaw-chromium", "browserclaw-shim",
                      "browserclaw-server"]]
    assert ok["status"]["units"]["server"]["active"] is True
    assert ok["status"]["capabilities"]["sidecar"] is True


def test_control_reports_nonzero_systemctl(monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_run", lambda argv, **kw: (1, "Failed."))
    monkeypatch.setattr(mod, "_unit_states",
                        lambda: ({k: {"active": False, "sub": "dead",
                                      "pid": 0, "loaded": True}
                                  for k in mod.UNITS}, True))
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": False, "49337": False, "49338": False})
    res = mod._control("restart")
    assert res["ok"] is False and res["error"] == "systemctl_failed"
    assert res["action"] == "restart"
    # exec failure (timeout/missing binary) is also a control failure
    monkeypatch.setattr(mod, "_run", lambda argv, **kw: (None, ""))
    res = mod._control("restart")
    assert res["ok"] is False and res["error"] == "systemctl_failed"


def _fake_urlopen(payload, fail=False):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    def _open(req, timeout=None):
        if fail:
            raise OSError("conn refused")
        return _Resp(payload if isinstance(payload, bytes)
                     else json.dumps(payload).encode())
    return _open


def test_tab_count_pages_only(monkeypatch):
    mod = load()
    targets = [
        {"type": "page", "url": "https://a"},
        {"type": "page", "url": "https://b"},
        {"type": "service_worker", "url": "chrome://sw"},
        {"type": "background_page", "url": "chrome://ext"},
    ]
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(targets))
    assert mod._tab_count() == 2


def test_tab_count_failure_and_shape(monkeypatch):
    mod = load()
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(None, fail=True))
    assert mod._tab_count() is None
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen({"not": "a list"}))
    assert mod._tab_count() is None


def test_control_per_unit_restart(monkeypatch):
    mod = load()
    calls = []
    monkeypatch.setattr(mod, "_run",
                        lambda argv, **kw: (0, calls.append(list(argv)) or ""))
    monkeypatch.setattr(mod, "_unit_states",
                        lambda: ({k: {"active": True, "sub": "running",
                                      "pid": 1, "loaded": True}
                                  for k in mod.UNITS}, True))
    monkeypatch.setattr(mod, "_listening_ports",
                        lambda: {"9211": True, "49337": True, "49338": True})
    # The post-control status pass would otherwise hit 127.0.0.1:49338.
    monkeypatch.setattr(mod, "_tab_count", lambda: 3)
    res = mod._control("restart", "shim")
    assert res["ok"] is True
    assert res["action"] == "restart:shim"
    assert calls == [["/usr/bin/systemctl", "--user", "restart",
                      "browserclaw-shim"]]


def test_control_rejects_bad_unit(monkeypatch):
    mod = load()
    def _no_run(argv, **kw):
        raise AssertionError("_run must not be called for a bad unit")
    monkeypatch.setattr(mod, "_run", _no_run)
    res = mod._control("restart", "bogus")
    assert res["ok"] is False and res["error"] == "bad_unit"


def test_catalog_marks_neo_local_only():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    neo = next(p for p in catalog["plugins"] if p["id"] == "io.github.duketopceo.neo")
    assert neo["localOnly"] is True
    assert neo.get("repo") in (None, "")


def test_publish_script_excludes_neo_and_retired_ids():
    text = PUBLISH.read_text()
    assert "omarchy-neo" not in text
    assert "io.github.duketopceo.neo" not in text
    for retired in ("lukedaduke.ticker", "lukedaduke.agents", "lukedaduke.connections"):
        assert f"[{retired}]" not in text
    # resolve neo must fail
    script = (
        f'source "{PUBLISH}"; '
        'if resolve neo >/dev/null 2>&1; then exit 1; else exit 0; fi'
    )
    completed = subprocess.run(["bash", "-c", script], check=False)
    assert completed.returncode == 0


def test_panel_hides_on_absent_sidecar_and_reads_endpoint():
    panel = (ROOT / "plugins/io.github.duketopceo.neo/Panel.qml").read_text()
    assert "visible: root.sidecarPresent" in panel
    assert "property string endpoint: \"\"" in panel
    assert "caps.sidecar === false" in panel
    assert "statusTimer.stop()" in panel
