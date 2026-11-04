"""Media.js for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Media.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const M=require({json.dumps(str(MODULE))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def player(name, playing, identity=None, desktop=""):
    return {"identity": identity or name, "desktopEntry": desktop, "dbusName": name, "isPlaying": playing}


FP = player("org.mpris.MediaPlayer2.spotifast", True, "Spotifast", "spotifast")
SP = player("org.mpris.MediaPlayer2.spotify", True, "Spotify", "spotify")
FF = player("org.mpris.MediaPlayer2.firefox.instance1", True, "Mozilla Firefox")


def pick(players, preferred=None):
    got = run(f"M.pick({json.dumps(players)}, {json.dumps(preferred)})")
    return got["dbusName"] if got else None


def test_kind():
    assert [run(f"M.kind({json.dumps(p)})") for p in (FP, SP, FF)] == ["fastpotify", "spotify", "other"]
    assert run("M.kind(null)") == "other"


def test_prefers_fastpotify_then_spotify_then_other():
    assert pick([FF, SP, FP]) == FP["dbusName"]
    assert pick([FF, SP]) == SP["dbusName"]
    assert pick([FF]) == FF["dbusName"]


def test_playing_beats_paused_even_for_preferred_kind():
    paused_fp = dict(FP, isPlaying=False)
    assert pick([paused_fp, FF]) == FF["dbusName"]
    assert pick([paused_fp, dict(SP, isPlaying=False)]) == FP["dbusName"]


def test_pick_empty_and_override():
    assert pick([]) is None
    assert pick([FP, FF], FF["dbusName"]) == FF["dbusName"]
    assert pick([FP, FF], "gone") == FP["dbusName"]


def test_glyph():
    assert run(f"M.glyphFor({json.dumps(FP)})") == "\U000F04C7"
    assert run(f"M.glyphFor({json.dumps(FF)})") == ""


@pytest.mark.parametrize("title,artist,mx,expected", [
    ("Song", "Band", 40, "Song — Band"),
    ("Song", "", 40, "Song"),
    ("", "Band", 40, "Band"),
    ("", "", 40, ""),
    ("Song", "A Very Long Artist Name", 16, "Song — A Very Lo…"),
    ("A Very Long Song Title Indeed", "Band", 12, "A Very Long…"),
    ("Song", "Band", 0, "Song — Band"),
])
def test_format_title(title, artist, mx, expected):
    assert run(f"M.formatTitle({json.dumps(title)}, {json.dumps(artist)}, {mx})") == expected


def test_format_title_never_exceeds_max():
    for mx in range(1, 30):
        assert len(run(f"M.formatTitle('Hello World', 'Some Artist', {mx})")) <= mx


@pytest.mark.parametrize("sec,expected", [
    (0, "0:00"), (5, "0:05"), (65.9, "1:05"), (600, "10:00"), (3600, "1:00:00"),
    (3725, "1:02:05"), (-4, "0:00"), ("x", "0:00"),
])
def test_format_time(sec, expected):
    assert run(f"M.formatTime({json.dumps(sec)})") == expected


def test_fraction():
    assert run("M.fraction(30, 120)") == 0.25
    assert run("M.fraction(5, 0)") == 0
    assert run("M.fraction(500, 100)") == 1


BIN = "/home/u/.local/bin/fastpotify"


def test_argv_builders():
    assert run(f"M.likeArgv('{BIN}')") == [BIN, "like"]
    assert run(f"M.shuffleArgv('{BIN}')") == [BIN, "shuffle"]
    assert run(f"M.shuffleArgv('{BIN}', true)") == [BIN, "shuffle", "on"]
    assert run(f"M.shuffleArgv('{BIN}', false)") == [BIN, "shuffle", "off"]
    assert run(f"M.repeatArgv('{BIN}')") == [BIN, "repeat"]
    assert run(f"M.repeatArgv('{BIN}', 'track')") == [BIN, "repeat", "track"]
    assert run(f"M.repeatArgv('{BIN}', 'bogus')") == [BIN, "repeat", "off"]
    assert run(f"M.transferArgv('{BIN}', 'abc123')") == [BIN, "transfer", "abc123"]
    assert run(f"M.seekToArgv('{BIN}', 83.6)") == [BIN, "seek-to", "84"]
    assert run(f"M.seekToArgv('{BIN}', -3)") == [BIN, "seek-to", "0"]
    assert run(f"M.nowPlayingArgv('{BIN}')") == [BIN, "now-playing", "--raw"]
    assert run(f"M.showArgv('{BIN}')") == [BIN, "show"]


def test_argv_requires_absolute_path():
    for bad in ("''", "'fastpotify'", "null"):
        assert run(f"M.likeArgv({bad})") == []
    assert run(f"M.transferArgv('{BIN}', '')") == []
    assert run(f"M.seekToArgv('{BIN}', 'x')") == []


def test_next_repeat_cycles():
    assert [run(f"M.nextRepeat('{m}')") for m in ("off", "context", "track")] == ["context", "track", "off"]


def test_parse_now_playing():
    line = "playing\tThe Shoe Fits\tDrake\tAlbum\t83308\t374025\t70\ton\tcontext\thttps://x/y\tyes\tSpotifast\n"
    got = run(f"M.parseNowPlaying({json.dumps(line)})")
    assert got["title"] == "The Shoe Fits" and got["saved"] is True and got["shuffle"] is True
    assert got["repeat"] == "context" and got["durationMs"] == 374025
    assert run("M.parseNowPlaying('nothing playing')") is None
