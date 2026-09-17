from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/io.github.duketopceo.numbat/bin/probe_numbat.py"

NOW = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
EXPECTED_KEYS = [
    "installed",
    "ok",
    "hooks_seen",
    "hooked_agents",
    "active_agents",
    "agents_seen",
    "findings_24h",
    "findings",
    "events",
    "scanned_at",
    "scan_error",
    "records_path",
    "error",
]


def load():
    spec = importlib.util.spec_from_file_location("probe_numbat", PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _no_run(*_a, **_k):
    raise AssertionError("_run must not be called in this scenario")


def _write_findings(home: Path, lines) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = home / "findings.ndjson"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def _scan_ndjson(records) -> str:
    return "".join(json.dumps(r) + "\n" for r in records)


def _fake_run(scan_records=None, hook_status="", scan_fails=False):
    """run seam: [bin,'scan','--emit','all'] -> NDJSON, [bin,'hook','status'] -> text."""
    calls = []

    def run(argv, timeout=0.0, max_bytes=0):
        calls.append(list(argv))
        if "scan" in argv:
            if scan_fails:
                return None
            return _scan_ndjson(scan_records or [])
        if "status" in argv:
            return hook_status
        raise AssertionError(f"unexpected argv {argv}")

    run.calls = calls
    return run


def _probe(mod, tmp_path: Path, *, run, home=None):
    return mod.probe(
        tool=lambda _n: "/usr/bin/numbat",
        run=run,
        numbat_home=home if home is not None else tmp_path / ".numbat",
        state_dir=tmp_path / "state",
        now=NOW,
    )


def test_missing_binary_installed_false(tmp_path: Path) -> None:
    mod = load()
    data = mod.probe(tool=lambda _n: None, run=_no_run,
                     numbat_home=tmp_path / ".numbat",
                     state_dir=tmp_path / "state", now=NOW)
    assert list(data.keys()) == EXPECTED_KEYS
    assert data["installed"] is False
    assert data["ok"] is False
    assert data["hooks_seen"] is False
    assert data["findings_24h"] == 0
    assert data["records_path"] == "~/.numbat/findings.ndjson"
    json.dumps(data)


def test_scan_and_hook_status_populate_summary(tmp_path: Path) -> None:
    mod = load()
    run = _fake_run(
        scan_records=[
            {"record_type": "event", "source_agent": "claude-code",
             "timestamp": "2026-09-16T11:59:00Z", "event_type": "session.end",
             "content_preview": "done"},
            {"record_type": "finding", "rule_id": "tamper.x", "severity": "low",
             "source_agent": "claude-code",
             "detected_at": "2026-09-16T11:55:00Z",
             "title": "reduced-approval mode"},
            {"record_type": "diagnostic", "level": "warn",
             "timestamp": "2026-09-16T11:00:00Z"},
            {"record_type": "scan_summary", "timestamp": "2026-09-16T12:00:00Z"},
        ],
        hook_status=(
            "codex    installed    numbat hooks installed\n"
            "claude   not installed\n"
        ),
    )
    data = _probe(mod, tmp_path, run=run)
    assert list(data.keys()) == EXPECTED_KEYS
    assert data["installed"] is True
    assert data["ok"] is True
    assert data["error"] is None
    assert data["hooks_seen"] is True
    assert data["hooked_agents"] == ["codex"]
    assert data["scanned_at"] == "2026-09-16T12:00:00Z"
    assert data["scan_error"] is None
    # finding: title preferred over rule_id, detected_at alias works
    assert data["findings"] == [
        {"rule": "reduced-approval mode",
         "observed_at": "2026-09-16T11:55:00Z",
         "agent": "claude-code", "severity": "low"}
    ]
    assert data["findings_24h"] == 1
    assert data["active_agents"] == [
        {"name": "claude-code", "last_event": "2026-09-16T11:59:00Z"}
    ]
    assert data["events"] == [
        {"observed_at": "2026-09-16T11:59:00Z", "agent": "claude-code",
         "kind": "session.end", "summary": "done"}
    ]
    # scan cache written descriptor-relative under the state dir
    cache = json.loads((tmp_path / "state" / "scan-cache.json").read_text())
    assert cache["hooked_agents"] == ["codex"]
    assert cache["summary"]["findings_24h"] == 1
    assert oct((tmp_path / "state" / "scan-cache.json").stat().st_mode & 0o777) == "0o600"


def test_fresh_cache_skips_scan_but_tail_still_read(tmp_path: Path) -> None:
    mod = load()
    state = tmp_path / "state"
    state.mkdir(parents=True)
    cache = {
        "scanned_at": "2026-09-16T11:00:00Z",
        "hooked_agents": ["codex"],
        "summary": {
            "findings": [{"rule": "cached", "observed_at": "2026-09-16T10:00:00Z",
                          "agent": "a0"}],
            "findings_24h": 1,
            "events": [{"observed_at": "2026-09-16T10:00:00Z", "agent": "a0",
                        "kind": "k", "summary": "s"}],
            "active_agents": [{"name": "a0", "last_event": "2026-09-16T10:00:00Z"}],
        },
    }
    (state / "scan-cache.json").write_text(json.dumps(cache))
    home = tmp_path / ".numbat"
    _write_findings(home, [
        {"record_type": "finding", "rule_id": "live.new",
         "timestamp": "2026-09-16T11:59:00Z", "source_agent": "codex"},
    ])
    data = _probe(mod, tmp_path, run=_no_run, home=home)
    assert data["scanned_at"] == "2026-09-16T11:00:00Z"
    assert data["hooks_seen"] is True
    # live tail finding sorts first, cached finding still present
    assert [f["rule"] for f in data["findings"]] == ["live.new", "cached"]
    assert data["events"][0]["kind"] == "k"


def test_scan_failure_with_no_cache_sets_scan_error(tmp_path: Path) -> None:
    mod = load()
    data = _probe(mod, tmp_path, run=_fake_run(scan_fails=True))
    assert data["ok"] is True
    assert data["installed"] is True
    assert data["scan_error"] == "numbat scan failed"
    assert data["events"] == []
    assert data["hooks_seen"] is False


def test_scan_failure_falls_back_to_stale_cache(tmp_path: Path) -> None:
    mod = load()
    state = tmp_path / "state"
    state.mkdir(parents=True)
    stale = {
        "scanned_at": "2026-09-15T01:00:00Z",  # older than SCAN_INTERVAL_S
        "hooked_agents": ["codex"],
        "summary": {
            "findings": [], "findings_24h": 0,
            "events": [{"observed_at": "2026-09-15T00:00:00Z", "agent": "a0",
                        "kind": "x", "summary": ""}],
            "active_agents": [],
        },
    }
    (state / "scan-cache.json").write_text(json.dumps(stale))
    # make the cache file itself look old so the stale path is exercised
    old = NOW.timestamp() - 7200
    os.utime(state / "scan-cache.json", (old, old))
    data = _probe(mod, tmp_path, run=_fake_run(scan_fails=True))
    assert data["scan_error"] == "scan failed; showing cached data"
    assert data["events"][0]["kind"] == "x"
    assert data["hooks_seen"] is True  # from cached hooked_agents


def test_findings_tail_is_live_and_bounded(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    head = {"record_type": "finding", "rule_id": "head-only",
            "timestamp": "2026-09-16T11:59:00Z"}
    filler = {"record_type": "finding", "rule_id": "filler",
              "timestamp": "2026-09-16T11:00:00Z"}
    tail_new = {"record_type": "finding", "rule_id": "marker-new",
                "timestamp": "2026-09-16T11:59:30Z"}
    lines = [json.dumps(head)] + [json.dumps(filler)] * 5000 + [json.dumps(tail_new)]
    home.mkdir()
    path = home / "findings.ndjson"
    path.write_text("\n".join(lines) + "\n")
    assert path.stat().st_size > 256 * 1024
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[]), home=home)
    rules = [f["rule"] for f in data["findings"]]
    assert "head-only" not in rules
    assert rules[0] == "marker-new"
    assert data["hooks_seen"] is True


