"""Tests for scripts/check-qml-syntax.py: a missing qmllint must not pass in CI."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-qml-syntax.py"


def load():
    spec = importlib.util.spec_from_file_location("check_qml_syntax", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_qmllint_skips_locally(monkeypatch) -> None:
    mod = load()
    monkeypatch.setattr(mod, "find_qmllint", lambda: None)
    monkeypatch.delenv("REQUIRE_QMLLINT", raising=False)
    assert mod.main() == 0


def test_missing_qmllint_fails_when_required(monkeypatch) -> None:
    mod = load()
    monkeypatch.setattr(mod, "find_qmllint", lambda: None)
    monkeypatch.setenv("REQUIRE_QMLLINT", "1")
    assert mod.main() == 1
