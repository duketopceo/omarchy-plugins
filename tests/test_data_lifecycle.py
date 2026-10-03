from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "data-lifecycle.json"
CHECKER = ROOT / "scripts" / "check-data-lifecycle.py"


def load_checker():
    assert CHECKER.exists(), f"data lifecycle checker is missing: {CHECKER}"
    spec = importlib.util.spec_from_file_location("check_data_lifecycle", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_policy_declares_voice_and_data_ownership() -> None:
    policy = json.loads(POLICY.read_text())
    assert policy["voice"]["default"] == "hancore.voxtype-enhance"
    assert policy["voice"]["alternate"] == "io.github.duketopceo.dim"
    assert policy["voice"]["simultaneous_allowed"] is False
    required = {
        "screen_capture",
        "voice",
        "clipboard",
        "messages",
        "calendar",
        "finance",
        "weather",
    }
    assert required <= {surface["id"] for surface in policy["surfaces"]}
    for surface in policy["surfaces"]:
        assert surface["purpose"]
        assert surface["egress"]
        assert surface["retention"]
        assert surface["pause"]
        assert surface["delete"]
        assert surface["export"]


def test_policy_passes_structural_validation() -> None:
    checker = load_checker()
    errors = checker.validate_policy(json.loads(POLICY.read_text()))
    assert errors == []


def test_policy_validation_requires_lifecycle_controls() -> None:
    checker = load_checker()
    policy = json.loads(POLICY.read_text())
    del policy["surfaces"][0]["delete"]
    errors = checker.validate_policy(policy)
    assert any("delete" in error for error in errors)


def test_policy_contains_no_secret_or_host_path_values() -> None:
    serialized = POLICY.read_text()
    assert "/home/" not in serialized
    assert "sk-" not in serialized
    assert "password" not in serialized.lower()
