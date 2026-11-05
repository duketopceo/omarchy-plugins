"""The yay guard refuses --sudoloop without a terminal and passes everything else through."""

from __future__ import annotations

import shlex
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
    source = GUARD.read_text()
    # Never let a test fall through to the real yay.
    assert "REAL=/usr/bin/yay" in source
    guard.write_text(source.replace("REAL=/usr/bin/yay", f"REAL={fake}"))
    guard.chmod(0o755)
    if stdin_tty:
        # script(1) gives the child a real pty on stdin.
        return subprocess.run(
            ["script", "-qec", shlex.join([str(guard), *args]), "/dev/null"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
    return subprocess.run([str(guard), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def test_passes_through_without_sudoloop(tmp_path) -> None:
    # No terminal: the loop is forced off so a saved SudoLoop config can't start it.
    out = run_guard(tmp_path, ["-Q"])
    assert out.returncode == 0
    assert out.stdout.strip() == "REAL --sudoloop=false -Q"


def test_refuses_sudoloop_without_terminal(tmp_path) -> None:
    for flag in ("--sudoloop", "--sudoloop=true", "--sudoloop=1"):
        out = run_guard(tmp_path, ["-S", flag, "foo"])
        assert out.returncode == 2, flag
        assert "REAL" not in out.stdout
        assert "--sudoloop" in out.stderr


def test_explicit_sudoloop_false_is_allowed_without_terminal(tmp_path) -> None:
    out = run_guard(tmp_path, ["-S", "--sudoloop=false", "foo"])
    assert out.returncode == 0
    assert "REAL --sudoloop=false -S --sudoloop=false foo" in out.stdout


def test_allows_sudoloop_in_a_terminal(tmp_path) -> None:
    out = run_guard(tmp_path, ["-S", "--sudoloop", "foo"], stdin_tty=True)
    assert "REAL -S --sudoloop foo" in out.stdout
