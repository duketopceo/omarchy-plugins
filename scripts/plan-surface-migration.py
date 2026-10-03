#!/usr/bin/env python3
"""Plan a reversible bar/plugin surface migration without changing the host."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCORECARD = ROOT / "docs" / "SCORECARD.md"


def retiring_ids(scorecard: Path | None = None) -> set[str]:
    """Plugin ids docs/SCORECARD.md lists as retiring; never placed again.

    Raises ValueError when the list cannot be read, so the placement guard
    fails closed instead of silently allowing a retired plugin back.
    """
    path = scorecard if scorecard is not None else SCORECARD
    try:
        text = path.read_text()
    except OSError as exc:
        raise ValueError(f"cannot read retiring list from {path.name}: {exc}") from exc
    match = re.search(r"```scorecard-config\n(.*?)\n```", text, re.S)
    if not match:
        raise ValueError(f"{path.name} has no scorecard-config block")
    try:
        config = json.loads(match.group(1))
    except ValueError as exc:
        raise ValueError(f"{path.name} scorecard-config is not valid JSON: {exc}") from exc
    retiring = config.get("retiring", []) if isinstance(config, dict) else None
    if not isinstance(retiring, list):
        raise ValueError(f"{path.name} scorecard-config has no retiring list")
    return {str(i) for i in retiring}


def _direct_bar_ids(config: Mapping[str, Any]) -> set[str]:
    bar = config.get("bar")
    layout = bar.get("layout", {}) if isinstance(bar, Mapping) else {}
    ids: set[str] = set()
    if isinstance(layout, Mapping):
        for entries in layout.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, Mapping) and isinstance(entry.get("id"), str):
                    ids.add(entry["id"])
    return ids


def plan_migration(
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
    retiring: set[str] | None = None,
) -> dict[str, Any]:
    retiring = retiring or set()
    current_ids = _direct_bar_ids(current)
    desired_ids = _direct_bar_ids(desired)
    placed_retired = sorted(desired_ids & retiring)
    if placed_retired:
        raise ValueError("desired layout places retired plugin(s): " + ", ".join(placed_retired))
    remove = sorted(current_ids - desired_ids)
    add = sorted(desired_ids - current_ids)
    retained = sorted(current_ids & desired_ids)
    return {
        "schema_version": 1,
        "remove_bar_ids": remove,
        "add_bar_ids": add,
        "retained_bar_ids": retained,
        "retired_bar_ids": sorted(set(remove) & retiring),
        "requires_shell_backup": bool(remove or add),
        "destructive_actions": [],
        "rollback": "Restore the prior sanitized bar/idle/plugin snapshot; do not delete plugin data or keyring entries.",
        "notes": [
            "Voxtype is the default voice owner; Dim is opt-in.",
            "The custom tray remains because it owns hosted widgets.",
            "The stock active-window widget replaces the custom clone only after a reversible layout smoke test.",
        ],
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def render_markdown(plan: Mapping[str, Any]) -> str:
    lines = [
        "# Surface migration plan",
        "",
        "This is a dry-run plan. It does not edit the live shell or delete data.",
        "",
        "## Changes",
        "",
        f"- Remove bar IDs: {', '.join(f'`{item}`' for item in plan.get('remove_bar_ids', [])) or 'none'}",
        f"- Add bar IDs: {', '.join(f'`{item}`' for item in plan.get('add_bar_ids', [])) or 'none'}",
        f"- Retain bar IDs: {', '.join(f'`{item}`' for item in plan.get('retained_bar_ids', [])) or 'none'}",
        f"- Retired (replaced) bar IDs: {', '.join(f'`{item}`' for item in plan.get('retired_bar_ids', [])) or 'none'}",
        "",
        "## Safety",
        "",
        f"- Shell backup required: **{'yes' if plan.get('requires_shell_backup') else 'no'}**",
        "- Destructive actions: **none**",
        f"- Rollback: {plan.get('rollback', 'restore the prior snapshot')}",
        "",
    ]
    lines.extend(f"- {note}" for note in plan.get("notes", []))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, default=Path.home() / ".config/omarchy/shell.json")
    parser.add_argument("--desired", type=Path, default=ROOT / "machine/bar-layout.json")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        plan = plan_migration(_read_json(args.current), _read_json(args.desired), retiring_ids())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
