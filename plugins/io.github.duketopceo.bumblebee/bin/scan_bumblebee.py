#!/usr/bin/python3
"""Supply-chain exposure scan for the io.github.duketopceo.bumblebee panel.

Wraps Perplexity's bumblebee (github.com/perplexityai/bumblebee): a read-only
scanner that inventories lockfiles/package metadata and exact-matches them
against an operator-supplied exposure catalog. The upstream binary ships no
threat intel, so this plugin supplies catalog/exposures.json and merges any
user entries under ~/.config/omarchy/plugins-data/bumblebee/catalog.d/.

Contract with the panel — exactly one JSON object on stdout, exit 0:

  {"installed": bool, "ok": bool, "scanned_at": iso8601|null,
   "age_s": int|null, "exposure_count": int,
   "exposures": [{"name","ecosystem","package","version","severity"}],
   "catalog_entries": int, "catalog_names": [str],
   "log": [{"scanned_at","status","exposure_count","duration_ms","error"?}],
   "partial": bool, "error": string|null}

Scans are expensive, so the last result is cached at
~/.local/state/omarchy/bumblebee/last-scan.json and only re-run once the
cache is older than SCAN_INTERVAL_S (default 6h; BUMBLEBEE_SCAN_INTERVAL_S
overrides, in seconds; `--force` argv bypasses freshness entirely). Every
scan attempt also appends to a rolling log at scan-log.json next to the
cache — newest first, capped at 20 entries, same descriptor-relative +
atomic 0600 publish as the cache — and the payload re-emits it as "log".
bumblebee is a v0.x tool: every flag/record assumption below is handled
defensively — malformed NDJSON lines are skipped, non-zero exits are
tolerated when records still parse, and a missing binary degrades to
{"installed": false} instead of a dead call.
"""
import json
import os
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

JOB_DEADLINE_S = 30            # whole-job wall clock backstop
SCAN_TIMEOUT_S = 20            # per-exec deadline for the bumblebee scan
MAX_OUT_BYTES = 512 * 1024     # NDJSON stdout budget (findings-only should be small)
CACHE_MAX_BYTES = 64 * 1024    # cached payload read cap
CATALOG_MAX_BYTES = 256 * 1024 # per-catalog-file read cap
MAX_CATALOG_FILES = 64
MAX_EXPOSURES = 50             # cap on the emitted exposure list
MAX_STR = 96
MAX_LOG_ENTRIES = 20           # rolling scan-log cap, newest first
MAX_CATALOG_NAMES = 12         # cap on emitted catalog_names preview
LOG_MAX_BYTES = 32 * 1024      # scan-log read cap

DEFAULT_SCAN_INTERVAL_S = 6 * 3600
INTERVAL_ENV = "BUMBLEBEE_SCAN_INTERVAL_S"

try:
    HOME = Path.home()
except Exception:
    HOME = Path("/")

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_CATALOG_DIR = PLUGIN_ROOT / "catalog"
CACHE_DIR_REL = ".local/state/omarchy/bumblebee"
CACHE_NAME = "last-scan.json"
LOG_NAME = "scan-log.json"
USER_CATALOG_REL = ".config/omarchy/plugins-data/bumblebee/catalog.d"

# Fixed tool-lookup path: no ambient $PATH, but the user's own ~/.local/bin is
# where a `go install`/tarball bumblebee most likely lives.
SAFE_PATH = "/usr/local/bin:/usr/bin:/bin:" + str(HOME / ".local" / "bin")
SAFE_ENV = {"PATH": SAFE_PATH, "HOME": str(HOME), "LC_ALL": "C", "LANG": "C"}


def _tool(name):
    """Absolute path for an external helper, resolved under SAFE_PATH only."""
    return shutil.which(name, path=SAFE_PATH)


def _kill_tree(proc):
    # Children are spawned with start_new_session, so the child's pgid equals
    # its pid and killpg reaps the whole scan subtree on timeout/overflow.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.wait(timeout=0.5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass


