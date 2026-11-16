"""Palette.js: dominant colors from canvas pixels (node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def dominant(pixels, opts=None):
    """pixels: list of (r, g, b, a) bytes."""
    flat = [v for px in pixels for v in px]
    js = (f"const P=require({json.dumps(str(PLUGIN / 'Palette.js'))});"
          f"console.log(JSON.stringify(P.dominant({json.dumps(flat)},{json.dumps(opts)})));")
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def test_single_color_image_gives_that_color():
    out = dominant([(255, 0, 0, 255)] * 64)
    assert len(out) == 1
    assert out[0]["r"] == pytest.approx(1.0) and out[0]["g"] == 0 and out[0]["b"] == 0


def test_most_common_color_first():
    out = dominant([(0, 0, 255, 255)] * 40 + [(255, 0, 0, 255)] * 24)
    assert out[0]["b"] == pytest.approx(1.0)
    assert out[1]["r"] == pytest.approx(1.0)


def test_transparent_pixels_ignored():
    assert dominant([(255, 0, 0, 0)] * 64) == []


def test_rare_colors_dropped():
    out = dominant([(0, 255, 0, 255)] * 99 + [(255, 0, 0, 255)])
    assert len(out) == 1


def test_similar_shades_share_a_bucket_and_average():
    out = dominant([(250, 0, 0, 255)] * 32 + [(254, 0, 0, 255)] * 32)
    assert len(out) == 1
    assert out[0]["r"] == pytest.approx(252 / 255)


def test_empty_and_bad_input():
    assert dominant([]) == []
    js = (f"const P=require({json.dumps(str(PLUGIN / 'Palette.js'))});"
          "console.log(JSON.stringify([P.dominant(null),P.dominant(undefined),P.dominant({})]));")
    out = json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)
    assert out == [[], [], []]


def test_max_colors_option():
    px = [(0, 0, 255, 255)] * 30 + [(255, 0, 0, 255)] * 30 + [(0, 255, 0, 255)] * 30
    assert len(dominant(px, {"max": 2})) == 2
