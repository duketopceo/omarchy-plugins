from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "plugins/io.github.duketopceo.pplx/bin/pplx_search.py"
STATUS = ROOT / "plugins/io.github.duketopceo.pplx/bin/pplx_status.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


pplx_search = load(SEARCH, "pplx_search")
pplx_status = load(STATUS, "pplx_status")

SECRET = "pplx-secret-TESTKEY-0123456789"

HITS_PAYLOAD = {
    "hits": [
        {
            "title": "Title %d" % i,
            "url": "https://example%d.com/page" % i,
            "snippet": "snippet %d" % i,
            "date": "2026-09-1%d" % i,
        }
        for i in range(10)
    ],
    "total": 10,
}

OK = {"rc": 0, "err": "", "timeout": False, "overflow": False}


def _resp(out="", **kw):
    r = dict(OK)
    r["out"] = out
    r.update(kw)
    return r


def make_tool(present):
    def tool(name):
        return "/fake/bin/%s" % name if name in present else None
    return tool


def make_run(script):
    """Fake _run: script maps an argv[0] substring to a canned result dict.

    Returns (run, calls); every call records argv/timeout/cap/extra_env.
    """
    calls = []

    def run(argv, timeout=2.0, cap=262144, extra_env=None):
        calls.append({
            "argv": list(argv),
            "timeout": timeout,
            "cap": cap,
            "extra_env": dict(extra_env or {}),
        })
        for frag, resp in script.items():
            if frag in argv[0]:
                return dict(resp)
        return dict(OK, out="")

    return run, calls


# --- capability degradation ------------------------------------------------

def test_missing_binary_no_exec() -> None:
    run, calls = make_run({})
    res = pplx_search.search("hello", environ={}, run=run, tool=make_tool(set()))
    assert res["installed"] is False
    assert res["ok"] is False
    assert res["needs_key"] is False
    assert res["hits"] == []
    assert isinstance(res["elapsed_ms"], int)
    assert calls == []
    json.dumps(res)


def test_no_key_needs_key_no_exec() -> None:
    # pplx present, no env key, omaseal absent -> needs_key, pplx never exec'd.
    run, calls = make_run({})
    res = pplx_search.search("q", environ={}, run=run, tool=make_tool({"pplx"}))
    assert res["installed"] is True
    assert res["needs_key"] is True
    assert res["ok"] is False
    assert calls == []


def test_omaseal_empty_needs_key() -> None:
    run, calls = make_run({
        "omaseal": _resp("", rc=1, err="not found"),
    })
    res = pplx_search.search("q", environ={}, run=run,
                             tool=make_tool({"pplx", "omaseal"}))
    assert res["needs_key"] is True
    assert res["ok"] is False
    # omaseal probed once, pplx never executed.
    assert len(calls) == 1
    assert "omaseal" in calls[0]["argv"][0]


# --- key handling ----------------------------------------------------------

