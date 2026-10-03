#!/usr/bin/env python3
"""Fail on QML syntax errors in shared/qml and plugin QML.

qmllint also warns about unresolved imports (qs.Commons, Quickshell modules
exist only inside the Omarchy shell), so only syntax errors fail this check.
Exits 0 with a notice when qmllint is not installed, unless REQUIRE_QMLLINT=1
(set in CI), where a missing qmllint is a failure rather than a silent pass.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ["/usr/lib/qt6/bin/qmllint", "/usr/lib/qt6/libexec/qmllint", "qmllint6", "qmllint"]
SYNTAX = re.compile(r"Syntax error|Expected token|Unexpected token")


def find_qmllint() -> str | None:
    for candidate in CANDIDATES:
        path = candidate if Path(candidate).is_file() else shutil.which(candidate)
        if path:
            return str(path)
    return None


def main() -> int:
    qmllint = find_qmllint()
    if qmllint is None:
        if os.environ.get("REQUIRE_QMLLINT") == "1":
            print("error: qmllint required (REQUIRE_QMLLINT=1) but not installed", file=sys.stderr)
            return 1
        print("skip: qmllint not installed")
        return 0
    files = sorted((ROOT / "shared" / "qml").glob("*.qml")) + sorted((ROOT / "plugins").glob("*/*.qml"))
    bad = []
    for path in files:
        out = subprocess.run([qmllint, str(path)], capture_output=True, text=True)
        lines = [line for line in (out.stdout + out.stderr).splitlines() if SYNTAX.search(line)]
        if lines:
            bad.append(f"{path.relative_to(ROOT)}: {lines[0].strip()}")
    for line in bad:
        print(line, file=sys.stderr)
    if bad:
        return 1
    print(f"ok: {len(files)} QML files parse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
