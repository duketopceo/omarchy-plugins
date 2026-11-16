"""Activity.js: isLive and layout (priority order, held slots while the card is shown)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / "plugins/io.github.duketopceo.island/Activity.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const A = require({json.dumps(str(ACTIVITY))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(A[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({"fn": fn, "args": list(args)}),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def act(id_, priority, active=True, text="x", **extra):
    d = {"id": id_, "active": active, "priority": priority, "text": text}
    d.update(extra)
    return d


DICT = act("dictation", 90)
HUD = act("hud", 80)
TIMER = act("timer", 70)
MEDIA = act("media", 50)
CHARGING = act("charging", 30)
NOW = 1_000_000


def ids(items):
    return [a["id"] for a in items]


def test_is_live_rules():
    assert js("isLive", MEDIA, NOW) is True
    assert js("isLive", act("media", 50, active=False), NOW) is False
    assert js("isLive", act("media", 50, text=""), NOW) is False
    assert js("isLive", act("hud", 80, until=NOW + 1), NOW) is True
    assert js("isLive", act("hud", 80, until=NOW), NOW) is False
    assert js("isLive", act("hud", 80, until=NOW - 5), NOW) is False
    assert js("isLive", None, NOW) is False


def test_highest_priority_wins_and_ties_keep_list_order():
    r = js("layout", [MEDIA, DICT, TIMER], [], False, NOW)
    assert r["top"]["id"] == "dictation"
    assert r["second"]["id"] == "timer"
    assert ids(r["rows"]) == ["timer", "media"]
    tie = js("layout", [act("a", 50), act("b", 50)], [], False, NOW)
    assert tie["top"]["id"] == "a" and tie["second"]["id"] == "b"


def test_inactive_empty_text_and_expired_are_skipped():
    lst = [
        act("dictation", 90, active=False),
        act("hud", 80, text=""),
        act("timer", 70, until=NOW - 1),
        MEDIA,
    ]
    r = js("layout", lst, [], False, NOW)
    assert r["top"]["id"] == "media"
    assert r["second"] is None
    assert r["rows"] == []


def test_card_shown_held_media_keeps_top_when_dictation_appears():
    r = js("layout", [DICT, MEDIA], ["media"], True, NOW)
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["dictation"]
    assert r["held"] == ["media", "dictation"]


def test_card_closed_same_inputs_puts_dictation_on_top():
    r = js("layout", [DICT, MEDIA], ["media"], False, NOW)
    assert r["top"]["id"] == "dictation"
    assert r["second"]["id"] == "media"
    assert r["held"] == []


def test_held_id_that_goes_inactive_leaves_and_slot_refills_by_priority():
    lst = [act("media", 50, active=False), TIMER, CHARGING]
    r = js("layout", lst, ["media", "charging"], True, NOW)
    # media left slot 0; charging stays in slot 1; timer fills the free top slot.
    assert r["held"] == ["timer", "charging"]
    assert r["top"]["id"] == "timer"
    assert ids(r["rows"]) == ["charging"]


def test_card_shown_nothing_live_then_media_then_dictation():
    r = js("layout", [], [], True, NOW)
    assert r["top"] is None and r["second"] is None and r["rows"] == [] and r["held"] == []
    r = js("layout", [MEDIA], r["held"], True, NOW)
    assert r["top"]["id"] == "media"
    assert r["held"] == ["media"]
    r = js("layout", [DICT, MEDIA], r["held"], True, NOW)
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["dictation"]


def test_held_media_timer_then_dictation_appears_rows_become_timer_dictation():
    r = js("layout", [DICT, TIMER, MEDIA], ["media", "timer"], True, NOW)
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["timer", "dictation"]
    assert r["held"] == ["media", "timer", "dictation"]


def test_full_slots_a_fourth_activity_changes_nothing():
    held = ["media", "timer", "charging"]
    r = js("layout", [DICT, MEDIA, TIMER, CHARGING, HUD], held, True, NOW)
    assert r["held"] == held
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["timer", "charging"]


def test_held_top_leaves_and_nothing_refills_rows_close_up():
    # Media (top) went inactive and nothing new is live: timer moves up rather
    # than leaving an empty top slot above a row.
    r = js("layout", [TIMER], ["media", "timer"], True, NOW)
    assert r["top"]["id"] == "timer"
    assert ids(r["rows"]) == []
    assert r["held"] == ["timer"]


def test_middle_row_leaves_and_nothing_refills_last_row_moves_up():
    r = js("layout", [MEDIA, CHARGING], ["media", "timer", "charging"], True, NOW)
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["charging"]
    assert r["held"] == ["media", "charging"]


def test_four_live_activities_card_closed_rows_capped_at_two():
    r = js("layout", [CHARGING, MEDIA, DICT, TIMER], [], False, NOW)
    assert r["top"]["id"] == "dictation"
    assert r["second"]["id"] == "timer"
    assert ids(r["rows"]) == ["timer", "media"]


def test_empty_or_non_array_input_is_empty():
    for bad in ([], None, "nope", {"a": 1}):
        r = js("layout", bad, [], False, NOW)
        assert r == {"top": None, "second": None, "rows": [], "held": []}
    r = js("layout", [None, MEDIA, None], None, True, NOW)
    assert r["top"]["id"] == "media"


BT = act("bluetooth", 20, cardOnly=True)
BT2 = act("bt2", 10, cardOnly=True)


def test_card_only_is_excluded_while_card_closed():
    r = js("layout", [BT], [], False, NOW)
    assert r == {"top": None, "second": None, "rows": [], "held": []}
    r = js("layout", [BT, MEDIA, CHARGING], [], False, NOW)
    assert r["top"]["id"] == "media" and r["second"]["id"] == "charging"
    assert ids(r["rows"]) == ["charging"]


def test_card_only_alone_shown_sits_in_rows_with_empty_top_held():
    r = js("layout", [BT, BT2], [], True, NOW)
    assert r["top"] is None and r["second"] is None
    assert ids(r["rows"]) == ["bluetooth", "bt2"]
    assert r["held"] == ["", "bluetooth", "bt2"]


def test_card_only_row_does_not_move_when_media_arrives():
    r = js("layout", [BT], [], True, NOW)
    r = js("layout", [BT, MEDIA], r["held"], True, NOW)
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["bluetooth"]
    assert r["second"] is None
    assert r["held"] == ["media", "bluetooth"]


def test_card_only_never_takes_top_even_with_higher_priority():
    hi = act("bluetooth", 99, cardOnly=True)
    r = js("layout", [hi, MEDIA], [], True, NOW)
    assert r["top"]["id"] == "media"
    assert ids(r["rows"]) == ["bluetooth"]
    r = js("layout", [hi, MEDIA], ["bluetooth"], True, NOW)
    assert r["top"]["id"] == "media"


def test_held_top_leaves_card_only_stays_in_row():
    r = js("layout", [BT], ["media", "bluetooth"], True, NOW)
    assert r["top"] is None
    assert ids(r["rows"]) == ["bluetooth"]
    assert r["held"] == ["", "bluetooth"]
