"""island-probe: one JSON object of existence checks, against a fixture root."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/io.github.duketopceo.island/bin/island-probe"
FIXROOT = ROOT / "tests/fixtures/island/root"

TOOLS = ["wordink", "herdr-app", "snapdex-ctl", "blip", "cliphist", "wl-copy",
         "wpctl", "tailscale", "nordvpn", "dayflow"]


def run_probe(*extra, root=FIXROOT):
    # PATH points only at the fixture bin dir, so presence is deterministic.
    env = {"PATH": str(root / "bin"), "HOME": str(root)}
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(PROBE), "--root", str(root), *extra],
        capture_output=True, text=True, timeout=20, env=env,
    )
    return proc, time.monotonic() - started


def test_probe_is_executable_with_python_shebang():
    assert os.access(PROBE, os.X_OK)
    assert PROBE.read_text().splitlines()[0] == "#!/usr/bin/env python3"


def test_probe_prints_one_json_object_with_every_key():
    proc, _ = run_probe()
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.strip().splitlines()) == 1
    data = json.loads(proc.stdout)
    for key in ("platform", "tools", "cutouts", "model"):
        assert key in data
    assert set(data["platform"]) >= {"system", "machine"}
    assert set(data["tools"]) == set(TOOLS)
    assert all(isinstance(v, bool) for v in data["tools"].values())


def test_probe_reads_cutouts_and_model_from_the_root():
    data = json.loads(run_probe()[0].stdout)
    assert {"connector": "eDP", "width": 3456, "height": 2234, "top": 64} in data["cutouts"]
    assert data["model"] == "j316"


def test_missing_tool_reports_false_and_present_reports_true():
    tools = json.loads(run_probe()[0].stdout)["tools"]
    assert tools["wordink"] is True
    assert tools["herdr-app"] is True
    assert tools["wpctl"] is True
    assert tools["nordvpn"] is False
    assert tools["blip"] is False


def test_empty_root_reports_empty_data_without_failing(tmp_path):
    proc, _ = run_probe(root=tmp_path)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["cutouts"] == []
    assert data["model"] == ""
    assert not any(data["tools"].values())


def test_probe_exits_within_its_deadline():
    proc, elapsed = run_probe()
    assert proc.returncode == 0
    assert elapsed < 5
    assert "signal.alarm" in PROBE.read_text()