def _run(argv, timeout=SCAN_TIMEOUT_S, max_bytes=MAX_OUT_BYTES):
    """Run argv with minimal env, hard deadline, producer byte cap.

    Returns (stdout_text|None, error|None, returncode|None). error is one of
    "empty_argv", "spawn_failed", "timeout", "output_too_large". The exit
    status is reported, not judged — callers tolerate non-zero exits when the
    output still parses (v0.x CLI semantics are not fixed).
    """
    if not argv or not argv[0]:
        return None, "empty_argv", None
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=SAFE_ENV, start_new_session=True,
        )
    except OSError:
        return None, "spawn_failed", None
    buf = bytearray()
    deadline = time.monotonic() + timeout
    completed = False
    overflow = False
    sel = selectors.DefaultSelector()
    try:
        sel.register(proc.stdout, selectors.EVENT_READ)
        while True:
            if proc.poll() is not None:
                # Drain remaining output without a blocking read(): a
                # descendant holding the pipe must not stall us past the
                # deadline — select() reports EOF or times out.
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not sel.select(remaining):
                        break
                    try:
                        tail = os.read(proc.stdout.fileno(), 65536)
                    except OSError:
                        break
                    if not tail:
                        break
                    buf += tail
                    if len(buf) > max_bytes:
                        break
                completed = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if not sel.select(remaining):
                break
            try:
                chunk = os.read(proc.stdout.fileno(), 65536)
            except OSError:
                break
            if not chunk:
                completed = True
                break
            buf += chunk
            if len(buf) > max_bytes:
                overflow = True
                break
    finally:
        sel.close()
        if proc.poll() is None:
            _kill_tree(proc)
        try:
            proc.stdout.close()
        except OSError:
            pass
    if overflow or len(buf) > max_bytes:
        return None, "output_too_large", None
    if not completed:
        return None, "timeout", None
    return buf.decode(errors="replace"), None, proc.returncode


def _clean(value, limit=MAX_STR):
    """Control-char-normalized, length-clipped string for the payload."""
    s = "".join(
        c if (ord(c) >= 0x20 and ord(c) != 0x7F) else " "
        for c in str(value if value is not None else "")
    )
    return s[:limit].strip()


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _scan_interval_s():
    raw = os.environ.get(INTERVAL_ENV)
    if raw in (None, ""):
        return DEFAULT_SCAN_INTERVAL_S
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL_S


# --- cache: descriptor-relative read, atomic republish (standby pattern) ---

def _open_dir(path):
    """Descriptor for a directory — no symlinks, must be ours."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        os.close(fd)
        raise PermissionError(f"{path} is not a user-owned real directory")
    return fd


def _read_capped(dirfd, name, limit):
    """Bounded, no-follow, regular-file read -> (bytes, mtime); (None, None) on anomaly."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dirfd)
    except OSError:
        return None, None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_size > limit:
            return None, None
        return os.read(fd, limit), st.st_mtime
    finally:
        os.close(fd)


def _publish(dirfd, name, data):
    """Write via exclusive same-dir temp file + atomic rename, mode 0600."""
    tmp = f".{name}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dirfd)
    try:
        os.write(fd, data.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, name, src_dir_fd=dirfd, dst_dir_fd=dirfd)


def _read_cache(cache_dir):
    """-> (payload_dict|None, cache_mtime|None). Only re-emit plausible dicts."""
    try:
        dirfd = _open_dir(cache_dir)
    except (OSError, PermissionError):
        return None, None
    try:
        raw, mtime = _read_capped(dirfd, CACHE_NAME, CACHE_MAX_BYTES)
    finally:
        os.close(dirfd)
    if raw is None or mtime is None:
        return None, None
    try:
        data = json.loads(raw)
    except ValueError:
        return None, None
    if not isinstance(data, dict) or "installed" not in data:
        return None, None
    return data, mtime


def _write_cache(cache_dir, payload):
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        dirfd = _open_dir(cache_dir)
    except (OSError, PermissionError):
        return False
    try:
        _publish(dirfd, CACHE_NAME, json.dumps(payload))
        return True
    except OSError:
        return False
    finally:
        os.close(dirfd)


# --- rolling scan log (same descriptor-relative + atomic-publish rules) ---

def _clean_int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clean_log_entry(entry):
    """Fixed-shape copy of a stored entry — the file is user-writable, so
    re-emission re-clips strings and coerces ints instead of trusting it."""
    if not isinstance(entry, dict):
        return None
    out = {
        "scanned_at": _clean(entry.get("scanned_at"), 40),
        "status": _clean(entry.get("status"), 16),
        "exposure_count": _clean_int(entry.get("exposure_count")),
        "duration_ms": _clean_int(entry.get("duration_ms")),
    }
    err = _clean(entry.get("error"), 120)
    if err:
        out["error"] = err
    return out