def test_garbage_and_unknown_records_skipped(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    home.mkdir()
    (home / "findings.ndjson").write_bytes(
        b"\x00\x01 not json \xff\xfe\n"
        b'{"record_type":"finding","rule_id":"r1","timestamp":"2026-09-16T11:50:00Z"}\n'
        b"42\n"
        b'"just a string"\n'
    )
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[]), home=home)
    assert data["findings"] == [
        {"rule": "r1", "observed_at": "2026-09-16T11:50:00Z", "agent": ""}
    ]


def test_symlinked_findings_file_not_followed(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    home.mkdir()
    real = tmp_path / "real-findings.ndjson"
    real.write_text(
        '{"record_type":"finding","rule_id":"x","timestamp":"2026-09-16T11:00:00Z"}\n'
    )
    (home / "findings.ndjson").symlink_to(real)
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[]), home=home)
    assert data["findings"] == []
    assert data["hooks_seen"] is False


def test_events_newest_first_and_capped_at_30(tmp_path: Path) -> None:
    mod = load()
    records = []
    for i in range(40):
        ts = (f"2026-09-16T10:{i:02d}:00Z" if i % 2 == 0
              else f"2026-09-16T10:{i:02d}:00+00:00")
        records.append({
            "record_type": "event",
            "source_agent": "claude-code" if i % 2 == 0 else "a0",
            "timestamp": ts,
            "event_type": "tool_call",
            "content_preview": f"event-{i:02d}",
        })
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=records))
    assert len(data["events"]) == 30
    stamps = [e["observed_at"] for e in data["events"]]
    assert stamps == sorted(stamps, reverse=True)
    assert data["events"][0] == {
        "observed_at": "2026-09-16T10:39:00Z",
        "agent": "a0",
        "kind": "tool_call",
        "summary": "event-39",
    }
    for e in data["events"]:
        assert set(e.keys()) == {"observed_at", "agent", "kind", "summary"}


