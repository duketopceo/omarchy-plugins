from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-plugin-contract.py"


def load_module():
    assert SCRIPT.exists(), f"contract checker is missing: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("check_plugin_contract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dynamic_qml_text_requires_plain_text(tmp_path: Path) -> None:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    (plugin / "Panel.qml").write_text(
        "import QtQuick\nText { text: modelData.name }\n"
    )

    findings = module.scan_plugin(plugin)

    assert any(item["rule"] == "qml-plain-text" for item in findings)


def test_formatted_dynamic_qml_text_passes(tmp_path: Path) -> None:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    (plugin / "Panel.qml").write_text(
        "import QtQuick\nText { text: modelData.name; textFormat: Text.PlainText }\n"
    )

    findings = module.scan_plugin(plugin)

    assert not any(item["rule"] == "qml-plain-text" for item in findings)


def test_ambient_interpreter_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    (plugin / "Panel.qml").write_text(
        "import QtQuick\nProcess { executable: \"python3\" }\n"
    )

    findings = module.scan_plugin(plugin)

    assert any(item["rule"] == "fixed-executable" for item in findings)


def test_secret_elevation_path_is_rejected(tmp_path: Path) -> None:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    helper = plugin / "bin" / "start.sh"
    helper.parent.mkdir()
    helper.write_text("#!/bin/sh\nprintf '%s\\n' \"$PASSWORD\" | sudo -S helper\n")

    findings = module.scan_plugin(plugin)

    assert any(item["rule"] == "secret-elevation" for item in findings)


def test_https_network_urls_are_allowed(tmp_path: Path) -> None:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    helper = plugin / "bin" / "fetch.py"
    helper.parent.mkdir()
    helper.write_text("URL = 'https://example.invalid/data'\n")

    findings = module.scan_plugin(plugin)

    assert not any(item["rule"] == "https-only" for item in findings)


def _https_findings(tmp_path: Path, url: str) -> list[dict]:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    helper = plugin / "bin" / "fetch.py"
    helper.parent.mkdir()
    helper.write_text(f"URL = '{url}'\n")
    return [item for item in module.scan_plugin(plugin) if item["rule"] == "https-only"]


def test_loopback_ipv4_http_is_allowed(tmp_path: Path) -> None:
    assert _https_findings(tmp_path, "http://127.0.0.1:9211/mcp") == []


def test_loopback_ipv6_http_is_allowed(tmp_path: Path) -> None:
    assert _https_findings(tmp_path, "http://[::1]:9211/mcp") == []


def test_loopback_lookalike_host_still_requires_https(tmp_path: Path) -> None:
    assert _https_findings(tmp_path, "http://127.0.0.1.evil.example/x") != []


def test_localhost_prefixed_domain_still_requires_https(tmp_path: Path) -> None:
    assert _https_findings(tmp_path, "http://localhost.evil.com/x") != []


def test_private_lan_http_still_requires_https(tmp_path: Path) -> None:
    assert _https_findings(tmp_path, "http://10.0.0.1/x") != []


def test_timer_budget_understands_multiplication_expressions(tmp_path: Path) -> None:
    module = load_module()
    plugin = tmp_path / "demo"
    plugin.mkdir()
    (plugin / "Panel.qml").write_text(
        "import QtQuick\nTimer { interval: 5 * 60 * 1000; repeat: true }\n"
    )

    findings = module.scan_plugin(plugin)

    assert not any(item["rule"] == "timer-budget" for item in findings)


def test_owned_plugin_tree_has_no_contract_errors() -> None:
    module = load_module()
    findings = module.scan_tree(ROOT / "plugins")
    assert not [item for item in findings if item["severity"] == "error"]


def test_contract_tree_skips_legacy_backup_directories(tmp_path: Path) -> None:
    module = load_module()
    backup = tmp_path / "demo.bak.1"
    backup.mkdir()
    (backup / "manifest.json").write_text("{}")
    (backup / "Panel.qml").write_text("Text { text: modelData.name }\n")

    assert module.scan_tree(tmp_path) == []