def _read_log(cache_dir):
    """-> stored entries newest-first (<=MAX_LOG_ENTRIES); [] on anomaly."""
    try:
        dirfd = _open_dir(cache_dir)
    except (OSError, PermissionError):
        return []
    try:
        raw, _mtime = _read_capped(dirfd, LOG_NAME, LOG_MAX_BYTES)
    finally:
        os.close(dirfd)
    if raw is None:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    entries = []
    for e in data:
        e = _clean_log_entry(e)
        if e is not None:
            entries.append(e)
        if len(entries) >= MAX_LOG_ENTRIES:
            break
    return entries


def _append_log(cache_dir, entry):
    """Prepend entry, cap at MAX_LOG_ENTRIES, atomic 0600 republish.

    Returns the in-memory list (also what's written) so the payload still
    carries the new entry even when the publish fails.
    """
    entries = ([entry] + _read_log(cache_dir))[:MAX_LOG_ENTRIES]
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        dirfd = _open_dir(cache_dir)
    except (OSError, PermissionError):
        return entries
    try:
        _publish(dirfd, LOG_NAME, json.dumps(entries))
    except OSError:
        pass
    finally:
        os.close(dirfd)
    return entries


# --- exposure catalog counting (shipped dir + user catalog.d) ---

def _read_file_capped(path, limit):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            return None
        return os.read(fd, limit)
    except OSError:
        return None
    finally:
        os.close(fd)


def _catalog_stats(dir_path, name_cap):
    """-> (entry_count, names[:name_cap]) across *.json; bad files skipped.

    names is a small preview for the panel's catalog tab: each entry's
    "name" (or "id"), cleaned and clipped like any emitted string.
    """
    total = 0
    names = []
    try:
        file_names = sorted(os.listdir(dir_path))
    except OSError:
        return total, names
    seen = 0
    for name in file_names:
        if not name.endswith(".json"):
            continue
        seen += 1
        if seen > MAX_CATALOG_FILES:
            break
        raw = _read_file_capped(dir_path / name, CATALOG_MAX_BYTES)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict):
            entries = data.get("entries")
        elif isinstance(data, list):
            entries = data
        else:
            continue
        if not isinstance(entries, list):
            continue
        total += len(entries)
        for e in entries:
            if len(names) >= name_cap:
                break
            if isinstance(e, dict):
                n = _clean(e.get("name") or e.get("id"))
            elif isinstance(e, str):
                n = _clean(e)
            else:
                continue
            if n:
                names.append(n)
    return total, names


# --- NDJSON parsing (defensive: record_type-keyed, malformed lines skipped) ---

def _pick(*vals):
    for v in vals:
        if v:
            return v
    return ""


def _finding_exposure(rec):
    """Map a finding record onto the emit shape, tolerating v0.x field drift."""
    exp = rec.get("exposure") if isinstance(rec.get("exposure"), dict) else {}
    comp = rec.get("component") if isinstance(rec.get("component"), dict) else {}
    return {
        "name": _clean(_pick(rec.get("name"), exp.get("name"),
                             rec.get("advisory"), exp.get("id"), rec.get("id"))),
        "ecosystem": _clean(_pick(rec.get("ecosystem"), exp.get("ecosystem"),
                                  comp.get("ecosystem"))),
        "package": _clean(_pick(rec.get("package"), exp.get("package"),
                                rec.get("package_name"), comp.get("package"),
                                comp.get("name"))),
        "version": _clean(_pick(rec.get("version"), rec.get("installed_version"),
                                comp.get("version"), exp.get("version_spec"))),
        "severity": _clean(_pick(rec.get("severity"), exp.get("severity"))),
    }


def parse_ndjson(text):
    """-> (exposures[:MAX_EXPOSURES], finding_count, partial, records_seen)."""
    exposures = []
    findings = 0
    partial = False
    records_seen = False
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        rtype = rec.get("record_type")
        if not isinstance(rtype, str):
            continue
        records_seen = True
        if rtype == "finding":
            findings += 1
            if len(exposures) < MAX_EXPOSURES:
                exposures.append(_finding_exposure(rec))
        elif rtype == "scan_summary":
            status = rec.get("status")
            if status is None and isinstance(rec.get("summary"), dict):
                status = rec["summary"].get("status")
            if str(status or "") != "complete":
                partial = True
    return exposures, findings, partial, records_seen


