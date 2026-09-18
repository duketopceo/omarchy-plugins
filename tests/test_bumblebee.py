from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "plugins/io.github.duketopceo.bumblebee/bin/scan_bumblebee.py"
REFRESH = ROOT / "plugins/io.github.duketopceo.bumblebee/bin/refresh_catalog.py"
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


def log_path(home: Path) -> Path:
    return cache_dir(home) / "scan-log.json"


def complete_run(argv, timeout=None, max_bytes=None):
    return ndjson({"record_type": "scan_summary", "status": "complete"}), None, 0


def test_log_entry_written_on_scan(tmp_path):
    mod = load()
    out = ndjson(finding(),
                 {"record_type": "scan_summary", "status": "complete"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    log = payload["log"]
    assert len(log) == 1
    e = log[0]
    assert e["status"] == "complete"
    assert e["exposure_count"] == 1
    assert e["scanned_at"] == mod._iso(NOW)
    assert e["duration_ms"] >= 0
    assert "error" not in e
    f = log_path(tmp_path)
    assert json.loads(f.read_text()) == log
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600


def test_log_entry_status_error_and_partial(tmp_path):
    mod = load()
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (None, "timeout", None),
        home=tmp_path,
        tool="/usr/bin/bumblebee",
    )
    e = payload["log"][0]
    assert e["status"] == "error"
    assert e["error"] == "timeout"
    assert e["exposure_count"] == 0

    home2 = tmp_path / "h2"
    out = ndjson({"record_type": "scan_summary", "status": "interrupted"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
        home=home2,
        tool="/usr/bin/bumblebee",
    )
    assert payload["partial"] is True
    assert payload["log"][0]["status"] == "partial"


def test_log_capped_at_20_newest_first(tmp_path):
    mod = load()
    d = cache_dir(tmp_path)
    d.mkdir(parents=True, exist_ok=True)
    old = [{"scanned_at": f"2026-01-01T00:00:{i:02d}Z", "status": "complete",
            "exposure_count": i, "duration_ms": 1} for i in range(25)]
    log_path(tmp_path).write_text(json.dumps(old))
    payload = mod.collect(now=NOW, run=complete_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    log = payload["log"]
    assert len(log) == mod.MAX_LOG_ENTRIES == 20
    assert log[0]["scanned_at"] == mod._iso(NOW)  # new entry lands first
    assert log[1]["exposure_count"] == 0          # then oldest-kept order
    assert json.loads(log_path(tmp_path).read_text()) == log


def test_corrupt_log_tolerated(tmp_path):
    mod = load()
    d = cache_dir(tmp_path)
    d.mkdir(parents=True, exist_ok=True)
    log_path(tmp_path).write_bytes(b"\x00\xff garbage")
    payload = mod.collect(now=NOW, run=complete_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert payload["ok"] is True
    assert len(payload["log"]) == 1
    assert payload["log"][0]["status"] == "complete"
    json.loads(log_path(tmp_path).read_text())  # republished as valid json


def test_cache_hit_reemits_stored_log(tmp_path):
    mod = load()
    write_cache(tmp_path, {"installed": True, "ok": True, "exposure_count": 3},
                age_s=60)
    cache_dir(tmp_path)  # exists from write_cache
    log_path(tmp_path).write_text(json.dumps(
        [{"scanned_at": "2026-09-16T01:00:00Z", "status": "error",
          "exposure_count": 3, "duration_ms": 5, "error": "timeout"},
         "junk", 42, None]))  # non-dict entries filtered on re-emit
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path,
                          tool="/usr/bin/bumblebee")
    assert len(payload["log"]) == 1
    e = payload["log"][0]
    assert e["status"] == "error" and e["error"] == "timeout"
    assert e["exposure_count"] == 3 and e["duration_ms"] == 5


def test_force_bypasses_fresh_cache(tmp_path):
    mod = load()
    write_cache(tmp_path, {"installed": True, "ok": True, "exposure_count": 9},
                age_s=10)
    calls = []

    def fake_run(argv, timeout=None, max_bytes=None):
        calls.append(1)
        return ndjson({"record_type": "scan_summary", "status": "complete"}), None, 0

    payload = mod.collect(now=NOW, run=fake_run, home=tmp_path,
                          tool="/usr/bin/bumblebee", force=True)
    assert calls == [1]
    assert payload["exposure_count"] == 0  # scan result, not the cached 9
    # The forced scan's republished cache is honored again without --force.
    payload2 = mod.collect(now=NOW, run=never_run, home=tmp_path,
                           tool="/usr/bin/bumblebee")
    assert payload2["scanned_at"] == mod._iso(NOW)


def test_main_parses_force_flag(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod.os, "setsid", lambda: None)
    monkeypatch.setattr(mod.signal, "alarm", lambda *_: None)
    seen = {}
    monkeypatch.setattr(mod, "collect", lambda **kw: seen.update(kw) or {})
    monkeypatch.setattr(mod.sys, "argv", ["scan_bumblebee.py", "--force"])
    mod.main()
    assert seen.get("force") is True


def test_catalog_names_emitted_capped_clean(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_tool", lambda name: None)
    shipped = json.loads(SHIPPED_CATALOG.read_text())["entries"]
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path)
    assert payload["catalog_names"] == [e["name"] for e in shipped]
    assert len(payload["catalog_names"]) <= mod.MAX_CATALOG_NAMES == 12
    for n in payload["catalog_names"]:
        assert all(ord(c) >= 0x20 for c in n)

    # User catalog.d names merge after the shipped ones under the same cap.
    catd = tmp_path / ".config/omarchy/plugins-data/bumblebee/catalog.d"
    catd.mkdir(parents=True)
    (catd / "extra.json").write_text(json.dumps(
        {"entries": [{"name": "user-advisory-a"}, {"id": "user-advisory-b"}]}))
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path)
    assert payload["catalog_names"][-2:] == ["user-advisory-a",
                                             "user-advisory-b"]
    assert payload["catalog_entries"] == shipped_count() + 2


# --- age verb (service staleness probe — pure stat, never scans) ---

def test_age_verb_stats_cache_no_scan(tmp_path):
    mod = load()
    write_cache(tmp_path, {"installed": True, "ok": True,
                           "exposure_count": 2,
                           "exposures": [
                               {"name": "adv-a", "ecosystem": "npm",
                                "package": "p1", "version": "1.0"},
                               {"name": "", "ecosystem": "pypi",
                                "package": "p2", "version": "2.0"},
                           ]},
                age_s=3600)
    payload = mod.collect_age(now=NOW, home=tmp_path,
                              tool="/usr/bin/bumblebee")
    assert payload["installed"] is True
    assert payload["ok"] is True
    assert payload["last_scan_age_s"] == 3600
    assert payload["exposure_count"] == 2
    assert payload["exposure_ids"] == ["adv-a|npm|p1@1.0", "|pypi|p2@2.0"]
    assert len(payload["exposures"]) == 2
    assert payload["error"] is None
    json.dumps(payload)


def test_age_verb_no_cache_is_null_age(tmp_path):
    mod = load()
    payload = mod.collect_age(now=NOW, home=tmp_path,
                              tool="/usr/bin/bumblebee")
    assert payload["installed"] is True
    assert payload["last_scan_age_s"] is None  # service treats as stale
    assert payload["exposure_count"] == 0
    assert payload["exposure_ids"] == []
    json.dumps(payload)


def test_age_verb_reports_installed_flag(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_tool", lambda name: None)
    payload = mod.collect_age(now=NOW, home=tmp_path)
    assert payload["installed"] is False
    assert payload["error"] is None


def test_age_verb_never_execs_run(tmp_path):
    # collect_age has no run seam at all — scanning is impossible by shape.
    mod = load()
    write_cache(tmp_path, {"installed": True, "ok": True,
                           "exposure_count": 1,
                           "exposures": [{"name": "n", "ecosystem": "e",
                                          "package": "p", "version": "v"}]},
                age_s=60)
    payload = mod.collect_age(now=NOW, home=tmp_path,
                              tool="/usr/bin/bumblebee")
    assert payload["exposure_ids"] == ["n|e|p@v"]


def test_main_parses_age_verb(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod.os, "setsid", lambda: None)
    monkeypatch.setattr(mod.signal, "alarm", lambda *_: None)
    seen = {}
    monkeypatch.setattr(mod, "collect_age",
                        lambda **kw: seen.update(kw) or {"ok": True})
    monkeypatch.setattr(mod, "collect",
                        lambda **kw: (_ for _ in ()).throw(
                            AssertionError("collect must not run on age")))
    monkeypatch.setattr(mod.sys, "argv", ["scan_bumblebee.py", "age"])
    mod.main()
    assert seen == {}


# --- catalog provenance + refresh timestamp ---

def catalog_d(home: Path) -> Path:
    return home / ".config/omarchy/plugins-data/bumblebee/catalog.d"


def test_catalog_refreshed_at_and_sources(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_tool", lambda name: None)
    catd = catalog_d(tmp_path)
    catd.mkdir(parents=True)
    upstream = catd / "upstream.json"
    upstream.write_text(json.dumps(
        {"entries": [{"id": "u1"}, {"id": "u2"}]}))
    (catd / "mine.json").write_text(json.dumps({"entries": [{"id": "m1"}]}))
    os.utime(upstream, (NOW - 86400, NOW - 86400))
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path)
    assert payload["catalog_refreshed_at"] == mod._iso(NOW - 86400)
    assert payload["catalog_sources"] == {
        "bundled": shipped_count(), "catalog_d": 1, "upstream": 2}
    assert payload["catalog_entries"] == shipped_count() + 3


def test_catalog_refreshed_at_null_without_upstream(tmp_path, monkeypatch):
    mod = load()
    monkeypatch.setattr(mod, "_tool", lambda name: None)
    catd = catalog_d(tmp_path)
    catd.mkdir(parents=True)
    (catd / "mine.json").write_text(json.dumps({"entries": [{"id": "m1"}]}))
    payload = mod.collect(now=NOW, run=never_run, home=tmp_path)
    assert payload["catalog_refreshed_at"] is None
    assert payload["catalog_sources"]["upstream"] == 0
    assert payload["catalog_sources"]["catalog_d"] == 1


def test_exposure_ids_in_payload_and_cache_reemit(tmp_path):
    mod = load()
    out = ndjson(finding(),
                 {"record_type": "scan_summary", "status": "complete"})
    payload = mod.collect(
        now=NOW,
        run=lambda argv, timeout=None, max_bytes=None: (out, None, 0),
        home=tmp_path, tool="/usr/bin/bumblebee")
    assert payload["exposure_ids"] == [
        "chalk npm account-takeover release (Sep 2025 qix phish)"
        "|npm|chalk@5.6.1"]
    # A cached re-emit recomputes ids from the stored exposures. The
    # republished cache carries the real mtime, so pin it to NOW for a
    # deterministic fresh hit.
    cached_file = cache_dir(tmp_path) / "last-scan.json"
    os.utime(cached_file, (NOW, NOW))
    payload2 = mod.collect(now=NOW + 60, run=never_run, home=tmp_path,
                           tool="/usr/bin/bumblebee")
    assert payload2["exposure_ids"] == payload["exposure_ids"]


# --- refresh_catalog.py: pinned opt-in upstream merge ---

def load_refresh():
    spec = importlib.util.spec_from_file_location("refresh_catalog", REFRESH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def make_entry(i, **kw):
    base = {
        "id": f"adv-{i}",
        "name": f"advisory {i}",
        "ecosystem": "npm",
        "package": f"pkg{i}",
        "versions": ["1.0.0"],
        "severity": "high",
    }
    base.update(kw)
    return base


def make_tarball(members, top="bumblebee-0.1.2") -> bytes:
    """members: {relpath: str|bytes} placed under <top>/ in the tar."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel, data in members.items():
            blob = data if isinstance(data, bytes) else data.encode()
            ti = tarfile.TarInfo(f"{top}/{rel}")
            ti.size = len(blob)
            tf.addfile(ti, io.BytesIO(blob))
    return buf.getvalue()


def fake_fetch(blob):
    def fetch(url, timeout_s=None, max_bytes=None):
        return blob
    return fetch


def catalog_doc(entries):
    return json.dumps({"schema_version": "0.1.0", "entries": entries})


def test_refresh_success_merges_atomically(tmp_path):
    mod = load_refresh()
    blob = make_tarball({
        "threat_intel/one.json": catalog_doc([make_entry(1), make_entry(2)]),
        "threat_intel/two.json": catalog_doc([make_entry(3)]),
        "threat_intel/README.md": "docs, not json",
        "src/main.go": "package main",
    })
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["entries_added"] == 3
    assert payload["entries_total"] == 3
    assert payload["entries_skipped"] == 0
    assert payload["tag"] == mod.RELEASE_TAG
    assert payload["refreshed_at"] == mod._iso(NOW)
    merged = catalog_d(tmp_path) / "upstream.json"
    doc = json.loads(merged.read_text())
    assert doc["upstream_tag"] == mod.RELEASE_TAG
    assert len(doc["entries"]) == 3
    assert stat.S_IMODE(os.stat(merged).st_mode) == 0o600


def test_refresh_http_error_leaves_dir_untouched(tmp_path):
    mod = load_refresh()

    def fail(url, timeout_s=None, max_bytes=None):
        raise mod.FetchError("http_404")

    payload = mod.refresh(fetch=fail, home=tmp_path, now=NOW)
    assert payload["ok"] is False
    assert payload["error"] == "http_404"
    assert not (catalog_d(tmp_path) / "upstream.json").exists()


def test_refresh_oversized_blob_aborts(tmp_path):
    mod = load_refresh()
    blob = b"x" * (mod.MAX_TARBALL_BYTES + 1)
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert payload["ok"] is False
    assert payload["error"] == "too_large"
    assert not (catalog_d(tmp_path) / "upstream.json").exists()


def test_fetch_byte_cap_aborts_download(monkeypatch):
    mod = load_refresh()

    class Resp:
        headers = {}

        def read(self, n=-1):
            return b"x" * (n if n and n > 0 else 65536)

        def close(self):
            pass

    monkeypatch.setattr(mod.urllib.request, "urlopen",
                        lambda *a, **k: Resp())
    try:
        mod._fetch("https://example.invalid/x", timeout_s=5, max_bytes=1024)
        assert False, "expected FetchError"
    except mod.FetchError as exc:
        assert str(exc) == "too_large"


def test_fetch_rejects_non_https():
    mod = load_refresh()
    for bad in ("http://github.com/x", "file:///etc/passwd", ""):
        try:
            mod._fetch(bad, timeout_s=1, max_bytes=10)
            assert False, bad
        except mod.FetchError as exc:
            assert str(exc) == "scheme_not_https"


def test_refresh_schema_invalid_entries_skipped(tmp_path):
    mod = load_refresh()
    blob = make_tarball({
        "threat_intel/ok.json": catalog_doc([
            make_entry(1),
            make_entry(2, versions=[]),            # empty versions list
            make_entry(3, versions="1.0.0"),       # versions not a list
            {"id": "x", "name": "no ecosystem"},   # missing fields
            "not-a-dict",
        ]),
    })
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert payload["ok"] is True
    assert payload["entries_added"] == 1
    assert payload["entries_total"] == 1
    assert payload["entries_skipped"] == 4


def test_refresh_creates_catalog_d_modes(tmp_path):
    mod = load_refresh()
    blob = make_tarball({"threat_intel/one.json": catalog_doc([make_entry(1)])})
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert payload["ok"] is True
    catd = catalog_d(tmp_path)
    assert stat.S_IMODE(os.stat(catd).st_mode) == 0o700
    merged = catd / "upstream.json"
    assert stat.S_IMODE(os.stat(merged).st_mode) == 0o600


def test_refresh_rejects_traversal_and_nonregular(tmp_path):
    mod = load_refresh()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # Path traversal + absolute members: must never be read as intel.
        for name in ("pkg/threat_intel/../../evil.json",
                     "/abs/threat_intel/x.json",
                     "pkg/threat_intel/../x.json"):
            blob = catalog_doc([make_entry(9)]).encode()
            ti = tarfile.TarInfo(name)
            ti.size = len(blob)
            tf.addfile(ti, io.BytesIO(blob))
        # A symlink at the intel path: never followed.
        ti = tarfile.TarInfo("pkg/threat_intel/link.json")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc/passwd"
        tf.addfile(ti)
        # One real advisory keeps the refresh honest.
        blob = catalog_doc([make_entry(1)]).encode()
        ti = tarfile.TarInfo("pkg/threat_intel/ok.json")
        ti.size = len(blob)
        tf.addfile(ti, io.BytesIO(blob))
    payload = mod.refresh(fetch=fake_fetch(buf.getvalue()),
                          home=tmp_path, now=NOW)
    assert payload["ok"] is True
    assert payload["entries_total"] == 1
    doc = json.loads((catalog_d(tmp_path) / "upstream.json").read_text())
    assert [e["id"] for e in doc["entries"]] == ["adv-1"]


def test_refresh_no_threat_intel_is_error(tmp_path):
    mod = load_refresh()
    blob = make_tarball({"src/main.go": "package main", "README.md": "x"})
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert payload["ok"] is False
    assert payload["error"] == "no_threat_intel"
    assert not (catalog_d(tmp_path) / "upstream.json").exists()


def test_refresh_bad_tarball_is_error(tmp_path):
    mod = load_refresh()
    payload = mod.refresh(fetch=fake_fetch(b"not a tarball"),
                          home=tmp_path, now=NOW)
    assert payload["ok"] is False
    assert payload["error"] == "bad_tarball"


def test_refresh_entries_added_is_delta_vs_prior(tmp_path):
    mod = load_refresh()
    catd = catalog_d(tmp_path)
    catd.mkdir(parents=True)
    (catd / "upstream.json").write_text(catalog_doc([make_entry(1)]))
    blob = make_tarball({
        "threat_intel/one.json": catalog_doc([make_entry(1), make_entry(2)]),
    })
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert payload["ok"] is True
    assert payload["entries_added"] == 1   # adv-2 only; adv-1 already known
    assert payload["entries_total"] == 2


def test_refresh_never_prints_advisory_bodies(tmp_path):
    mod = load_refresh()
    blob = make_tarball({
        "threat_intel/one.json": catalog_doc(
            [make_entry(1, name="SECRET-ADVISORY-NAME")]),
    })
    payload = mod.refresh(fetch=fake_fetch(blob), home=tmp_path, now=NOW)
    assert "SECRET-ADVISORY-NAME" not in json.dumps(payload)
    assert "advisory 1" not in json.dumps(payload)
