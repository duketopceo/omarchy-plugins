#!/usr/bin/env python3
"""Measure idle process spawns per plugin from an execve trace.

Unprivileged tracing is blocked here (kernel.yama.ptrace_scope=1) and /proc
sampling misses sub-second helpers, so measurement uses a root-scoped strace
of the running shell:

  sudo strace -f -tt -qq -s 4096 -e trace=execve,clone,clone3,fork,vfork \
       -p <shell-pid> -o /tmp/shell.trace
  scripts/measure-plugin-cost.py --log /tmp/shell.trace --window 600

With --live the script runs that strace itself through `sudo -n` for the
window (sudo must already be authorized, e.g. via the omaseal pattern in the
machine profile). Each successful exec is attributed to the plugin whose
directory appears in its path or argv (".../plugins/<id>/"), and every process
that plugin's helper forks is credited to the same plugin; everything else
counts as "other". strace cuts strings at 32 bytes by default, which hides the
plugin path, so traces need -s 4096: a truncated argv is reported, and --record
refuses such a trace. --record writes each plugin's rate and today's date into
the spawn_measurement item of its docs/reviews/<id>.md scorecard block.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECVE = re.compile(r'execve\("(?P<path>[^"]*)",\s*\[(?P<argv>[^\]]*)\]')
FAILED = re.compile(r"\)\s*=\s*-1\b")
PLUGIN = re.compile(r"/plugins/(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*)/")
PID = re.compile(r"^\s*(?P<pid>\d+)\s")
FORK = re.compile(r"\b(?:clone3?|v?fork)\(.*\)\s*=\s*(?P<child>\d+)\s*$")
TRUNCATED = re.compile(r'"\.\.\.')
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def attribute(lines: list[str], window_s: float) -> dict:
    counts: Counter[str] = Counter()
    owner: dict[str, str] = {}   # pid -> plugin, inherited by forked children
    truncated = 0
    for line in lines:
        pid_match = PID.search(line)
        pid = pid_match.group("pid") if pid_match else ""
        fork = FORK.search(line)
        if fork and pid in owner:
            owner[fork.group("child")] = owner[pid]
            continue
        match = EXECVE.search(line)
        if not match or FAILED.search(line):
            continue
        hit = PLUGIN.search(match.group("path")) or PLUGIN.search(match.group("argv"))
        if hit:
            owner[pid] = hit.group("id")
            counts[hit.group("id")] += 1
        elif pid in owner:
            counts[owner[pid]] += 1
        elif TRUNCATED.search(match.group("argv")):
            truncated += 1
        else:
            counts["other"] += 1
    minutes = max(window_s, 1.0) / 60.0
    return {
        "window_s": window_s,
        "truncated": truncated,
        "counts": dict(sorted(counts.items())),
        "per_minute": {k: round(v / minutes, 2) for k, v in sorted(counts.items())},
    }


def shell_pid() -> int | None:
    out = subprocess.run(["/usr/bin/pgrep", "-o", "-f", "quickshell|omarchy-shell"],
                         capture_output=True, text=True)
    text = out.stdout.strip()
    return int(text) if text.isdigit() else None


def live_trace(window_s: int, out: Path) -> list[str]:
    pid = shell_pid()
    strace = shutil.which("strace", path=SAFE_PATH)
    if pid is None or strace is None:
        raise SystemExit("need a running shell and strace installed")
    cmd = ["/usr/bin/sudo", "-n", "/usr/bin/timeout", str(window_s), strace,
           "-f", "-tt", "-qq", "-s", "4096", "-e", "trace=execve,clone,clone3,fork,vfork",
           "-p", str(pid), "-o", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 124) or not out.exists():
        raise SystemExit("sudo strace failed; run it manually:\n  sudo " + " ".join(cmd[2:]))
    return out.read_text(errors="replace").splitlines()


def record(per_minute: dict[str, float], reviews: Path, today: str) -> list[str]:
    updated = []
    fence = re.compile(r"(```scorecard\n)(.*?)(\n```)", re.S)
    for path in sorted(reviews.glob("*.md")):
        text = path.read_text()
        match = fence.search(text)
        if not match:
            continue
        card = json.loads(match.group(2))
        plugin = card.get("plugin")
        if not plugin:
            continue
        card.setdefault("manual", {})["spawn_measurement"] = {
            "value": per_minute.get(plugin, 0.0), "date": today}
        body = json.dumps(card, indent=2)
        path.write_text(text[:match.start(2)] + body + text[match.end(2):])
        updated.append(plugin)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--log", type=Path, help="existing strace -f -tt -e trace=execve output")
    source.add_argument("--live", action="store_true", help="trace the running shell via sudo -n strace")
    parser.add_argument("--window", type=int, default=600, help="trace window in seconds")
    parser.add_argument("--record", action="store_true", help="write rates into docs/reviews scorecards")
    args = parser.parse_args(argv)

    if args.live:
        lines = live_trace(args.window, Path("/tmp") / f"plugin-cost-{dt.date.today()}.trace")
    else:
        lines = args.log.read_text(errors="replace").splitlines()
    result = attribute(lines, args.window)
    print(json.dumps(result, indent=2))
    if args.record:
        if result["truncated"]:
            raise SystemExit(f"refusing --record: {result['truncated']} exec(s) had truncated argv; "
                             "re-trace with strace -s 4096")
        updated = record(result["per_minute"], ROOT / "docs" / "reviews", dt.date.today().isoformat())
        print("recorded: " + ", ".join(updated), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
