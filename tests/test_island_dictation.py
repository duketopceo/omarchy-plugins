"""Dictation.js for the Island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

DICT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Dictation.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const D=require({json.dumps(str(DICT))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def status(cap):
    return run(f"D.fromStatus({json.dumps(json.dumps({'capture': {'state': cap}}))})")


def event(line):
    return run(f"D.fromEvent({json.dumps(line)})")


def state_line(s):
    return json.dumps({"kind": "state", "state": s})


def act(state, since_ms_ago=0):
    """Activity after stepping to `state` at t=1000000 then reading at +since_ms_ago."""
    return run(
        f"(()=>{{const m=D.step(D.initial(),{json.dumps(state)},1000000);"
        f"return D.activity(m,{1000000 + since_ms_ago})}})()"
    )


def test_status_states():
    assert status("recording") == "recording"
    assert status("transcribing") == "transcribing"
    assert status("idle") == "idle"


def test_status_unparseable():
    assert run('D.fromStatus("not json")') == ""
    assert run('D.fromStatus("")') == ""


def test_event_mapping():
    # WordInk returns to "listening" (ready, not recording) after every
    # dictation; only "dictating" means a recording is running (live log, 2026-11-15).
    assert event(state_line("listening")) == "idle"
    assert event(state_line("dictating")) == "recording"
    assert event(state_line("transcribing")) == "transcribing"
    assert event(state_line("stopping")) == "transcribing"
    assert event(state_line("sleeping")) == "idle"
    assert event(state_line("something-else")) == "idle"


def test_event_ignored_lines():
    assert event("{broken") == ""
    assert event(json.dumps({"kind": "api_server_stopped"})) == ""
    assert event(json.dumps({"kind": "state", "state": "listening", "pad": "x" * 4000})) == ""


def test_recording_text_and_card():
    a = act("recording", 12000)
    assert a["id"] == "dictation" and a["active"] is True and a["priority"] == 90
    assert a["text"] == "0:12" and a["card"] == "Recording 0:12" and a["state"] == "recording"
    assert a["glyph"] == "\U000F036C"
    assert act("recording", 75000)["text"] == "1:15"


def test_transcribing():
    a = act("transcribing")
    assert a["active"] is True and a["text"] == "…" and a["card"] == "Transcribing"
    assert a["glyph"] == "\U000F051F" and a["state"] == "transcribing"


def test_recording_to_transcribing_keeps_then_idle_drops():
    out = run(
        "(()=>{let m=D.step(D.initial(),'recording',1000);m=D.step(m,'transcribing',5000);"
        "const t=D.activity(m,6000);m=D.step(m,'idle',7000);return [t.active,D.activity(m,8000).active]})()"
    )
    assert out == [True, False]


def test_off_and_idle_inactive():
    for s in ("off", "idle"):
        a = act(s)
        assert a == {"id": "dictation", "active": False, "priority": 90, "text": "", "glyph": "", "card": "", "state": s}


def test_since_kept_while_recording_and_same_object_when_unchanged():
    out = run(
        "(()=>{let m=D.step(D.initial(),'recording',1000);const m2=D.step(m,'recording',9000);"
        "return [m2===m,m2.recordingSince,D.step(D.initial(),'idle',5).recordingSince]})()"
    )
    assert out == [True, 1000, 0]