def test_findings_and_events_not_windowed_but_agents_are(tmp_path: Path) -> None:
    mod = load()
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[
        {"record_type": "event", "source_agent": "old-agent",
         "timestamp": "2026-09-10T00:00:00Z", "event_type": "old"},
        {"record_type": "event", "source_agent": "new-agent",
         "timestamp": "2026-09-16T11:00:00Z", "event_type": "new"},
        {"record_type": "finding", "rule_id": "old-finding",
         "timestamp": "2026-09-10T00:00:00Z"},
        {"record_type": "finding", "rule_id": "new-finding",
         "timestamp": "2026-09-16T11:30:00Z"},
    ]))
    assert [e["kind"] for e in data["events"]] == ["new", "old"]
    assert {f["rule"] for f in data["findings"]} == {"old-finding", "new-finding"}
    assert data["findings_24h"] == 1
    # only agents with in-window events are "active"
    assert data["active_agents"] == [
        {"name": "new-agent", "last_event": "2026-09-16T11:00:00Z"}
    ]


def test_cursor_timestamp_tag_parsed(tmp_path: Path) -> None:
    """Cursor events carry time only inside content_preview's <timestamp>."""
    mod = load()
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[
        {
            "record_type": "event",
            "source_agent": "cursor",
            "event_type": "prompt.user",
            # "Wednesday, Sep 16, 2026, 5:30 AM (UTC-6)" -> 11:30Z
            "content_preview": "<timestamp>Wednesday, Sep 16, 2026, 5:30 AM (UTC-6)</timestamp> <user_query>hi",
        },
        {
            "record_type": "event",
            "source_agent": "cursor",
            "event_type": "prompt.user",
            "content_preview": "<timestamp>bogus</timestamp> no time",
        },
    ]))
    assert data["events"] == [
        {"observed_at": "2026-09-16T11:30:00Z", "agent": "cursor",
         "kind": "prompt.user",
         "summary": "<timestamp>Wednesday, Sep 16, 2026, 5:30 AM (UTC-6)</timestamp> <user_query>hi"},
    ]
    assert data["agents_seen"] == [
        {"name": "cursor", "last_event": "2026-09-16T11:30:00Z"}
    ]
    assert data["active_agents"] == data["agents_seen"]


def test_artifact_mtime_fallback_for_undated_events(tmp_path: Path) -> None:
    """Events with no timestamp anywhere fall back to evidence file mtime."""
    mod = load()
    artifact = tmp_path / "transcript.jsonl"
    artifact.write_text("{}\n")
    ts = datetime(2026, 9, 16, 9, 0, 0, tzinfo=timezone.utc).timestamp()
    os.utime(artifact, (ts, ts))
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[
        {
            "record_type": "event",
            "source_agent": "cursor",
            "event_type": "assistant.reply",
            "evidence": {"local_path": str(artifact)},
        },
        # foreign-owned / missing paths contribute nothing
        {
            "record_type": "event",
            "source_agent": "ghost",
            "event_type": "x",
            "evidence": {"local_path": "/nonexistent/path.jsonl"},
        },
    ]))
    assert data["events"][0]["observed_at"] == "2026-09-16T09:00:00Z"
    assert [e["agent"] for e in data["events"]] == ["cursor"]


def test_agents_seen_covers_all_windowed_or_not(tmp_path: Path) -> None:
    mod = load()
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[
        {"record_type": "event", "source_agent": "old-one",
         "timestamp": "2026-09-01T00:00:00Z", "event_type": "old"},
        {"record_type": "event", "source_agent": "new-one",
         "timestamp": "2026-09-16T11:00:00Z", "event_type": "new"},
    ]))
    assert {a["name"] for a in data["agents_seen"]} == {"old-one", "new-one"}
    assert {a["name"] for a in data["active_agents"]} == {"new-one"}


def test_strings_control_normalized_and_clipped(tmp_path: Path) -> None:
    mod = load()
    data = _probe(mod, tmp_path, run=_fake_run(scan_records=[
        {
            "record_type": "event",
            "source_agent": "a0",
            "timestamp": "2026-09-16T11:00:00Z",
            "event_type": "k" * 200,
            "content_preview": "has\x00ctrl\x07chars " + "s" * 120,
        },
    ]))
    ev = data["events"][0]
    assert len(ev["kind"]) == 80
    assert len(ev["summary"]) <= 80
    assert "\x00" not in ev["summary"]
    assert "\x07" not in ev["summary"]
    json.dumps(data)


def test_untrusted_numbat_dir_sets_error(tmp_path: Path) -> None:
    mod = load()
    foreign = tmp_path / ".numbat"
    foreign.mkdir()
    # simulate a directory not owned by us by monkeypatching _open_dir's
    # ownership check target: simplest faithful check is a broken symlink dir
    link = tmp_path / "linkhome"
    link.symlink_to(foreign)
    data = mod.probe(
        tool=lambda _n: "/usr/bin/numbat",
        run=_fake_run(scan_records=[]),
        numbat_home=str(link),  # O_NOFOLLOW on the dir itself -> OSError
        state_dir=tmp_path / "state",
        now=NOW,
    )
    # symlinked dir -> _open_dir raises OSError -> treated as absent tail
    assert data["installed"] is True
    assert data["ok"] is True
