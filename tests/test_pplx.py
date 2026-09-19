from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch, tmp_path):
    """Redirect the helpers' HOME so tests never touch the real journal."""
    monkeypatch.setattr(pplx_search, "HOME", tmp_path)
    monkeypatch.setattr(pplx_status, "HOME", tmp_path)


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
    assert "-n" in argv and "8" in argv


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
    assert calls[0]["argv"][1:] == ["get", pplx_search.OMASEAL_REF]
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


# --- history journal ----------------------------------------------------------

def _hist_file(tmp_path):
    return Path(tmp_path) / pplx_search.HISTORY_NAME


def _ok_search(query, tmp_path):
    run, calls = make_run({"pplx": _resp(json.dumps(HITS_PAYLOAD))})
    res = pplx_search.search(query, environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}),
                             state_dir=tmp_path)
    return res, calls


def test_history_appended_on_success(tmp_path) -> None:
    res, _ = _ok_search("first query", tmp_path)
    assert res["ok"] is True
    hist = json.loads(_hist_file(tmp_path).read_text())
    assert len(hist) == 1
    entry = hist[0]
    assert entry["query"] == "first query"
    assert entry["hits_count"] == 8      # 10 hits in payload, MAX_HITS caps at 8
    assert isinstance(entry["elapsed_ms"], int)
    assert isinstance(entry["at"], str) and "T" in entry["at"]
    # Newest first: a later search prepends.
    res, _ = _ok_search("second query", tmp_path)
    hist = json.loads(_hist_file(tmp_path).read_text())
    assert [e["query"] for e in hist] == ["second query", "first query"]
    # Published mode 0600 via the descriptor-relative pattern.
    assert (_hist_file(tmp_path).stat().st_mode & 0o777) == 0o600


def test_history_query_clipped(tmp_path) -> None:
    res, _ = _ok_search("x" * 300, tmp_path)
    assert res["ok"] is True
    hist = json.loads(_hist_file(tmp_path).read_text())
    assert len(hist[0]["query"]) == pplx_search.MAX_HISTORY_QUERY


def test_history_capped_at_30(tmp_path) -> None:
    _hist_file(tmp_path).write_text(json.dumps(
        [{"query": "old %d" % i, "hits_count": 1, "elapsed_ms": 1,
          "at": "2026-01-01T00:00:00+00:00"} for i in range(30)]))
    res, _ = _ok_search("fresh", tmp_path)
    assert res["ok"] is True
    hist = json.loads(_hist_file(tmp_path).read_text())
    assert len(hist) == 30
    assert hist[0]["query"] == "fresh"
    assert hist[-1]["query"] == "old 28"   # oldest entry dropped


def test_history_corrupt_file_tolerated(tmp_path) -> None:
    _hist_file(tmp_path).write_text("{not json!!")
    res, _ = _ok_search("q", tmp_path)
    assert res["ok"] is True
    hist = json.loads(_hist_file(tmp_path).read_text())
    assert [e["query"] for e in hist] == ["q"]


def test_history_not_written_on_failure(tmp_path, monkeypatch) -> None:
    recorded = []
    monkeypatch.setattr(pplx_search, "_record_history",
                        lambda *a, **k: recorded.append(a))
    for script in (
        {"pplx": _resp("", rc=1, err="boom")},
        {"pplx": _resp("", rc=None, timeout=True)},
    ):
        res = pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                                 run=make_run(script)[0],
                                 tool=make_tool({"pplx"}), state_dir=tmp_path)
        assert res["ok"] is False
    # needs_key and not-installed paths also skip the journal.
    pplx_search.search("q", environ={}, run=make_run({})[0],
                       tool=make_tool({"pplx"}), state_dir=tmp_path)
    pplx_search.search("q", environ={}, run=make_run({})[0],
                       tool=make_tool(set()), state_dir=tmp_path)
    assert recorded == []
    assert not _hist_file(tmp_path).exists()


def test_history_write_failure_does_not_break_emit(tmp_path) -> None:
    # state_dir is an existing regular file: mkdir/_open_dir fail and the
    # journal silently skips — the search emit must be untouched.
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    res, _ = _ok_search("q", blocker)
    assert res["ok"] is True
    assert len(res["hits"]) == 8


