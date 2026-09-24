from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit-live-plugins.py"


def load_module():
    assert SCRIPT.exists(), f"inventory script is missing: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("audit_live_plugins", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_manifest(plugin_dir: Path, plugin_id: str, **overrides: object) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": 1,
        "id": plugin_id,
        "name": plugin_id,
        "version": "1.2.3",
        "author": "fixture-owner",
        "license": "MIT",
        "kinds": ["bar-widget"],
        "entryPoints": {"barWidget": "Panel.qml"},
    }
    manifest.update(overrides)
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
    (plugin_dir / "Panel.qml").write_text("// fixture\n")


def make_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture"
    write_manifest(fixture / "plugins" / "demo.widget", "demo.widget")
    write_manifest(
        fixture / "plugins" / "hosted.widget",
        "hosted.widget",
        kinds=["overlay"],
        entryPoints={"overlay": "Overlay.qml"},
    )
    (fixture / "plugins" / "hosted.widget" / "Overlay.qml").write_text("// fixture\n")
    shell = {
        "bar": {
            "layout": {
                "right": [
                    {
                        "id": "demo.widget",
                    },
                    {
                        "id": "demo.tray",
                        "widgets": [{"entry": {"id": "hosted.widget"}}],
                    },
                ]
            }
        },
        "plugins": ["demo.service"],
        "disabledPlugins": ["demo.disabled"],
    }
    (fixture / "shell.json").write_text(json.dumps(shell))
    registry = [
        {
            "id": "demo.widget",
            "name": "Demo",
            "kinds": ["bar-widget"],
            "enabled": True,
            "active": False,
            "firstParty": False,
        },
        {
            "id": "hosted.widget",
            "name": "Hosted",
            "kinds": ["overlay"],
            "enabled": True,
            "active": False,
            "firstParty": False,
        },
        {
            "id": "demo.service",
            "name": "Service",
            "kinds": ["service"],
            "enabled": True,
            "active": False,
            "firstParty": False,
        },
        {
            "id": "demo.disabled",
            "name": "Disabled",
            "kinds": ["bar-widget"],
            "enabled": False,
            "active": False,
            "firstParty": False,
        },
        {
            "id": "demo.host",
            "name": "Host-only",
            "kinds": ["panel"],
            "enabled": True,
            "active": False,
            "firstParty": True,
        },
        {
            "id": "demo.tray",
            "name": "Fixture tray",
            "kinds": ["bar-widget"],
            "enabled": True,
            "active": False,
            "firstParty": False,
        },
    ]
    (fixture / "registry.ndjson").write_text(
        "\n".join(json.dumps(item) for item in registry) + "\n"
    )
    (fixture / "services.json").write_text(
        json.dumps(
            {
                "demo.service": {
                    "loaded": True,
                    "running": True,
                    "health": "healthy",
                }
            }
        )
    )
    (fixture / "dispositions.json").write_text(
        json.dumps({"demo.widget": "keep", "hosted.widget": "keep"})
    )
    return fixture


def test_fixture_audit_distinguishes_direct_hosted_and_runtime_state(tmp_path: Path) -> None:
    module = load_module()
    fixture = make_fixture(tmp_path)
    shell = json.loads((fixture / "shell.json").read_text())
    registry = [json.loads(line) for line in (fixture / "registry.ndjson").read_text().splitlines()]
    services = json.loads((fixture / "services.json").read_text())
    dispositions = json.loads((fixture / "dispositions.json").read_text())

    inventory = module.audit_inventory(
        plugin_root=fixture / "plugins",
        shell_config=shell,
        registry_entries=registry,
        services=services,
        dispositions=dispositions,
        git_status={"demo.widget": "dirty", "hosted.widget": "clean"},
        command_status={"python": "present"},
    )

    assert inventory["counts"] == {
        "discovered": 6,
        "enabled": 5,
        "direct_bar": 2,
        "enabled_non_bar": 3,
        "hosted": 1,
        "duplicates": 0,
        "warnings": 0,
    }
    by_id = {entry["id"]: entry for entry in inventory["plugins"]}
    assert by_id["demo.widget"]["state"]["direct_bar"] is True
    assert by_id["demo.widget"]["state"]["loaded"] is False
    assert by_id["demo.widget"]["source_status"] == "dirty"
    assert by_id["hosted.widget"]["state"]["hosted"] is True
    assert by_id["hosted.widget"]["status"] == "hosted"
    assert by_id["demo.service"]["status"] == "healthy"
    assert by_id["demo.disabled"]["status"] == "disabled"
    assert by_id["demo.host"]["source"] == "host"
    assert str(fixture) not in json.dumps(inventory)


