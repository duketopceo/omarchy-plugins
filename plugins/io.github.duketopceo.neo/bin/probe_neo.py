#!/usr/bin/python3
"""Status + control probe for the local BrowserOS neo sidecar.

The sidecar is three systemd user units on this machine:

  browserclaw-chromium  headless stock chromium, CDP :49337, only the
                        browserclaw extension allowed (Omarchy force-installs
                        1Password into every profile via
                        /usr/share/chromium/extensions — that extension
                        deadlocks fresh-profile navigation)
  browserclaw-shim      CDP compat shim :49338 (numeric tab ids, isHidden,
                        open-queueing)
  browserclaw-server    browseros-claw-server :9211, MCP at /mcp

Verbs — exactly one JSON object on stdout, exit 0:

  status (default)
      {"ok": true, "units": {"chromium": {"active","sub","pid"},
        "shim": {...}, "server": {...}},
       "ports": {"9211": bool, "49337": bool, "49338": bool},
       "mcp": {"up": bool, "server": str|null, "version": str|null},
       "endpoint": "http://127.0.0.1:9211/mcp", "error": str|null}

  start | stop | restart
      systemctl --user <verb> on all three units, then a status payload
      shaped like above (mcp check skipped on stop — nothing to probe).

Everything is bounded: one `systemctl show` call, one /proc/net/tcp read,
one 3s MCP initialize. Unit control uses absolute /usr/bin/systemctl under
the same hard deadline. Helper output stays small — the panel parses it.
"""
import json
import os
import signal
import subprocess
import sys
import urllib.request

JOB_DEADLINE_S = 45   # control verbs can wait out a unit's TimeoutStopSec
SYSTEMCTL_TIMEOUT_S = 35
SYSTEMCTL = "/usr/bin/systemctl"
UNITS = {  # display key -> unit name
    "chromium": "browserclaw-chromium",
    "shim": "browserclaw-shim",
    "server": "browserclaw-server",
}
PORTS = {"9211": 9211, "49337": 49337, "49338": 49338}
ENDPOINT = "http://127.0.0.1:9211/mcp"
MCP_TIMEOUT_S = 3.0
OUT_MAX_BYTES = 8 * 1024

_INIT_BODY = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "omarchy-neo-panel", "version": "0.1.0"},
    },
}).encode()


def _clean(value, limit=120):
    s = str(value if value is not None else "")
    s = "".join(" " if ord(c) < 32 or 127 <= ord(c) <= 159 else c for c in s)
    return s.strip()[:limit]


def _run(argv, timeout_s=8.0, max_bytes=65536):
    """Bounded subprocess — absolute binary, fixed PATH, no shell.
    XDG_RUNTIME_DIR is the minimum systemctl --user needs to find the
    caller's own user bus (honours DBUS_SESSION_BUS_ADDRESS too when set)."""
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C",
           "XDG_RUNTIME_DIR": "/run/user/%d" % os.getuid()}
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        env["DBUS_SESSION_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    try:
        p = subprocess.run(
            argv, timeout=timeout_s, capture_output=True, env=env,
        )
    except Exception:
        return None
    return p.stdout[:max_bytes].decode("utf-8", errors="replace")


def _unit_states():
    """One `systemctl show` for all three units -> {key: {active,sub,pid}}."""
    out = _run([SYSTEMCTL, "--user", "show",
                "-p", "Id,ActiveState,SubState,MainPID",
                *[UNITS[k] for k in UNITS]])
    states = {k: {"active": False, "sub": "unknown", "pid": 0}
              for k in UNITS}
    if out is None:
        return states
    by_name = {v: k for k, v in UNITS.items()}
    cur = None
    for line in out.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key == "Id":
            name = val[:-len(".service")] if val.endswith(".service") else val
            cur = states.get(by_name.get(name, ""))
        elif cur is not None:
            if key == "ActiveState":
                cur["active"] = val == "active"
                cur["sub"] = val
            elif key == "SubState":
                cur["sub"] = val
            elif key == "MainPID":
                try:
                    cur["pid"] = max(0, int(val))
                except ValueError:
                    cur["pid"] = 0
    return states


def _listening_ports():
    """Which of the sidecar ports hold a LISTEN socket — /proc/net/tcp{,6},
    no exec. Loopback shows as 0100007F:XXXX / 0000...0001:XXXX."""
    listening = set()
    for procfile in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(procfile, "r") as f:
                next(f, None)
                for line in f:
                    cols = line.split()
                    if len(cols) < 4 or cols[3] != "0A":
                        continue
                    try:
                        listening.add(int(cols[1].rsplit(":", 1)[1], 16))
                    except (ValueError, IndexError):
                        continue
        except OSError:
            continue
    return {k: (port in listening) for k, port in PORTS.items()}


def _mcp_health():
    """POST initialize to the MCP endpoint -> (up, server_name, version).

    Loopback, 3s, read-only. A 200 with serverInfo is the truth test —
    a bound socket alone can belong to a wedged process.
    """
    req = urllib.request.Request(
        ENDPOINT, data=_INIT_BODY, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
    try:
        with urllib.request.urlopen(req, timeout=MCP_TIMEOUT_S) as resp:
            blob = resp.read(64 * 1024).decode("utf-8", errors="replace")
    except Exception:
        return False, None, None
    # MCP answers initialize as JSON or an SSE frame — find serverInfo either
    # way without a full SSE parse.
    for line in blob.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if "serverInfo" not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        info = (obj.get("result") or {}).get("serverInfo") or {}
        if isinstance(info, dict) and info:
            return True, _clean(info.get("name"), 64), _clean(
                info.get("version"), 32)
        return True, None, None
    return False, None, None


def _status(check_mcp=True):
    units = _unit_states()
    ports = _listening_ports()
    mcp_up, mcp_name, mcp_ver = _mcp_health() if check_mcp \
        else (False, None, None)
    return {
        "ok": True,
        "units": units,
        "ports": ports,
        "mcp": {"up": mcp_up, "server": mcp_name, "version": mcp_ver},
        "endpoint": ENDPOINT,
        "error": None,
    }


def _control(verb):
    """systemctl --user <verb> all three units -> {"ok","action","error"}."""
    if verb not in ("start", "stop", "restart"):
        return {"ok": False, "action": verb, "error": "bad_verb"}
    out = _run([SYSTEMCTL, "--user", verb, *UNITS.values()],
               timeout_s=SYSTEMCTL_TIMEOUT_S)
    ok = out is not None
    payload = {"ok": ok, "action": verb,
               "error": None if ok else "systemctl_failed"}
    # MCP health is checked on the next regular status poll — right after a
    # unit transition it would flap for a second or two anyway.
    payload["status"] = _status(check_mcp=False)
    return payload


def main():
    try:
        os.setsid()
    except OSError:
        pass
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)

    verb = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        payload = (_control(verb) if verb in ("start", "stop", "restart")
                   else _status())
    except Exception as exc:
        payload = {"ok": False, "error": "internal: " + _clean(exc, 120)}
    sys.stdout.write(json.dumps(payload)[:OUT_MAX_BYTES] + "\n")


if __name__ == "__main__":
    main()
