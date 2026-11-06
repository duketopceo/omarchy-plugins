"""Theme.js + Settings theme picker for the notch island, run through node.

Swift is the polished default (live Omarchy palette for text/accent/font,
pinned status colors as before); Pxl pins every token to retro-pixel values.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = (
        f"const T=require({json.dumps(str(NOTCH / 'Theme.js'))});"
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


# ---------------------------------------------------------------- theme.js

def test_two_themes_swift_default():
    assert run("T.ids()") == ["swift", "pxl"]
    assert run("T.DEFAULT_THEME") == "swift"
    assert run("T.resolve('swift').label") == "Swift"
    assert run("T.resolve('pxl').label") == "Pxl"
    assert run("T.isTheme('swift') && T.isTheme('pxl') && !T.isTheme('nope') && !T.isTheme(null)")


def test_unknown_theme_falls_back_to_swift():
    for junk in ("nope", "", "SWIFT", None, 42):
        assert run(f"T.resolve({json.dumps(junk)}).id") == "swift"


def test_swift_pins_what_was_hardcoded_and_inherits_the_rest():
    swift = run("T.resolve('swift')")
    # Was hardcoded before: black island, green/amber/red status, blue info.
    assert swift["island"] == "#000000"
    assert (swift["good"], swift["warn"], swift["bad"]) == ("#6fbf73", "#e0b050", "#d9695f")
    assert (swift["info"], swift["danger"], swift["bubble"], swift["bubbleText"]) == ("#4aa3ff", "#f53d3d", "#f2f2f4", "#06121f")
    assert (swift["islandRadius"], swift["cardRadius"], swift["pillRadius"], swift["borderWidth"]) == (24, 8, 13, 1)
    # Follow-the-Omarchy-theme tokens stay blank (Notch.qml resolves them).
    assert (swift["text"], swift["dim"], swift["accent"], swift["urgent"], swift["fontFamily"]) == ("", "", "", "", "")
    assert (swift["card"], swift["chip"], swift["chipHover"]) == ("", "", "")


def test_pxl_pins_every_token_retro():
    pxl = run("T.resolve('pxl')")
    for key, value in pxl.items():
        if key in ("id", "label"):
            continue
        assert value != "", f"pxl.{key} should be pinned, got blank"
    assert pxl["island"] == "#0d0d1a" and pxl["text"] == "#f4f4e8"
    assert pxl["accent"] == "#ffd23f" and pxl["info"] == "#4cc9f0"
    assert (pxl["islandRadius"], pxl["cardRadius"], pxl["pillRadius"]) == (4, 2, 2)
    assert "monospace" in pxl["fontFamily"]


def test_both_themes_share_the_same_token_set():
    assert sorted(run("Object.keys(T.resolve('swift'))")) == sorted(run("Object.keys(T.resolve('pxl'))"))


def test_token_falls_back_to_swift_when_blank():
    assert run("T.token('swift','text')") == ""
    assert run("T.token('pxl','text')") == "#f4f4e8"
    assert run("T.token('pxl','good')") == "#58d068"
    assert run("T.token('nope','good')") == "#6fbf73"
    assert run("T.token('pxl','nope')") == ""


# ---------------------------------------------------------------- settings picker

def test_theme_default_is_swift():
    assert run("S.DEFAULTS.theme") == "swift"
    assert run("S.resolve(null).theme") == "swift"


def test_theme_field_is_a_choice_swift_pxl():
    f = run("S.field('theme')")
    assert f["type"] == "choice"
    assert [(o["value"], o["label"]) for o in f["options"]] == [("swift", "Swift"), ("pxl", "Pxl")]


def test_theme_resolves_valid_and_rejects_junk():
    assert run("S.resolve({theme:'pxl'}).theme") == "pxl"
    assert run("S.resolve({theme:'nope'}).theme") == "swift"
    assert run("S.resolve({theme:''}).theme") == "swift"
    assert run("S.resolve({theme:'pxl'},{theme:'swift'}).theme") == "swift"


def test_theme_next_cycles_swift_pxl():
    assert run("S.next(S.resolve(null),'theme',1)") == "pxl"
    assert run("S.next(S.resolve({theme:'pxl'}),'theme',1)") == "swift"
    assert run("S.next(S.resolve(null),'theme',-1)") == "pxl"
    assert run("S.format(S.field('theme'),'pxl')") == "Pxl"
    assert run("S.format(S.field('theme'),'swift')") == "Swift"


def test_theme_composes_with_theme_js():
    # Settings resolve -> Theme resolve round trip, as Notch.qml does it.
    assert run("T.resolve(S.resolve({theme:'pxl'}).theme).id") == "pxl"
    assert run("T.resolve(S.resolve({theme:'junk'}).theme).id") == "swift"
    assert run("T.resolve(S.resolve(null).theme).island") == "#000000"


# ---------------------------------------------------------------- qml wiring (static)

def test_notch_qml_applies_theme_on_load_and_change():
    qml = (NOTCH / "Notch.qml").read_text()
    assert 'import "Theme.js" as Theme' in qml
    assert "readonly property var themeObj: Theme.resolve(settings.theme)" in qml
    assert "readonly property string themeId: themeObj.id" in qml
    # Derived colors follow the theme, falling back to the live palette.
    assert "themeObj.text || Commons.Color.foreground" in qml
    assert "themeObj.dim || Commons.Color.muted" in qml
    assert "themeObj.fontFamily || Commons.Style.font.family" in qml
    assert "readonly property color islandColor: themeObj.island" in qml
    assert "Math.min(root.islandRadius" in qml
    assert "root.goodColor" in qml and "root.warnColor" in qml


def test_tabs_read_themeobj_instead_of_hardcoded_hex():
    checks = {
        "ExpandedPanel.qml": ["notch.themeObj", "themeObj.islandRadius"],
        "AgentsTab.qml": ["notch.themeObj", "themeObj.warn", "themeObj.good"],
        "NetworkTab.qml": ["themeObj.good", "themeObj.warn", "themeObj.bad", "themeObj.card", "themeObj.chipHover", "onColor: tab.good"],
        "PowerTab.qml": ["notch.themeObj", "t.good", "t.warn", "t.hold"],
        "MessagesTab.qml": ["themeObj.info", "themeObj.bubble", "themeObj.bubbleText"],
        "DayflowTab.qml": ["themeObj.danger"],
        "SystemTab.qml": ["themeObj.info", "themeObj.good", "themeObj.warn"],
        "StocksTab.qml": ["themeObj.good", "themeObj.bad", "toneFor"],
        "ScreenshotsTab.qml": ["notch.goodColor"],
    }
    for name, needles in checks.items():
        text = (NOTCH / name).read_text()
        for needle in needles:
            assert needle in text, f"{name} missing {needle}"


def test_watchlist_slide_up_color_follows_theme():
    slide = (NOTCH / "WatchlistSlide.qml").read_text()
    assert "property color upColor" in slide
    assert "d === \"up\" ? upColor" in slide
    notch = (NOTCH / "Notch.qml").read_text()
    assert notch.count("upColor: root.goodColor") == 2


def test_pixelart_stays_fixed():
    # PixelArt.js sprite colors are icon art, not chrome: Theme.js must not
    # own them and Notch.qml must not recolor PixelWeather.
    assert "SPRITE_COLORS" in (NOTCH / "PixelArt.js").read_text()
    assert "SPRITE_COLORS" not in (NOTCH / "Theme.js").read_text()
    assert "themeObj" not in (NOTCH / "PixelWeather.qml").read_text()
