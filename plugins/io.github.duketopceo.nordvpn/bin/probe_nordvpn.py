#!/usr/bin/python3
"""Status + control probe for the NordVPN CLI (nordvpn-bin).

Verbs — exactly one JSON object on stdout, exit 0:

  status (default)
      {"ok": true, "cli": bool, "logged_in": bool,
       "status": {"state": "connected|disconnected|connecting",
                  "server","hostname","ip","country","city",
                  "technology","protocol","transfer","uptime": str},
       "killswitch": bool, "autoconnect": bool,
       "countries": [str, ...], "error": str|null}

  connect [country]   nordvpn connect [country]; empty = recommended
  disconnect          nordvpn disconnect
  killswitch on|off   nordvpn set killswitch on|off

Everything is bounded: absolute /usr/bin/nordvpn, fixed PATH, no shell,
per-call timeouts, single capped JSON on stdout. Country args are matched
against the fetched `nordvpn countries` list before use.
"""
import json
import os
import re
import signal
import subprocess
import sys
import urllib.request

NORDVPN = "/usr/bin/nordvpn"
OUT_MAX_BYTES = 24 * 1024
STATUS_TIMEOUT_S = 8.0
CONNECT_TIMEOUT_S = 35.0
JOB_DEADLINE_S = 45
API_BASE = "https://api.nordvpn.com/v1"
API_TIMEOUT_S = 8.0

_KV = re.compile(r"^\s*([A-Za-z][A-Za-z /-]*?)\s*:\s*(.*\S)\s*$")
_COUNTRY_OK = re.compile(r"^[A-Za-z_][A-Za-z_ .'-]{0,60}$")
_SERVER_OK = re.compile(r"^[a-z]{2}\d{1,5}$")


def _clean(value, limit=120):
    s = str(value if value is not None else "")
    s = "".join(" " if ord(c) < 32 or 127 <= ord(c) <= 159 else c for c in s)
    return s.strip()[:limit]