def test_main_stdout_has_no_history_key(capsys, monkeypatch) -> None:
    # The journal is a side file; the stdout contract is unchanged.
    monkeypatch.setattr(pplx_search, "search",
                        lambda *a, **k: {"ok": True, "needs_key": False,
                                         "installed": True, "hits": [],
                                         "error": None, "elapsed_ms": 1})
    rc = pplx_search.main(["pplx_search.py", "hello"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "history" not in data


# --- status helper ----------------------------------------------------------

def test_status_installed_authed_env() -> None:
    run, calls = make_run({})
    res = pplx_status.status(environ={"PERPLEXITY_API_KEY": SECRET},
                             run=run, tool=make_tool({"pplx"}),
                             copy_bin="/nonexistent-wl-copy")
    assert res == {"installed": True, "authed": True,
                   "copy_available": False, "history": []}
    assert calls == []  # env key short-circuits, no omaseal probe


def test_status_omaseal_authed() -> None:
    run, calls = make_run({"omaseal": _resp(SECRET + "\n")})
    res = pplx_status.status(environ={}, run=run,
                             tool=make_tool({"pplx", "omaseal"}),
                             copy_bin="/nonexistent-wl-copy")
    assert res == {"installed": True, "authed": True,
                   "copy_available": False, "history": []}
    assert len(calls) == 1


def test_status_no_key() -> None:
    run, _ = make_run({})
    res = pplx_status.status(environ={}, run=run, tool=make_tool({"pplx"}),
                             copy_bin="/nonexistent-wl-copy")
    assert res == {"installed": True, "authed": False,
                   "copy_available": False, "history": []}


def test_status_missing_binary() -> None:
    run, calls = make_run({})
    res = pplx_status.status(environ={}, run=run, tool=make_tool(set()),
                             copy_bin="/nonexistent-wl-copy")
    assert res == {"installed": False, "authed": False,
                   "copy_available": False, "history": []}
    assert calls == []


def test_status_emits_history_newest_first(tmp_path) -> None:
    entries = [{"query": "q%d" % i, "hits_count": i, "elapsed_ms": i * 10,
                "at": "2026-09-16T00:00:%02d+00:00" % i} for i in range(35)]
    (tmp_path / pplx_status.HISTORY_NAME).write_text(json.dumps(entries))
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path)
    assert res["installed"] is False
    # File is already newest-first; emit preserves order, capped at 30.
    assert len(res["history"]) == 30
    assert res["history"][0]["query"] == "q0"
    assert res["history"][-1]["query"] == "q29"


def test_status_history_missing_and_corrupt(tmp_path) -> None:
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path)
    assert res["history"] == []
    (tmp_path / pplx_status.HISTORY_NAME).write_text("[{bad json")
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path)
    assert res["history"] == []
    (tmp_path / pplx_status.HISTORY_NAME).write_text('{"not": "a list"}')
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path)
    assert res["history"] == []


def test_status_history_entry_normalization(tmp_path) -> None:
    (tmp_path / pplx_status.HISTORY_NAME).write_text(json.dumps([
        {"query": "ok", "hits_count": 3, "elapsed_ms": 42,
         "at": "2026-09-16T00:00:00+00:00"},
        {"query": ""},            # empty query dropped
        "not-a-dict",             # non-dict dropped
        {"query": "y" * 500, "hits_count": -1, "elapsed_ms": "big", "at": 42},
    ]))
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path)
    hist = res["history"]
    assert len(hist) == 2
    assert hist[0] == {"query": "ok", "hits_count": 3, "elapsed_ms": 42,
                       "at": "2026-09-16T00:00:00+00:00"}
    assert len(hist[1]["query"]) == pplx_status.MAX_HISTORY_QUERY
    assert hist[1]["hits_count"] == 0
    assert hist[1]["elapsed_ms"] == 0
    assert hist[1]["at"] == ""


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


# --- search option flags (KTD4) ------------------------------------------------

def _flagged_argv(opts):
    """Argv the helper would exec for a search under the given panel opts."""
    run, calls = make_run({"pplx": _resp(json.dumps(HITS_PAYLOAD))})
    pplx_search.search("q", environ={"PERPLEXITY_API_KEY": SECRET},
                       run=run, tool=make_tool({"pplx"}), opts=opts)
    return calls[0]["argv"]


def test_flag_mapping_recency_context_limit() -> None:
    argv = _flagged_argv({"recency": "week", "context": "high", "limit": "15"})
    assert argv[1:3] == ["search", "web"]
    i = argv.index("--recency-filter")
    assert argv[i + 1] == "week"
    i = argv.index("--search-context-size")
    assert argv[i + 1] == "high"
    i = argv.index("-n")
    assert argv[i + 1] == "15"
    assert argv[-2] == "--" and argv[-1] == "q"   # query stays last, terminated


