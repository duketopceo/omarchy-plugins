#!/usr/bin/env python3
"""Emit CopyQ history as JSON for the Omarchy overlay.

One CopyQ `eval` dump for Pins + &clipboard (fast). Image thumbnails are
fetched only for image rows. Fixed CopyQ path; COPYQ_BIN override for tests.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))
from copyq_hotkeys import classify_secret, harvest_texts, list_overlay_entries

COPYQ = os.environ.get("COPYQ_BIN", "/usr/bin/copyq")
DEFAULT_LIMIT = 80
MAX_LIMIT = 200
MAX_READ = 8_192
# Caps a runaway eval dump. Real rows are truncated in the script (160, or
# 512 for a key candidate), so a healthy payload stays well under this.
DUMP_MAX_BYTES = 512_000
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

# CopyQ script: dump previews in-process (one spawn). LIMIT is substituted.
_DUMP_SCRIPT = r"""
function dump(tabName, limit, pinned) {
  tab(tabName);
  var n = Math.min(count(), limit);
  var rows = [];
  for (var i = 0; i < n; ++i) {
    var fmts = str(read("?", i)).split("\n");
    var image = "";
    for (var f = 0; f < fmts.length; ++f) {
      var m = fmts[f];
      if (m.indexOf("image/") === 0) { image = m; break; }
    }
    if (image !== "") {
      rows.push({
        index: i,
        tab: tabName,
        pinned: pinned,
        type: "image",
        mime: image,
        preview: "Image",
        text: "",
        previewPath: ""
      });
      continue;
    }
    var t = str(read(i));
    if (t.replace(/\s+/g, "") === "") continue;
    var one = t.replace(/\r/g, "").replace(/\n/g, " ");
    var trimmed = one.replace(/^\s+|\s+$/g, "");
    var keyish = /^(sk-|sk-or-v1-|sk-ant-|gh[pousr]_|github_pat_|xox[baprs]-|AIza|AKIA|Bearer\s)/i.test(trimmed);
    if (keyish && trimmed.length > 512) keyish = false;
    var prev = one;
    if (!keyish && prev.length > 160) prev = prev.substring(0, 160) + "…";
    rows.push({
      index: i,
      tab: tabName,
      pinned: pinned,
      type: "text",
      mime: "text/plain",
      preview: keyish ? trimmed : prev,
      text: keyish ? trimmed : prev,
      keyish: keyish,
      previewPath: ""
    });
  }
  return { rows: rows, total: count() };
}
var pinPack = { rows: [], total: 0 };
try { pinPack = dump("Pins", LIMIT, true); } catch (e) { pinPack = { rows: [], total: 0 }; }
var remaining = LIMIT - pinPack.rows.length;
if (remaining < 1) remaining = 1;
var clipPack = dump("&clipboard", remaining, false);
var all = pinPack.rows.concat(clipPack.rows);
print(JSON.stringify({
  ok: true,
  pinCount: pinPack.total,
  clipCount: clipPack.total,
  count: pinPack.total + clipPack.total,
  entries: all
}));
"""


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
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        runtime = os.path.join(
            "/tmp", f"lukedaduke.copyq-{os.getuid()}-{os.getpid()}"
        )
    path = Path(runtime) / "lukedaduke.copyq"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _copyq_args(*parts: str, tab: str | None = None) -> list[str]:
    args = [COPYQ]
    if tab:
        args.extend(["tab", tab])
    args.extend(parts)
    return args


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


def _dump_eval(limit: int) -> dict[str, object]:
    script = _DUMP_SCRIPT.replace("LIMIT", str(limit))
    try:
        proc = _run([COPYQ, "eval", "--", script], timeout=5.0, max_bytes=DUMP_MAX_BYTES)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"copyq_eval:{exc}") from exc
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 or not raw:
        err = (proc.stderr or "").strip() or f"exit:{proc.returncode}"
        raise RuntimeError(f"copyq_eval:{err}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"copyq_eval:json:{exc}") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("copyq_eval:bad_payload")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("copyq_eval:bad_entries")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "image":
            continue
        mime = str(entry.get("mime") or "")
        tab = str(entry.get("tab") or CLIPBOARD_TAB)
        try:
            index = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        if mime not in IMAGE_MIMES and not mime.lower().startswith("image/"):
            continue
        path = _write_image_preview(index, tab, mime)
        if path:
            entry["previewPath"] = path
    return payload


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
            payload = _dump_eval(limit)
        except RuntimeError as exc:
            print(
                json.dumps({"ok": False, "error": str(exc), "entries": []}),
                flush=True,
            )
            return 1

        entries = payload.get("entries")
        if not isinstance(entries, list):
            entries = []

        # Pull API-key shaped clips into the encrypted hot vault (~30m TTL),
        # then hide the plaintext rows from the main list.
        candidates: list[str] = []
        kept: list[object] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or entry.get("preview") or "")
            entry.pop("keyish", None)
            # Prefix alone is not enough: `sk-example` matches the eval hint
            # and fails classify_secret, so it must stay a normal row.
            if classify_secret(text):
                candidates.append(text)
                continue
            if len(text) > 160:
                short = text[:160] + "…"
                entry["preview"] = short
                entry["text"] = short
            kept.append(entry)

        if candidates:
            try:
                harvest_texts(candidates)
            except OSError:
                pass

        try:
            hot_rows = list_overlay_entries()
        except OSError:
            hot_rows = []

        merged = hot_rows + kept
        payload["entries"] = merged
        payload["hotCount"] = len(hot_rows)
        payload["count"] = (
            int(payload.get("pinCount") or 0)
            + int(payload.get("clipCount") or 0)
            + len(hot_rows)
        )

        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return 0
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
