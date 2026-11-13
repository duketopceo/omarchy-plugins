#!/usr/bin/env python3
"""Ephemeral encrypted vault for API-key-shaped clipboard clips (~30 min TTL).

Stored under $XDG_RUNTIME_DIR (cleared on reboot). Fernet key stays 0600 beside
the ciphertext. Overlay lists masked previews; activate decrypts on demand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

COPYQ = os.environ.get("COPYQ_BIN", "/usr/bin/copyq")
DEFAULT_TTL_SECS = 30 * 60
MAX_ITEMS = 24
ENV = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "")}

# Kind, pattern (full-string match preferred), label for UI.
KEY_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("openrouter", re.compile(r"^sk-or-v1-[A-Za-z0-9]{16,}$"), "OpenRouter"),
    ("openai", re.compile(r"^sk-[A-Za-z0-9_-]{20,}$"), "OpenAI-style"),
    ("anthropic", re.compile(r"^sk-ant-[A-Za-z0-9_-]{16,}$"), "Anthropic"),
    ("github_pat", re.compile(r"^github_pat_[A-Za-z0-9_]{20,}$"), "GitHub"),
    ("github", re.compile(r"^gh[pousr]_[A-Za-z0-9_]{20,}$"), "GitHub"),
    ("slack", re.compile(r"^xox[baprs]-[A-Za-z0-9-]{10,}$"), "Slack"),
    ("google", re.compile(r"^AIza[0-9A-Za-z_-]{20,}$"), "Google"),
    ("aws", re.compile(r"^AKIA[0-9A-Z]{16}$"), "AWS access"),
    ("bearer", re.compile(r"^Bearer\s+\S{16,}$", re.I), "Bearer token"),
]


def _runtime_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        runtime = os.path.join("/tmp", f"lukedaduke.copyq-{os.getuid()}")
    path = Path(runtime) / "lukedaduke.copyq"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _key_path() -> Path:
    return _runtime_dir() / "hotkeys.key"


def _store_path() -> Path:
    return _runtime_dir() / "hotkeys.fernet"


def _fernet() -> Fernet:
    path = _key_path()
    if path.is_file():
        raw = path.read_bytes().strip()
    else:
        raw = Fernet.generate_key()
        path.write_bytes(raw + b"\n")
        os.chmod(path, 0o600)
    return Fernet(raw)


def _fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:24]


def classify_secret(text: str) -> tuple[str, str] | None:
    """Return (kind, label) if text looks like a secret key."""
    s = text.strip()
    if not s or "\n" in s or len(s) > 512:
        return None
    # Prefer more specific patterns first (list order).
    for kind, pattern, label in KEY_PATTERNS:
        if pattern.match(s):
            # Avoid treating generic sk- as OpenAI when already matched openrouter/ant.
            if kind == "openai" and s.startswith(("sk-or-", "sk-ant-")):
                continue
            return kind, label
    return None


def mask_secret(secret: str) -> str:
    s = secret.strip()
    if len(s) <= 12:
        return s[:2] + "…" + s[-2:]
    return s[:10] + "…" + s[-4:]


def _load_items() -> list[dict]:
    path = _store_path()
    if not path.is_file():
        return []
    try:
        token = path.read_bytes()
        raw = _fernet().decrypt(token)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, InvalidToken, json.JSONDecodeError, ValueError):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def _save_items(items: list[dict]) -> None:
    payload = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
    token = _fernet().encrypt(payload)
    path = _store_path()
    path.write_bytes(token)
    os.chmod(path, 0o600)


def purge_expired(now: float | None = None, ttl_secs: int = DEFAULT_TTL_SECS) -> list[dict]:
    del ttl_secs  # expires_at already absolute
    now = time.time() if now is None else now
    items = [i for i in _load_items() if float(i.get("expires_at", 0)) > now]
    _save_items(items)
    return items


def upsert_secret(
    secret: str,
    *,
    ttl_secs: int = DEFAULT_TTL_SECS,
    now: float | None = None,
) -> dict | None:
    classified = classify_secret(secret)
    if not classified:
        return None
    kind, label = classified
    now = time.time() if now is None else now
    secret = secret.strip()
    fp = _fingerprint(secret)
    items = purge_expired(now=now)
    for item in items:
        if item.get("fp") == fp:
            item["expires_at"] = now + ttl_secs
            item["kind"] = kind
            item["label"] = label
            item["preview"] = mask_secret(secret)
            _save_items(items)
            return item
    item = {
        "id": str(uuid.uuid4()),
        "fp": fp,
        "kind": kind,
        "label": label,
        "preview": mask_secret(secret),
        "secret": secret,
        "created_at": now,
        "expires_at": now + ttl_secs,
    }
    items.insert(0, item)
    _save_items(items[:MAX_ITEMS])
    return item


def harvest_texts(texts: list[str], *, ttl_secs: int = DEFAULT_TTL_SECS) -> int:
    added = 0
    for text in texts:
        if upsert_secret(text, ttl_secs=ttl_secs):
            added += 1
    return added


def list_overlay_entries(*, now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    items = purge_expired(now=now)
    out: list[dict] = []
    for item in items:
        left = max(0, int(float(item["expires_at"]) - now))
        mins = max(1, (left + 59) // 60) if left > 0 else 0
        ttl = f"{mins}m left" if mins else "expiring"
        preview = f"⏱ {item.get('label', 'Key')} · {item.get('preview', '')} · {ttl}"
        out.append(
            {
                "index": -1,
                "tab": "hot",
                "pinned": False,
                "hot": True,
                "hotId": item["id"],
                "type": "text",
                "preview": preview,
                "text": "",
                "previewPath": "",
                "mime": "text/plain",
            }
        )
    return out


def get_secret(hot_id: str) -> str | None:
    now = time.time()
    for item in purge_expired(now=now):
        if item.get("id") == hot_id:
            return str(item.get("secret") or "") or None
    return None


def drop_secret(hot_id: str) -> bool:
    items = _load_items()
    keep = [i for i in items if i.get("id") != hot_id]
    if len(keep) == len(items):
        return False
    _save_items(keep)
    return True


def activate(hot_id: str, *, paste: bool) -> int:
    secret = get_secret(hot_id)
    if not secret:
        return 1
    if not os.path.isfile(COPYQ) or not os.access(COPYQ, os.X_OK):
        return 1
    # Put secret on clipboard via CopyQ, then optional paste.
    proc = subprocess.run(
        [COPYQ, "copy", secret],
        check=False,
        capture_output=True,
        text=True,
        timeout=3,
        env=ENV,
    )
    if proc.returncode != 0:
        # Fallback write+select
        proc = subprocess.run(
            [COPYQ, "add", secret],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
            env=ENV,
        )
        if proc.returncode != 0:
            return 1
        subprocess.run(
            [COPYQ, "select", "0"],
            check=False,
            capture_output=True,
            timeout=3,
            env=ENV,
        )
    if paste:
        time.sleep(0.08)
        subprocess.run(
            [COPYQ, "paste"],
            check=False,
            capture_output=True,
            timeout=3,
            env=ENV,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ephemeral encrypted API-key vault")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="JSON overlay rows for hot keys")
    p_list.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECS)

    p_harvest = sub.add_parser("harvest", help="Ingest secrets from JSON entry list on stdin")
    p_harvest.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECS)

    p_act = sub.add_parser("activate", help="Copy/paste a hot key by id")
    p_act.add_argument("--id", required=True)
    p_act.add_argument("--copy-only", action="store_true")

    p_drop = sub.add_parser("drop", help="Remove a hot key by id")
    p_drop.add_argument("--id", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "list":
        print(json.dumps({"ok": True, "entries": list_overlay_entries()}, ensure_ascii=False))
        return 0
    if args.cmd == "harvest":
        raw = sys.stdin.read()
        try:
            data = json.loads(raw or "[]")
        except json.JSONDecodeError:
            return 2
        texts: list[str] = []
        if isinstance(data, list):
            for row in data:
                if isinstance(row, str):
                    texts.append(row)
                elif isinstance(row, dict):
                    texts.append(str(row.get("text") or row.get("preview") or ""))
        n = harvest_texts(texts, ttl_secs=args.ttl)
        print(json.dumps({"ok": True, "harvested": n}))
        return 0
    if args.cmd == "activate":
        return activate(args.id, paste=not args.copy_only)
    if args.cmd == "drop":
        ok = drop_secret(args.id)
        print(json.dumps({"ok": ok}))
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
