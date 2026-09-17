from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/io.github.duketopceo.numbat/bin/probe_numbat.py"

NOW = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
EXPECTED_KEYS = [
    "installed",
    "ok",
    "hooks_seen",
    "active_agents",
    "findings_24h",
    "findings",
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
    raise AssertionError("_run must not be called when records exist")


def _write_records(home: Path, lines) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = home / "records.ndjson"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def test_missing_binary_installed_false(tmp_path: Path) -> None:
    mod = load()
    data = mod.probe(tool=lambda _n: None, run=_no_run, numbat_home=tmp_path / ".numbat", now=NOW)
    assert list(data.keys()) == EXPECTED_KEYS
    assert data["installed"] is False
    assert data["ok"] is False
    assert data["hooks_seen"] is False
    assert data["active_agents"] == []
    assert data["findings_24h"] == 0
    assert data["findings"] == []
    assert data["records_path"] == "~/.numbat/records.ndjson"
    json.dumps(data)


def test_no_numbat_dir_uses_agents_cli_fallback(tmp_path: Path) -> None:
    mod = load()
    calls = []

    def fake_run(argv, timeout=0.0, max_bytes=0):
        calls.append(list(argv))
        return json.dumps(
            {
                "agents": [
                    {"name": "claude-code", "last_seen": "2026-09-16T10:00:00Z"},
                    "a0",
                ]
            }
        )

    data = mod.probe(
        tool=lambda _n: "/usr/bin/numbat",
        run=fake_run,
        numbat_home=tmp_path / ".numbat",
        now=NOW,
    )
    assert data["installed"] is True
    assert data["ok"] is True
    assert data["hooks_seen"] is False
    assert data["error"] is None
    assert calls == [["/usr/bin/numbat", "agents", "--all"]]
    assert data["active_agents"] == [
        {"name": "claude-code", "last_event": "2026-09-16T10:00:00Z"},
        {"name": "a0", "last_event": ""},
    ]


def test_agents_fallback_non_json_degrades_to_empty(tmp_path: Path) -> None:
    mod = load()
    data = mod.probe(
        tool=lambda _n: "/usr/bin/numbat",
        run=lambda *_a, **_k: "numbat 1.2.3 — agents: claude-code, a0",
        numbat_home=tmp_path / ".numbat",
        now=NOW,
    )
    assert data["ok"] is True
    assert data["active_agents"] == []
    assert data["error"] is None


def test_agents_fallback_run_failure_sets_error(tmp_path: Path) -> None:
    mod = load()
    data = mod.probe(
        tool=lambda _n: "/usr/bin/numbat",
        run=lambda *_a, **_k: None,
        numbat_home=tmp_path / ".numbat",
        now=NOW,
    )
    assert data["installed"] is True
    assert data["ok"] is False
    assert data["hooks_seen"] is False
    assert data["error"]


def test_mixed_event_and_finding_records(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    _write_records(
        home,
        [
            {"record_type": "event", "source_agent": "claude-code", "observed_at": "2026-09-16T11:00:00Z"},
            {"record_type": "event", "source_agent": "claude-code", "observed_at": "2026-09-16T11:59:00Z"},
            {"record_type": "event", "source_agent": "a0", "ts": "2026-09-16T10:00:00+00:00"},
            {
                "record_type": "finding",
                "rule": "secret-in-prompt",
                "observed_at": "2026-09-16T11:30:00Z",
                "source_agent": "claude-code",
            },
            # outside the 24h window — must not be counted
            {"record_type": "finding", "rule": "stale-rule", "observed_at": "2026-09-10T00:00:00Z"},
            # unknown record_type — counts as a record but not event/finding
            {"record_type": "heartbeat", "observed_at": "2026-09-16T11:59:59Z"},
        ],
    )
    data = mod.probe(tool=lambda _n: "/usr/bin/numbat", run=_no_run, numbat_home=home, now=NOW)
    assert list(data.keys()) == EXPECTED_KEYS
    assert data["installed"] is True
    assert data["ok"] is True
    assert data["error"] is None
    assert data["hooks_seen"] is True
    assert data["findings_24h"] == 1
    assert data["findings"] == [
        {
            "rule": "secret-in-prompt",
            "observed_at": "2026-09-16T11:30:00Z",
            "agent": "claude-code",
        }
    ]
    agents = {a["name"]: a["last_event"] for a in data["active_agents"]}
    assert agents == {
        "claude-code": "2026-09-16T11:59:00Z",  # newest event wins
        "a0": "2026-09-16T10:00:00Z",
    }


def test_garbage_and_truncated_lines_skipped(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    home.mkdir()
    (home / "records.ndjson").write_bytes(
        b"\x00\x01\x02 not json \xff\xfe\n"
        b'{"record_type":"event","source_agent":"claude-code","observed_at":"2026-09-16T11:0'  # truncated mid-line
        b'\n{"record_type":"event","source_agent":"claude-code","observed_at":"2026-09-16T11:45:00Z"}\n'
        b"42\n"
        b'"just a string"\n'
        b'{"record_type":"finding","rule":"r1","observed_at":"2026-09-16T11:50:00Z"}\n'
    )
    data = mod.probe(tool=lambda _n: "/usr/bin/numbat", run=_no_run, numbat_home=home, now=NOW)
    assert data["hooks_seen"] is True
    assert data["findings_24h"] == 1
    assert data["findings"][0]["rule"] == "r1"
    assert data["active_agents"] == [{"name": "claude-code", "last_event": "2026-09-16T11:45:00Z"}]


def test_tail_read_bounded(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    home.mkdir()
    head = {"record_type": "finding", "rule": "head-only", "observed_at": "2026-09-16T11:59:00Z"}
    filler = {"record_type": "finding", "rule": "filler", "observed_at": "2026-09-16T11:00:00Z"}
    tail_old = {"record_type": "finding", "rule": "marker-old", "observed_at": "2026-09-16T11:58:30Z"}
    tail_new = {"record_type": "finding", "rule": "marker-new", "observed_at": "2026-09-16T11:59:30Z"}
    path = home / "records.ndjson"
    lines = [json.dumps(head)] + [json.dumps(filler)] * 5000 + [
        json.dumps(tail_old),
        json.dumps(tail_new),
    ]
    path.write_text("\n".join(lines) + "\n")
    assert path.stat().st_size > 256 * 1024

    data = mod.probe(tool=lambda _n: "/usr/bin/numbat", run=_no_run, numbat_home=home, now=NOW)
    assert data["hooks_seen"] is True
    # Bounded tail-read: the head of the file was never read.
    assert 0 < data["findings_24h"] < 5002
    rules = [f["rule"] for f in data["findings"]]
    assert "head-only" not in rules
    assert rules[0] == "marker-new"  # newest first
    assert "marker-old" in rules


def test_z_and_offset_timestamps_both_windowed(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    _write_records(
        home,
        [
            {"record_type": "finding", "rule": "z-form", "observed_at": "2026-09-16T11:00:00Z"},
            {"record_type": "finding", "rule": "offset-form", "observed_at": "2026-09-16T11:00:00+00:00"},
            # 13:30 at +02:00 is 11:30 UTC — inside the window
            {"record_type": "finding", "rule": "other-offset", "observed_at": "2026-09-16T13:30:00+02:00"},
            # older than 24h — excluded
            {"record_type": "finding", "rule": "too-old", "observed_at": "2026-09-14T13:00:00Z"},
        ],
    )
    data = mod.probe(tool=lambda _n: "/usr/bin/numbat", run=_no_run, numbat_home=home, now=NOW)
    assert data["findings_24h"] == 3
    rules = {f["rule"] for f in data["findings"]}
    assert rules == {"z-form", "offset-form", "other-offset"}
    # newest instant first (other-offset = 11:30Z)
    assert data["findings"][0]["rule"] == "other-offset"
    assert data["findings"][0]["observed_at"] == "2026-09-16T11:30:00Z"


def test_symlinked_records_file_not_followed(tmp_path: Path) -> None:
    mod = load()
    home = tmp_path / ".numbat"
    home.mkdir()
    real = tmp_path / "real-records.ndjson"
    real.write_text(
        '{"record_type":"event","source_agent":"x","observed_at":"2026-09-16T11:00:00Z"}\n'
    )
    (home / "records.ndjson").symlink_to(real)

    calls = []
    data = mod.probe(
        tool=lambda _n: "/usr/bin/numbat",
        run=lambda *a, **k: calls.append(1) or "[]",
        numbat_home=home,
        now=NOW,
    )
    assert data["hooks_seen"] is False
    assert calls  # treated as absent -> CLI fallback ran
