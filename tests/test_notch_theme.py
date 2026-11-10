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
    assert (pxl["islandRadius"], pxl["cardRadius"], pxl["pillRadius"], pxl["borderWidth"]) == (0, 2, 0, 2)
    assert (pxl["fontFamily"], pxl["labelFamily"], pxl["fallbackFamily"]) == ("Pixelify Sans", "Silkscreen", "Terminus")
    assert (pxl["steps"], pxl["stepMs"]) == (3, 45)
    assert (pxl["amber"], pxl["gray"], pxl["sky"], pxl["purple"], pxl["pink"]) == ("#ff9f1c", "#a0a8c0", "#6aa9e0", "#b48cf2", "#ff8fc7")
    assert (pxl["white"], pxl["black"]) == ("#f4f4e8", "#0d0d1a")
    assert (pxl["card"], pxl["chip"], pxl["chipHover"], pxl["hairline"], pxl["border"]) == ("#16162a", "#22223c", "#2e2e4e", "#22223c", "#3a3a5c")
    assert (pxl["dim"], pxl["faint"], pxl["urgent"], pxl["hold"], pxl["danger"]) == ("#a0a8c0", "#5a6480", "#ff5252", "#6aa9e0", "#ff5252")
    assert (pxl["bubble"], pxl["bubbleText"]) == ("#f4f4e8", "#0d0d1a")


def test_pxl_palette_is_16_colors_or_fewer():
    pxl = run("T.resolve('pxl')")
    colors = {v.lower() for v in pxl.values() if isinstance(v, str) and v.startswith("#")}
    assert len(colors) <= 16, sorted(colors)


def test_swift_new_tokens_unchanged_values():
    swift = run("T.resolve('swift')")
    assert (swift["amber"], swift["gray"], swift["sky"], swift["white"], swift["black"]) == ("#f5a742", "#8b8f98", "#6fa8ff", "white", "black")
    assert (swift["labelFamily"], swift["fallbackFamily"], swift["steps"], swift["stepMs"]) == ("", "", 0, 0)


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
    assert [(o["value"], o["label"]) for o in f["options"]] == [("swift", "Swift"), ("pxl", "Pxl (16-bit)")]


def test_theme_resolves_valid_and_rejects_junk():
    assert run("S.resolve({theme:'pxl'}).theme") == "pxl"
    assert run("S.resolve({theme:'nope'}).theme") == "swift"
    assert run("S.resolve({theme:''}).theme") == "swift"
    assert run("S.resolve({theme:'pxl'},{theme:'swift'}).theme") == "swift"


def test_theme_next_cycles_swift_pxl():
    assert run("S.next(S.resolve(null),'theme',1)") == "pxl"
    assert run("S.next(S.resolve({theme:'pxl'}),'theme',1)") == "swift"
    assert run("S.next(S.resolve(null),'theme',-1)") == "pxl"
    assert run("S.format(S.field('theme'),'pxl')") == "Pxl (16-bit)"
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
    # Derived colors come from Tk, which follows the live palette but lifts
    # it to AA contrast against the fixed dark island.
    assert "readonly property color textColor: Tk.text" in qml
    assert "readonly property color dimColor: Tk.dim" in qml
    assert "readonly property string fontFamily: Tk.family" in qml
    assert 'Binding { target: Tk; property: "id"; value: root.themeId }' in qml
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


# ---------------------------------------------------------------- 16-bit wiring (static)

import re

# Content that is the user's own (app/brand/data colours, art), not chrome.
ALLOW_LITERALS = {
    "AgentsTab.qml": 4,   # tint of the agent app's own icon colour
}
SKIP = {"Tk.qml"}


def qml_files():
    return [p for p in sorted(NOTCH.glob("*.qml")) if p.name not in SKIP]


def test_tk_singleton_registered_and_toggle_wired():
    assert "singleton Tk Tk.qml" in (NOTCH / "qmldir").read_text()
    tk = (NOTCH / "Tk.qml").read_text()
    assert "pragma Singleton" in tk and "function tint(" in tk and "function r(" in tk
    notch = (NOTCH / "Notch.qml").read_text()
    assert "function toggleTheme(): void { root.toggleTheme() }" in notch
    assert 'setSetting("theme", themeId === "pxl" ? "swift" : "pxl")' in notch
    panel = (NOTCH / "ExpandedPanel.qml").read_text()
    assert "panel.notch.toggleTheme()" in panel


def test_fonts_bundled_with_licenses():
    for rel in ("fonts/Silkscreen/Silkscreen-Regular.ttf", "fonts/Silkscreen/OFL.txt",
                "fonts/PixelifySans/PixelifySans[wght].ttf", "fonts/PixelifySans/OFL.txt"):
        assert (NOTCH / rel).is_file(), rel


def test_no_qml_hardcodes_colors_outside_tokens():
    bad = []
    for p in qml_files():
        src = p.read_text()
        n = len(re.findall(r'"#[0-9a-fA-F]{3,8}"|Qt\.rgba\(|Qt\.color\(|Commons\.Color\.', src))
        if n > ALLOW_LITERALS.get(p.name, 0) + (0 if p.name != "Notch.qml" else 5):
            bad.append((p.name, n))
    assert not bad, bad


def test_no_qml_hardcodes_radius_or_family():
    bad = []
    for p in qml_files():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for m in re.finditer(r'(?<![\w.])radius: *([^;}]+)', line):
                v = m.group(1).strip()
                if not v.startswith("Tk.r(") and v not in ("tab.radius", "tab.cardRadius", "0"):
                    bad.append((p.name, i, "radius", v))
            for m in re.finditer(r'font\.family: *([^;}]+)', line):
                v = m.group(1).strip()
                if not (v.startswith("Tk.") or re.fullmatch(r"(tab|panel|slide|chart|cal|spark|ring|root)\.(family|fontFamily)", v)):
                    bad.append((p.name, i, "family", v))
    assert not bad, bad[:10]


def test_ensure_contrast_lifts_dark_theme_text_onto_black_island():
    # Light Omarchy themes have a dark foreground; on the black island that is ~2:1.
    out = run("(function(){var fg=[0.298,0.31,0.412],bg=[0,0,0];var o=T.ensureContrast(fg,bg,7);"
              "return [T.contrast(fg,bg),T.contrast(o,bg)]})()")
    assert out[0] < 3 and out[1] >= 7
    # Already-legible colours are returned untouched.
    same = run("T.ensureContrast([0.9,0.92,0.95],[0,0,0],7)")
    assert same == [0.9, 0.92, 0.95]
    # Pxl text and dim pass AA on the Pxl island.
    pxl = run("(function(){function h(x){return [1,3,5].map(function(i){return parseInt(x.substr(i,2),16)/255})}"
              "var t=T.THEMES.pxl;return [T.contrast(h(t.text),h(t.island)),T.contrast(h(t.dim),h(t.island)),T.contrast(h(t.accent),h(t.island))]})()")
    assert min(pxl) >= 4.5
