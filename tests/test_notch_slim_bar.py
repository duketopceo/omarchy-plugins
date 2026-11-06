"""bin/notch-slim-bar: move, remove, dry-run and undo on a fixture shell.json."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/bin/notch-slim-bar"
FIXTURE = Path(__file__).resolve().parent / "fixtures/notch_bar.json"

REMOVED = {
    "omarchy.tailscale", "io.github.duketopceo.nordvpn", "io.github.duketopceo.snapdex",
    "io.github.duketopceo.wordink", "mohamedmansour.finance", "omarchy.elsewhen",
    "omarchy.active-window", "lukedaduke.lidguard", "io.github.tyrichards.tray",
    "io.github.ncr.omaphones", "omarchy.tray",
}
KEPT = {"omarchy.indicators", "omarchy.microphone", "nixfred.blip",
        "io.github.duketopceo.wisp", "omarchy.system-update"}
BACKUP = "*.bak-notch-v4*"
SIDECAR = ".notch-v4-removed.json"


def run(cfg, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--config", str(cfg), *args], capture_output=True, text=True)


def ids(cfg):
    layout = json.loads(Path(cfg).read_text())["bar"]["layout"]
    return {section: [e["id"] for e in entries] for section, entries in layout.items()}


def make(tmp_path):
    cfg = tmp_path / "shell.json"
    shutil.copy(FIXTURE, cfg)
    return cfg


def test_dry_run_writes_nothing(tmp_path):
    cfg = make(tmp_path)
    before = cfg.read_bytes()
    r = run(cfg, "--dry-run")
    assert r.returncode == 0
    for wid in REMOVED:
        assert wid in r.stdout
    assert "move   omarchy.system-update" in r.stdout
    assert cfg.read_bytes() == before
    assert not list(tmp_path.glob("shell.json" + BACKUP))


def test_removes_only_covered_widgets_and_backs_up(tmp_path):
    cfg = make(tmp_path)
    original = cfg.read_bytes()
    assert run(cfg).returncode == 0
    flat = {i for section in ids(cfg).values() for i in section}
    assert not flat & REMOVED
    assert KEPT <= flat
    assert {"omarchy.workspaces", "omarchy.menu", "omarchy.network", "example.tray", "example.panel"} <= flat
    backup = list(tmp_path.glob("shell.json" + BACKUP))
    assert len(backup) == 1 and backup[0].read_bytes() == original
    # Other top-level config is untouched.
    assert json.loads(cfg.read_text())["plugins"] == [{"id": "io.github.duketopceo.notch", "snapdex": True}]


def test_moves_system_update_to_the_front_of_the_right(tmp_path):
    cfg = make(tmp_path)
    assert run(cfg).returncode == 0
    layout = ids(cfg)
    assert "omarchy.system-update" not in layout["left"]
    assert layout["right"][0] == "omarchy.system-update"
    # Extra keys survive the move.
    entry = json.loads(cfg.read_text())["bar"]["layout"]["right"][0]
    assert entry["autoCheckUpdates"] is True


def test_idempotent(tmp_path):
    cfg = make(tmp_path)
    run(cfg)
    after = cfg.read_bytes()
    r = run(cfg)
    assert r.returncode == 0 and "nothing to do" in r.stdout
    assert cfg.read_bytes() == after


def test_undo_restores_positions_and_entries(tmp_path):
    cfg = make(tmp_path)
    original = json.loads(cfg.read_text())
    run(cfg)
    r = run(cfg, "--undo")
    assert r.returncode == 0
    assert json.loads(cfg.read_text()) == original
    assert not Path(str(cfg) + SIDECAR).exists()


def test_undo_keeps_later_edits(tmp_path):
    cfg = make(tmp_path)
    run(cfg)
    data = json.loads(cfg.read_text())
    data["bar"]["layout"]["right"].append({"id": "example.added-later"})
    cfg.write_text(json.dumps(data))
    run(cfg, "--undo")
    layout = ids(cfg)
    assert "example.added-later" in layout["right"]
    assert "omarchy.tailscale" in layout["right"]
    assert "omarchy.system-update" in layout["left"]


def test_undo_without_record_fails_cleanly(tmp_path):
    cfg = make(tmp_path)
    r = run(cfg, "--undo")
    assert r.returncode == 1 and "bak-notch-v4" in r.stderr


def test_existing_backup_is_not_overwritten(tmp_path):
    cfg = make(tmp_path)
    old = tmp_path / "shell.json.bak-notch-v4"
    old.write_text("{}")
    run(cfg)
    assert old.read_text() == "{}"
    assert len(list(tmp_path.glob("shell.json" + BACKUP))) == 2


def test_unreadable_config_is_an_error(tmp_path):
    r = run(tmp_path / "missing.json")
    assert r.returncode == 1
