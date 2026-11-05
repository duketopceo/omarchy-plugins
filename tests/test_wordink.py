from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/io.github.duketopceo.wordink"
INSTALL = "curl -fsSL https://github.com/duketopceo/WordInk/releases/latest/download/install.sh | sh"


def test_manifest_shape() -> None:
    m = json.loads((PLUGIN / "manifest.json").read_text())
    assert m["id"] == "io.github.duketopceo.wordink"
    assert m["kinds"] == ["bar-widget"]
    assert m["entryPoints"] == {"barWidget": "Panel.qml"}
    assert m["barWidget"]["category"] == "Productivity"
    assert m["barWidget"]["allowMultiple"] is False
    assert m["license"] == "MIT"


def test_catalog_entry_matches_manifest() -> None:
    m = json.loads((PLUGIN / "manifest.json").read_text())
    cat = json.loads((ROOT / "catalog.json").read_text())
    entry = next(p for p in cat["plugins"] if p["id"] == m["id"])
    assert entry["version"] == m["version"]
    assert entry["path"] == "plugins/io.github.duketopceo.wordink"


def test_launcher_reports_missing_cli_as_127() -> None:
    r = subprocess.run(
        ["/bin/sh", str(PLUGIN / "bin/wordink-cli.sh"), "status"],
        env={"HOME": "/nonexistent-home", "PATH": "/nonexistent"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 127


def test_panel_contract() -> None:
    qml = (PLUGIN / "Panel.qml").read_text()
    assert INSTALL in qml
    assert INSTALL in (PLUGIN / "README.md").read_text()
    for needle in (
        '"dictation", "toggle"',
        '"logs", "-f"',
        '"status", "--json"',
        '"usage", "--window", "week"',
        '"diagnostics"',
        "code === 3",
        "interval: 5000",
    ):
        assert needle in qml, needle
    # R11: local CLI only
    for banned in ("http://", "XMLHttpRequest", "fetch(", "curl "):
        assert banned not in qml.replace(INSTALL, "")
