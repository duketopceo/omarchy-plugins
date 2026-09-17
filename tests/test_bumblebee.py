from __future__ import annotations

import importlib.util
import json
import os
import stat
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "plugins/io.github.duketopceo.bumblebee/bin/scan_bumblebee.py"
SHIPPED_CATALOG = ROOT / "plugins/io.github.duketopceo.bumblebee/catalog/exposures.json"

NOW = 1_800_000_000.0  # fixed clock for deterministic age_s assertions


def load():
    spec = importlib.util.spec_from_file_location("scan_bumblebee", HELPER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def shipped_count() -> int:
    return len(json.loads(SHIPPED_CATALOG.read_text())["entries"])


def cache_dir(home: Path) -> Path:
    return home / ".local/state/omarchy/bumblebee"


def write_cache(home: Path, payload: dict, age_s: float) -> Path:
    d = cache_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "last-scan.json"
    f.write_text(json.dumps(payload))
    past = NOW - age_s
    os.utime(f, (past, past))
    return f


def never_run(*_a, **_k):
    raise AssertionError("bumblebee exec must not run")


def ndjson(*records) -> str:
    return "".join(
        r if isinstance(r, str) else json.dumps(r) + "\n" for r in records
    )


def finding(**kw) -> dict:
    base = {
        "record_type": "finding",
        "name": "chalk npm account-takeover release (Sep 2025 qix phish)",
        "ecosystem": "npm",
        "package": "chalk",
        "version": "5.6.1",
        "severity": "critical",
    }
    base.update(kw)
    return base


def test_missing_binary_degrades_no_exec(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_tool", lambda name: None)
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path)
    assert payload["installed"] is False
    assert payload["ok"] is False
    assert payload["scanned_at"] is None
    assert payload["age_s"] is None
    assert payload["exposure_count"] == 0
    assert payload["exposures"] == []
    assert payload["partial"] is False
    assert payload["error"] is None
    assert payload["catalog_entries"] == shipped_count()
    json.dumps(payload)


def test_fresh_cache_no_exec_recomputed_age(tmp_path):
    mod = load()
    cached = {
        "installed": True,
        "ok": True,
        "scanned_at": "2026-09-16T01:00:00Z",
        "age_s": 0,
        "exposure_count": 1,
        "exposures": [{"name": "n", "ecosystem": "npm", "package": "chalk",
                       "version": "5.6.1", "severity": "critical"}],
        "catalog_entries": 0,
        "partial": True,
        "error": None,
    }
    write_cache(tmp_path, cached, age_s=120)
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert payload["exposure_count"] == 1
    assert payload["partial"] is True
    assert payload["scanned_at"] == "2026-09-16T01:00:00Z"
    assert payload["age_s"] == 120  # recomputed from cache mtime
    assert payload["catalog_entries"] == shipped_count()  # refreshed
    json.dumps(payload)


def test_stale_cache_scans_and_republishes(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setenv("BUMBLEBEE_SCAN_INTERVAL_S", "3600")
    stale = write_cache(tmp_path, {"installed": True, "ok": True,
                                   "exposure_count": 0}, age_s=7200)
    out = ndjson(
        {"record_type": "component", "ecosystem": "npm", "name": "chalk",
         "version": "5.6.0"},
        finding(),
        {"record_type": "scan_summary", "status": "complete"},
    )
    seen = {}

    def fake_run(argv, timeout=None, max_bytes=None):
        seen["argv"] = list(argv)
        return out, None, 0

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    argv = seen["argv"]
    assert argv[:4] == ["/usr/bin/bumblebee", "scan", "--profile", "baseline"]
    assert str(mod.PLUGIN_ROOT / "catalog") in argv
    assert argv.count("--exposure-catalog") == 1  # no user catalog.d here
    assert "--findings-only" in argv
    assert "stdout" in argv
    assert payload["ok"] is True
    assert payload["exposure_count"] == 1
    assert payload["exposures"][0]["package"] == "chalk"
    assert payload["exposures"][0]["version"] == "5.6.1"
    assert payload["partial"] is False
    assert payload["error"] is None
    assert payload["age_s"] == 0

    republished = json.loads(stale.read_text())
    assert republished["exposure_count"] == 1
    assert republished["ok"] is True
    mode = stat.S_IMODE(os.stat(stale).st_mode)
    assert mode == 0o600


def test_malformed_ndjson_lines_skipped(tmp_path):
    mod = load()
    out = ndjson(
        "this is not json\n",
        '{"record_type": "finding", "package": "broken"',  # truncated
        "\n",
        "[1, 2, 3]\n",
        "42\n",
        json.dumps({"no_record_type": True}) + "\n",
        finding(),
        {"record_type": "scan_summary", "status": "complete"},
    )

    def fake_run(argv, timeout=None, max_bytes=None):
        return out, None, 0

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert payload["ok"] is True
    assert payload["exposure_count"] == 1
    assert len(payload["exposures"]) == 1
    json.dumps(payload)


def test_scan_summary_non_complete_sets_partial(tmp_path):
    mod = load()
    for status in ("partial", "interrupted", "error"):
        out = ndjson({"record_type": "scan_summary", "status": status})
        payload = mod.collect(
            now=NOW,
            run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
            home=tmp_path,
            tool="/usr/bin/bumblebee",
        )
        assert payload["partial"] is True, status
    out = ndjson({"record_type": "scan_summary", "status": "complete"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    assert payload["partial"] is False


def test_user_catalog_d_merges_into_count_and_argv(tmp_path):
    mod = load()
    catd = tmp_path / ".config/omarchy/plugins-data/bumblebee/catalog.d"
    catd.mkdir(parents=True)
    (catd / "extra.json").write_text(json.dumps(
        {"schema_version": "0.2.0",
         "entries": [{"name": "a"}, {"name": "b"}]}))
    (catd / "bad.json").write_text("{not json")          # skipped
    (catd / "ignored.txt").write_text("[]")               # not .json
    (catd / "empty.json").write_text(json.dumps({"entries": []}))
    seen = {}

    def fake_run(argv, timeout=None, max_bytes=None):
        seen["argv"] = list(argv)
        return ndjson({"record_type": "scan_summary", "status": "complete"}), None, 0

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert payload["catalog_entries"] == shipped_count() + 2
    assert str(catd) in seen["argv"]
    assert seen["argv"].count("--exposure-catalog") == 2


def test_oversized_output_records_error_still_valid_json(tmp_path):
    mod = load()

    def fake_run(argv, timeout=None, max_bytes=None):
        return None, "output_too_large", None

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert payload["installed"] is True
    assert payload["ok"] is False
    assert payload["error"] == "output_too_large"
    assert payload["exposure_count"] == 0
    assert payload["exposures"] == []
    json.dumps(payload)
    # Failure is still cached so the panel cadence stays one exec per interval.
    assert (cache_dir(tmp_path) / "last-scan.json").exists()


def test_nonzero_exit_tolerated_when_records_parse(tmp_path):
    mod = load()
    out = ndjson(finding(), {"record_type": "scan_summary", "status": "complete"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 1),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    assert payload["ok"] is True
    assert payload["exposure_count"] == 1
    assert payload["error"] is None


def test_nonzero_exit_without_records_is_error(tmp_path):
    mod = load()
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: ("", None, 2),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    assert payload["ok"] is False
    assert payload["error"] == "exit 2"
    assert payload["exposure_count"] == 0


def test_finding_strings_clipped_and_control_stripped(tmp_path):
    mod = load()
    nasty = finding(
        name="evil\x1b[31m\x00name\n" + "x" * 500,
        package="pkg" + "\t" * 200,
    )
    out = ndjson(nasty, {"record_type": "scan_summary", "status": "complete"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    exp = payload["exposures"][0]
    assert len(exp["name"]) <= mod.MAX_STR
    assert len(exp["package"]) <= mod.MAX_STR
    for v in exp.values():
        assert all(ord(c) >= 0x20 for c in v)


def test_exposure_list_capped_count_kept(tmp_path):
    mod = load()
    out = ndjson(*[finding(package=f"pkg{i}") for i in range(60)],
                 {"record_type": "scan_summary", "status": "complete"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    assert payload["exposure_count"] == 60
    assert len(payload["exposures"]) == mod.MAX_EXPOSURES == 50


def test_env_interval_override_forces_stale(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setenv("BUMBLEBEE_SCAN_INTERVAL_S", "10")
    write_cache(tmp_path, {"installed": True, "ok": True, "exposure_count": 7},
                age_s=30)
    calls = []

    def fake_run(argv, timeout=None, max_bytes=None):
        calls.append(1)
        return ndjson({"record_type": "scan_summary", "status": "complete"}), None, 0

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert calls == [1]
    assert payload["exposure_count"] == 0


def test_corrupt_cache_triggers_scan(tmp_path):
    mod = load()
    d = cache_dir(tmp_path)
    d.mkdir(parents=True)
    (d / "last-scan.json").write_bytes(b"\x00\xff garbage")
    calls = []

    def fake_run(argv, timeout=None, max_bytes=None):
        calls.append(1)
        return "", None, 0

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert calls == [1]
    assert payload["ok"] is True


def test_run_real_exec_and_byte_cap():
    mod = load()
    text, err, rc = mod._run(
        ["/usr/bin/python3", "-c", "print('ok')"], timeout=5)
    assert err is None and rc == 0 and text.strip() == "ok"

    text, err, rc = mod._run(
        ["/usr/bin/python3", "-c", "import sys; sys.stdout.write('x' * 200000)"],
        timeout=5, max_bytes=1024)
    assert text is None and err == "output_too_large"


def test_run_timeout_group_kills():
    mod = load()
    start = time.monotonic()
    text, err, rc = mod._run(
        ["/usr/bin/python3", "-c", "import time; time.sleep(60)"],
        timeout=0.4)
    assert text is None and err == "timeout"
    assert time.monotonic() - start < 10
