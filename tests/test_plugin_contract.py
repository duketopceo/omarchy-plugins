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


# --- estate rules (U7): warnings by default, errors for shared-lib consumers ---

def _plugin(tmp_path: Path, files: dict[str, str], manifest: dict | None = None) -> Path:
    import json
    plugin = tmp_path / "demo"
    plugin.mkdir()
    (plugin / "manifest.json").write_text(json.dumps(manifest or {
        "id": "demo", "kinds": ["bar-widget"], "entryPoints": {"barWidget": "Panel.qml"}}))
    for rel, text in files.items():
        path = plugin / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return plugin


def _rules(findings: list[dict]) -> dict[str, str]:
    return {f["rule"]: f["severity"] for f in findings}


UNGATED = """import QtQuick
import Quickshell.Io
Item {
  Process { id: p; command: ["/usr/bin/true"] }
  Timer { interval: 5000; running: true; repeat: true; onTriggered: p.running = true }
}
"""


def test_ungated_polling_timer_is_flagged(tmp_path: Path) -> None:
    module = load_module()
    plugin = _plugin(tmp_path, {"Panel.qml": UNGATED})
    assert _rules(module.scan_plugin(plugin)).get("ungated-poll") == "warning"


def test_polling_timer_bound_to_visibility_gate_passes(tmp_path: Path) -> None:
    module = load_module()
    gated = UNGATED.replace("running: true;", "running: gate.visible;")
    plugin = _plugin(tmp_path, {"Panel.qml": gated})
    assert "ungated-poll" not in _rules(module.scan_plugin(plugin))


def test_service_entry_may_poll_ungated(tmp_path: Path) -> None:
    module = load_module()
    plugin = _plugin(tmp_path, {"Service.qml": UNGATED}, {
        "id": "demo", "kinds": ["service"], "entryPoints": {"service": "Service.qml"}})
    assert "ungated-poll" not in _rules(module.scan_plugin(plugin))


def test_raw_process_and_pid_are_flagged(tmp_path: Path) -> None:
    module = load_module()
    src = UNGATED.replace("onTriggered: p.running = true", "onTriggered: console.log(p.pid)")
    rules = _rules(module.scan_plugin(_plugin(tmp_path, {"Panel.qml": src})))
    assert rules.get("raw-process") == "warning"
    assert rules.get("process-pid") == "warning"


def test_vendored_lib_is_not_scanned_for_raw_process(tmp_path: Path) -> None:
    module = load_module()
    lib = "import Quickshell.Io\nProcess { id: proc; property Process killer: Process {} }\n"
    plugin = _plugin(tmp_path, {"lib/DeadlineProcess.qml": lib})
    assert "raw-process" not in _rules(module.scan_plugin(plugin))


def test_exec_detached_is_flagged(tmp_path: Path) -> None:
    module = load_module()
    src = 'import Quickshell\nItem { Component.onCompleted: Quickshell.execDetached(["/usr/bin/xdg-open", "x"]) }\n'
    assert _rules(module.scan_plugin(_plugin(tmp_path, {"Panel.qml": src}))).get("exec-detached-env") == "warning"


def test_reserved_ipc_target_is_flagged(tmp_path: Path) -> None:
    module = load_module()
    src = 'import Quickshell.Io\nIpcHandler { target: "omarchy.power" }\n'
    assert _rules(module.scan_plugin(_plugin(tmp_path, {"Panel.qml": src}))).get("reserved-ipc") == "warning"


def test_helper_without_alarm_is_flagged(tmp_path: Path) -> None:
    module = load_module()
    helper = 'import json\n\ndef main():\n    print(json.dumps({}))\n\nif __name__ == "__main__":\n    main()\n'
    plugin = _plugin(tmp_path, {"bin/probe.py": helper})
    assert _rules(module.scan_plugin(plugin)).get("helper-alarm") == "warning"
    with_alarm = helper.replace("def main():", "import signal\n\ndef main():\n    signal.alarm(8)")
    (plugin / "bin" / "probe.py").write_text(with_alarm)
    assert "helper-alarm" not in _rules(module.scan_plugin(plugin))


def test_estate_rules_are_errors_for_shared_lib_consumers(tmp_path: Path) -> None:
    module = load_module()
    plugin = _plugin(tmp_path, {"Panel.qml": UNGATED})
    rules = _rules(module.scan_plugin(plugin, strict_estate=True))
    assert rules.get("ungated-poll") == "error"
    assert rules.get("raw-process") == "error"


def test_extensionless_python_helper_is_scanned(tmp_path: Path) -> None:
    module = load_module()
    helper = '#!/usr/bin/python3\nimport json\n\nif __name__ == "__main__":\n    print(json.dumps({}))\n'
    plugin = _plugin(tmp_path, {"bin/standby-data": helper})
    assert _rules(module.scan_plugin(plugin)).get("helper-alarm") == "warning"


def test_consumers_file_turns_estate_rules_into_errors(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    plugin = _plugin(tmp_path, {"Panel.qml": UNGATED})
    consumers = tmp_path / "consumers.txt"
    consumers.write_text("# opt-in\ndemo\n")
    monkeypatch.setattr(module, "CONSUMERS_FILE", consumers)
    rules = _rules(module.scan_plugin(plugin))
    assert rules.get("ungated-poll") == "error"
    assert rules.get("raw-process") == "error"
