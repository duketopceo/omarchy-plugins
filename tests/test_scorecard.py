from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-scorecard.py"
spec = importlib.util.spec_from_file_location("check_scorecard", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DATE = "2026-10-03"


def card(plugin="demo.a", status="pass", x86=DATE, spawn=0.5):
    return {
        "plugin": plugin,
        "criteria": {k: status for k in mod.CRITERIA},
        "manual": {
            "spawn_measurement": {"value": spawn, "date": DATE},
            "asahi_pass": {"date": DATE},
            "x86_64_pass": {"date": x86},
        },
    }


def build(tmp_path, catalog_ids, cards, retiring=(), plugin_dirs=None, waivers=None, budgets=None, estate_budget=None):
    (tmp_path / "docs" / "reviews").mkdir(parents=True)
    (tmp_path / "plugins").mkdir()
    config = {"budgets": budgets if budgets is not None else {"demo.a": 1},
              "retiring": list(retiring), "waivers": waivers or {}}
    if estate_budget is not None:
        config["estate_budget"] = estate_budget
    (tmp_path / "docs" / "SCORECARD.md").write_text("# s\n\n```scorecard-config\n" + json.dumps(config) + "\n```\n")
    (tmp_path / "catalog.json").write_text(json.dumps({"plugins": [{"id": i} for i in catalog_ids]}))
    for plugin in plugin_dirs if plugin_dirs is not None else catalog_ids:
        (tmp_path / "plugins" / plugin).mkdir()
    for plugin, c in cards.items():
        (tmp_path / "docs" / "reviews" / f"{plugin}.md").write_text("# r\n\n```scorecard\n" + json.dumps(c) + "\n```\n")
    return tmp_path


def run(root, release=False):
    return mod.check(root=root, release=release)


def test_retiring_without_scorecard_passes_default(tmp_path):
    root = build(tmp_path, ["old.x"], {}, retiring=["old.x"])
    errors, states = run(root)
    assert errors == [] and states["old.x"] == "retiring"


def test_all_passing_and_dated_is_clean_in_both_modes(tmp_path):
    root = build(tmp_path, ["demo.a"], {"demo.a": card()})
    for release in (False, True):
        errors, states = run(root, release)
        assert errors == [] and states["demo.a"] == "pass"


def test_missing_x86_date_is_pending_and_fails_release_only(tmp_path):
    root = build(tmp_path, ["demo.a"], {"demo.a": card(x86=None)})
    errors, states = run(root)
    assert errors == [] and states["demo.a"] == "pending"
    errors, _ = run(root, release=True)
    assert any("x86_64_pass" in e for e in errors)


def test_waived_x86_counts_as_satisfied(tmp_path):
    root = build(tmp_path, ["demo.a"], {"demo.a": card(x86=None)}, waivers={"demo.a": {"x86_64_pass": "local-only"}})
    errors, states = run(root, release=True)
    assert errors == [] and states["demo.a"] == "pass"


def test_plugin_dir_without_scorecard_fails(tmp_path):
    root = build(tmp_path, [], {}, plugin_dirs=["demo.a"])
    errors, _ = run(root)
    assert any("demo.a" in e and "no scorecard" in e for e in errors)


def test_catalog_id_without_scorecard_fails_even_if_not_retiring(tmp_path):
    root = build(tmp_path, ["gone.y"], {})
    errors, _ = run(root)
    assert any("gone.y" in e for e in errors)


def test_retiring_id_still_in_catalog_fails_release_only(tmp_path):
    root = build(tmp_path, ["old.x"], {}, retiring=["old.x"])
    assert run(root)[0] == []
    errors, _ = run(root, release=True)
    assert any("retiring but still in catalog" in e for e in errors)


def test_fail_status_fails_default_mode(tmp_path):
    c = card()
    c["criteria"]["envelope"] = "fail"
    errors, _ = run(build(tmp_path, ["demo.a"], {"demo.a": c}))
    assert any("envelope" in e for e in errors)


def test_pending_criterion_passes_default_fails_release(tmp_path):
    c = card()
    c["criteria"]["fixture_tests"] = "pending"
    root = build(tmp_path, ["demo.a"], {"demo.a": c})
    assert run(root)[0] == []
    assert run(root, release=True)[0] != []


def test_spawn_over_budget_fails(tmp_path):
    errors, _ = run(build(tmp_path, ["demo.a"], {"demo.a": card(spawn=3)}))
    assert any("exceeds budget" in e for e in errors)


def test_undated_spawn_measurement_is_pending(tmp_path):
    c = card()
    c["manual"]["spawn_measurement"] = {"value": 0.1, "date": None}
    _, states = run(build(tmp_path, ["demo.a"], {"demo.a": c}))
    assert states["demo.a"] == "pending"


def test_contract_cross_check_flags_false_pass(tmp_path):
    root = build(tmp_path, ["demo.a"], {"demo.a": card()})

    class Contract:
        @staticmethod
        def scan_plugin(_):
            return [{"severity": "error", "rule": "x"}]

    errors, _ = mod.check(root=root, contract=Contract)
    assert any("contract checker" in e for e in errors)


def test_real_repo_default_mode_exits_zero_with_every_survivor_assessed():
    out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    for pid in ("lukedaduke.fan", "lukedaduke.power", "lukedaduke.standby", "lukedaduke.nexus",
                "io.github.duketopceo.bumblebee", "io.github.duketopceo.numbat",
                "io.github.duketopceo.pplx", "io.github.duketopceo.neo"):
        assert f"{pid}: pending" in out.stdout or f"{pid}: pass" in out.stdout


def test_numeric_spawn_without_a_budget_fails(tmp_path):
    root = build(tmp_path, ["demo.a"], {"demo.a": card()}, budgets={})
    errors, _ = run(root)
    assert any("no idle spawn budget" in e for e in errors)


def test_estate_budget_is_enforced_across_plugins(tmp_path):
    cards = {"demo.a": card(spawn=0.9), "demo.b": card(plugin="demo.b", spawn=0.9)}
    root = build(tmp_path, ["demo.a", "demo.b"], cards, budgets={"demo.a": 1, "demo.b": 1}, estate_budget=1.5)
    errors, _ = run(root)
    assert any("estate" in e and "1.8" in e for e in errors)


def test_exec_discipline_pass_is_checked_with_strict_estate_rules(tmp_path):
    root = build(tmp_path, ["demo.a"], {"demo.a": card()})
    seen = {}

    class Contract:
        @staticmethod
        def scan_plugin(_, strict_estate=False):
            seen["strict"] = strict_estate
            return [{"severity": "error" if strict_estate else "warning", "rule": "process-pid"}]

    errors, _ = mod.check(root=root, contract=Contract)
    assert seen["strict"] is True
    assert any("contract checker" in e for e in errors)
