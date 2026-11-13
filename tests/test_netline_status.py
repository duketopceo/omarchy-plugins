"""Netline helper tests: status payload shape and the panel's read contract.

These exercise `bin/status.py` against a fixture store so the bar's contract is
checked without a live capture daemon.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/lukedaduke.netline"
STATUS = PLUGIN / "bin/status.py"
SCHEMA = """
CREATE TABLE flows(
  id INTEGER PRIMARY KEY,
  bucket INTEGER NOT NULL,
  ts_first INTEGER, ts_last INTEGER,
  proto TEXT, pid INTEGER, comm TEXT,
  src TEXT, sport INTEGER, dst TEXT, dport INTEGER,
  bytes_out INTEGER DEFAULT 0, bytes_in INTEGER DEFAULT 0,
  state TEXT, dns TEXT, sni TEXT, host TEXT,
  flagged INTEGER DEFAULT 0, flag_reason TEXT
);
CREATE TABLE hostmap(ip TEXT PRIMARY KEY, name TEXT, ts INTEGER);
"""


def _load_status():
    """Import status.py as a module, the way the panel cannot but a test can."""
    spec = importlib.util.spec_from_file_location("netline_status", STATUS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _store(rows=(), hosts=()):
    """Create a fixture store and return its path."""
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    now = int(time.time())
    for comm, dst, sent, recv, flag in rows:
        con.execute(
            "INSERT INTO flows(bucket,ts_first,ts_last,proto,comm,src,dst,dport,"
            "bytes_out,bytes_in,host,flagged,flag_reason) "
            "VALUES(?,?,?,'tcp',?,'10.0.0.2',?,443,?,?,?,?,?)",
            (now // 10, now, now, comm, dst, sent, recv, dst, flag,
             "first contact" if flag else None))
    for ip, name in hosts:
        con.execute("INSERT INTO hostmap(ip,name,ts) VALUES(?,?,?)", (ip, name, now))
    con.commit()
    con.close()
    return path


class StatusPayloadTest(unittest.TestCase):
    """Assertions shared by the subprocess and in-process cases."""

    def test_payload_has_the_keys_the_panel_reads(self):
        path = _store([("chromium", "93.184.216.34", 5000, 100, 1)])
        try:
            env = dict(os.environ, NETLINE_DB=path)
            out = subprocess.run([sys.executable, str(STATUS)], env=env,
                                 capture_output=True, text=True, timeout=20)
            data = json.loads(out.stdout)
        finally:
            os.unlink(path)
        for key in ("ok", "live", "stale_s", "flagged", "top",
                    "bytes_in", "bytes_out"):
            self.assertIn(key, data)
        self.assertTrue(data["ok"])
        self.assertTrue(data["flagged"], "a flagged row should surface")
        row = data["flagged"][0]
        for key in ("comm", "where", "why", "bytes", "pretty"):
            self.assertIn(key, row)

    def test_missing_store_reports_an_error_not_a_clean_scan(self):
        env = dict(os.environ, NETLINE_DB="/nonexistent/netline.db")
        out = subprocess.run([sys.executable, str(STATUS)], env=env,
                             capture_output=True, text=True, timeout=20)
        data = json.loads(out.stdout)
        self.assertFalse(data.get("ok", True))
        self.assertIn("error", data)

    def test_clip_bounds_a_long_field(self):
        status = _load_status()
        self.assertEqual(len(status.clip("x" * 400)), 120)
        self.assertEqual(status.clip(None), "")

    def test_human_formats_bytes(self):
        status = _load_status()
        self.assertEqual(status.human(0), "0B")
        self.assertEqual(status.human(2048), "2.0K")