def test_flag_allowlist_defaults() -> None:
    argv = _flagged_argv(None)
    assert argv[3:5] == ["-n", "8"]
    assert "--recency-filter" not in argv
    assert "--search-context-size" not in argv


def test_injection_shaped_values_dropped() -> None:
    for bad in ("week; rm -rf /", "../etc", "$(id)", "WEEK", "week ",
                "week --recency-filter day", "day\x00"):
        argv = _flagged_argv({"recency": bad})
        assert "--recency-filter" not in argv, bad
    for bad in ("high;id", "../x", "HIGH", "high ", "medium\x00"):
        argv = _flagged_argv({"context": bad})
        assert "--search-context-size" not in argv, bad
    # non-string / non-dict inputs can't reach argv either
    argv = _flagged_argv({"recency": ["week"], "context": 42, "limit": None})
    assert argv[3:5] == ["-n", "8"]
    assert "--recency-filter" not in argv
    assert "--search-context-size" not in argv
    assert pplx_search._search_flags("junk") == ["-n", "8"]


def test_limit_clamping() -> None:
    for bad in ("0", "21", "-3", "abc", "3.5", "", "0x10"):
        argv = _flagged_argv({"limit": bad})
        i = argv.index("-n")
        assert argv[i + 1] == "8", (bad, argv)
    for good in ("1", "10", "20"):
        argv = _flagged_argv({"limit": good})
        i = argv.index("-n")
        assert argv[i + 1] == good, (good, argv)


def test_parse_args_splits_opts_from_query() -> None:
    opts, tail = pplx_search._parse_args(
        ["--recency", "week", "--context", "high", "--limit", "12",
         "--", "real query"])
    assert opts == {"recency": "week", "context": "high", "limit": "12"}
    assert tail == ["real query"]
    # a query that is flag-shaped text stays byte-identical behind --
    opts, tail = pplx_search._parse_args(["--", "--recency", "week"])
    assert opts == {} and tail == ["--recency", "week"]
    # unknown flags are never consumed — they join the query tail
    opts, tail = pplx_search._parse_args(["--bogus", "x"])
    assert opts == {} and tail == ["--bogus", "x"]
    # a dangling known flag keeps its place in the query too
    opts, tail = pplx_search._parse_args(["--recency"])
    assert opts == {} and tail == ["--recency"]
    # values are consumed verbatim; validation happens in _search_flags
    opts, tail = pplx_search._parse_args(["--recency", "week; x", "q"])
    assert opts == {"recency": "week; x"} and tail == ["q"]


def test_main_passes_opts_and_query(capsys, monkeypatch) -> None:
    captured = {}

    def fake_search(query, **kw):
        captured["query"] = query
        captured["opts"] = kw.get("opts")
        return {"ok": True, "needs_key": False, "installed": True,
                "hits": [], "error": None, "elapsed_ms": 1}

    monkeypatch.setattr(pplx_search, "search", fake_search)
    rc = pplx_search.main(["pplx_search.py", "--recency", "week",
                           "--limit", "12", "--", "real query"])
    assert rc == 0
    assert captured["query"] == "real query"
    assert captured["opts"] == {"recency": "week", "limit": "12"}


# --- history delete verb ---------------------------------------------------------

def _seed_history(tmp_path, n=3):
    entries = [{"query": "q%d" % i, "hits_count": i, "elapsed_ms": i * 10,
                "at": "2026-09-16T00:00:%02d+00:00" % i} for i in range(n)]
    (tmp_path / pplx_status.HISTORY_NAME).write_text(json.dumps(entries))
    return entries


def test_delete_removes_exactly_one_preserves_order(tmp_path) -> None:
    _seed_history(tmp_path, 4)
    res = pplx_status.delete_history(1, state_dir=tmp_path)
    assert res["ok"] is True
    assert res["error"] is None
    hist = json.loads((tmp_path / pplx_status.HISTORY_NAME).read_text())
    assert [e["query"] for e in hist] == ["q0", "q2", "q3"]  # only q1 gone
    assert [e["query"] for e in res["history"]] == ["q0", "q2", "q3"]
    # rewritten atomically at 0600 like the search helper's journal
    assert ((tmp_path / pplx_status.HISTORY_NAME).stat().st_mode
            & 0o777) == 0o600


