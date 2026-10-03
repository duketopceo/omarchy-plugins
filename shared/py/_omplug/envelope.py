"""The versioned JSON envelope every helper emits (R13).

Shape, always complete even when the helper crashes:

    {"schema": int, "ok": bool, "error": str|null, "data": any,
     "capabilities": {...}}

A helper's main function returns (data, capabilities). To report an expected
failure ("locked", "setup", "unavailable", ...) it raises HelperError; any
other exception becomes error "internal:<ExceptionType>" so no exception text
(paths, secrets) leaks to the panel.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from .text import clean_text

ERROR_MAX = 120


class HelperError(Exception):
    """Expected failure: becomes ok=false with a short machine error code."""

    def __init__(self, error: str, data: Any = None, capabilities: dict | None = None) -> None:
        super().__init__(error)
        self.error = error
        self.data = data
        self.capabilities = capabilities or {}


def make(
    data: Any = None,
    *,
    schema: int = 1,
    ok: bool = True,
    error: str | None = None,
    capabilities: dict | None = None,
) -> dict:
    return {
        "schema": int(schema),
        "ok": bool(ok),
        "error": None if error is None else clean_text(error, ERROR_MAX),
        "data": data,
        "capabilities": dict(capabilities or {}),
    }


def wrap(fn: Callable[[], Any], schema: int = 1) -> dict:
    """Call fn() and always return a complete envelope; never raises."""
    try:
        result = fn()
        data, capabilities = result
        if not isinstance(capabilities, dict):
            raise TypeError("capabilities must be a dict")
        env = make(data, schema=schema, capabilities=capabilities)
        json.dumps(env)  # fail here, inside the guard, not at print time
        return env
    except HelperError as exc:
        env = make(exc.data, schema=schema, ok=False, error=exc.error, capabilities=exc.capabilities)
        try:
            json.dumps(env)
            return env
        except (TypeError, ValueError):
            return make(None, schema=schema, ok=False, error=exc.error)
    except Exception as exc:  # noqa: BLE001 - the envelope must survive anything
        return make(None, schema=schema, ok=False, error=f"internal:{type(exc).__name__}")


def main(fn: Callable[[], Any], schema: int = 1) -> int:
    """Print wrap(fn) as one JSON line on stdout; exit status is always 0."""
    sys.stdout.write(json.dumps(wrap(fn, schema=schema), separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return 0
