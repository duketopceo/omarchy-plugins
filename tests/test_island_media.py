"""Media.js for the Island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MEDIA = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Media.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

NOW = 10_000_000
MIN = 60_000


def run(expr):
    js = f"const M=require({json.dumps(str(MEDIA))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def player(name, playing, **kw):
    p = {"dbusName": name, "identity": name.upper(), "title": "T-" + name, "artist": "A", "artUrl": "",
         "playing": playing, "length": 200, "position": 10, "canSeek": True, "canGoNext": True,
         "canGoPrevious": False, "canTogglePlaying": True}
    p.update(kw)
    return p


def pick(players, held="", last=None):
    return run(f"M.pick({json.dumps(players)},{json.dumps(held)},{json.dumps(last or {})},{NOW})")


def test_playing_beats_paused():
    r = pick([player("a", False), player("b", True)], last={"a": NOW - MIN})
    assert r["dbusName"] == "b"


def test_paused_within_grace_active_beyond_inactive():
    assert pick([player("a", False)], last={"a": NOW - 3 * MIN})["dbusName"] == "a"
    assert pick([player("a", False)], last={"a": NOW - 11 * MIN}) is None


def test_most_recent_paused_wins():
    r = pick([player("a", False), player("b", False)], last={"a": NOW - 5 * MIN, "b": NOW - 2 * MIN})
    assert r["dbusName"] == "b"


def test_held_player_kept_while_other_plays():
    r = pick([player("a", False), player("b", True)], held="a", last={"a": NOW - MIN})
    assert r["dbusName"] == "a"


def test_held_player_ineligible_falls_through():
    r = pick([player("a", False), player("b", True)], held="a", last={"a": NOW - 11 * MIN})
    assert r["dbusName"] == "b"


def test_no_players():
    assert pick([]) is None
    a = run(f"M.activity(null,{NOW})")
    assert a == {"id": "media", "active": False, "priority": 50, "text": "", "glyph": "", "card": ""}


def test_activity_fields():
    a = run(f"M.activity({json.dumps(player('a', True, artUrl='file:///x.png'))},{NOW})")
    assert a["id"] == "media" and a["active"] is True and a["priority"] == 50
    assert a["text"] == "T-a" and a["card"] == "T-a" and a["glyph"] == "\U000F040A"
    assert a["art"] == "file:///x.png" and a["playing"] is True and a["artist"] == "A"
    assert a["position"] == 10 and a["length"] == 200 and a["dbusName"] == "a"
    assert a["canSeek"] is True and a["canGoNext"] is True and a["canGoPrevious"] is False
    assert a["canTogglePlaying"] is True
    b = run(f"M.activity({json.dumps(player('a', False, artUrl='https://e/x.png'))},{NOW})")
    assert b["glyph"] == "\U000F03E4" and b["art"] == ""


def test_title_falls_back_to_identity():
    a = run(f"M.activity({json.dumps(player('a', True, title=''))},{NOW})")
    assert a["text"] == "A" and a["card"] == ""


def test_art_url():
    assert run('M.artUrl("file:///x.png")') == "file:///x.png"
    assert run('M.artUrl("data:image/png;base64,AAAA")') == "data:image/png;base64,AAAA"
    assert run('M.artUrl("FILE:///x.png")') == "FILE:///x.png"
    assert run('M.artUrl("https://e/x.png")') == ""
    assert run('M.artUrl("http://e/x.png")') == ""


def test_fmt():
    assert run("M.fmt(0)") == "0:00"
    assert run("M.fmt(185)") == "3:05"
    assert run("M.fmt(3725)") == "1:02:05"
    assert run("M.fmt(-4)") == "0:00"
    assert run("M.fmt(NaN)") == "0:00"


def test_seek_target():
    assert run("M.seekTarget(1.4, 200)") == 200
    assert run("M.seekTarget(-1, 200)") == 0
    assert run("M.seekTarget(0.5, 200)") == 100
    assert run("M.seekTarget(0.5, 0)") == 0
