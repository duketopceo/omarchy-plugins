"""Timer.js (timer and pomodoro) for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

MIN = 60_000


def run(expr):
    js = (
        f"const T=require({json.dumps(str(NOTCH / 'Timer.js'))});"
        f"const M=require({json.dumps(str(NOTCH / 'Model.js'))});"
        f"const D=require({json.dumps(str(NOTCH / 'Dayflow.js'))});"
        f"const A=require({json.dumps(str(NOTCH / 'Activity.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def started(minutes=10, now=1_000):
    return run(f"T.start(T.initial(),'timer',{minutes},{now})")


def test_start_pause_resume_cancel():
    m = started(10)
    assert m["state"] == "running" and m["endsAt"] == 1_000 + 10 * MIN
    assert run(f"T.remaining({json.dumps(m)},{1_000 + 4 * MIN})") == 6 * MIN
    p = run(f"T.pause({json.dumps(m)},{1_000 + 4 * MIN})")
    assert p["state"] == "paused" and p["remainingMs"] == 6 * MIN
    assert run(f"T.remaining({json.dumps(p)},{1_000 + 99 * MIN})") == 6 * MIN  # paused time stands still
    r = run(f"T.resume({json.dumps(p)},{50 * MIN})")
    assert r["state"] == "running" and r["endsAt"] == 56 * MIN
    c = run(f"T.cancel({json.dumps(r)})")
    assert c["state"] == "idle" and run(f"T.remaining({json.dumps(c)},1)") == 0


def test_invalid_states_are_ignored():
    idle = run("T.initial()")
    assert run(f"T.pause({json.dumps(idle)},5)") == idle
    assert run(f"T.resume({json.dumps(idle)},5)") == idle
    assert run("T.start(T.initial(),'timer',0,0)")["totalMs"] == MIN  # at least a minute


def test_ear_shows_remaining_time_and_pause():
    m = started(10)
    assert run(f"T.slotText({json.dumps(m)},{1_000 + 4 * MIN + 30_000})") == "⏱ 5:30"
    p = run(f"T.pause({json.dumps(m)},{1_000 + 4 * MIN})")
    assert run(f"T.slotText({json.dumps(p)},{99 * MIN})") == "⏸ 6:00"
    assert run("T.slotText(T.initial(),5)") == ""
    assert run("T.fmt(3723000)") == "1:02:03" and run("T.fmt(0)") == "0:00" and run("T.fmt(1)") == "0:01"


def test_finishing_notifies_exactly_once():
    m = started(5)
    end = 1_000 + 5 * MIN
    before = run(f"T.tick({json.dumps(m)},{end - 1})")
    assert before["notify"] is None and before["model"]["state"] == "running"
    fin = run(f"T.tick({json.dumps(m)},{end})")
    assert fin["notify"]["title"] == "Timer done" and fin["model"]["state"] == "idle"
    again = run(f"T.tick({json.dumps(fin['model'])},{end + 5000})")
    assert again["notify"] is None
    late = run(f"T.tick({json.dumps(m)},{end + 99_000})")  # woke from suspend long after
    assert late["notify"]["title"] == "Timer done"
    assert run(f"T.tick({json.dumps(late['model'])},{end + 100_000})")["notify"] is None


def test_done_flash_is_an_activity_for_eight_seconds():
    m = started(5)
    end = 1_000 + 5 * MIN
    fin = run(f"T.tick({json.dumps(m)},{end})")["model"]
    assert run(f"T.doneActive({json.dumps(fin)},{end + 100})") is True
    assert run(f"T.doneActive({json.dumps(fin)},{end + run('T.DONE_MS')})") is False
    assert run("T.DONE_PRIORITY") == 85
    act = {"id": "timer", "active": True, "priority": 85, "text": fin["doneText"]}
    assert run(f"A.pick([{json.dumps(act)},{{id:'media',active:true,priority:50,text:'x'}}]).id") == "timer"
    assert run(f"A.pick([{json.dumps(act)},{{id:'dictation',active:true,priority:90,text:'y'}}]).id") == "dictation"


def test_notify_argv_is_one_notify_send_call():
    assert run("T.notifyArgs({title:'Timer done',body:'5:00 elapsed'})") == ["notify-send", "-a", "Notch", "Timer done", "5:00 elapsed"]


def test_pomodoro_cycles_focus_break_and_long_break():
    m = run("T.start(T.initial(),'pomodoro',99,0)")
    assert m["phase"] == "focus" and m["totalMs"] == 25 * MIN
    t = 0
    seen = []
    for _ in range(8):
        t = m["endsAt"]
        r = run(f"T.tick({json.dumps(m)},{t})")
        assert r["notify"] is not None
        m = r["model"]
        assert m["state"] == "ready"  # waits for Start; never auto-runs
        seen.append(m["phase"])
        m = run(f"T.resume({json.dumps(m)},{t + 1000})")
        assert m["state"] == "running"
    assert seen == ["rest", "focus", "rest", "focus", "rest", "focus", "long", "focus"]


def test_pomodoro_ready_state_shows_next_phase_length_and_no_ear_slot():
    m = run("T.start(T.initial(),'pomodoro',0,0)")
    r = run(f"T.tick({json.dumps(m)},{25 * MIN})")
    assert r["model"]["remainingMs"] == 5 * MIN and r["notify"]["body"] == "Next: Break 5:00"
    assert run(f"T.slotText({json.dumps(r['model'])},{25 * MIN})") == ""


def test_timer_shares_the_idle_slot_with_dayflow_by_rotation():
    running = started(10)
    views = run(f"T.idleViews(D.idleViews(['weather'],true,{{ok:true,recording:true}},{{current:{{category:'work'}},streakMin:5}}),{json.dumps(running)})")
    assert views[:2] == ["weather", "dayflow"] and views[-1] == "timer"
    # every view gets its turn: the slot rotates, nothing is replaced
    slide = 7
    shown = [run(f"M.idleSlot({n * slide},{json.dumps(views)},{slide})") for n in range(len(views))]
    assert sorted(shown) == sorted(views)
    assert run("T.idleViews(['weather'],T.initial())") == ["weather"]
    paused = run(f"T.pause({json.dumps(running)},5000)")
    assert "timer" in run(f"T.idleViews([],{json.dumps(paused)})")


def test_progress_runs_zero_to_one():
    m = started(10, 0)
    assert run(f"T.progress({json.dumps(m)},0)") == 0
    assert run(f"T.progress({json.dumps(m)},{5 * MIN})") == 0.5
    assert run(f"T.progress({json.dumps(m)},{20 * MIN})") == 1
    assert run("T.progress(T.initial(),5)") == 0