def test_env_key_injected_never_on_argv() -> None:
    run, calls = make_run({
        "pplx": _resp(json.dumps(HITS_PAYLOAD)),
    })
    res = pplx_search.search("rust async", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["ok"] is True
    assert len(calls) == 1  # env key short-circuits; no omaseal probe
    assert calls[0]["extra_env"].get("PERPLEXITY_API_KEY") == SECRET
    assert all(SECRET not in a for a in calls[0]["argv"])
    argv = calls[0]["argv"]
    assert argv[1:3] == ["search", "web"]
    assert "--limit" in argv and "8" in argv


def test_omaseal_key_resolution() -> None:
    run, calls = make_run({
        "omaseal": _resp(SECRET + "\n"),
        "pplx": _resp(json.dumps(HITS_PAYLOAD)),
    })
    res = pplx_search.search("q", environ={}, run=run,
                             tool=make_tool({"pplx", "omaseal"}))
    assert res["ok"] is True
    assert len(calls) == 2
    assert "omaseal" in calls[0]["argv"][0]
    assert calls[0]["argv"][1:] == ["resolve", "omaseal://perplexity/api-key"]
    assert "pplx" in calls[1]["argv"][0]
    assert calls[1]["extra_env"]["PERPLEXITY_API_KEY"] == SECRET
    assert all(SECRET not in a for a in calls[1]["argv"])


def test_key_never_in_emitted_json() -> None:
    # A valid error JSON whose message echoes the key must be redacted.
    run, _ = make_run({
        "pplx": _resp("", rc=1, err=json.dumps(
            {"error": {"code": "UPSTREAM", "message": "leak " + SECRET}})),
    })
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    blob = repr(res) + json.dumps(res)
    assert SECRET not in blob
    assert "***" in (res["error"] or "")

    # Same guarantee if the key shows up inside hit fields.
    payload = {"hits": [{"title": "t " + SECRET,
                         "url": "https://x.io/?k=" + SECRET,
                         "snippet": SECRET, "date": "d"}]}
    run, _ = make_run({"pplx": _resp(json.dumps(payload))})
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["ok"] is True
    assert SECRET not in repr(res) + json.dumps(res)


# --- result mapping ---------------------------------------------------------

def test_hits_compaction_and_clipping() -> None:
    payload = {"hits": [
        {"title": "Big", "url": "https://deep.sub.example.co.uk/a?b=c",
         "snippet": "x" * 500 + "\x07\x1f", "published_date": "2026-09-16"},
        {"title": "No URL", "snippet": "skip me"},
        {"title": "Ctrl\tName\n", "url": "http://b.io", "snippet": "ok"},
        "not-a-dict",
        {"title": "F", "url": "notaurl", "snippet": "s"},
    ]}
    run, _ = make_run({"pplx": _resp(json.dumps(payload))})
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["ok"] is True
    hits = res["hits"]
    assert len(hits) == 3  # no-url entry and non-dict dropped
    assert hits[0]["domain"] == "deep.sub.example.co.uk"
    assert len(hits[0]["snippet"]) <= 200
    assert all(ord(c) >= 0x20 for c in hits[0]["snippet"])
    assert hits[0]["date"] == "2026-09-16"  # date-ish fallback field
    assert hits[1]["domain"] == "b.io"
    assert hits[1]["title"] == "Ctrl Name"
    assert hits[2]["domain"] == ""


def test_hits_capped_at_eight() -> None:
    run, _ = make_run({"pplx": _resp(json.dumps(HITS_PAYLOAD))})
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["ok"] is True
    assert len(res["hits"]) == 8


def test_stderr_authentication_needs_key() -> None:
    run, _ = make_run({
        "pplx": _resp("", rc=1, err=json.dumps(
            {"error": {"code": "AUTHENTICATION", "message": "invalid api key"}})),
    })
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["needs_key"] is True
    assert res["ok"] is False
    assert "invalid api key" in (res["error"] or "")


def test_stderr_nonjson_generic_error() -> None:
    run, _ = make_run({
        "pplx": _resp("", rc=2, err="panic: something raw " + SECRET),
    })
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["ok"] is False
    assert res["needs_key"] is False
    assert res["error"] == "search failed (rc=2)"
    assert SECRET not in repr(res)  # raw stderr never surfaces


def test_timeout() -> None:
    run, _ = make_run({
        "pplx": _resp("", rc=None, timeout=True),
    })
    res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res["ok"] is False
    assert res["error"] == "timeout"


def test_shell_metachars_single_argv() -> None:
    query = ';$(rm -rf /);`id`&&cat|sh "lit"'
    run, calls = make_run({"pplx": _resp('{"hits": []}')})
    pplx_search.search(query, environ={"PERPLEXITY_API_KEY": SECRET},
                       run=run, tool=make_tool({"pplx"}))
    argv = calls[0]["argv"]
    assert argv[-1] == query           # one argv element, byte-identical
    assert argv.count(query) == 1


def test_leading_dash_query_not_a_flag() -> None:
    query = "-n 5 hack"
    run, calls = make_run({"pplx": _resp('{"hits": []}')})
    pplx_search.search(query, environ={"PERPLEXITY_API_KEY": SECRET},
                       run=run, tool=make_tool({"pplx"}))
    argv = calls[0]["argv"]
    assert argv[-1] == query
    assert argv[-2] == "--"            # flag terminator precedes the query


# --- status helper ----------------------------------------------------------

def test_status_installed_authed_env() -> None:
    run, calls = make_run({})
    res = pplx_status.status(environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}))
    assert res == {"installed": True, "authed": True}
    assert calls == []  # env key short-circuits, no omaseal probe


def test_status_omaseal_authed() -> None:
    run, calls = make_run({"omaseal": _resp(SECRET + "\n")})
    res = pplx_status.status(environ={}, run=run,
                             tool=make_tool({"pplx", "omaseal"}))
    assert res == {"installed": True, "authed": True}
    assert len(calls) == 1


def test_status_no_key() -> None:
    run, _ = make_run({})
    res = pplx_status.status(environ={}, run=run, tool=make_tool({"pplx"}))
    assert res == {"installed": True, "authed": False}


def test_status_missing_binary() -> None:
    run, calls = make_run({})
    res = pplx_status.status(environ={}, run=run, tool=make_tool(set()))
    assert res == {"installed": False, "authed": False}
    assert calls == []


# --- real _run hardening (no fakes) -----------------------------------------

def test_real_run_echo() -> None:
    res = pplx_search._run(["/bin/echo", "hi"], timeout=2.0, cap=1024)
    assert res["rc"] == 0
    assert res["out"].strip() == "hi"
    assert res["timeout"] is False
    assert res["overflow"] is False


def test_real_run_timeout_kills_group() -> None:
    res = pplx_search._run(["/bin/sleep", "30"], timeout=0.4, cap=1024)
    assert res["timeout"] is True
    assert res["rc"] in (-15, -9)


def test_real_run_byte_cap() -> None:
    res = pplx_search._run(
        ["/bin/sh", "-c", "head -c 1000000 /dev/zero | tr '\\0' 'a'"],
        timeout=3.0, cap=1024)
    assert res["overflow"] is True
    assert len(res["out"]) <= 1024 + 65536


# --- CLI surface ------------------------------------------------------------

def test_main_usage_error(capsys) -> None:
    rc = pplx_search.main(["pplx_search.py"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc == 2
    assert data["ok"] is False
    assert "usage" in (data["error"] or "")
