#!/usr/bin/env python3
"""Emit CopyQ history as JSON for the Omarchy overlay.

Fixed CopyQ path; no ambient PATH resolution. Text rows only for v0.1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

COPYQ = "/usr/bin/copyq"
DEFAULT_LIMIT = 80
MAX_LIMIT = 200
MAX_TEXT = 200_000
ENV = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "")}


def _limit_from_argv() -> int:
    if len(sys.argv) < 2:
        return DEFAULT_LIMIT
    try:
        value = int(sys.argv[1])
    except ValueError:
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _run(args: list[str], *, timeout: float = 3.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=ENV,
    )


def _preview(text: str) -> str:
    one = text.replace("\r", "").replace("\n", " ")
    if len(one) > 160:
        return one[:160] + "…"
    return one


def main() -> int:
    if not os.path.isfile(COPYQ) or not os.access(COPYQ, os.X_OK):
        print(
            json.dumps({"ok": False, "error": "copyq_missing", "entries": []}),
            flush=True,
        )
        return 1

    limit = _limit_from_argv()
    try:
        count_proc = _run([COPYQ, "count"])
        total = int((count_proc.stdout or "0").strip() or "0")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(
            json.dumps({"ok": False, "error": f"copyq_count:{exc}", "entries": []}),
            flush=True,
        )
        return 1

    entries: list[dict[str, object]] = []
    n = min(total, limit)
    for index in range(n):
        try:
            read_proc = _run([COPYQ, "read", str(index)])
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(
                json.dumps(
                    {"ok": False, "error": f"copyq_read:{exc}", "entries": []}
                ),
                flush=True,
            )
            return 1
        if read_proc.returncode != 0:
            continue
        text = read_proc.stdout or ""
        if not text.strip():
            continue
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT]
        entries.append(
            {
                "index": index,
                "type": "text",
                "text": text,
                "preview": _preview(text),
            }
        )

    print(
        json.dumps(
            {"ok": True, "count": total, "entries": entries},
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
