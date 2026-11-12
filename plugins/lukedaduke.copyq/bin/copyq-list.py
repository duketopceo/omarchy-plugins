#!/usr/bin/env python3
"""Emit CopyQ history as JSON for the Omarchy overlay.

One `copyq eval` collects Pins + clipboard rows inside the CopyQ process —
per-row CLI reads cost ~5ms each and made opening the overlay take seconds.
Only image rows still cost an extra `copyq read` for thumbnail bytes.
Text + image rows. Fixed CopyQ path; COPYQ_BIN override for tests.
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
# Overlay only needs a short preview; eval output is capped wholesale.
MAX_IMAGE_PREVIEW = 2_000_000
MAX_EVAL_BYTES = 4_000_000
RUN_TIMEOUT = 4.0
HELPER_ALARM_SECS = 8
ENV = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "")}

# Runs inside CopyQ's script engine. __LIMIT__ is substituted by main().
# tab() switches the script's row context; size()/read() follow it.
# copyq eval unescapes backslash sequences in the script argument, so this
# source must stay free of \n \s \uXXXX etc. — use String.fromCharCode and
# charCodeAt comparisons instead.
_EVAL_SCRIPT = r"""
function __trim(s) {
  var a = 0;
  var b = s.length;
  while (a < b && s.charCodeAt(a) <= 32) a++;
  while (b > a && s.charCodeAt(b - 1) <= 32) b--;
  return s.substring(a, b);
}
function __oneLine(s) {
  return s.split(String.fromCharCode(13)).join(" ")
          .split(String.fromCharCode(10)).join(" ");
}
function __collect(tabName, pinned, limit) {
  var res = { entries: [], total: 0 };
  try { tab(tabName); } catch (e) { return res; }
  var n = 0;
  try { n = size(); } catch (e) { return res; }
  res.total = n;
  var lim = n < limit ? n : limit;
  var imgMimes = ["image/png", "image/jpeg", "image/jpg", "image/webp",
                  "image/bmp", "image/gif"];
  for (var i = 0; i < lim; i++) {
    var formats = [];
    try {
      var flines = str(read("?", i)).split(String.fromCharCode(10));
      for (var k = 0; k < flines.length; k++) {
        var fm = __trim(flines[k]);
        if (fm.length) formats.push(fm);
      }
    } catch (e) {}
    var imgMime = "";
    for (var a = 0; a < formats.length && !imgMime; a++) {
      var low = formats[a].toLowerCase();
      for (var b = 0; b < imgMimes.length; b++) {
        if (low === imgMimes[b]) { imgMime = formats[a]; break; }
      }
    }
    if (imgMime) {
      res.entries.push({ index: i, tab: tabName, pinned: pinned,
        type: "image", text: "", preview: "Image", previewPath: "",
        mime: imgMime, imageMime: imgMime });
      continue;
    }
    var plainIdx = -1;
    var textIdx = -1;
    for (var c = 0; c < formats.length; c++) {
      var cl = formats[c].toLowerCase();
      if (cl === "text/plain") plainIdx = c;
      else if (textIdx < 0 && cl.indexOf("text/") === 0) textIdx = c;
    }
    var pick = plainIdx >= 0 ? plainIdx : textIdx;
    if (pick < 0) continue;
    var text = "";
    try { text = str(read(formats[pick], i)); } catch (e) { continue; }
    if (__trim(text) === "") continue;
    var one = __oneLine(text);
    var prev = one.length > 160
      ? one.substring(0, 160) + String.fromCharCode(8230)
      : one;
    res.entries.push({ index: i, tab: tabName, pinned: pinned,
      type: "text", text: prev, preview: prev, previewPath: "",
      mime: formats[pick], imageMime: "" });
  }
  return res;
}
var __limit = __LIMIT__;
var __pins = __collect("Pins", true, __limit);
var __clips = __collect("&clipboard", false,
  Math.max(1, __limit - __pins.entries.length));
print(JSON.stringify({ pins: __pins, clips: __clips }));
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
    # Prefer the private runtime dir; never fall back to world-readable /tmp.
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


def _eval_collect(limit: int) -> dict:
    """Run the in-process collector; returns {pins, clips} or raises."""
    script = _EVAL_SCRIPT.replace("__LIMIT__", str(limit))
    proc = _run([COPYQ, "eval", script], max_bytes=MAX_EVAL_BYTES)
    out = proc.stdout or ""
    if proc.returncode != 0:
        # Byte-cap kill still yields a usable JSON prefix only if it parses;
        # a truncated payload does not, so treat overflow as failure.
        raise RuntimeError(f"copyq_eval:exit:{proc.returncode}")
    text = out.strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise RuntimeError(f"copyq_eval_json:{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("copyq_eval_json:not_object")
    return payload


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
    safe_tab = "pins" if tab == "Pins" else "clip"
    out = _preview_dir() / f"preview-{safe_tab}-{index}.{ext}"
    try:
        out.write_bytes(proc.stdout[:MAX_IMAGE_PREVIEW])
    except OSError:
        return None
    return str(out)


def _collect_entries(group: dict) -> tuple[list[dict[str, object]], int]:
    raw_entries = group.get("entries") if isinstance(group, dict) else None
    total = group.get("total") if isinstance(group, dict) else None
    if not isinstance(raw_entries, list):
        return [], 0
    entries: list[dict[str, object]] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        entry_type = str(item.get("type") or "text")
        preview = str(item.get("preview") or "")
        if entry_type == "text" and not preview.strip():
            continue
        preview = _preview(preview)
        if entry_type == "image":
            text = ""
        else:
            text = preview
        image_mime = str(item.get("imageMime") or "")
        preview_path = ""
        if entry_type == "image" and image_mime:
            try:
                index = int(item.get("index", -1))
            except (TypeError, ValueError):
                index = -1
            tab = str(item.get("tab") or "")
            if index >= 0 and tab:
                preview_path = _write_image_preview(index, tab, image_mime) or ""
        entries.append(
            {
                "index": item.get("index", 0),
                "tab": str(item.get("tab") or "&clipboard"),
                "pinned": bool(item.get("pinned")),
                "type": entry_type,
                "text": text,
                "preview": preview,
                "previewPath": preview_path,
                "mime": str(item.get("mime") or "text/plain"),
            }
        )
    try:
        total_int = int(total) if total is not None else len(entries)
    except (TypeError, ValueError):
        total_int = len(entries)
    return entries, total_int


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
            groups = _eval_collect(limit)
        except RuntimeError as exc:
            print(
                json.dumps({"ok": False, "error": str(exc), "entries": []}),
                flush=True,
            )
            return 1

        pin_entries, pin_total = _collect_entries(groups.get("pins") or {})
        clip_entries, clip_total = _collect_entries(groups.get("clips") or {})

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
