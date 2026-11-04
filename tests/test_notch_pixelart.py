"""PixelArt.js for the notch island, run through node."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

KINDS = ["clear", "night", "partly", "night-cloudy", "cloudy", "fog", "rain", "snow", "storm"]


def run(expr, lib="PixelArt.js"):
    js = f"const M=require({json.dumps(str(PLUGIN / lib))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


@pytest.mark.parametrize("kind", KINDS)
def test_frames_are_square_and_in_palette(kind):
    size = run("M.SPRITE_SIZE")
    palette = run("M.SPRITE_COLORS")
    frames = run(f"M.weatherSprite({json.dumps(kind)})")
    assert 2 <= len(frames) <= 4
    for frame in frames:
        assert len(frame) == size
        for row in frame:
            assert len(row) == size
            assert set(row) <= set(palette) | {"."}
    assert any(c != "." for f in frames for r in f for c in r)


@pytest.mark.parametrize("kind", KINDS)
def test_frames_actually_animate(kind):
    frames = run(f"M.weatherSprite({json.dumps(kind)})")
    assert len({json.dumps(f) for f in frames}) == len(frames)


def test_palette_values_are_hex():
    assert all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in run("M.SPRITE_COLORS").values())


def test_every_weather_kind_has_a_sprite():
    kinds = run("[0,1,2,3,45,53,63,73,81,95].flatMap(c=>[M.weatherKind(c,true),M.weatherKind(c,false)])", "Model.js")
    assert set(kinds) <= set(KINDS)
    assert set(KINDS) == set(run("M.SPRITE_KINDS"))


def test_unknown_kind_falls_back_and_frames_cycle():
    assert run("M.weatherSprite('bogus')") == run("M.weatherSprite('cloudy')")
    assert run("[0,649,650,1300,1950].map(ms=>M.spriteFrame('cloudy',ms,650))") == [0, 0, 1, 2, 0]
    assert run("M.spriteFrame('clear',-5,0)") == 0
