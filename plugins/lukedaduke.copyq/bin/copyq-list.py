#!/usr/bin/env python3
"""Emit CopyQ history as JSON for the Omarchy overlay.

Lists Pins tab first, then &clipboard. Text + image rows.
Fixed CopyQ path; COPYQ_BIN override for tests.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

COPYQ = os.environ.get("COPYQ_BIN", "/usr/bin/copyq")
DEFAULT_LIMIT = 80
MAX_LIMIT = 200
# Overlay only needs a short preview; never buffer unbounded clip bodies.
MAX_READ = 8_192
MAX_IMAGE_PREVIEW = 2_000_000
CLIPBOARD_TAB = "&clipboard"
PINS_TAB = "Pins"
IMAGE_MIMES = (
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/gif",
)
RUN_TIMEOUT = 3.0
HELPER_ALARM_SECS = 8
ENV = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "")}


def _limit_from_argv() -> int:
    if len(sys.argv) < 2:
        return DEFAULT_LIMIT
    try:
        value = int(sys.argv[1])
    except ValueError:
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _run(
    args: list[str],
    *,
    timeout: float = RUN_TIMEOUT,
    text: bool = True,
    max_bytes: int | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run CopyQ with an optional stdout byte cap (kill child on overflow)."""
    if max_bytes is None:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=text,
            timeout=timeout,
            env=ENV,
        )
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        env=ENV,
    )
    assert proc.stdout is not None
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            block = proc.stdout.read(min(65_536, max_bytes + 1 - total))
            if not block:
                break
            total += len(block)
            if total > max_bytes:
                proc.kill()
                chunks.append(block[: max(0, max_bytes - (total - len(block)))])
                break
            chunks.append(block)
        stdout = b"".join(chunks)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)
            raise
        stderr = proc.stderr.read() if proc.stderr else b""
    finally:
        if proc.poll() is None:
            proc.kill()
    if text:
        return subprocess.CompletedProcess(
            args,
            proc.returncode if proc.returncode is not None else 1,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    return subprocess.CompletedProcess(
        args,
        proc.returncode if proc.returncode is not None else 1,
        stdout,
        stderr,
    )


def _preview(text: str) -> str:
    one = text.replace("\r", "").replace("\n", " ")
    if len(one) > 160:
        return one[:160] + "…"
    return one


def _preview_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(runtime) / "lukedaduke.copyq"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _copyq_args(*parts: str, tab: str | None = None) -> list[str]:
    args = [COPYQ]
    if tab:
        args.extend(["tab", tab])
    args.extend(parts)
    return args


def _formats(index: int, tab: str) -> list[str]:
    try:
        proc = _run(_copyq_args("read", "?", str(index), tab=tab))
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _image_mime(formats: list[str]) -> str | None:
    lower = {f.lower(): f for f in formats}
    for mime in IMAGE_MIMES:
        if mime in lower:
            return lower[mime]
    return None


def _write_image_preview(index: int, tab: str, mime: str) -> str | None:
    try:
        proc = _run(
            _copyq_args("read", mime, str(index), tab=tab),
            text=False,
            timeout=5.0,
            max_bytes=MAX_IMAGE_PREVIEW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode not in (0, -9) or not proc.stdout:
        # -9: killed after cap; still usable if we kept capped bytes
        if not proc.stdout:
            return None
    ext = "jpg" if "jpeg" in mime.lower() or mime.lower().endswith("/jpg") else "png"
    if "webp" in mime.lower():
        ext = "webp"
    elif "gif" in mime.lower():
        ext = "gif"
    elif "bmp" in mime.lower():
        ext = "bmp"
    safe_tab = "pins" if tab == PINS_TAB else "clip"
    out = _preview_dir() / f"preview-{safe_tab}-{index}.{ext}"
    try:
        out.write_bytes(proc.stdout[:MAX_IMAGE_PREVIEW])
    except OSError:
        return None
    return str(out)


def _read_text(index: int, tab: str) -> tuple[str | None, int]:
    try:
        proc = _run(
            _copyq_args("read", str(index), tab=tab),
            max_bytes=MAX_READ,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"copyq_read:{exc}") from exc
    out = proc.stdout or ""
    if proc.returncode == 0:
        return out, 0
    # Byte-cap kill still yields a usable preview prefix.
    if proc.returncode == -9 and out.strip():
        return out, 0
    return None, proc.returncode or 1


def _count(tab: str) -> int:
    try:
        proc = _run(_copyq_args("count", tab=tab))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"copyq_count:{exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"copyq_count:exit:{proc.returncode}")
    raw = (proc.stdout or "0").strip() or "0"
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"copyq_count:{exc}") from exc


def _collect_tab(tab: str, *, pinned: bool, limit: int) -> tuple[list[dict[str, object]], int]:
    try:
        total = _count(tab)
    except RuntimeError:
        if pinned:
            # Pins tab may not exist yet.
            return [], 0
        raise
    entries: list[dict[str, object]] = []
    n = min(total, limit)
    for index in range(n):
        formats = _formats(index, tab)
        image_mime = _image_mime(formats)
        if image_mime:
            preview_path = _write_image_preview(index, tab, image_mime)
            entries.append(
                {
                    "index": index,
                    "tab": tab,
                    "pinned": pinned,
                    "type": "image",
                    "text": "",
                    "preview": "Image",
                    "previewPath": preview_path or "",
                    "mime": image_mime,
                }
            )
            continue
        text, code = _read_text(index, tab)
        if code != 0 or text is None:
            continue
        if not text.strip():
            continue
        preview = _preview(text)
        entries.append(
            {
                "index": index,
                "tab": tab,
                "pinned": pinned,
                "type": "text",
                # Overlay filters/displays preview only; activation uses index+tab.
                "text": preview,
                "preview": preview,
                "previewPath": "",
                "mime": "text/plain",
            }
        )
    return entries, total


def main() -> int:
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(SystemExit(1)))
    signal.alarm(HELPER_ALARM_SECS)
    try:
        if not os.path.isfile(COPYQ) or not os.access(COPYQ, os.X_OK):
            print(
                json.dumps({"ok": False, "error": "copyq_missing", "entries": []}),
                flush=True,
            )
            return 1

        limit = _limit_from_argv()
        try:
            pin_entries, pin_total = _collect_tab(PINS_TAB, pinned=True, limit=limit)
            remaining = max(1, limit - len(pin_entries))
            clip_entries, clip_total = _collect_tab(
                CLIPBOARD_TAB, pinned=False, limit=remaining
            )
        except RuntimeError as exc:
            print(
                json.dumps({"ok": False, "error": str(exc), "entries": []}),
                flush=True,
            )
            return 1

        entries = pin_entries + clip_entries
        print(
            json.dumps(
                {
                    "ok": True,
                    "count": pin_total + clip_total,
                    "pinCount": pin_total,
                    "clipCount": clip_total,
                    "entries": entries,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
