"""Pages.js: the Island card's page registry (node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Pages.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def js(expr: str):
    script = f"const P=require({json.dumps(str(MOD))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


def chips(avail, live=None):
    return js(f"P.chips({json.dumps(avail)}, {json.dumps(live or {})})")


ALL = {"music": True, "agents": True, "shots": True, "messages": True, "dayflow": True}


def test_ae1_clean_machine_has_home_system_more():
    r = chips({})
    assert r["chips"] == ["home", "system", "more"]
    assert r["more"] == ["settings"]


def test_ae2_six_chips_with_messages_promoted():
    r = chips({"music": True, "agents": True, "messages": True}, {"messages": True})
    assert r["chips"] == ["home", "music", "agents", "system", "messages", "more"]


def test_ae3_dayflow_stays_under_more_when_row_is_full():
    r = chips(ALL, {"messages": True, "dayflow": True})
    assert r["chips"] == ["home", "music", "agents", "system", "messages", "more"]
    assert "dayflow" in r["more"]


def test_never_more_than_six_chips():
    r = chips(ALL, {"messages": True, "shots": True, "dayflow": True})
    assert len(r["chips"]) == 6


def test_promotion_order_messages_shots_dayflow_when_room():
    r = chips({"shots": True, "messages": True, "dayflow": True},
              {"messages": True, "shots": True, "dayflow": True})
    assert r["chips"] == ["home", "system", "messages", "shots", "dayflow", "more"]


def test_shots_before_dayflow():
    r = chips(ALL, {"shots": True, "dayflow": True})
    assert r["chips"][4] == "shots"


def test_undetected_page_never_promoted_or_listed():
    r = chips({}, {"messages": True, "dayflow": True})
    assert "messages" not in r["chips"] and "messages" not in r["more"]
    assert "dayflow" not in r["more"]


def test_more_lists_detected_pages_in_fixed_order_then_settings():
    r = chips(ALL)
    assert r["more"] == ["shots", "messages", "dayflow", "settings"]


def test_promoted_page_still_listed_under_more():
    r = chips(ALL, {"messages": True})
    assert "messages" in r["more"]


def test_normalize_aliases_and_unknowns():
    assert js('P.normalize("now")') == "home"
    assert js('P.normalize("music")') == "music"
    assert js('P.normalize("bogus")') == ""
    assert js('P.normalize("")') == ""
    assert js("P.normalize(null)") == ""


def test_label_for_each_page():
    labels = js("P.PAGE_IDS.map(P.label)")
    assert labels == ["Home", "Music", "Agents", "System", "More", "Shots", "Messages", "Dayflow", "Settings"]


def test_reachable_falls_back_to_home():
    avail = {"music": False}
    assert js(f'P.reachable("music", {json.dumps(avail)})') == "home"
    assert js(f'P.reachable("system", {json.dumps(avail)})') == "system"
    assert js(f'P.reachable("settings", {json.dumps(avail)})') == "settings"
    assert js(f'P.reachable("now", {json.dumps(avail)})') == "home"
    assert js(f'P.reachable("", {json.dumps(avail)})') == "home"
