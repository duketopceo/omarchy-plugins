"""Tests for shared/qml (U5): structure everywhere, live behaviour when qs exists."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "shared" / "qml"
COMPONENTS = ["PluginRoot", "ProcEnv", "DeadlineProcess", "VisibilityGate", "StaleLabel", "ToastStack"]
QS = shutil.which("qs")
QMLLINT = Path("/usr/lib/qt6/bin/qmllint")


def src(name: str) -> str:
    return (QML / f"{name}.qml").read_text()


def code(name: str) -> str:
    """Component source with // comments removed, for code-only assertions."""
    return "\n".join(line.split("//", 1)[0] for line in src(name).splitlines())


def test_every_component_exists() -> None:
    for name in COMPONENTS:
        assert (QML / f"{name}.qml").is_file(), name


def test_procenv_never_uses_null_values() -> None:
    # Under clearEnvironment, a null value INHERITS the shell's variable.
    body = src("ProcEnv")
    assert not re.search(r'"[A-Z_]+"\s*:\s*null', body)
    assert "/usr/bin:/bin:/usr/sbin:/sbin" in body


def test_deadline_process_uses_process_id_and_a_clean_killer() -> None:
    body = code("DeadlineProcess")
    assert "processId" in body
    assert not re.search(r"\bproc\.pid\b", body)
    assert "execDetached" not in body
    assert "helperAlarmS" in body
    assert '"/usr/bin/kill", "-KILL", "--"' in body


def test_visibility_gate_has_no_lid_input_and_reads_lock_service() -> None:
    body = code("VisibilityGate")
    assert "omarchy.lock" in body
    assert "signal revealed()" in body
    assert not re.search(r"\blid", body, re.I)


def test_toast_stack_policy_strict_and_plain_text() -> None:
    body = src("ToastStack")
    assert '["info", "low", "medium", "high", "critical"]' in body
    assert "if (root.dnd) return" in body
    for block in re.findall(r"Text \{[^}]*\}", body):
        assert "Text.PlainText" in block
    assert not re.search(r"#[0-9a-fA-F]{6}\b", body)


@pytest.mark.skipif(not QMLLINT.exists(), reason="qmllint unavailable")
def test_qmllint_reports_no_syntax_errors() -> None:
    for name in COMPONENTS:
        out = subprocess.run([str(QMLLINT), str(QML / f"{name}.qml")], capture_output=True, text=True)
        text = out.stdout + out.stderr
        assert not re.search(r"Syntax|Expected token|Unexpected token", text), (name, text)


SMOKE = """
import QtQuick
import Quickshell
import Quickshell.Io
import "lib"

ShellRoot {
  id: top
  property string out: Quickshell.env("QSLIB_OUT")
  PluginRoot { id: pr; url: "file:///tmp/my%20plugin/" }
  ProcEnv { id: pe; extra: ({ "OPENROUTER_API_KEY": "x", "MY_FLAG": "1" }) }
  StaleLabel { id: sl; intervalMs: 1000 }
  DeadlineProcess {
    id: envProc
    command: ["/usr/bin/sh", "-c", "/usr/bin/env > " + top.out + ".env"]
    environment: pe.env
    deadlineMs: 5000
    onExited: slowProc.start()
  }
  DeadlineProcess {
    id: slowProc
    command: ["/usr/bin/setsid", "/usr/bin/sh", "-c", "/usr/bin/sleep 30 & echo $! > " + top.out + ".gc; wait"]
    environment: pe.env
    deadlineMs: 800
    onExited: {
      sl.lastGoodMs = Date.now() - 5000; sl.nowMs = Date.now(); sl.failures = 3
      writer.setText(JSON.stringify({ root: pr.path, timedOut: slowProc.timedOut,
        stale: sl.stale, age: sl.ageText, nextDelay: sl.nextDelayMs }))
      quitTimer.start()
    }
  }
  FileView { id: writer; path: top.out + ".json"; atomicWrites: true }
  Timer { id: quitTimer; interval: 300; onTriggered: Qt.quit() }
  Component.onCompleted: envProc.start()
}
"""


@pytest.mark.skipif(QS is None, reason="quickshell (qs) unavailable")
def test_live_components_offscreen(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    (cfg / "lib").mkdir(parents=True)
    for name in ["PluginRoot", "ProcEnv", "DeadlineProcess", "StaleLabel"]:
        shutil.copy(QML / f"{name}.qml", cfg / "lib")
    (cfg / "shell.qml").write_text(SMOKE)
    out = tmp_path / "out"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QSLIB_OUT=str(out), OPENROUTER_API_KEY="leak-check")
    try:
        subprocess.run([QS, "-p", str(cfg / "shell.qml")], env=env, capture_output=True, timeout=25)
    except subprocess.TimeoutExpired:
        pytest.fail("qs smoke run did not exit")
    result_file = out.with_suffix(".json")
    if not result_file.exists():
        pytest.skip("qs could not run offscreen here")
    result = json.loads(result_file.read_text())
    assert result["root"] == "/tmp/my plugin"
    assert result["timedOut"] is True
    assert result["stale"] is True and result["age"] == "5s ago"
    assert result["nextDelay"] == 8000
    env_seen = out.with_suffix(".env").read_text()
    assert "leak-check" not in env_seen and "OPENROUTER" not in env_seen
    assert "PATH=/usr/bin:/bin:/usr/sbin:/sbin\n" in env_seen
    assert "MY_FLAG=1\n" in env_seen
    grandchild = int(out.with_suffix(".gc").read_text())
    time.sleep(0.5)
    try:
        os.kill(grandchild, 0)
    except ProcessLookupError:
        return
    os.kill(grandchild, signal.SIGKILL)
    pytest.fail("deadline group-kill left the grandchild running")