def test_delete_out_of_range_is_noop(tmp_path) -> None:
    _seed_history(tmp_path, 3)
    before = (tmp_path / pplx_status.HISTORY_NAME).read_text()
    for bad in (-1, 3, 99, None, "2", 1.5, True):
        res = pplx_status.delete_history(bad, state_dir=tmp_path)
        assert res["ok"] is False, bad
        assert res["error"], bad
        # the unchanged list still comes back for the panel
        assert [e["query"] for e in res["history"]] == ["q0", "q1", "q2"]
    assert (tmp_path / pplx_status.HISTORY_NAME).read_text() == before


def test_delete_missing_and_corrupt_history(tmp_path) -> None:
    res = pplx_status.delete_history(0, state_dir=tmp_path)
    assert res["ok"] is False and res["error"]
    assert not (tmp_path / pplx_status.HISTORY_NAME).exists()
    (tmp_path / pplx_status.HISTORY_NAME).write_text("{not json")
    res = pplx_status.delete_history(0, state_dir=tmp_path)
    assert res["ok"] is False and res["error"]
    # corrupt file left untouched — no destructive rewrite
    assert (tmp_path / pplx_status.HISTORY_NAME).read_text() == "{not json"


def test_delete_via_main_verb(capsys, tmp_path) -> None:
    # autouse fixture points HOME at tmp_path, so the journal lives nested.
    state_dir = tmp_path / ".local/state/omarchy/pplx"
    state_dir.mkdir(parents=True)
    (state_dir / pplx_status.HISTORY_NAME).write_text(json.dumps([
        {"query": "a", "hits_count": 1, "elapsed_ms": 1, "at": "t"},
        {"query": "b", "hits_count": 1, "elapsed_ms": 1, "at": "t"}]))
    rc = pplx_status.main(["pplx_status.py", "--delete", "1"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ok"] is True
    assert [e["query"] for e in data["history"]] == ["a"]
    # --delete with a non-integer index is an error, not a crash
    rc = pplx_status.main(["pplx_status.py", "--delete", "bogus"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ok"] is False and data["error"]


def test_delete_with_matching_tags_uses_rendered_index(tmp_path) -> None:
    entries = _seed_history(tmp_path, 3)
    res = pplx_status.delete_history(
        1, state_dir=tmp_path, at=entries[1]["at"], query=entries[1]["query"])
    assert res["ok"] is True
    hist = json.loads((tmp_path / pplx_status.HISTORY_NAME).read_text())
    assert [e["query"] for e in hist] == ["q0", "q2"]


def test_delete_tags_heal_a_shifted_index(tmp_path) -> None:
    # TOCTOU: the panel rendered [q0,q1,q2] and the user clicked q1 at
    # index 1 — but a search prepended qNew before the delete landed, so
    # index 1 now holds q0. The tags must retarget the delete to q1.
    entries = _seed_history(tmp_path, 3)
    target = entries[1]
    res = pplx_status.delete_history(
        1, state_dir=tmp_path, at=target["at"], query="q1")
    # sanity: plain index delete of the same position would remove q0's
    # slot contents — the tag proves identity wins.
    assert res["ok"] is True
    hist = json.loads((tmp_path / pplx_status.HISTORY_NAME).read_text())
    assert [e["query"] for e in hist] == ["q0", "q2"]

    # Now simulate the actual race: prepend a row, delete by the stale
    # index + tags — the new row survives and q1 still dies.
    entries = _seed_history(tmp_path, 3)
    state = tmp_path / pplx_status.HISTORY_NAME
    rows = json.loads(state.read_text())
    rows.insert(0, {"query": "qNew", "hits_count": 1, "elapsed_ms": 1,
                    "at": "2026-09-17T00:00:00+00:00"})
    state.write_text(json.dumps(rows))
    res = pplx_status.delete_history(
        1, state_dir=tmp_path, at=entries[1]["at"], query="q1")
    assert res["ok"] is True
    hist = json.loads(state.read_text())
    assert [e["query"] for e in hist] == ["qNew", "q0", "q2"]


def test_delete_tags_no_match_is_noop(tmp_path) -> None:
    _seed_history(tmp_path, 3)
    before = (tmp_path / pplx_status.HISTORY_NAME).read_text()
    res = pplx_status.delete_history(
        1, state_dir=tmp_path, at="1999-01-01T00:00:00+00:00",
        query="no such row")
    assert res["ok"] is False
    assert res["error"] == "history entry not found"
    assert [e["query"] for e in res["history"]] == ["q0", "q1", "q2"]
    assert (tmp_path / pplx_status.HISTORY_NAME).read_text() == before


def test_delete_tags_out_of_range_index_still_scans(tmp_path) -> None:
    # The list shrank between render and click — index 9 is gone, but the
    # tagged entry is still present and gets found by identity.
    entries = _seed_history(tmp_path, 2)
    res = pplx_status.delete_history(
        9, state_dir=tmp_path, at=entries[1]["at"], query="q1")
    assert res["ok"] is True
    hist = json.loads((tmp_path / pplx_status.HISTORY_NAME).read_text())
    assert [e["query"] for e in hist] == ["q0"]


def test_delete_tags_via_main_verb(capsys, tmp_path) -> None:
    state_dir = tmp_path / ".local/state/omarchy/pplx"
    state_dir.mkdir(parents=True)
    (state_dir / pplx_status.HISTORY_NAME).write_text(json.dumps([
        {"query": "a", "hits_count": 1, "elapsed_ms": 1, "at": "ta"},
        {"query": "b", "hits_count": 1, "elapsed_ms": 1, "at": "tb"}]))
    rc = pplx_status.main(
        ["pplx_status.py", "--delete", "0", "--at", "tb", "--query", "b"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ok"] is True
    # index 0 tagged as b's identity -> scan finds b at index 1, a survives
    assert [e["query"] for e in data["history"]] == ["a"]
    # A flag-shaped query value is consumed verbatim as the tag, never
    # parsed as another flag.
    rc = pplx_status.main(
        ["pplx_status.py", "--delete", "0", "--at", "ta", "--query", "--at"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ok"] is False and data["error"]


def test_copy_available_flag(tmp_path) -> None:
    fake = tmp_path / "wl-copy"
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path,
                             copy_bin=str(fake))
    assert res["copy_available"] is False
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path,
                             copy_bin=str(fake))
    assert res["copy_available"] is True
    # a non-executable file doesn't count either
    fake.chmod(0o644)
    res = pplx_status.status(environ={}, run=make_run({})[0],
                             tool=make_tool(set()), state_dir=tmp_path,
                             copy_bin=str(fake))
    assert res["copy_available"] is False


# --- panel wiring (structural greps, same style as test_manifests) ---------------

PANEL = ROOT / "plugins/io.github.duketopceo.pplx/Panel.qml"


def test_panel_copy_gate_https_only() -> None:
    # copyHit() shares openHit's scheme gate and execs the fixed wl-copy
    # path detached with the URL as the sole argv element — non-https
    # can never reach the clipboard tool.
    panel = PANEL.read_text()
    for fn in ("function openHit", "function copyHit"):
        gate = panel.index(fn)
        seg = panel[gate:gate + 700]
        assert "/^https:\\/\\//" in seg, fn
    assert 'execDetached(["/usr/bin/wl-copy", url])' in seg
    # http:// is deliberately not admitted anywhere in either gate.
    assert "/^https?:\\/\\//" not in panel


def test_panel_chips_and_delete_wiring() -> None:
    panel = PANEL.read_text()
    # chip state maps to the helper's allowlisted flag pairs behind --
    assert 'cmd.push("--recency", root.recency)' in panel
    assert 'cmd.push("--context", root.context)' in panel
    assert 'cmd.push("--", q)' in panel
    # history ✕ runs the status helper's delete verb with the row index
    # plus the entry's at/query tags so a racing insert can't retarget it
    assert '"--delete", String(index)' in panel
    assert '"--at", String(row.at || "")' in panel
    assert '"--query", String(row.query || "")' in panel
    # no hardcoded colors anywhere (repo rule)
    import re as _re
    assert _re.search(r"#[0-9a-fA-F]{3,8}\b", panel) is None


def test_panel_cancel_and_status_wiring() -> None:
    panel = PANEL.read_text()
    # A user kill is flagged so the empty-stdout path can't banner it.
    assert "searchCancelled = true" in panel
    assert "root.searchCancelled = false" in panel
    # A dead status helper still resolves the pill — no CHECKING forever.
    assert 'if (!text || text.trim().length === 0) { root.statusKnown = true; return }' in panel
    # every helper exec collects stderr (cross-plugin sweep contract)
    assert panel.count("stderr: StdioCollector") >= 3
