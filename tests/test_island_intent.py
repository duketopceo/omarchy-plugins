"""Intent.js (pointer-speed filter for hover open) for the Island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

INTENT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Intent.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const I=require({json.dumps(str(INTENT))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def feed(points):
    """Add [x, y, t] samples in order from an empty list; return the final list."""
    return f"{json.dumps(points)}.reduce((s,p)=>I.add(s,p[0],p[1],p[2]),[])"


def sweep(x0, x1, t0, t1, steps):
    return [[x0 + (x1 - x0) * i / steps, 10, t0 + (t1 - t0) * i / steps] for i in range(steps + 1)]


def test_fast_sweep_ending_now_is_moving():
    # 200 px in 100 ms: 2 px/ms, last sample at "now".
    assert run(f"I.moving({feed(sweep(0, 200, 1000, 1100, 10))}, 1100)") is True


def test_one_px_per_ms_still_moving_at_timer():
    # About 1 px/ms, still in motion when the 140 ms open timer fires.
    assert run(f"I.moving({feed(sweep(0, 140, 1000, 1140, 14))}, 1140)") is True


def test_resting_pointer_is_not_moving():
    # The sweep ended 100 ms before the check: nothing inside the window.
    assert run(f"I.moving({feed(sweep(0, 200, 1000, 1100, 10))}, 1200)") is False


def test_slow_drift_is_not_moving():
    # 0.2 px/ms over 160 ms reads as an arriving pointer.
    assert run(f"I.moving({feed(sweep(0, 32, 1000, 1160, 16))}, 1160)") is False


def test_single_sample_is_not_moving():
    assert run(f"I.moving({feed([[5, 5, 1000]])}, 1000)") is False
    assert run("I.moving([], 1000)") is False
    assert run("I.moving(null, 1000)") is False


def test_vertical_motion_counts():
    pts = [[50, y * 10, 1000 + y * 8] for y in range(11)]  # 1.25 px/ms downward
    assert run(f"I.moving({feed(pts)}, 1080)") is True


def test_add_caps_and_trims():
    out = run(f"{feed(sweep(0, 400, 1000, 1400, 40))}")
    assert len(out) <= I_MAX
    # Only samples inside the keep window survive.
    assert all(s["t"] >= 1400 - 150 for s in out)
    assert out[-1]["x"] == 400 and out[-1]["t"] == 1400


def test_add_does_not_mutate_input():
    assert run("(()=>{const a=[];I.add(a,1,2,3);return a.length})()") == 0


def test_stale_samples_before_a_gap_are_dropped():
    # A burst long ago, then one sample now: no motion inside the window.
    pts = sweep(0, 200, 0, 100, 10) + [[200, 10, 5000]]
    assert run(f"I.moving({feed(pts)}, 5000)") is False


I_MAX = 12

HOVER = INTENT.with_name("Hover.js")


def simulate(points, enter_t, leave_t, until):
    """Drive Hover.js like IslandWindow.qml does: motion samples feed Intent.js,
    the open timer carries `moving`, a leave at leave_t (or None). Returns the
    final state and when it opened (or None)."""
    js = (
        f"const I=require({json.dumps(str(INTENT))});const H=require({json.dumps(str(HOVER))});"
        f"const pts={json.dumps(points)};const enterT={enter_t};const leaveT={json.dumps(leave_t)};"
        "let m=H.initial(),s=[],due=null,opened=null,inside=false;"
        "function send(e,t){const r=H.step(m,e,null);m=r.model;if(r.timer>0)due=t+r.timer;else if(r.timer===0)due=null;"
        "if(m.state==='open'&&opened===null)opened=t}"
        f"for(let t=0;t<={until};t++){{"
        "for(const p of pts)if(p[2]===t&&(leaveT===null||t<leaveT))s=I.add(s,p[0],p[1],t);"
        "if(t===enterT){inside=true;send('enter',t)}"
        "if(leaveT!==null&&t===leaveT){inside=false;s=[];send('leave',t)}"
        "if(due!==null&&t>=due){due=null;send({type:'timer',hovered:inside,moving:I.moving(s,t)},t)}}"
        "console.log(JSON.stringify({state:m.state,opened}))"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def test_hover_check_stepped_move_still_opens_on_time():
    # island-hover-check: 25 px steps every 15 ms (about 1.7 px/ms), entering
    # the pill three steps before the end, then resting.
    pts = [[i * 25, 10, i * 15] for i in range(13)]
    out = simulate(pts, enter_t=135, leave_t=None, until=600)
    assert out["state"] == "open" and out["opened"] == 135 + 140


def test_passing_pointer_never_opens():
    # About 1 px/ms across a 300 px pill: still moving when the 140 ms timer
    # fires, gone at 300 ms.
    pts = [[i * 8, 10, i * 8] for i in range(60)]
    out = simulate(pts, enter_t=0, leave_t=300, until=800)
    assert out["state"] == "closed" and out["opened"] is None


def test_slowing_pointer_opens_after_it_settles():
    # Fast for 200 ms, then stops on the pill: opens once the window clears.
    pts = [[i * 10, 10, i * 8] for i in range(26)]
    out = simulate(pts, enter_t=0, leave_t=None, until=800)
    assert out["state"] == "open" and 200 < out["opened"] <= 200 + 80 + 40 + 1
