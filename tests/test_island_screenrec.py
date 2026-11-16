"""ScreenRec.js: pid parsing, process elapsed time from /proc, recording activity (node)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/ScreenRec.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    const v = typeof M[a.fn] === "function" ? M[a.fn].apply(null, a.args) : M[a.fn];
    process.stdout.write(JSON.stringify(v === undefined ? null : v));
    """
    out = subprocess.run(["node", "-e", script], input=json.dumps({"fn": fn, "args": list(args)}),
                         capture_output=True, text=True, timeout=20, check=True).stdout
    return json.loads(out)


def cp(n: int) -> str:
    return chr(n)


# comm contains spaces and parentheses; starttime (field 22) is 12345 ticks.
STAT = ("4242 (Web Content (x) y) S 1 4242 4242 0 -1 4194304 100 0 0 0 5 5 0 0 20 0 1 0 "
        "12345 1000000 100 18446744073709551615")


def test_priority():
    assert js("PRIORITY") == 88


@pytest.mark.parametrize("text,pid", [("1234\n", 1234), ("", 0), ("abc", 0), ("0", 0),
                                      ("-5", 0), ("12x", 0)])
def test_parse_pid(text, pid):
    assert js("parsePid", text) == pid


def test_elapsed_handles_comm_with_spaces_and_parens():
    # 12345 ticks at 100 Hz = 123.45 s; uptime 200.5 -> 77.05 -> 77
    assert js("elapsed", STAT, "200.50 800.10\n", 100) == 77
    assert js("elapsed", STAT, "200.50 800.10\n") == 77


def test_elapsed_hz_clamp_and_garbage():
    assert js("elapsed", STAT, "300.5 1", 50) == 53  # 300.5 - 246.9
    assert js("elapsed", STAT, "100.0 1", 100) == 0  # clamped at 0
    assert js("elapsed", "", "200 1") == -1
    assert js("elapsed", "no parens here", "200 1") == -1
    assert js("elapsed", "1 (a) S 1 2", "200 1") == -1
    assert js("elapsed", STAT, "") == -1
    assert js("elapsed", STAT, "x y") == -1


def test_initial_and_inactive_activity():
    assert js("initial") == {"recording": False, "pid": 0, "startedAt": 0}
    off = {"id": "screenrec", "active": False, "priority": 88, "text": "", "glyph": "", "card": ""}
    assert js("activity", js("initial"), 5000) == off
    assert js("activity", {"recording": True, "pid": 1, "startedAt": 0}, 5000) == off
    assert js("activity", {"recording": False, "pid": 0, "startedAt": 100}, 5000) == off


def test_active_activity_text():
    m = {"recording": True, "pid": 9, "startedAt": 1000}
    a = js("activity", m, 66000)
    assert a["active"] is True and a["id"] == "screenrec" and a["priority"] == 88
    assert a["text"] == "1:05" and a["card"] == "Recording 1:05"
    assert a["glyph"] == cp(0xF044A) and a["state"] == "recording"
    assert js("activity", m, 1000 + 3725000)["text"] == "1:02:05"
    assert js("activity", m, 1000)["text"] == "0:00"


def test_current_accepts_only_the_live_pid_while_enabled():
    # A status check or start-time read counts only for the pid it began with,
    # while the source is on and that pid is still the one in the pid file.
    assert js("current", 1234, 1234, True) is True
    assert js("current", 1234, 1234, False) is False
    assert js("current", 1234, 5678, True) is False
    # The pid file vanished during the check: nothing is recording.
    assert js("current", 0, 0, True) is False
    assert js("current", 1234, 0, True) is False
