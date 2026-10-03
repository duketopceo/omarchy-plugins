#!/usr/bin/env python3
"""Validate the repository's explicit data-lifecycle policy."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "docs" / "data-lifecycle.json"
REQUIRED_SURFACE_FIELDS = ("id", "owner", "purpose", "egress", "retention", "pause", "delete", "export")
SECRET_VALUE_RE = re.compile(r"(?:sk-[A-Za-z0-9]|Bearer\s+[A-Za-z0-9]|/home/|/Users/)", re.IGNORECASE)


def validate_policy(policy: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return ["policy must be an object"]
    if policy.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    secret = policy.get("secret_surface")
    if not isinstance(secret, dict) or secret.get("canonical") != "OmaSeal":
        errors.append("secret_surface.canonical must be OmaSeal")
    voice = policy.get("voice")
    if not isinstance(voice, dict):
        errors.append("voice policy is missing")
    else:
        if voice.get("default") != "hancore.voxtype-enhance":
            errors.append("voice.default must be hancore.voxtype-enhance")
        if voice.get("alternate") != "io.github.duketopceo.dim":
            errors.append("voice.alternate must be io.github.duketopceo.dim")
        if voice.get("simultaneous_allowed") is not False:
            errors.append("voice.simultaneous_allowed must be false")
    surfaces = policy.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        return errors + ["surfaces must be a non-empty list"]
    seen: set[str] = set()
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            errors.append(f"surface {index} must be an object")
            continue
        surface_id = surface.get("id")
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"surface {index} has no id")
        elif surface_id in seen:
            errors.append(f"duplicate surface id: {surface_id}")
        else:
            seen.add(surface_id)
        for field in REQUIRED_SURFACE_FIELDS:
            if field not in surface:
                errors.append(f"surface {surface_id or index} missing {field}")
        for field in ("purpose", "egress", "retention", "delete", "export"):
            if field in surface and (not isinstance(surface[field], str) or not surface[field].strip()):
                errors.append(f"surface {surface_id or index} has empty {field}")
        for field in ("pause",):
            if field in surface and not isinstance(surface[field], bool):
                errors.append(f"surface {surface_id or index} {field} must be boolean")
        for value in surface.values():
            if isinstance(value, str) and SECRET_VALUE_RE.search(value):
                errors.append(f"surface {surface_id or index} contains a secret or host path")
                break
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--json", action="store_true", help="emit errors as JSON")
    args = parser.parse_args(argv)
    try:
        policy = json.loads(args.policy.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        errors = [f"unable to read policy: {exc}"]
    else:
        errors = validate_policy(policy)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(error, file=sys.stderr)
    else:
        print("ok: data lifecycle policy")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
