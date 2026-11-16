"""Agents.js for the notch island (herdr agent status, AI usage), run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plugins/io.github.duketopceo.notch/Agents.js"
FIX = ROOT / "tests/fixtures/notch-agents"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr, **env):
    js = f"const A=require({json.dumps(str(MODULE))});{''.join(f'const {k}={json.dumps(v)};' for k, v in env.items())}console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


LS = (FIX / "herdr-ls.json").read_text()
USAGE = (FIX / "usage.json").read_text()


def ls(doc):
    return run("A.parseLs(t)", t=json.dumps(doc))


def term(status, app="devin", tid="t1", **kw):
    return {"terminal": tid, "pane": "p", "status": status, "app": app, "sub_agents": [], **kw}


def one(*terms):
    return {"spaces": [{"id": "s", "name": "S", "machine": None, "tabs": [{"id": "b", "name": "tab", "terminals": list(terms)}]}]}


def test_parse_ls_counts_and_groups():
    s = run("A.parseLs(t)", t=LS)
    assert s["ok"] and s["total"] == 6  # plain shell skipped
    assert s["counts"] == {"working": 2, "blocked": 1, "done": 1, "idle": 2}
    assert [g["space"] for g in s["groups"]] == ["Home", "Project", "Remote"]  # blocked space first
    assert s["groups"][2]["machine"] == "box1"
    assert s["groups"][0]["agents"][0]["status"] == "blocked"
    assert s["groups"][0]["agents"][0]["appName"] == "Codex"
    assert s["groups"][2]["agents"][0]["terminal"] == "box1/t1"


def test_parse_ls_invalid():
    for bad in ["", "nope", "{}", '{"spaces": 3}']:
        s = run("A.parseLs(t)", t=bad)
        assert s["ok"] is False and s["total"] == 0


def test_sub_agents_counted():
    s = ls(one(term("idle", sub_agents=[term("working", tid="t2")])))
    assert s["counts"]["working"] == 1 and s["total"] == 2


@pytest.mark.parametrize("status,prio", [("blocked", 80), ("done", 40), ("working", 10), ("idle", 0), (None, 0), ("weird", 0)])
def test_status_priority(status, prio):
    assert run("A.statusPriority(s)", s=status) == prio


def test_activity_from_fixture():
    s = run("A.parseLs(t)", t=LS)
    assert run("[A.isActive(s), A.priority(s), A.activityText(s), A.glyph(s), A.badgeText(s)]", s=s) == [True, 80, "Codex needs you", "!", "● 2"]


@pytest.mark.parametrize("terms,expect", [
    ([term("blocked"), term("blocked", tid="t2")], [True, 80, "2 need you"]),
    ([term("done", app="claude-code")], [False, 40, "Claude done"]),
    ([term("done"), term("done", tid="t2")], [False, 40, "2 done"]),  # "done" never takes the collapsed notch
    ([term("working"), term("working", tid="t2"), term("working", tid="t3")], [False, 0, "3 working"]),
    ([term("idle")], [False, 0, ""]),
    ([term("blocked"), term("done", tid="t2")], [True, 80, "Devin needs you"]),
])
def test_activity_cases(terms, expect):
    s = ls(one(*terms))
    assert run("[A.isActive(s), A.priority(s), A.activityText(s)]", s=s) == expect


def test_badge_empty_when_nothing_working():
    s = ls(one(term("idle")))
    assert run("A.badgeText(s)", s=s) == ""
    assert run("A.badgeText(s)", s=ls({"spaces": []})) == ""


def test_parse_usage_fixture():
    u = run("A.parseUsage(t)", t=USAGE)
    assert u["ok"]
    assert [p["id"] for p in u["providers"]] == ["anthropic", "cursor"]  # errored provider dropped
    claude = u["providers"][0]
    assert claude["name"] == "Claude"
    assert [r["label"] for r in claude["rows"]][:2] == ["Session (5h)", "Weekly (7d)"]
    assert [r["percent"] for r in claude["rows"]][:2] == [10, 63]
    assert claude["rows"][1]["severity"] == "mid"
    assert claude["rows"][0]["resetAt"] == "2026-11-04T12:50:00Z"


def test_parse_usage_invalid_and_clamp():
    assert run("A.parseUsage(t)", t="x")["ok"] is False
    assert run("A.parseUsage(t)", t="{}")["ok"] is False
    doc = {"entries": [{"id": "a", "sections": [{"type": "metric", "label": "x", "percent": 250}, {"type": "metric", "percent": "n/a"}]}]}
    u = run("A.parseUsage(t)", t=json.dumps(doc))
    assert u["providers"][0]["rows"] == [{"label": "x", "percent": 100, "resetAt": "", "severity": "critical"}]


@pytest.mark.parametrize("delta_min,expect", [(-5, "now"), (12, "12m"), (206, "3h 26m"), (3 * 1440 + 300, "3d 5h")])
def test_reset_in(delta_min, expect):
    now = 1_800_000_000_000
    iso = run("new Date(n + d * 60000).toISOString()", n=now, d=delta_min)
    assert run("A.resetIn(i, n)", i=iso, n=now) == expect
    assert run("A.resetIn('', 0)") == ""


def test_top_usage_picks_the_busiest_metric_across_providers():
    usage = {"ok": True, "providers": [
        {"id": "a", "name": "Alpha", "rows": [{"percent": 16}, {"percent": 64}]},
        {"id": "b", "name": "Beta", "rows": [{"percent": 40}]},
    ]}
    assert run("A.topUsage(u)", u=usage) == {"name": "Alpha", "percent": 64}
    assert run("A.topUsage(null)") is None
    assert run("A.topUsage({ok:false,providers:[]})") is None
    assert run("A.topUsage({ok:true,providers:[]})") is None


def test_pretty_app_name():
    assert run("A.prettyApp('com.example.herdr-app')") == "Herdr app"
    assert run("A.prettyApp('foot')") == "Foot"
    assert run("A.prettyApp('')") == "" and run("A.prettyApp(null)") == ""


def test_counts_text_and_totals():
    assert run("A.countsText({working:2,blocked:1,done:0,idle:0})") == "1 needs you · 2 working"
    assert run("A.countsText({working:0,blocked:0,done:0,idle:0})") == ""
    assert run("A.totalsText(A.parseLs(t))", t=LS) == "6 agents"
    assert run("A.totalsText(A.parseLs(''))") == "No agents"


def test_group_model_order_and_keys():
    g = run("A.groupModel(A.parseLs(t))", t=LS)
    assert [x["key"] for x in g] == ["Home", "Project", "box1/Remote"]
    assert g[0]["blocked"] is True and g[0]["countsText"].startswith("1 needs you")


def test_collapsed_set_and_auto_expand():
    blocked = {"key": "Home", "blocked": True}
    plain = {"key": "Project", "blocked": False}
    assert run("A.isCollapsed(['Home','Project'], g)", g=blocked) is False
    assert run("A.isCollapsed(['Home','Project'], g)", g=plain) is True
    assert run("A.toggleCollapsed(['Home'], g)", g=plain) == ["Home", "Project"]
    assert run("A.toggleCollapsed(['Project'], g)", g=plain) == []
    assert run("A.normCollapsed('x')") == []
    cfg = {"plugins": [{"id": "p", "agents.collapsed": ["a", 3, ""]}]}
    assert run("A.readCollapsed(c, 'p')", c=cfg) == ["a"]
    assert run("A.readCollapsed(null, 'p')") == []


def test_icon_mapping():
    assert run("A.iconFor('claude-code')")["file"] == "claude.svg"
    d = run("A.iconFor('devin')")
    assert d["file"] == "" and d["monogram"] == "D"
    assert run("A.iconFor(null)")["monogram"] == "A"


def test_status_label():
    assert [run("A.statusLabel(s)", s=s) for s in ["blocked", "done", "working", None]] == ["needs you", "done", "working", "idle"]


def test_usage_rows_top3_and_expand():
    usage = {"ok": True, "providers": [
        {"id": c, "name": c.upper(), "rows": [{"label": "w", "percent": p, "resetAt": "2026-11-04T13:00:00Z", "severity": sev}]}
        for c, p, sev in [("a", 10, "low"), ("b", 95, "critical"), ("c", 60, "mid"), ("d", 80, "high")]]}
    now = 1_793_800_000_000  # 2026-11-04T..Z area; only used for formatting
    r = run("A.usageRows(u, n, false, 3)", u=usage, n=now)
    assert [x["id"] for x in r["rows"]] == ["b", "d", "c"] and r["hidden"] == 1
    assert [x["severity"] for x in r["rows"]] == ["critical", "warn", "warn"]
    assert run("A.usageRows(u, n, true, 3)", u=usage, n=now)["hidden"] == 0
    assert run("A.usageRows(null, 0, false, 3)")["rows"] == []


@pytest.mark.parametrize("delta_min,expect", [(-1, "now"), (12, "12m"), (206, "3h"), (3 * 1440 + 300, "3d")])
def test_reset_short(delta_min, expect):
    now = 1_800_000_000_000
    iso = run("new Date(n + d * 60000).toISOString()", n=now, d=delta_min)
    assert run("A.resetShort(i, n)", i=iso, n=now) == expect
