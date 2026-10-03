"""Deadline-bounded subprocess execution under a minimal environment.

Every child runs in its own session (process group), with stdin closed, a
fixed PATH, and a hard wall-clock deadline. On timeout or output overflow the
whole group is killed (TERM, then KILL), so detached grandchildren die too.
"""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

# System directories only. The ambient $PATH is never consulted, and no
# user-writable directory is searched before these. Callers that must find a
# tool installed per-user pass it via tool(extra_dirs=...), which is searched
# after the system directories.
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
MAX_OUT_BYTES = 256 * 1024
_READ_CHUNK = 65536


def safe_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Minimal child environment: fixed PATH, C locale, HOME when known."""
    env = {"PATH": SAFE_PATH, "LC_ALL": "C", "LANG": "C"}
    home = os.path.expanduser("~")
    if home and home != "~":
        env["HOME"] = home
    if extra:
        env.update(extra)
    return env


def tool(name: str, extra_dirs: Iterable[str] = ()) -> str | None:
    """Absolute path of an executable under SAFE_PATH, then extra_dirs."""
    if not name or "/" in name:
        return None
    path = ":".join([SAFE_PATH, *(str(d) for d in extra_dirs if d)])
    return shutil.which(name, path=path)


@dataclass
class RunResult:
    rc: int | None = None
    out: str = ""
    err: str = ""
    error: str | None = None  # empty_argv | spawn_failed | timeout | output_too_large
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        """Spawned, finished within the deadline, output complete, exit 0."""
        return self.error is None and self.rc == 0


def kill_group(proc: subprocess.Popen) -> None:
    """TERM then KILL the child's process group; reap the direct child."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            continue
        if sig == signal.SIGTERM:
            # Leader is gone; grandchildren may still hold the group.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        return


def run(
    argv: Sequence[str | None],
    timeout: float = 2.0,
    max_bytes: int = MAX_OUT_BYTES,
    *,
    stderr: bool = False,
    extra_env: Mapping[str, str] | None = None,
) -> RunResult:
    """Run argv (no shell) with a hard deadline and a byte cap. Never raises.

    stdout (and stderr when requested) are each capped at max_bytes; on
    overflow the output is cut at max_bytes, truncated is set and the group is
    killed. The exit status is reported, not judged.
    """
    res = RunResult()
    if not argv or not argv[0]:
        res.error = "empty_argv"
        return res
    try:
        proc = subprocess.Popen(
            [str(a) for a in argv],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if stderr else subprocess.DEVNULL,
            env=safe_env(extra_env),
            start_new_session=True,
        )
    except (OSError, ValueError):
        res.error = "spawn_failed"
        return res

    bufs: dict[object, bytearray] = {proc.stdout: bytearray()}
    if stderr:
        bufs[proc.stderr] = bytearray()
    deadline = time.monotonic() + timeout
    sel = selectors.DefaultSelector()
    abnormal = False
    try:
        for pipe in bufs:
            sel.register(pipe, selectors.EVENT_READ)
        open_pipes = set(bufs)
        while open_pipes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                res.timed_out = True
                break
            events = sel.select(remaining)
            if not events:
                res.timed_out = True
                break
            for key, _ in events:
                pipe = key.fileobj
                try:
                    chunk = os.read(pipe.fileno(), _READ_CHUNK)
                except OSError:
                    chunk = b""
                if not chunk:
                    sel.unregister(pipe)
                    open_pipes.discard(pipe)
                    continue
                buf = bufs[pipe]
                buf += chunk
                if len(buf) > max_bytes:
                    del buf[max_bytes:]
                    res.truncated = True
            if res.truncated:
                break
        if not res.timed_out and not res.truncated:
            # Pipes hit EOF; the child may still be running.
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                res.timed_out = True
        abnormal = res.timed_out or res.truncated
    finally:
        sel.close()
        if abnormal or proc.poll() is None:
            kill_group(proc)
        for pipe in bufs:
            try:
                pipe.close()
            except OSError:
                pass

    if res.truncated:
        res.error = "output_too_large"
    elif res.timed_out:
        res.error = "timeout"
    else:
        res.rc = proc.returncode
    res.out = bufs[proc.stdout].decode(errors="replace")
    if stderr:
        res.err = bufs[proc.stderr].decode(errors="replace")
    return res
