"""Wordink.js for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Wordink.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const W=require({json.dumps(str(MODULE))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def ev(**kw):
    return json.dumps(kw)


@pytest.mark.parametrize("line,expected", [
    (ev(kind="state", state="dictating", device="Mic"), "recording"),
    (ev(kind="state", state="transcribing"), "transcribing"),
    (ev(kind="state", state="stopping"), "transcribing"),
    (ev(kind="state", state="listening"), "idle"),
    (ev(kind="dictation", phase="started", text=""), "recording"),
    (ev(kind="dictation", phase="transcribing", text=""), "transcribing"),
    (ev(kind="dictation", phase="pasted", text="hello"), "idle"),
    (ev(kind="dictation", phase="cancelled"), "idle"),
    (ev(kind="dictation", phase="discarded"), "idle"),
    (ev(kind="dictation", phase="failed"), "error"),
    (ev(kind="transcript", phase="completed", text="x"), None),
    (ev(kind="transcript", phase="failed"), "error"),
    (ev(kind="session_started"), None),
    (ev(kind="state", state="mystery"), None),
    ("not json", None),
    ("", None),
])
def test_event_lines(line, expected):
    assert run(f"W.eventToState({json.dumps(line)})") == expected


def test_oversized_line_ignored():
    assert run("W.eventToState('x'.repeat(5000))") is None


def status(capture="idle", model_error=None, mic="ready"):
    return {"capture": {"state": capture}, "model": {"installed": True, "error": model_error},
            "permissions": {"ready": True, "microphone": mic}, "listener": {"running": True, "status": "Enabled"}}


@pytest.mark.parametrize("doc,expected", [
    (status(), "idle"),
    (status("recording"), "recording"),
    (status("transcribing"), "transcribing"),
    (status(model_error="boom"), "error"),
    (status(mic="denied"), "error"),
    ({}, "idle"),
])
def test_status_json(doc, expected):
    assert run(f"W.statusToState({json.dumps(doc)})") == expected


def test_status_bad_input():
    assert run("W.statusToState('{nope')") is None
    assert run("W.statusToState(null)") is None


def test_priority_over_media_and_idle():
    assert run("W.chooseView(true,true,'clock')") == "dictation"
    assert run("W.chooseView(true,false,'weather')") == "dictation"
    assert run("W.chooseView(false,true,'clock')") == "media"
    assert run("W.chooseView(false,false,'weather')") == "weather"


def test_done_flash_timing():
    js = """(function(){
      var m = W.initial();
      m = W.step(m, 'recording', 1000);
      m = W.step(m, 'transcribing', 2000);
      m = W.step(m, 'idle', 3000);
      return [W.current(m,3000), W.current(m,4999), W.current(m,5000), W.isActive(m,4999), W.isActive(m,5000)];
    })()"""
    assert run(js) == ["done", "done", "idle", True, False]


def test_cancelled_recording_has_no_done_flash():
    js = """(function(){
      var m = W.step(W.initial(), 'recording', 1000);
      m = W.step(m, 'idle', 1500);
      return W.current(m,1501);
    })()"""
    assert run(js) == "idle"


def test_new_dictation_cancels_done_flash():
    js = """(function(){
      var m = W.step(W.step(W.step(W.initial(),'transcribing',0),'idle',10),'recording',500);
      return [W.current(m,501), W.step(m,'idle',900).doneUntil];
    })()"""
    assert run(js) == ["recording", 0]


def test_error_takeover_is_brief():
    js = """(function(){
      var m = W.step(W.initial(), 'error', 1000);
      return [W.current(m,1000), W.isActive(m,1000), W.isActive(m,1000+W.ERROR_MS), W.current(m,1000+W.ERROR_MS)];
    })()"""
    assert run(js) == ["error", True, False, "error"]


def test_not_running_inactive_and_unknown_ignored():
    assert run("W.isActive(W.initial(),0)") is False
    assert run("W.step(W.initial(),null,0).base") == "not-running"
    assert run("W.step(W.initial(),'bogus',0).base") == "not-running"


def test_display_text():
    assert run("W.displayText('recording')").endswith("Listening")
    assert run("W.displayText('transcribing')").endswith("Transcribing…")
    assert run("W.displayText('error')").endswith("Mic error")
    assert run("W.displayText('done')").endswith("Done")
    assert run("W.displayText('idle')") == ""
    assert run("W.displayText('not-running')") == ""
