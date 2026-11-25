"""Regression tests for equivalent shortcut modifier names."""

import json
import os
from pathlib import Path
import subprocess
import sys


RECORDER = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.hotkey-tally/bin/hotkey-tally.py"


def test_control_alias_matches_ctrl_menu_record(tmp_path: Path) -> None:
    env = {**os.environ, "XDG_STATE_HOME": str(tmp_path)}
    subprocess.run(
        [sys.executable, str(RECORDER), "record", "--key", "CONTROL + B", "--label", "Browser"],
        env=env,
        check=True,
    )
    result = subprocess.run(
        [sys.executable, str(RECORDER), "annotate"],
        input="CTRL + B → Browser\texec\tbrowser\n",
        text=True,
        env=env,
        capture_output=True,
        check=True,
    )
    assert "Browser  ×1" in result.stdout
    row = json.loads((tmp_path / "hotkey-tally/uses.jsonl").read_text())
    assert row["key"] == "CONTROL + B"
