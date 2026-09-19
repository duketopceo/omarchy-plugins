"""Tests for plugins/lukedaduke.agents (omarchy-agents fork).

The plugin ships no helpers of its own — the testable surface is the QML
itself: the embedded bash sync scan (executed for real against tmp dirs),
the frame parser the scan output feeds (ported from parseSyncScanOutput),
and structural checks on the QML source (PlainText coverage, provider
allowlist, process watchdogs, helper probe).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/lukedaduke.agents"
MAIN_QML = PLUGIN / "Main.qml"
PANEL_QML = PLUGIN / "Panel.qml"
MANIFEST = PLUGIN / "manifest.json"

PER_FILE_CAP = 1048576
MAX_FILES = 64

# ---------------------------------------------------------------- helpers


def main_src() -> str:
    return MAIN_QML.read_text()


def panel_src() -> str:
    return PANEL_QML.read_text()


def _unescape_qml_string(lit: str) -> str:
    """Undo the escapes used inside a double-quoted QML/JS string literal."""
    out = []
    i = 0
    while i < len(lit):
        ch = lit[i]
        if ch == "\\" and i + 1 < len(lit):
            nxt = lit[i + 1]
            out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def sync_scan_script() -> str:
    """The exact bash script Main.qml hands to `bash -c ... $0=<dir>`."""
    m = re.search(r'var script = "((?:[^"\\]|\\.)*)"', main_src())
    assert m, "startSyncScan() no longer defines a `var script` string"
    return _unescape_qml_string(m.group(1))


def run_scan(sync_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", sync_scan_script(), str(sync_dir)],
        capture_output=True, text=True, timeout=30,
    )


def qml_block(src: str, start: int) -> str:
    """Return the {...} block beginning at the brace after `start`."""
    open_idx = src.index("{", start)
    depth = 0
    for i in range(open_idx, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError("unbalanced braces in QML source")


def text_blocks(src: str) -> list[str]:
    return [qml_block(src, m.start()) for m in re.finditer(r"\bText\s*\{", src)]


def parse_sync_scan_output(output: str) -> list[dict]:
    """Python port of Main.qml parseSyncScanOutput()'s frame splitting.

    Kept in lockstep: `===<path>===` starts a frame, `=== EOM ===` ends it,
    each frame body is JSON.parsed and kept only when it carries providers.
    """
    snapshots = []
    current_path = ""
    current_json: list[str] = []

    def flush() -> None:
        nonlocal current_path, current_json
        if current_path == "":
            return
        raw = "\n".join(current_json).strip()
        try:
            parsed = json.loads(raw)
            # QML keeps `parsed && parsed.providers` — JS truthiness: an empty
            # object counts, 0/""/false/null do not.
            providers = parsed.get("providers") if isinstance(parsed, dict) else None
            if providers is not None and providers is not False and providers != 0 and providers != "":
                snapshots.append(parsed)
        except Exception:
            pass
        current_path = ""
        current_json = []

    for line in output.split("\n"):
        start = re.match(r"^===(.+)===$", line)
        if start and line != "=== EOM ===":
            flush()
            current_path = start.group(1)
            current_json = []
            continue
        if line == "=== EOM ===":
            flush()
            continue
        if current_path != "":
            current_json.append(line)
    flush()
    return snapshots


def snapshot(device: str = "laptop", **providers) -> dict:
    return {
        "schemaVersion": 1,
        "deviceId": device,
        "updatedAt": "2026-09-17T00:00:00Z",
        "providers": providers,
    }


# ------------------------------------------------------------- sync scan


def test_scan_script_extracted_and_bounded() -> None:
    script = sync_scan_script()
    # contract: find-based scan, no glob cat
    assert 'cat "$f"' not in script
    assert "find" in script and "-type f" in script
    assert "-size" in script and "head -c" in script


def test_scan_frames_regular_json_files(tmp_path: Path) -> None:
    snap = snapshot("laptop", claude={"totalPrompts": 3})
    other = snapshot("desktop", codex={"totalPrompts": 1})
    (tmp_path / "laptop.json").write_text(json.dumps(snap, indent=2))
    (tmp_path / "desktop.json").write_text(json.dumps(other))
    res = run_scan(tmp_path)
    assert res.returncode == 0
    assert res.stdout.count("=== EOM ===") == 2
    assert f"==={tmp_path}/laptop.json===" in res.stdout
    parsed = parse_sync_scan_output(res.stdout)
    assert {p["deviceId"] for p in parsed} == {"laptop", "desktop"}


def test_scan_refuses_symlinks(tmp_path: Path) -> None:
    secret = tmp_path / "outside.json"
    secret.write_text(json.dumps(snapshot("evil", x={"totalPrompts": 9})))
    sync_dir = tmp_path / "sync"
    sync_dir.mkdir()
    (sync_dir / "link.json").symlink_to(secret)
    (sync_dir / "real.json").write_text(json.dumps(snapshot("ok", a={"totalPrompts": 1})))
    res = run_scan(sync_dir)
    assert res.returncode == 0
    assert "evil" not in res.stdout
    assert str(secret) not in res.stdout
    parsed = parse_sync_scan_output(res.stdout)
    assert [p["deviceId"] for p in parsed] == ["ok"]


def test_scan_refuses_dangling_and_dir_symlinks(tmp_path: Path) -> None:
    (tmp_path / "dangling.json").symlink_to(tmp_path / "nonexistent.json")
    real_dir = tmp_path / "realdir.json"  # a directory whose name ends .json
    real_dir.mkdir()
    (real_dir / "inner.json").write_text("{}")
    (tmp_path / "dirlink.json").symlink_to(real_dir, target_is_directory=True)
    res = run_scan(tmp_path)
    assert res.returncode == 0
    assert res.stdout == ""


def test_scan_skips_files_at_or_over_1mib(tmp_path: Path) -> None:
    small = tmp_path / "small.json"
    small.write_text(json.dumps(snapshot("small", a={"totalPrompts": 1})))
    # strictly under the cap passes
    assert small.stat().st_size < PER_FILE_CAP
    over = tmp_path / "over.json"
    over.write_bytes(b" " * PER_FILE_CAP)
    huge = tmp_path / "huge.json"
    huge.write_bytes(b"x" * (PER_FILE_CAP * 2))
    res = run_scan(tmp_path)
    assert res.returncode == 0
    assert "over.json" not in res.stdout
    assert "huge.json" not in res.stdout
    parsed = parse_sync_scan_output(res.stdout)
    assert [p["deviceId"] for p in parsed] == ["small"]


def test_scan_file_size_backstop_caps_output(tmp_path: Path) -> None:
    # A file just under the cap must appear in full; the head -c backstop is
    # what bounds a file that grows after find's stat (not reproducible in a
    # test, so assert the cap exists and boundary files behave).
    body = json.dumps(snapshot("edge", a={"v": "y" * (PER_FILE_CAP - 300)}))
    f = tmp_path / "edge.json"
    f.write_text(body)
    assert f.stat().st_size < PER_FILE_CAP
    res = run_scan(tmp_path)
    assert res.returncode == 0
    parsed = parse_sync_scan_output(res.stdout)
    assert parsed[0]["deviceId"] == "edge"


def test_scan_caps_file_count(tmp_path: Path) -> None:
    for i in range(MAX_FILES + 6):
        (tmp_path / f"{i:03d}.json").write_text(
            json.dumps(snapshot(f"d{i}", a={"totalPrompts": i})))
    res = run_scan(tmp_path)
    assert res.returncode == 0
    assert res.stdout.count("=== EOM ===") == MAX_FILES
    assert len(parse_sync_scan_output(res.stdout)) == MAX_FILES


def test_scan_missing_dir_is_silent_success(tmp_path: Path) -> None:
    res = run_scan(tmp_path / "does-not-exist")
    assert res.returncode == 0
    assert res.stdout == ""


def test_scan_ignores_non_json_and_subdirs(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("{}")
    (tmp_path / "b.JSON.txt").write_text("{}")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "inner.json").write_text(json.dumps(snapshot("inner")))
    (tmp_path / "top.json").write_text(json.dumps(snapshot("top", a={"x": 1})))
    res = run_scan(tmp_path)
    assert res.returncode == 0
    parsed = parse_sync_scan_output(res.stdout)
    assert [p["deviceId"] for p in parsed] == ["top"]


# ------------------------------------------------------- frame parser port


def test_frame_parser_skips_bad_json_and_providerless(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{not json")
    (tmp_path / "empty.json").write_text(json.dumps({"deviceId": "x"}))
    (tmp_path / "good.json").write_text(
        json.dumps(snapshot("good", claude={"totalPrompts": 2}), indent=2)
    )
    parsed = parse_sync_scan_output(run_scan(tmp_path).stdout)
    assert [p["deviceId"] for p in parsed] == ["good"]


def test_frame_parser_survives_pretty_json(tmp_path: Path) -> None:
    # Marker-looking content inside JSON string values must not split frames.
    snap = snapshot("tricky", claude={"note": "=== EOM ===", "other": "===x==="})
    (tmp_path / "tricky.json").write_text(json.dumps(snap, indent=2))
    parsed = parse_sync_scan_output(run_scan(tmp_path).stdout)
    assert len(parsed) == 1
    assert parsed[0]["providers"]["claude"]["note"] == "=== EOM ==="


def test_scan_output_size_guard_present() -> None:
    src = main_src()
    assert "80 * 1024 * 1024" in src
    assert "oversized scan output" in src


# ---------------------------------------------------- structural: QML sinks


def test_every_text_element_is_plaintext() -> None:
    blocks = text_blocks(panel_src())
    assert len(blocks) >= 15, f"expected ~16 Text blocks, found {len(blocks)}"
    missing = [b for b in blocks if "textFormat: Text.PlainText" not in b]
    assert missing == [], f"{len(missing)} Text block(s) lack PlainText"


def test_tooltips_rely_on_plaintext_component() -> None:
    # PanelToolTip's own contentItem is Text.PlainText upstream; the panel
    # must not re-implement raw ToolTip/TextEdit sinks for dynamic strings.
    src = panel_src()
    assert src.count("PanelToolTip {") == 2
    assert "ToolTip {" not in src.replace("PanelToolTip {", "")
    assert "TextEdit" not in src and "TextArea" not in src


def test_provider_allowlist_matches_manifest_defaults() -> None:
    m = re.search(r"var allowed = \{([^}]*)\}", main_src())
    assert m, "providerEnabled() allowed map not found"
    allowed = set(re.findall(r"(\w+): true", m.group(1)))
    manifest = json.loads(MANIFEST.read_text())
    defaults = set(manifest["barWidget"]["defaults"]["providers"].keys())
    assert "fireworks" in allowed
    assert allowed == defaults, f"code/manifest drift: {allowed ^ defaults}"


def test_every_process_has_a_watchdog() -> None:
    src = main_src()
    proc_ids = re.findall(r"Process \{\s*id: (\w+)", src)
    assert proc_ids == [
        "listProcess", "helperCheckProcess", "updateProcess",
        "syncMkdirProcess", "syncScanProcess",
    ]
    for proc in proc_ids:
        assert f"{proc}.signal(9)" in src, f"{proc} has no watchdog kill"
        assert f"{proc}.running" in src


def test_processes_started_with_armed_deadline() -> None:
    src = main_src()
    # each deadline timer is restarted at its exec site and stopped on exit
    for deadline in [
        "listDeadline", "helperCheckDeadline", "updateDeadline",
        "syncMkdirDeadline", "syncScanDeadline",
    ]:
        assert f"{deadline}.restart()" in src, f"{deadline} never armed"
        assert f"{deadline}.stop()" in src, f"{deadline} never stopped"


def test_helper_existence_check_and_setup_state() -> None:
    src = main_src()
    assert '["test", "-x", root.updateBin]' in src
    assert "helperAvailable" in src and "helperMissing" in src
    panel = panel_src()
    assert "usage.helperMissing" in panel
    assert "Setup required" in panel
    # the bar icon must stay visible so the setup message is reachable
    assert "providers.length > 0 || usage.helperMissing" in panel


def test_record_derived_argv_is_gated() -> None:
    src = main_src()
    assert r"/^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(" in src
    # gate applied to both --except keys and positional agent ids
    assert 'command.push("--except", id)' in src
    assert re.search(r"isSafeArgValue\(id\)", src)
    assert re.search(r"isSafeArgValue\(agentIds\[i\]\)", src)
    # Panel's omarchy-agent <id> fallback is gated too
    assert r"/^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(id)" in panel_src()


def test_safe_arg_value_semantics() -> None:
    """Same regex as QML: plain ids pass, flag-looking values do not.

    The leading character must not be a dash — "--force" is all hyphens and
    letters, so a permissive body class alone cannot keep flags out.
    """
    rx = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    for good in ["claude", "a0", "gpt-5.6", "my_host.json", "x"]:
        assert rx.match(good)
    for bad in ["--force", "--except", "-f", "-", "a;b", "a b", "$(x)", "", "a/b"]:
        assert not rx.match(bad), bad


def test_refresh_interval_cannot_go_nan() -> None:
    src = main_src()
    assert "isFinite(n) ? Math.max(30, n) : 900" in src


def test_record_collections_capped_at_parse() -> None:
    src = main_src()
    assert "capList(record.limits, 16)" in src
    assert "capList(synced ? stats.recentDays : record.recentDays, 31)" in src
    assert src.count("capDict(") >= 3  # helper + todayTokensByModel + modelUsage
