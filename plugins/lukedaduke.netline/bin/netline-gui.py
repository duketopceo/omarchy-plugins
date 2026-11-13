#!/usr/bin/env python3
"""netline GUI server — serves the arc map and its data feed.

Read-only: opens the SQLite store and exposes two routes.
  GET /           the visualization
  GET /api/data   aggregated process -> destination graph for the last 15 min

Only rolled-up numbers leave this process; no packet contents, no URLs beyond
hostnames that netline already named.
"""
import http.server
import json
import os
import sqlite3
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("NETLINE_DB", "/home/lukekimball/.local/share/netline/netline.db")
PORT = int(os.environ.get("NETLINE_GUI_PORT", "8899"))
WINDOW_S = 900


def pretty_ip(ip):
    """Shorten all-zero IPv6 forms conntrack emits into something readable."""
    if not ip or ":" not in ip:
        return ip
    if set(ip.replace(":", "")) == {"0"}:
        return "v6-any"
    # 0000:0000:...:1 style -> keep trailing segment
    parts = ip.split(":")
    while len(parts) > 2 and parts[0] == "0000":
        parts.pop(0)
    return ":".join(parts)


def db():
    # Read-only URI: the GUI must never be able to mutate the store.
    uri = f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5)
    return con


def build_payload():
    con = db()
    since = int(time.time()) - WINDOW_S
    cur = con.cursor()

    stats = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(bytes_out),0), COALESCE(SUM(bytes_in),0), "
        "SUM(CASE WHEN host IS NOT NULL THEN 1 ELSE 0 END) "
        "FROM flows WHERE ts_last > ?", (since,)).fetchone()
    total_flows = cur.execute("SELECT COUNT(*) FROM flows").fetchone()[0]

    # Destination rollup, named where possible.
    inner = con.cursor()
    dests = []
    for host, dst, o, i, n in cur.execute(
            "SELECT COALESCE(host, dst), dst, SUM(bytes_out), SUM(bytes_in), COUNT(*) "
            "FROM flows WHERE ts_last > ? AND dport NOT IN (53) "
            "AND dst NOT LIKE '127.%' AND dst NOT LIKE '100.%' AND dst NOT LIKE '172.1%' "
            "AND dst NOT LIKE '172.2%' "
            "GROUP BY COALESCE(host, dst), dst ORDER BY (SUM(bytes_out)+SUM(bytes_in)) DESC LIMIT 24",
            (since,)):
        flag = inner.execute(
            "SELECT 1 FROM flows WHERE (host=? OR dst=?) AND flagged=1 AND ts_last > ? LIMIT 1",
            (host, dst, since)).fetchone()
        dests.append({
            "name": pretty_ip(host), "ip": pretty_ip(dst) if host != dst else None,
            "out": o or 0, "in": i or 0, "bytes": (o or 0) + (i or 0),
            "flows": n, "flag": bool(flag),
        })

    # Process rollup.
    procs = [{"name": comm or "unknown", "bytes": (o or 0) + (i or 0), "flows": n}
             for comm, o, i, n in cur.execute(
                 "SELECT comm, SUM(bytes_out), SUM(bytes_in), COUNT(*) FROM flows "
                 "WHERE ts_last > ? AND comm IS NOT NULL "
                 "GROUP BY comm ORDER BY (SUM(bytes_out)+SUM(bytes_in)) DESC LIMIT 12",
                 (since,))]

    # Edges: which process talked to which destination.
    links = []
    for comm, host, dst, o, i in cur.execute(
            "SELECT comm, COALESCE(host, dst), dst, SUM(bytes_out), SUM(bytes_in) "
            "FROM flows WHERE ts_last > ? AND comm IS NOT NULL AND dport NOT IN (53) "
            "AND dst NOT LIKE '127.%' AND dst NOT LIKE '100.%' AND dst NOT LIKE '172.1%' "
            "AND dst NOT LIKE '172.2%' "
            "GROUP BY comm, COALESCE(host,dst), dst "
            "ORDER BY (SUM(bytes_out)+SUM(bytes_in)) DESC LIMIT 60", (since,)):
        flag = inner.execute(
            "SELECT 1 FROM flows WHERE comm=? AND (host=? OR dst=?) AND flagged=1 "
            "AND ts_last > ? LIMIT 1", (comm, host, dst, since)).fetchone()
        links.append({"proc": comm, "dst": host, "out": o or 0, "in": i or 0,
                      "flag": bool(flag)})

    flags = [{"comm": c, "host": h, "dst": d, "reason": r}
             for c, h, d, r in cur.execute(
                 "SELECT comm, host, dst, flag_reason FROM flows "
                 "WHERE flagged=1 AND ts_last > ? ORDER BY ts_last DESC LIMIT 20", (since,))]

    con.close()
    return {
        "window_s": WINDOW_S,
        "generated": int(time.time()),
        "stats": {"flows": total_flows, "in": stats[2], "out": stats[1],
                  "named": stats[3] or 0},
        "dests": dests,
        "procs": procs,
        "links": links,
        "flags": flags,
    }


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # keep the journal clean; the daemon is the thing we log

    def do_GET(self):
        path = urlparse(self.path).path
        # `/` is the lightweight hex map; `/arc` keeps the old canvas view for
        # when the per-link arcs are what you want to look at.
        page = {"/": "gui-hex.html", "/index.html": "gui-hex.html",
                "/arc": "gui.html", "/arc.html": "gui.html"}.get(path)
        if page:
            try:
                with open(os.path.join(HERE, page), "rb") as f:
                    body = f.read()
            except OSError:
                self.send_error(500, f"{page} missing")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/data":
            try:
                body = json.dumps(build_payload()).encode()
            except Exception as e:
                self.send_error(500, str(e))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[netline-gui] http://127.0.0.1:{PORT}")
    srv.serve_forever()
