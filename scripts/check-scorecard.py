#!/usr/bin/env python3
"""Check per-plugin scorecards (docs/SCORECARD.md, KTD3)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("pass", "fail", "pending")
CRITERIA = (
    "no_open_hm_findings",
    "plaintext_external_text",
    "exec_discipline",
    "envelope",
    "fixture_tests",
    "visibility_gating",
    "stale_backoff",
    "readme_claims",
)
MANUAL = ("spawn_measurement", "asahi_pass", "x86_64_pass")
CONTRACT_BACKED = ("plaintext_external_text", "exec_discipline")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _block(text: str, name: str) -> Any:
    match = re.search(rf"^```{re.escape(name)}\n(.*?)^```", text, re.S | re.M)
    if not match:
        return None
    return json.loads(match.group(1))


def _load_contract():
    path = Path(__file__).resolve().parent / "check-plugin-contract.py"
    spec = importlib.util.spec_from_file_location("check_plugin_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scan_strict(contract, plugin_dir: Path) -> list[dict[str, Any]]:
    """Contract findings with estate rules at error severity (a claimed pass
    must hold to the rules a shared-lib consumer is held to)."""
    try:
        return contract.scan_plugin(plugin_dir, strict_estate=True)
    except TypeError:
        return contract.scan_plugin(plugin_dir)


def _evaluate(plugin: str, card: dict[str, Any], config: dict[str, Any], plugin_dir: Path, contract) -> tuple[str, list[str], list[str]]:
    """Return (state, problems, pending). state is pass|pending|fail."""
    problems: list[str] = []
    pending: list[str] = []
    criteria = card.get("criteria", {})
    for key in CRITERIA:
        status = criteria.get(key)
        if status not in STATUSES:
            problems.append(f"{plugin}: criterion {key} has invalid status {status!r}")
        elif status == "fail":
            problems.append(f"{plugin}: criterion {key} failed")
        elif status == "pending":
            pending.append(key)
    for key in sorted(set(criteria) - set(CRITERIA)):
        problems.append(f"{plugin}: unknown criterion {key}")

    if contract is not None and plugin_dir.is_dir():
        claimed = [k for k in CONTRACT_BACKED if criteria.get(k) == "pass"]
        if claimed:
            errors = [f for f in _scan_strict(contract, plugin_dir) if f.get("severity", "error") == "error"]
            if errors:
                problems.append(f"{plugin}: {', '.join(claimed)} marked pass but contract checker reports {len(errors)} error(s)")

    waivers = config.get("waivers", {}).get(plugin, {})
    manual = card.get("manual", {})
    budget = config.get("budgets", {}).get(plugin)
    for key in MANUAL:
        if key in waivers:
            continue
        entry = manual.get(key) or {}
        date = entry.get("date")
        if date is not None and not DATE_RE.match(str(date)):
            problems.append(f"{plugin}: manual item {key} has invalid date {date!r}")
            continue
        if not date:
            pending.append(key)
            continue
        if key == "spawn_measurement":
            value = entry.get("value")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                pending.append(key)
            elif budget is None:
                problems.append(f"{plugin}: no idle spawn budget in SCORECARD.md for a measured rate")
            elif value > budget:
                problems.append(f"{plugin}: spawn measurement {value}/min exceeds budget {budget}/min")
    pending_msgs = [f"{plugin}: pending {k}" for k in pending]
    if problems:
        return "fail", problems, pending_msgs
    return ("pending" if pending else "pass"), [], pending_msgs


def check(
    root: Path = ROOT,
    catalog: Path | None = None,
    scorecard_doc: Path | None = None,
    reviews: Path | None = None,
    plugin_root: Path | None = None,
    release: bool = False,
    contract=None,
) -> tuple[list[str], dict[str, str]]:
    """Return (errors, per-plugin state). States: pass|pending|fail|retiring."""
    catalog = catalog or root / "catalog.json"
    scorecard_doc = scorecard_doc or root / "docs" / "SCORECARD.md"
    reviews = reviews or root / "docs" / "reviews"
    plugin_root = plugin_root or root / "plugins"
    errors: list[str] = []
    states: dict[str, str] = {}
    estate_total = 0.0

    try:
        config = _block(scorecard_doc.read_text(), "scorecard-config")
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to read scorecard config: {exc}"], states
    if not isinstance(config, dict):
        return ["SCORECARD.md has no scorecard-config block"], states
    retiring = set(config.get("retiring", []))

    try:
        catalog_ids = [p["id"] for p in json.loads(catalog.read_text())["plugins"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"unable to read catalog: {exc}"], states
    dir_ids = sorted(p.name for p in plugin_root.iterdir() if p.is_dir()) if plugin_root.is_dir() else []

    for plugin in sorted(set(catalog_ids) | set(dir_ids)):
        review = reviews / f"{plugin}.md"
        card = None
        if review.is_file():
            try:
                card = _block(review.read_text(), "scorecard")
            except json.JSONDecodeError as exc:
                errors.append(f"{plugin}: unparsable scorecard block: {exc}")
                states[plugin] = "fail"
                continue
        if plugin in retiring:
            states[plugin] = "retiring"
            if release and plugin in catalog_ids:
                errors.append(f"{plugin}: retiring but still in catalog.json")
                states[plugin] = "fail"
            continue
        if not isinstance(card, dict):
            errors.append(f"{plugin}: no scorecard block in docs/reviews/{plugin}.md")
            states[plugin] = "fail"
            continue
        state, problems, pending = _evaluate(plugin, card, config, plugin_root / plugin, contract)
        states[plugin] = state
        errors.extend(problems)
        if release:
            errors.extend(pending)
            if state == "pending":
                states[plugin] = "fail"
        value = ((card.get("manual") or {}).get("spawn_measurement") or {}).get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            estate_total += value
    estate_budget = config.get("estate_budget")
    if isinstance(estate_budget, (int, float)) and estate_total > estate_budget:
        errors.append(f"estate idle spawns {round(estate_total, 2)}/min exceed estate budget {estate_budget}/min")
    return errors, states


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="pending items and retiring ids in the catalog fail")
    args = parser.parse_args(argv)
    errors, states = check(release=args.release, contract=_load_contract())
    for plugin, state in sorted(states.items()):
        print(f"{plugin}: {state}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ok: scorecard" + (" (release)" if args.release else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