def _run(argv, timeout_s=8.0):
    """Bounded subprocess. Returns (returncode, stdout); (None, "") on
    timeout/missing binary/signal. HOME is the minimum nordvpn needs —
    without it the CLI fatals with 'cannot get user home dir'."""
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C",
           "HOME": os.path.expanduser("~"),
           "XDG_RUNTIME_DIR": "/run/user/%d" % os.getuid()}
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        env["DBUS_SESSION_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    try:
        out = subprocess.check_output(
            argv, stderr=subprocess.DEVNULL, env=env,
            timeout=timeout_s)
        return 0, out.decode("utf-8", "replace")
    except subprocess.CalledProcessError as e:
        return e.returncode, (e.output or b"").decode("utf-8", "replace")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, ""


def _kv(text):
    """Parse `nordvpn` "Key: value" lines into a lower-snake dict."""
    d = {}
    for line in text.splitlines():
        m = _KV.match(line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            d[key] = _clean(m.group(2), 160)
    return d


def _api_get(path):
    """One bounded GET to api.nordvpn.com; returns parsed JSON or raises."""
    req = urllib.request.Request(
        API_BASE + path,
        headers={"User-Agent": "omarchy-nordvpn-plugin/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as r:
        return json.loads(r.read(2 * 1024 * 1024).decode("utf-8", "replace"))


def _countries():
    rc, out = _run([NORDVPN, "countries"], STATUS_TIMEOUT_S)
    if rc != 0:
        return []
    names = []
    for line in out.splitlines():
        n = _clean(line, 60)
        if n and _COUNTRY_OK.match(n):
            names.append(n)
    return names[:200]


def _api_countries():
    """Country/city tree for the picker. Falls back to the CLI flat list —
    picker never goes empty offline."""
    try:
        raw = _api_get("/servers/countries")
        out = []
        for c in raw:
            cities = [{"name": _clean(x.get("name"), 60),
                       "dns_name": _clean(x.get("dns_name"), 60)}
                      for x in (c.get("cities") or [])]
            out.append({"id": c.get("id"), "name": _clean(c.get("name"), 60),
                        "code": _clean(c.get("code"), 4),
                        "serverCount": c.get("serverCount") or 0,
                        "cities": cities})
        out.sort(key=lambda x: x["name"])
        return {"countries": out, "source": "api"}
    except Exception:
        flat = [{"id": None, "name": n, "code": "", "serverCount": 0, "cities": []}
                for n in _countries()]
        return {"countries": flat, "source": "cli"}


def _api_servers(country_id):
    raw = _api_get("/servers/recommendations?filters[country_id]=%s&limit=8"
                   % int(country_id))
    out = []
    for s in raw:
        out.append({"hostname": _clean(s.get("hostname"), 80),
                    "name": _clean(s.get("name"), 80),
                    "load": s.get("load")})
    return out


def _cli_name(api_name):
    """API names use spaces ('United States'); the CLI canonical form uses
    underscores ('United_States')."""
    return str(api_name or "").strip().replace(" ", "_")


def _status_payload(countries=None):
    cli = os.path.exists(NORDVPN) or _run(["/usr/bin/which", "nordvpn"], 3)[0] == 0
    rc, out = _run([NORDVPN, "status"], STATUS_TIMEOUT_S)
    st = _kv(out)
    blob = (out or "").lower()

    state = "disconnected"
    for line in out.splitlines():
        if line.strip().lower().startswith("status:"):
            state = line.split(":", 1)[1].strip().lower() or "disconnected"
            break
    if "connecting" in blob:
        state = "connecting"

    logged_in = "not logged in" not in blob and "you're not logged" not in blob

    rc_s, sout = _run([NORDVPN, "settings"], STATUS_TIMEOUT_S)
    sets = _kv(sout) if rc_s == 0 else {}
    killswitch = sets.get("kill_switch", "").lower() == "enabled"
    autoconnect = sets.get("auto_connect", "").lower() == "enabled"

    if countries is None:
        countries = _countries()

    return {
        "ok": True,
        "cli": cli,
        "logged_in": logged_in,
        "status": {
            "state": state,
            "server": st.get("server", ""),
            "hostname": st.get("hostname", ""),
            "ip": st.get("ip", ""),
            "country": st.get("country", ""),
            "city": st.get("city", ""),
            "technology": st.get("current_technology", st.get("technology", "")),
            "protocol": st.get("current_protocol", st.get("protocol", "")),
            "transfer": st.get("transfer", ""),
            "uptime": st.get("uptime", ""),
        },
        "killswitch": killswitch,
        "autoconnect": autoconnect,
        "countries": countries,
        "error": None if cli else "nordvpn cli not found",
    }


def _with_status(verb_result=None, error=None):
    payload = _status_payload()
    if error:
        payload["error"] = error
    if verb_result is not None:
        payload["result"] = verb_result
    return payload


def _emit(obj):
    sys.stdout.write(json.dumps(obj)[:OUT_MAX_BYTES])
    sys.stdout.write("\n")


def _alarm(signum, frame):
    _emit({"ok": False, "error": "helper deadline exceeded"})
    sys.exit(0)


def main():
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(JOB_DEADLINE_S)

    args = [a for a in sys.argv[1:] if a]
    verb = args[0] if args else "status"

    if verb == "status":
        _emit(_status_payload())
        return

    if verb == "countries":
        _emit({"ok": True, **_api_countries()})
        return

    if verb == "servers":
        if len(args) < 2:
            _emit({"ok": False, "error": "servers needs a country_id"})
            return
        try:
            _emit({"ok": True, "servers": _api_servers(args[1])})
        except Exception:
            _emit({"ok": False, "error": "server list unavailable", "servers": []})
        return

    if verb == "connect":
        # Forms: connect | connect <server> | connect <country> | connect <country> <city>
        target1 = args[1] if len(args) > 1 else ""
        target2 = args[2] if len(args) > 2 else ""
        argv = [NORDVPN, "connect"]
        if target1:
            if _SERVER_OK.match(target1):
                argv.append(target1)                        # e.g. jp35
            elif _COUNTRY_OK.match(target1):
                argv.append(target1)                        # e.g. United_States
                if target2:
                    # city goes as its own argv element (no shell) — only
                    # reject flag-shaped or absurd input
                    if target2.startswith("-") or len(target2) > 80:
                        _emit({"ok": False, "error": "bad city: %s" % _clean(target2, 60)})
                        return
                    argv.append(target2)                    # e.g. Phoenix
            else:
                _emit({"ok": False, "error": "bad target: %s" % _clean(target1, 60)})
                return
        rc, out = _run(argv, CONNECT_TIMEOUT_S)
        if rc != 0:
            _emit({"ok": False, "error": "connect failed (rc=%s)" % rc,
                   "detail": _clean(out, 200)})
            return
        _emit(_with_status("connected"))

    elif verb == "disconnect":
        rc, out = _run([NORDVPN, "disconnect"], 15.0)
        if rc != 0:
            _emit({"ok": False, "error": "disconnect failed (rc=%s)" % rc,
                   "detail": _clean(out, 200)})
            return
        _emit(_with_status("disconnected"))

    elif verb == "killswitch":
        want = args[1] if len(args) > 1 else ""
        if want not in ("on", "off"):
            _emit({"ok": False, "error": "killswitch needs on|off"})
            return
        rc, out = _run([NORDVPN, "set", "killswitch", want], 15.0)
        if rc != 0:
            _emit({"ok": False, "error": "killswitch %s failed (rc=%s)" % (want, rc),
                   "detail": _clean(out, 200)})
            return
        _emit(_with_status("killswitch %s" % want))

    else:
        _emit({"ok": False, "error": "unknown verb: %s" % _clean(verb, 40)})


if __name__ == "__main__":
    main()
