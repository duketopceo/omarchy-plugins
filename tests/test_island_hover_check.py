"""island-hover-check deadline and refusal exit codes, via the real entry point."""
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/bin/island-hover-check"


def fake(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def run(tmp_path: Path, qs_body: str):
    fake(tmp_path / "qs", qs_body)
    fake(tmp_path / "hyprctl", 'if [ "$1" = cursorpos ]; then echo \'{"x":0,"y":0}\'; fi\nexit 0')
    env = {"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--deadline", "1", "--runs", "1"],
        env=env, capture_output=True, text=True, timeout=20,
    )


def test_deadline_exits_3(tmp_path):
    r = run(tmp_path, "sleep 30")
    assert r.returncode == 3, (r.stdout, r.stderr)
    assert "deadline" in r.stderr


def test_qs_failure_exits_2(tmp_path):
    r = run(tmp_path, "exit 1")
    assert r.returncode == 2, (r.stdout, r.stderr)
