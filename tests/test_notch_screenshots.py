"""Screenshots.js for the notch island (snapdex tab and caption flash), run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SHOTS = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Screenshots.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const S=require({json.dumps(str(SHOTS))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


INDEX = """# Screenshots

- [2026-10-01_10-00-00_login_page.png](2026-10-01_10-00-00_login_page.png) — login page
- [2026-10-02_11-30-00_build_logs.png](2026-10-02_11-30-00_build_logs.png) — build logs
not a row
"""


def test_parse_index():
    rows = run(f"S.parseIndex({json.dumps(INDEX)})")
    assert [r["caption"] for r in rows] == ["login page", "build logs"]
    assert rows[1]["ts"] == "2026-10-02_11-30-00" and rows[1]["name"].endswith("build_logs.png")
    assert run("S.parseIndex('')") == [] and run("S.parseIndex(null)") == []


def test_first_read_is_baseline_then_new_caption_flashes_4s_at_priority_30():
    rows = run(f"S.parseIndex({json.dumps(INDEX)})")
    base = run(f"S.step(S.initial(),{json.dumps(rows)},1000)")
    assert base["text"] == "" and run(f"S.isActive({json.dumps(base)},1001)") is False
    new = rows + [{"name": "2026-10-03_09-00-00_pricing_table.png", "caption": "pricing table", "ts": "2026-10-03_09-00-00"}]
    nxt = run(f"S.step({json.dumps(base)},{json.dumps(new)},5000)")
    assert nxt["text"] == "pricing table" and nxt["flashUntil"] == 5000 + 4000
    assert run("S.FLASH_MS") == 4000 and run("S.PRIORITY") == 30
    assert run(f"S.isActive({json.dumps(nxt)},8999)") is True
    assert run(f"S.isActive({json.dumps(nxt)},9001)") is False
    # Unchanged index later: no re-flash, text kept but expired.
    again = run(f"S.step({json.dumps(nxt)},{json.dumps(new)},20000)")
    assert again["flashUntil"] == nxt["flashUntil"]


def test_batch_shows_a_count_and_long_captions_are_capped():
    rows = [{"name": f"2026-10-0{i}_10-00-00_x.png", "caption": "x", "ts": f"2026-10-0{i}_10-00-00"} for i in range(1, 6)]
    base = run(f"S.step(S.initial(),{json.dumps(rows[:1])},0)")
    batch = run(f"S.step({json.dumps(base)},{json.dumps(rows)},10)")
    assert batch["text"] == "4 screenshots captioned"
    assert len(run("S.flashText('word '.repeat(40))")) <= 36
    assert run("S.flashText('   ')") == ""


def test_parse_panel_newest_first_limited_to_8():
    items = [{"name": f"2026-10-{d:02d}_10-00-00_c.png", "caption": f"c{d}", "ts": f"2026-10-{d:02d}_10-00-00", "path": f"/p/{d}.png"} for d in range(1, 13)]
    panel = json.dumps({"ok": True, "pending": 3, "indexed": 12, "dst": "/p", "auto": {"enabled": True}, "items": items})
    p = run(f"S.parsePanel({json.dumps(panel)})")
    assert p["ok"] and p["pending"] == 3 and p["autoOn"] is True and p["dst"] == "/p"
    assert len(p["items"]) == 8 and p["items"][0]["caption"] == "c12" and p["items"][-1]["caption"] == "c5"
    for junk in ("", "x", "[]"):
        q = run(f"S.parsePanel({json.dumps(junk)})")
        assert q["ok"] is False and q["items"] == []


def test_commands_call_snapdex_ctl_with_absolute_paths():
    a = run("S.ctlArgs('/home/x',['process'])")
    assert a == ["/usr/bin/python3", "/home/x/.config/omarchy/plugins/io.github.duketopceo.snapdex/bin/snapdex-ctl", "process"]
    assert run("S.autoArgs(true)") == ["auto", "on"] and run("S.autoArgs(false)") == ["auto", "off"]
    assert run("S.indexPath('/home/x')") == "/home/x/Pictures/Screenshots/index.md"
    assert run("S.shortPath('/home/x/Pictures/Screenshots','/home/x')") == "~/Pictures/Screenshots"
    assert run("S.pendingText(0)") == "All captioned" and run("S.pendingText(5)") == "5 unprocessed"


def test_folders_use_snapdex_fields_then_fall_back():
    p = run("S.folders({inbox:'/i', library:'/l', dst:''}, '/h', false)")
    assert p == {"library": "/l", "inbox": "/i", "separate": True}
    assert run("S.folders({inbox:'', library:'', dst:''}, '/h', true)") == {
        "library": "/h/Pictures/Screenshots/Library", "inbox": "/h/Pictures/Screenshots", "separate": True}
    assert run("S.folders({inbox:'', library:'', dst:''}, '/h', false)") == {
        "library": "/h/Pictures/Screenshots", "inbox": "/h/Pictures/Screenshots", "separate": False}
    assert run("S.libraryIndexPath('/h')") == "/h/Pictures/Screenshots/Library/index.md"


def test_library_dir_is_only_a_real_library():
    # the Island's "Library" control opens nothing when the library is absent,
    # rather than revealing a directory that does not exist
    assert run("S.libraryDir('/h', true)") == "/h/Pictures/Screenshots/Library"
    assert run("S.libraryDir('/h', false)") == ""
    assert run("S.libraryDir('/h')") == ""
