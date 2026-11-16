"""Now Playing presentation: art URL policy, compact media sizing, card height (node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    pre = "".join(
        f"const {n}=require({json.dumps(str(PLUGIN / (n + '.js')))});"
        for n in ("Geom", "Zone", "Presentation", "Media", "Settings")
    )
    js = f"{pre}console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


MAC = "{cutouts:[{connector:'eDP',width:3456,height:2234,top:64}],model:'j316'}"
MAC_SCREEN = "{name:'eDP-1',width:1728,height:1117,physicalWidth:3456,physicalHeight:2234}"
PLAIN_SCREEN = "{name:'DP-3',width:3440,height:1440,physicalWidth:3440,physicalHeight:1440}"
G_NOTCH = f"Geom.compute({MAC},{MAC_SCREEN},0)"
G_PLAIN = f"Geom.compute({MAC},{PLAIN_SCREEN},0)"


# ---- art URL policy ----
@pytest.mark.parametrize("url,web,want", [
    ("https://i.scdn.co/image/ab67", True, "https://i.scdn.co/image/ab67"),
    ("HTTPS://i.scdn.co/image/ab67", True, "HTTPS://i.scdn.co/image/ab67"),
    ("https://i.scdn.co/image/ab67", False, ""),
    ("https://i.scdn.co/image/ab67", None, ""),
    ("http://e.example/x.png", True, ""),
    ("https://user:pw@e.example/x.png", True, ""),
    ("https://localhost/x.png", True, ""),
    ("https://127.0.0.1/x.png", True, ""),
    ("https://[::1]/x.png", True, ""),
    ("https:///x.png", True, ""),
    ("file:///tmp/x.png", False, "file:///tmp/x.png"),
    ("data:image/png;base64,AAAA", False, "data:image/png;base64,AAAA"),
    ("javascript:alert(1)", True, ""),
    ("", True, ""),
])
def test_art_url_policy(url, web, want):
    assert run(f"Media.artUrl({json.dumps(url)},{json.dumps(web)})") == want


def test_art_url_length_capped():
    assert run("Media.artUrl('https://e.example/'+'a'.repeat(3000), true)") == ""


def player(**kw):
    p = {"dbusName": "org.mpris.MediaPlayer2.spotify", "identity": "Spotify", "desktopEntry": "spotify",
         "title": "#432 The Mind of Napoleon", "artist": "Show Name", "album": "The Album",
         "artUrl": "https://i.scdn.co/image/x", "playing": True, "length": 3000, "position": 100,
         "canSeek": True, "canGoNext": True, "canGoPrevious": True, "canTogglePlaying": True}
    p.update(kw)
    return p


def test_activity_carries_identity_subtitle_and_web_art():
    a = run(f"Media.activity({json.dumps(player())},1,true)")
    assert a["art"] == "https://i.scdn.co/image/x"
    assert a["identity"] == "Spotify" and a["desktopEntry"] == "spotify"
    assert a["subtitle"] == "Show Name"
    assert run(f"Media.activity({json.dumps(player())},1,false)")["art"] == ""


def test_subtitle_falls_back_to_album_then_empty():
    assert run(f"Media.activity({json.dumps(player(artist=''))},1,true)")["subtitle"] == "The Album"
    assert run(f"Media.activity({json.dumps(player(artist='', album=''))},1,true)")["subtitle"] == ""


def test_fmt_remaining():
    assert run("Media.fmtRemaining(100, 3000)") == "-48:20"
    assert run("Media.fmtRemaining(5000, 3000)") == "-0:00"
    assert run("Media.fmtRemaining(0, 0)") == ""


def test_settings_web_art_defaults_on_and_is_boolean():
    assert run("Settings.DEFAULTS.webArt") is True
    assert run("Settings.resolve({plugins:[{id:'x',webArt:'no'}]},'x').settings.webArt") is True
    assert run("Settings.resolve({plugins:[{id:'x',webArt:false}]},'x').settings.webArt") is False


# ---- compact media sizing ----
def test_media_compact_on_notch_is_camera_plus_minimum_ears():
    t = run(f"Presentation.compact({G_NOTCH},38,{{media:true,bubble:false,dots:0,screenWidth:1728}})")
    assert t["width"] == 186 + 2 * 56
    assert t["earWidth"] == 56


def test_media_compact_without_cutout_is_tight():
    t = run(f"Presentation.compact({G_PLAIN},38,{{media:true,bubble:false,dots:0,screenWidth:3440}})")
    assert t["width"] < 140
    assert t["width"] >= 2 * t["earWidth"]


def test_media_compact_without_cutout_keeps_camera_gap_for_dots():
    t = run(f"Presentation.compact({G_PLAIN},38,{{media:true,bubble:false,dots:1,screenWidth:3440}})")
    assert t["width"] >= 160 + 2 * 56 - 1


def test_media_tight_pill_zone_follows_target():
    t = f"Presentation.compact({G_PLAIN},38,{{media:true,bubble:false,dots:0,screenWidth:3440}})"
    r = run(f"Zone.rect('pill',{G_PLAIN},{t})")
    assert r["width"] == run(t)["width"] + 12


# ---- card height ----
BASE = {"page": "now", "kind": "media", "band": 28, "pad": 16, "content": 164, "rows": 0,
        "rowH": 36, "gap": 12, "pageRowH": 26, "max": 380}


def card_height(**over):
    m = dict(BASE, **over)
    return run(f"Presentation.cardHeight({json.dumps(m)})")


def test_media_card_height_fits_content():
    # band + pad + content + gap + page row + pad
    assert card_height() == 28 + 16 + 164 + 12 + 26 + 16 == 262


def test_media_card_adds_rows():
    assert card_height(rows=2) == 262 + 2 * (36 + 12)


def test_card_height_capped_at_max():
    assert card_height(rows=2, content=400) == 380


@pytest.mark.parametrize("over", [{"page": "settings"}, {"kind": "timer"}, {"kind": ""}])
def test_other_pages_and_kinds_use_full_height(over):
    assert card_height(**over) == 380


def test_card_height_ignores_junk():
    assert card_height(content="x", rows=-3) <= 380


# ---- hot zone follows the committed card height ----
def test_card_zone_uses_committed_height_and_window_stays_full():
    full = run(f"Zone.rect('card',{G_NOTCH})")
    short = run(f"Zone.rect('card',{G_NOTCH},null,262)")
    assert short["height"] == 262 + 12
    assert short["width"] == full["width"] and short["x"] == full["x"]
    assert full["height"] == 380 + 12
    assert run(f"Zone.windowSize({G_NOTCH})") == {"width": 744, "height": 392}


def test_card_zone_height_never_exceeds_full():
    assert run(f"Zone.rect('card',{G_NOTCH},null,9999)")["height"] == 380 + 12
    assert run(f"Zone.rect('card',{G_NOTCH},null,0)")["height"] == 380 + 12
