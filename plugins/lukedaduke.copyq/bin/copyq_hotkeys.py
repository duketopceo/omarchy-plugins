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
import stat
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


def _require_private_dir(path: Path) -> None:
    """Refuse a directory another user could have planted or can write."""
    if path.is_symlink():
        raise OSError(f"{path} is a symlink")
    st = path.stat()
    if not stat.S_ISDIR(st.st_mode):
        raise OSError(f"{path} is not a directory")
    if st.st_uid != os.getuid():
        raise OSError(f"{path} is not owned by the current user")
    if st.st_mode & 0o022:
        raise OSError(f"{path} is writable by group or others")


def _runtime_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        raise OSError("XDG_RUNTIME_DIR is unset")
    base = Path(runtime)
    _require_private_dir(base)
    path = base / "lukedaduke.copyq"
    path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink():
        raise OSError("vault directory is a symlink")
    os.chmod(path, 0o700)
    st = path.stat()
    if st.st_uid != os.getuid() or not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise OSError("vault directory is not private")
    return path


def _key_path() -> Path:
    return _runtime_dir() / "hotkeys.key"


def _store_path() -> Path:
    return _runtime_dir() / "hotkeys.fernet"


def _suppressed_path() -> Path:
    return _runtime_dir() / "hotkeys.suppressed"


def _read_private_bytes(path: Path) -> bytes:
    if path.is_symlink():
        raise OSError(f"{path} is a symlink")
    st = path.stat()
    if st.st_uid != os.getuid():
        raise OSError(f"{path} is not owned by the current user")
    if st.st_mode & 0o077:
        os.chmod(path, 0o600)
        st = path.stat()
        if st.st_mode & 0o077:
            raise OSError(f"{path} is not private")
    return path.read_bytes()


def _write_private(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise OSError(f"{path} is a symlink")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _fernet() -> Fernet:
    path = _key_path()
    if path.exists():
        raw = _read_private_bytes(path).strip()
    else:
        raw = Fernet.generate_key()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raw = _read_private_bytes(path).strip()
        else:
            try:
                os.write(fd, raw + b"\n")
            finally:
                os.close(fd)
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
        token = _read_private_bytes(path)
        raw = _fernet().decrypt(token)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, InvalidToken, json.JSONDecodeError, ValueError):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def _save_items(items: list[dict]) -> None:
    payload = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
    token = _fernet().encrypt(payload)
    _write_private(_store_path(), token)


def _load_suppressed() -> set[str]:
    path = _suppressed_path()
    if not path.is_file() or path.is_symlink():
        return set()
    try:
        data = json.loads(_read_private_bytes(path).decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return {item for item in data if isinstance(item, str) and item}


def _remember_suppressed(fingerprints: list[str]) -> None:
    fresh = [fp for fp in fingerprints if fp]
    if not fresh:
        return
    current = _load_suppressed()
    current.update(fresh)
    _write_private(_suppressed_path(), json.dumps(sorted(current)).encode("utf-8"))


def purge_expired(now: float | None = None, ttl_secs: int = DEFAULT_TTL_SECS) -> list[dict]:
    del ttl_secs  # expires_at already absolute
    now = time.time() if now is None else now
    kept: list[dict] = []
    expired: list[str] = []
    for item in _load_items():
        if float(item.get("expires_at", 0)) > now:
            kept.append(item)
        elif item.get("fp"):
            expired.append(str(item["fp"]))
    if expired:
        _remember_suppressed(expired)
    _save_items(kept)
    return kept


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
    # Drop and expiry tombstone the fingerprint so a later harvest of the
    # same CopyQ history row cannot refresh the TTL or recreate the entry.
    if fp in _load_suppressed():
        return None
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
    removed = [i for i in items if i.get("id") == hot_id]
    if not removed:
        return False
    _remember_suppressed([str(i["fp"]) for i in removed if i.get("fp")])
    _save_items([i for i in items if i.get("id") != hot_id])
    return True


def _copyq_stdin(args: list[str], secret: str) -> subprocess.CompletedProcess[bytes]:
    """Hand plaintext to CopyQ on stdin. `copy -` / `add -` read it; argv stays empty of the secret."""
    return subprocess.run(
        args,
        input=secret.encode("utf-8"),
        check=False,
        capture_output=True,
        timeout=3,
        env=ENV,
    )


def activate(hot_id: str, *, paste: bool) -> int:
    secret = get_secret(hot_id)
    if not secret:
        return 1
    if not os.path.isfile(COPYQ) or not os.access(COPYQ, os.X_OK):
        return 1
    proc = _copyq_stdin([COPYQ, "copy", "-"], secret)
    if proc.returncode != 0:
        proc = _copyq_stdin([COPYQ, "add", "-"], secret)
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