# --- orchestration ---

def _base_payload(installed, catalog_entries):
    return {
        "installed": installed,
        "ok": False,
        "scanned_at": None,
        "age_s": None,
        "exposure_count": 0,
        "exposures": [],
        "catalog_entries": catalog_entries,
        "catalog_names": [],
        "log": [],
        "partial": False,
        "error": None,
    }


def collect(now=None, run=None, tool=None, home=None, plugin_root=None,
            force=False):
    """Build the payload. run/tool/home/plugin_root/now/force are injectable
    seams; force=True bypasses cache freshness (the panel's Rescan button)."""
    if now is None:
        now = time.time()
    if run is None:
        run = _run
    home = Path(home) if home is not None else HOME
    plugin_root = Path(plugin_root) if plugin_root is not None else PLUGIN_ROOT

    interval = _scan_interval_s()
    shipped_dir = plugin_root / "catalog"
    user_cat = home / USER_CATALOG_REL
    cache_dir = home / CACHE_DIR_REL
    shipped_count, names = _catalog_stats(shipped_dir, MAX_CATALOG_NAMES)
    user_count, user_names = _catalog_stats(
        user_cat, max(0, MAX_CATALOG_NAMES - len(names)))
    catalog_entries = shipped_count + user_count
    catalog_names = (names + user_names)[:MAX_CATALOG_NAMES]

    if tool is None:
        tool = _tool("bumblebee")
    if not tool:
        # Capability degrade: no binary, no exec, still a valid payload.
        payload = _base_payload(False, catalog_entries)
        payload["catalog_names"] = catalog_names
        payload["log"] = _read_log(cache_dir)
        return payload

    cached, mtime = _read_cache(cache_dir)
    if not force and cached is not None and (now - mtime) < interval:
        cached["age_s"] = max(0, int(now - mtime))
        cached["catalog_entries"] = catalog_entries
        cached["catalog_names"] = catalog_names
        cached["log"] = _read_log(cache_dir)
        return cached

    argv = [tool, "scan", "--profile", "baseline",
            "--exposure-catalog", str(shipped_dir)]
    if user_cat.is_dir():
        argv += ["--exposure-catalog", str(user_cat)]
    argv += ["--findings-only", "--output", "stdout"]

    started = time.monotonic()
    try:
        text, err, rc = run(argv, timeout=SCAN_TIMEOUT_S, max_bytes=MAX_OUT_BYTES)
    except Exception:
        text, err, rc = None, "run_failed", None
    duration_ms = int((time.monotonic() - started) * 1000)

    exposures, findings, partial, records_seen = [], 0, False, False
    error = err
    if text is not None:
        exposures, findings, partial, records_seen = parse_ndjson(text)
        if error is None and rc not in (0, None) and not records_seen:
            error = f"exit {rc}"

    entry = {
        "scanned_at": _iso(now),
        "status": "error" if error is not None
                  else ("partial" if partial else "complete"),
        "exposure_count": findings,
        "duration_ms": duration_ms,
    }
    if error is not None:
        entry["error"] = _clean(error, 120)

    payload = {
        "installed": True,
        "ok": error is None and text is not None,
        "scanned_at": _iso(now),
        "age_s": 0,
        "exposure_count": findings,
        "exposures": exposures,
        "catalog_entries": catalog_entries,
        "catalog_names": catalog_names,
        "log": _append_log(cache_dir, entry),
        "partial": partial,
        "error": error,
    }
    _write_cache(cache_dir, payload)
    return payload


def main():
    # Session/group leader + SIGALRM backstop so a wedged run can always be
    # group-killed and never outlives JOB_DEADLINE_S.
    try:
        os.setsid()
    except OSError:
        pass
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)
    force = "--force" in sys.argv[1:]
    try:
        payload = collect(force=force)
    except Exception as exc:
        payload = _base_payload(False, 0)
        payload["error"] = "internal: " + _clean(exc, 120)
    sys.stdout.write(json.dumps(payload)[:MAX_OUT_BYTES] + "\n")


if __name__ == "__main__":
    main()
