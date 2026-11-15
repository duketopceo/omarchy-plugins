"""Fullscreen.js: real FS bit + idle step-aside policy."""
import json
import subprocess
from pathlib import Path

FS = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Fullscreen.js"


def run(expr: str):
    script = FS.read_text() + f"\nconsole.log(JSON.stringify({expr}))\n"
    out = subprocess.check_output(["node", "-e", script], text=True).strip()
    return json.loads(out)


def test_maximized_alone_is_not_fullscreen():
    ws = {"hasFullscreen": True, "toplevels": {"values": [{"lastIpcObject": {"fullscreen": 1}}]}}
    assert run(f"isFullscreen({json.dumps(ws)})") is False


def test_real_fullscreen_bit_two():
    ws = {"hasFullscreen": True, "toplevels": {"values": [{"lastIpcObject": {"fullscreen": 2}}]}}
    assert run(f"isFullscreen({json.dumps(ws)})") is True


def test_step_aside_only_when_idle_and_enabled():
    assert run("shouldStepAside(true, true, false)") is True
    assert run("shouldStepAside(true, true, true)") is False
    assert run("shouldStepAside(false, true, false)") is False
    assert run("shouldStepAside(true, false, false)") is False