def test_audit_redacts_secret_shaped_values_and_reports_duplicates(tmp_path: Path) -> None:
    module = load_module()
    fixture = make_fixture(tmp_path)
    write_manifest(fixture / "plugins" / "demo.widget.bak.1", "demo.widget")
    shell = {"bar": {"layout": {"right": [{"id": "demo.widget"}]}}, "plugins": []}
    registry = [
        {
            "id": "demo.widget",
            "enabled": True,
            "firstParty": False,
            "apiKey": "fixture-api-value",
            "authorization": "fixture-authorization-value",
        }
    ]

    inventory = module.audit_inventory(
        plugin_root=fixture / "plugins",
        shell_config=shell,
        registry_entries=registry,
    )

    serialized = json.dumps(inventory)
    assert "fixture-api-value" not in serialized
    assert "fixture-authorization-value" not in serialized
    duplicate = next(
        entry for entry in inventory["plugins"] if entry["id"] == "demo.widget"
    )
    assert duplicate["manifest_occurrences"] == 2
    assert inventory["counts"]["duplicates"] == 1
    assert inventory["counts"]["warnings"] >= 1
    assert str(fixture) not in serialized


def test_markdown_report_contains_counts_and_plugin_rows(tmp_path: Path) -> None:
    module = load_module()
    fixture = make_fixture(tmp_path)
    shell = json.loads((fixture / "shell.json").read_text())
    registry = [json.loads(line) for line in (fixture / "registry.ndjson").read_text().splitlines()]
    inventory = module.audit_inventory(
        plugin_root=fixture / "plugins",
        shell_config=shell,
        registry_entries=registry,
    )

    report = module.render_markdown(inventory)

    assert "## Summary" in report
    assert "## Host profile" in report
    assert "## Plugin inventory" in report
    assert "| `demo.widget` |" in report
    assert "hosted.widget" in report
    assert str(fixture) not in report


def test_fixture_loader_uses_only_supplied_roots(tmp_path: Path) -> None:
    module = load_module()
    fixture = make_fixture(tmp_path)
    inventory = module.audit_fixture(fixture, probe_git=False)
    assert inventory["counts"]["discovered"] == 6
    assert "demo.widget" in {entry["id"] for entry in inventory["plugins"]}
    assert str(tmp_path) not in json.dumps(inventory)


def test_live_registry_parser_accepts_the_hosts_json_array(monkeypatch) -> None:
    module = load_module()

    class Result:
        returncode = 0
        stdout = json.dumps([{"id": "demo.widget", "enabled": True}])
        stderr = ""

    monkeypatch.setattr(module.shutil, "which", lambda _name: "/fake/omarchy-shell")
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: Result())

    assert module._run_live_registry() == [{"id": "demo.widget", "enabled": True}]


def test_probe_environment_excludes_ambient_secret_variables(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-be-inherited")
    monkeypatch.setenv("SOME_AUTH_TOKEN", "should-not-be-inherited")
    monkeypatch.setenv("OMARCHY_PATH", "/opt/omarchy")
    environment = module._probe_environment()
    assert "OPENAI_API_KEY" not in environment
    assert "SOME_AUTH_TOKEN" not in environment
    assert environment["OMARCHY_PATH"] == "/opt/omarchy"
    assert "PATH" in environment


def test_invalid_utf8_registry_is_reported_as_an_inventory_error(tmp_path: Path) -> None:
    module = load_module()
    registry = tmp_path / "registry.ndjson"
    registry.write_bytes(b"\xff")

    with pytest.raises(module.InventoryError):
        module.read_ndjson(registry)


def test_live_service_probe_distinguishes_user_and_system_units(monkeypatch) -> None:
    module = load_module()
    calls: list[list[str]] = []

    class Result:
        stderr = ""

        def __init__(self, stdout: str, returncode: int) -> None:
            self.stdout = stdout
            self.returncode = returncode

    def run(argv, **_kwargs):
        calls.append(argv)
        if "dimd.service" in argv:
            return Result("inactive\n", 3)
        if "dayflow-capture.service" in argv:
            return Result("failed\n", 3)
        return Result("active\n", 0)

    monkeypatch.setattr(module.subprocess, "run", run)
    states = module._collect_live_services()

    assert states["lukedaduke.fan"]["state"] == "active"
    assert states["io.github.duketopceo.dayflow"]["health"] == "degraded"
    assert states["io.github.duketopceo.dim"]["state"] == "inactive"
    assert any("--user" in call for call in calls if "dimd.service" in call)
    assert all("--user" not in call for call in calls if "omarchy-fan-daemon.service" in call)
