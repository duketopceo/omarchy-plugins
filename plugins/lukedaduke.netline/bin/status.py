#!/usr/bin/env python3
"""netline widget backend — the small JSON surface the bar widget calls.

Kept separate from netline.py so the daemon stays untouched by UI concerns.
Every command prints one JSON object and exits 0, even on error, so the QML
side never has to distinguish "crashed" from "nothing to report".
"""
import json
import os
import sqlite3
import sys
import time

# The store lives beside the daemon by default; NETLINE_DB overrides it.
# Deriving it keeps the plugin installable on a machine whose home directory
# is not this one.
_STATE = os.environ.get("NETLINE_STATE") or os.path.expanduser(
    "~/.local/share/netline")
DB = os.environ.get("NETLINE_DB", os.path.join(_STATE, "netline.db"))
WINDOW_S = 900


def db():
    if not os.path.exists(DB):
        raise FileNotFoundError("no store yet")
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)


def human(n):
    n = float(n or 0)
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.0f}{u}" if n >= 10 or u == "B" else f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.0f}T"


def status():
    con = db()
    since = int(time.time()) - WINDOW_S
    cur = con.cursor()
    flags = cur.execute(
        "SELECT comm, host, dst, flag_reason, bytes_out+bytes_in AS total "
        "FROM flows WHERE flagged=1 AND ts_last > ? ORDER BY total DESC LIMIT 8",
        (since,)).fetchall()
    top = cur.execute(
        "SELECT COALESCE(host,dst) h, dst, SUM(bytes_out+bytes_in) b, "
        "GROUP_CONCAT(DISTINCT comm) FROM flows WHERE ts_last > ? "
        "AND dport NOT IN (53) AND dst NOT LIKE '127.%' AND dst NOT LIKE '100.%' "
        "AND dst NOT LIKE '172.1%' AND dst NOT LIKE '172.2%' "
        "GROUP BY h,dst ORDER BY b DESC LIMIT 6", (since,)).fetchall()
    tot = cur.execute(
        "SELECT COALESCE(SUM(bytes_out),0), COALESCE(SUM(bytes_in),0) "
        "FROM flows WHERE ts_last > ?", (since,)).fetchone()
    d = cur.execute("SELECT MAX(ts_last) FROM flows").fetchone()[0] or 0
    con.close()
    return {
        "ok": True,
        "live": (time.time() - d) < 30,
        "stale_s": int(time.time() - d),
        "flagged": [
            {"comm": c or "?", "where": h or dst, "why": r, "bytes": b, "pretty": human(b)}
            for c, h, dst, r, b in flags
        ],
        "top": [
            {"dest": h, "bytes": b, "pretty": human(b), "procs": (p or "").split(",")[:3]}
            for h, dst, b, p in top
        ],
        "bytes_in": human(tot[1]),
        "bytes_out": human(tot[0]),
    }


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if cmd == "status":
            print(json.dumps(status()))
        elif cmd == "open":
            os.system("xdg-open http://127.0.0.1:8899/ >/dev/null 2>&1 &")
            print(json.dumps({"ok": True, "opened": "http://127.0.0.1:8899/"}))
        else:
            print(json.dumps({"ok": False, "error": f"unknown command {cmd}"}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))


if __name__ == "__main__":
    main()
