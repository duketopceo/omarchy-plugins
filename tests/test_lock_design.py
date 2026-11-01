"""The Wisp Dashboard lock design: theme-only colors, no private data, clean lint."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "lock-designs" / "WispDashboard.qml"
INSTALL = ROOT / "scripts" / "install-lock-design.sh"
TEXT = DESIGN.read_text()


def test_colors_come_from_the_theme() -> None:
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", TEXT)
    assert not re.search(r"Qt\.rgba?\(", TEXT)


def test_no_private_data_is_read() -> None:
    # Wisp's state file carries transcripts; notification files carry text.
    assert "state.json" not in TEXT
    assert "XDG_RUNTIME_DIR" not in TEXT
    assert "FileView" not in TEXT
    assert "Process" not in TEXT
    assert "notifications/history" in TEXT  # counted by file name only


def test_keeps_the_explorer_import() -> None:
    assert 'import "../plugins/io.github.sirjul1337.lock-explorer/designs"' in TEXT


def _qmllint() -> str | None:
    return shutil.which("qmllint") or (
        "/usr/lib/qt6/bin/qmllint" if os.path.exists("/usr/lib/qt6/bin/qmllint") else None
    )


@pytest.mark.skipif(_qmllint() is None, reason="qmllint not installed")
def test_qmllint_reports_no_errors() -> None:
    out = subprocess.run([_qmllint(), str(DESIGN)], capture_output=True, text=True)
    errors = [ln for ln in (out.stdout + out.stderr).splitlines() if ln.startswith("Error")]
    assert errors == []


def test_install_copies_into_the_design_folder(tmp_path) -> None:
    env = dict(os.environ, LOCK_DESIGNS_DIR=str(tmp_path / "designs"))
    subprocess.run([str(INSTALL), "--no-rescan"], check=True, env=env, capture_output=True)
    installed = tmp_path / "designs" / "WispDashboard.qml"
    assert installed.is_file() and not installed.is_symlink()
    assert installed.read_text() == TEXT
