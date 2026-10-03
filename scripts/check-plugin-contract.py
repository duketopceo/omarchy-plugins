#!/usr/bin/env python3
"""Check the small, shared contract for owned Omarchy plugins.

The checker is intentionally conservative and syntax-light: it catches unsafe
constructs that are easy to reintroduce in QML/helpers, while leaving detailed
runtime behavior to the plugin-specific tests and native smoke checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLUGIN_ROOT = ROOT / "plugins"
TEXTUAL_SUFFIXES = {".qml", ".py", ".sh", ".bash", ".js", ".mjs", ".json", ".md"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", "target", "build", "dist"}
# Plain HTTP is allowed only to the loopback interface (local sidecars); the
# host must end right after the address so lookalike domains still fail.
LOOPBACK_HTTP = re.compile(r"http://(?:127\.0\.0\.1|\[::1\])(?=[:/'\"\s]|$)")


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _blocks(source: str, keyword: str) -> Iterator[tuple[int, str]]:
    pattern = re.compile(rf"\b{re.escape(keyword)}\s*\{{")
    for match in pattern.finditer(source):
        start = match.start()
        index = match.end()
        depth = 1
        quote: str | None = None
        escaped = False
        line_comment = False
        block_comment = False
        while index < len(source) and depth:
            current = source[index]
            following = source[index + 1] if index + 1 < len(source) else ""
            if line_comment:
                if current == "\n":
                    line_comment = False
            elif block_comment:
                if current == "*" and following == "/":
                    block_comment = False
                    index += 1
            elif quote:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    quote = None
            elif current == "/" and following == "/":
                line_comment = True
                index += 1
            elif current == "/" and following == "*":
                block_comment = True
                index += 1
            elif current in "'\"`":
                quote = current
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
            index += 1
        if depth == 0:
            yield start, source[start:index]


def _finding(path: Path, plugin_root: Path, source: str, offset: int, rule: str, message: str, severity: str = "error") -> dict[str, Any]:
    try:
        display_path = str(path.relative_to(plugin_root))
    except ValueError:
        display_path = path.name
    return {
        "path": display_path,
        "line": _line_number(source, offset),
        "rule": rule,
        "severity": severity,
        "message": message,
    }


def _scan_qml(path: Path, plugin_root: Path, source: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for offset, block in _blocks(source, "Text"):
        if re.search(r"\btext\s*:", block) and not re.search(
            r"\btextFormat\s*:\s*Text\.PlainText", block
        ):
            findings.append(
                _finding(
                    path,
                    plugin_root,
                    source,
                    offset,
                    "qml-plain-text",
                    "Text with a text binding must set textFormat: Text.PlainText",
                )
            )
    for match in re.finditer(
        r"\b(?:executable|command)\s*:\s*[\"'](?:python3|python|sh|bash)[\"']",
        source,
    ):
        findings.append(
            _finding(
                path,
                plugin_root,
                source,
                match.start(),
                "fixed-executable",
                "helpers must use a fixed executable path, not an ambient interpreter",
            )
        )
    for match in re.finditer(r"\bTimer\s*\{", source):
        block_match = re.search(
            r"\binterval\s*:\s*([0-9]+(?:\s*\*\s*[0-9]+)*)",
            source[match.end() : match.end() + 500],
        )
        interval_ms = None
        if block_match:
            interval_ms = 1
            for part in re.findall(r"\d+", block_match.group(1)):
                interval_ms *= int(part)
        if interval_ms is not None and interval_ms < 1000:
            findings.append(
                _finding(
                    path,
                    plugin_root,
                    source,
                    match.start(),
                    "timer-budget",
                    "sub-second timers require an explicit bounded/one-shot justification",
                    "warning",
                )
            )
    return findings


def _scan_python(path: Path, plugin_root: Path, source: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for match in re.finditer(r"\bshell\s*=\s*True\b", source):
        findings.append(
            _finding(
                path,
                plugin_root,
                source,
                match.start(),
                "shell-command",
                "Python helpers must pass argv directly instead of shell=True",
            )
        )
    for match in re.finditer(r"\bos\.system\s*\(", source):
        findings.append(
            _finding(
                path,
                plugin_root,
                source,
                match.start(),
                "shell-command",
                "Python helpers must not invoke os.system",
            )
        )
    for match in re.finditer(r"http://", source):
        if LOOPBACK_HTTP.match(source, match.start()):
            continue
        findings.append(
            _finding(
                path,
                plugin_root,
                source,
                match.start(),
                "https-only",
                "network URLs in executable code must use HTTPS",
            )
        )
    for match in re.finditer(r"\benv\s*=\s*os\.environ(?:\.copy\(\))?", source):
        findings.append(
            _finding(
                path,
                plugin_root,
                source,
                match.start(),
                "minimal-environment",
                "helpers must build an explicit minimal environment",
                "warning",
            )
        )
    return findings


def _scan_shell(path: Path, plugin_root: Path, source: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for match in re.finditer(r"\bsudo\s+-S\b|\bsu\s+-c\b", source):
        findings.append(
            _finding(
                path,
                plugin_root,
                source,
                match.start(),
                "secret-elevation",
                "stored-password and shell-string elevation paths are forbidden",
            )
        )
    for match in re.finditer(r"(?m)^\s*(?:python3|python|sh|bash)\s+", source):
        if not source[match.start() :].lstrip().startswith("#!"):
            findings.append(
                _finding(
                    path,
                    plugin_root,
                    source,
                    match.start(),
                    "fixed-executable",
                    "shell helpers must use a fixed executable path",
                )
            )
    return findings


def _files(plugin_root: Path) -> Iterable[Path]:
    for path in sorted(plugin_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXTUAL_SUFFIXES:
            yield path


def scan_plugin(plugin_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in _files(plugin_root):
        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if path.suffix == ".qml":
            findings.extend(_scan_qml(path, plugin_root, source))
        elif path.suffix == ".py":
            findings.extend(_scan_python(path, plugin_root, source))
        elif path.suffix in {".sh", ".bash"}:
            findings.extend(_scan_shell(path, plugin_root, source))
    return findings


def scan_tree(plugin_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not plugin_root.is_dir():
        return [{"path": plugin_root.name, "line": 0, "rule": "missing-root", "severity": "error", "message": "plugin root is unavailable"}]
    for directory in sorted(plugin_root.iterdir(), key=lambda item: item.name):
        if directory.name.startswith(".") or ".bak." in directory.name:
            continue
        if directory.is_dir() and (directory / "manifest.json").is_file():
            for finding in scan_plugin(directory):
                finding["path"] = f"{directory.name}/{finding['path']}"
                findings.append(finding)
    return findings


def _format_text(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "ok: plugin contract clean\n"
    lines = []
    for finding in findings:
        lines.append(
            f"{finding['severity']}: {finding['path']}:{finding['line']}: "
            f"[{finding['rule']}] {finding['message']}"
        )
    errors = sum(1 for finding in findings if finding["severity"] == "error")
    warnings = len(findings) - errors
    lines.append(f"summary: {errors} error(s), {warnings} warning(s)")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=DEFAULT_PLUGIN_ROOT)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="fail on warnings as well as errors")
    args = parser.parse_args(argv)
    findings = scan_tree(args.plugin_root)
    if args.format == "json":
        print(json.dumps({"findings": findings}, indent=2, sort_keys=True))
    else:
        sys.stdout.write(_format_text(findings))
    errors = any(finding["severity"] == "error" for finding in findings)
    warnings = any(finding["severity"] == "warning" for finding in findings)
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
