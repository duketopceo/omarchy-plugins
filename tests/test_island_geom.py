"""IslandGeom.js: Dynamic Island sizing (compact pill, not cutout-fill)."""
from pathlib import Path

import pytest

GEOM = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/IslandGeom.js"


def run(expr: str):
    import subprocess
    src = GEOM.read_text()
    script = src + f"\nconsole.log(JSON.stringify({expr}))\n"
    out = subprocess.check_output(["node", "-e", script], text=True).strip()
    import json
    return json.loads(out)


def test_compact_is_shorter_than_prototype_37():
    assert run("COMPACT_H") == 28
    assert run("COMPACT_H") < 37


def test_compact_width_caps_ears():
    # cam 186, ear ask 96 -> capped at EAR_CAP each side
    w = run("compactWidth(186, 96, 1728)")
    assert w == run("186 + 2 * EAR_CAP")
    assert w < 186 + 2 * 96


def test_compact_width_respects_floor_and_screen():
    assert run("compactWidth(80, 10, 1728)") == run("COMPACT_MIN_W")
    assert run("compactWidth(186, 96, 200)") == 200 - 16


def test_window_slack_is_tight():
    assert run("WINDOW_H_SLACK") == 4
    assert run("windowHeight(false)") == 28 + 4
    assert run("windowHeight(true)") == run("EXPANDED_H + WINDOW_H_SLACK")
