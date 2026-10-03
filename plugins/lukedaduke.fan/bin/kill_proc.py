#!/usr/bin/python3
"""Kill one user process by pid for the lukedaduke.fan panel.

usage: kill_proc.py <pid> [<starttime>]

Refuses pid <= 1. When the panel passes the process start time it saw, the
kill is refused if the pid now belongs to a different process (pid reuse while
the confirm prompt was open). Emits the R13 envelope.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _omplug import envelope  # noqa: E402

JOB_DEADLINE_S = 3


def _start_time(pid: int, proc_root: Path) -> int | None:
    try:
        raw = (proc_root / str(pid) / "stat").read_text()
        return int(raw[raw.rindex(")") + 2:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def kill(pid: int, expected_start: int = 0, proc_root: Path = Path("/proc")):
    if pid <= 1:
        raise envelope.HelperError("refused")
    if expected_start > 0:
        actual = _start_time(pid, proc_root)
        if actual is None:
            raise envelope.HelperError("gone")
        if actual != expected_start:
            raise envelope.HelperError("changed")
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        raise envelope.HelperError("gone") from None
    except PermissionError:
        raise envelope.HelperError("permission") from None
    return {"pid": pid}, {}


def parse(argv: list[str]):
    if not argv:
        raise envelope.HelperError("usage")
    try:
        pid = int(argv[0])
        start = int(argv[1]) if len(argv) > 1 else 0
    except ValueError:
        raise envelope.HelperError("usage") from None
    return kill(pid, start)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return envelope.main(lambda: parse(args))


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)
    raise SystemExit(main())
