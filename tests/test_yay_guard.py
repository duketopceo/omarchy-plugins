"""The yay guard refuses --sudoloop without a terminal and passes everything else through."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "machine" / "bin" / "yay"


def run_guard(tmp_path, args, stdin_tty=False):
    # A fake "real yay" that records its arguments instead of running.
    fake = tmp_path / "fake-yay"
    fake.write_text('#!/usr/bin/env bash\necho "REAL $*"\n')
    fake.chmod(0o755)
    guard = tmp_path / "yay"
    guard.write_text(GUARD.read_text().replace("REAL=/usr/bin/yay", f"REAL={fake}"))
    guard.chmod(0o755)
    if stdin_tty:
        # script(1) gives the child a real pty on stdin.
        return subprocess.run(
            ["script", "-qec", f"{guard} {' '.join(args)}", "/dev/null"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
    return subprocess.run([str(guard), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def test_passes_through_without_sudoloop(tmp_path) -> None:
    out = run_guard(tmp_path, ["-Q"])
    assert out.returncode == 0
    assert out.stdout.strip() == "REAL -Q"


def test_refuses_sudoloop_without_terminal(tmp_path) -> None:
    out = run_guard(tmp_path, ["-S", "--sudoloop", "foo"])
    assert out.returncode == 2
    assert "REAL" not in out.stdout
    assert "--sudoloop" in out.stderr


def test_allows_sudoloop_in_a_terminal(tmp_path) -> None:
    out = run_guard(tmp_path, ["-S", "--sudoloop", "foo"], stdin_tty=True)
    assert "REAL -S --sudoloop foo" in out.stdout
