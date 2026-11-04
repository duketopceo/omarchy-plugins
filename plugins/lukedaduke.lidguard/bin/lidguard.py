#!/usr/bin/env python3
"""lidguard — timed lid-close stay-awake via systemd-inhibit.

Arms a transient user unit that holds a `handle-lid-switch` block
inhibitor: while armed, closing the lid does nothing and agents keep
running. Expiry is recorded in a state file so `status` can report
remaining time.

Verbs:
    status              report current state
    arm <seconds|inf>   arm (or re-arm) the inhibitor
    disarm              release it now

Output: exactly one JSON object on stdout. Exit 0 on success, 2 on
bad arguments, 1 on control failure.
"""

import json
import os
import pwd
import subprocess
import sys
import time

UNIT = "lidguard.service"
SYSTEMD_RUN = "/usr/bin/systemd-run"
SYSTEMCTL = "/usr/bin/systemctl"
SYSTEMD_INHIBIT = "/usr/bin/systemd-inhibit"
SLEEP = "/usr/bin/sleep"

MAX_SECONDS = 7 * 24 * 3600


def _home() -> str:
    return os.environ.get("HOME") or pwd.getpwuid(os.getuid()).pw_dir


def _state_dir() -> str:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = xdg if xdg else os.path.join(_home(), ".local", "state")
    return os.path.join(base, "lidguard")


def _expiry_path() -> str:
    return os.path.join(_state_dir(), "expires")


def _bus_env() -> dict:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _home(),
        "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
        "LANG": "C",
        "LC_ALL": "C",
    }
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={env['XDG_RUNTIME_DIR']}/bus"
    return env


def _run(argv: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        env=_bus_env(),
        capture_output=True,
        text=True,
        timeout=15,
    )


def _unit_active() -> bool:
    proc = _run([SYSTEMCTL, "--user", "is-active", UNIT])
    return proc.returncode == 0 and proc.stdout.strip() in ("active", "activating")


def _read_expiry():
    try:
        raw = open(_expiry_path()).read().strip()
    except OSError:
        return None
    if raw == "inf":
        return "inf"
    try:
        return int(raw)
    except ValueError:
        return None


def _write_expiry(value) -> None:
    os.makedirs(_state_dir(), exist_ok=True)
    with open(_expiry_path(), "w") as fh:
        fh.write(str(value))


def _clear_expiry() -> None:
    try:
        os.unlink(_expiry_path())
    except OSError:
        pass


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")


def status() -> dict:
    active = _unit_active()
    exp = _read_expiry()
    armed = active
    remaining = None
    expires_at = None
    if active and isinstance(exp, int):
        expires_at = exp
        remaining = max(0, exp - int(time.time()))
    elif active and exp == "inf":
        remaining = -1  # armed, no expiry
    if not active:
        _clear_expiry()
    return {"ok": True, "armed": armed, "remaining_s": remaining,
            "expires_at": expires_at, "unit": UNIT}


def arm(seconds) -> dict:
    if seconds == "inf":
        dur = "infinity"
        exp = "inf"
        remaining = -1
        expires_at = None
    else:
        try:
            n = int(seconds)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"bad duration: {seconds!r}"}
        if n < 60 or n > MAX_SECONDS:
            return {"ok": False, "error": "duration out of range (60s..7d)"}
        dur = str(n)
        exp = int(time.time()) + n
        remaining = n
        expires_at = exp

    # --replace needs systemd v258+; stop-then-start works everywhere
    _run([SYSTEMCTL, "--user", "stop", UNIT])
    proc = _run([
        SYSTEMD_RUN, "--user",
        "--unit=lidguard",
        SYSTEMD_INHIBIT, "--what=handle-lid-switch",
        "--who=lidguard", "--why=lid-close stay-awake",
        SLEEP, dur,
    ])
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout).strip()[:300]}

    _write_expiry(exp)
    return {"ok": True, "armed": True, "remaining_s": remaining,
            "expires_at": expires_at, "unit": UNIT}


def disarm() -> dict:
    proc = _run([SYSTEMCTL, "--user", "stop", UNIT])
    _clear_expiry()
    if proc.returncode != 0 and "not loaded" not in (proc.stderr or "").lower():
        return {"ok": False, "armed": False,
                "error": (proc.stderr or proc.stdout).strip()[:300]}
    return {"ok": True, "armed": False, "unit": UNIT}


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        _emit(status())
        return 0
    verb = argv[0]
    if verb == "status":
        _emit(status())
        return 0
    if verb == "arm" and len(argv) == 2:
        out = arm(argv[1])
        _emit(out)
        return 0 if out.get("ok") else 1
    if verb == "disarm":
        out = disarm()
        _emit(out)
        return 0 if out.get("ok") else 1
    _emit({"ok": False, "error": f"usage: {os.path.basename(__file__)} "
                                 "[status|arm <seconds|inf>|disarm]"})
    return 2


if __name__ == "__main__":
    sys.exit(main())
