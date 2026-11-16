"""Tint.js: WCAG contrast and most-saturated accessible colour pick."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plugins/io.github.duketopceo.island/Tint.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(M[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({"fn": fn, "args": list(args)}),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def c(r, g, b):
    return {"r": r, "g": g, "b": b}


BLACK = c(0, 0, 0)
WHITE = c(1, 1, 1)


def test_contrast_extremes_and_symmetry():
    assert js("contrast", WHITE, BLACK) == pytest.approx(21.0)
    assert js("contrast", BLACK, WHITE) == pytest.approx(21.0)
    assert js("contrast", WHITE, WHITE) == pytest.approx(1.0)


def test_contrast_mid_grey_vs_black():
    assert js("contrast", c(0.5, 0.5, 0.5), BLACK) == pytest.approx(5.28, abs=0.01)


def test_pick_highest_saturation_among_qualifying():
    dull = c(0.6, 0.6, 0.65)
    vivid = c(1, 0.2, 0.2)
    dark = c(0.05, 0, 0)  # saturated but fails contrast on black
    assert js("pick", [dull, dark, vivid], BLACK) == vivid


def test_pick_none_qualify_or_bad_input():
    assert js("pick", [c(0.02, 0.02, 0.02)], BLACK) is None
    assert js("pick", [], BLACK) is None
    assert js("pick", None, BLACK) is None
    assert js("pick", "red", BLACK) is None
