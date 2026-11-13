"""Behavior of the Island's activity selection and safe actions."""

import json
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/IslandActivity.js"


def evaluate(expression):
    script = f"const I = require({json.dumps(str(MODULE))}); console.log(JSON.stringify({expression}));"
    return json.loads(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout)


def test_priorities_are_stable_and_empty_or_disabled_entries_are_skipped():
    assert evaluate("I.visible([{id:'a',active:true,priority:5,text:'A'},{id:'b',active:true,priority:9,text:'B'},{id:'c',active:true,priority:5,text:'C'},{id:'d',active:false,priority:99,text:'D'},{id:'e',active:true,priority:99,text:''}]).map(x=>x.id)") == ["b", "a", "c"]
    assert evaluate("I.visible(null)") == []


def test_selection_is_bound_to_identity_and_never_redirects():
    assert evaluate("I.selected([{id:'b',active:true,text:'B'}], 'a')") is None
    assert evaluate("I.selected([{id:'b',active:true,text:'B'}], 'b').id") == "b"


def test_stop_is_available_only_while_recording():
    assert evaluate("I.action('dictation', 'recording')") == "stop"
    assert evaluate("I.action('dictation', 'transcribing')") is None
    assert evaluate("I.action('dictation', 'done')") is None


def test_only_two_activities_fit_when_space_allows():
    assert evaluate("I.canSplit(220, 70, 70, 60)") is True
    assert evaluate("I.canSplit(199, 70, 70, 60)") is False
    assert evaluate("I.canSplit(220, 70, 70, 0)") is False
