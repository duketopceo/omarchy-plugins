#!/usr/bin/python3
"""Read-only numbat activity probe for the io.github.duketopceo.numbat panel.

Emits one JSON object on stdout describing numbat's presence and recent
signal: installed, hooks_seen, active_agents, findings_24h, findings,
events, scanned_at, error.

Data model (verified against numbat 0.2.0, schema 0.3.0):
  * `numbat hook install` writes findings-only hooks that append to
    ~/.numbat/findings.ndjson — tailed live on every call.
  * `numbat scan` reconstructs events + findings from on-disk agent
    artifacts and emits NDJSON to stdout. It is run on a stale-cache
    cycle (SCAN_INTERVAL_S) and the parsed result is cached under
    ~/.local/state/omarchy/numbat/ — never under ~/.numbat.
  * `numbat hook status` reports which agents have installed hooks and
    is folded into the same cache cycle.

This helper is an observe-only consumer: it never runs `numbat hook
install`, never writes under ~/.numbat, and never enables enforce mode.

All external tools run by absolute path under a fixed minimal environment
with a per-call byte budget and deadline; the whole job self-terminates at
JOB_DEADLINE_S. ~/.numbat and the state dir are opened descriptor-relative
with O_NOFOLLOW; records are untrusted user-owned input — strings are
control-char normalized and length-capped before they reach the QML layer.
"""
import json, os, selectors, shutil, signal, stat, subprocess, sys, time
from datetime import datetime, timezone

JOB_DEADLINE_S = 30
SCAN_TIMEOUT_S = 25          # per-exec deadline for `numbat scan`
SCAN_INTERVAL_S = int(os.environ.get("NUMBAT_SCAN_INTERVAL_S", "600"))
HOOKS_TIMEOUT_S = 3.0
MAX_OUT_BYTES = 262144
SCAN_MAX_BYTES = 32 * 1024 * 1024
TAIL_BYTES = 256 * 1024
WINDOW_S = 24 * 3600
FUTURE_SKEW_S = 300
MAX_STR = 64
MAX_FINDINGS = 20
MAX_EVENTS = 30
EVENT_STR = 80
MAX_AGENTS = 10
CACHE_MAX_BYTES = 128 * 1024

SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:" + os.path.join(
    os.path.expanduser("~"), ".local", "bin")
SAFE_ENV = {"PATH": SAFE_PATH, "HOME": os.path.expanduser("~"),
            "LC_ALL": "C", "LANG": "C"}

NUMBAT_HOME = os.path.join(os.path.expanduser("~"), ".numbat")
STATE_DIR = os.path.join(os.path.expanduser("~"),
                         ".local", "state", "omarchy", "numbat")
FINDINGS_NAME = "findings.ndjson"
CACHE_NAME = "scan-cache.json"
FINDINGS_PATH_DISPLAY = "~/.numbat/findings.ndjson"
TS_FIELDS = ("observed_at", "detected_at", "timestamp", "ts")
EVENT_KIND_FIELDS = ("observed_event_type", "event_type", "kind", "action")
EVENT_SUMMARY_FIELDS = ("summary", "detail", "message", "content_preview",
                        "observed_content_preview")
FINDING_NAME_FIELDS = ("title", "rule_id", "rule_name")


def _tool(name):
    """Absolute path for an external helper, resolved under SAFE_PATH only."""
    return shutil.which(name, path=SAFE_PATH)


def _kill_tree(proc):
    # Helpers share this process's session group (no start_new_session) so the
    # QML watchdog's group-kill reaches the whole tree; here we only need the
    # direct child.
    try:
        os.kill(proc.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass


def _run(argv, timeout=2.0, max_bytes=MAX_OUT_BYTES):
    """Run argv with minimal env, hard deadline, producer byte cap.

    Child joins this process's session group so the QML watchdog's group-kill
    reaches the whole tree. Returns stdout text or None on failure/timeout/
    overflow.
    """
    if not argv or not argv[0]:
        return None
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=SAFE_ENV,
        )
    except OSError:
        return None
    buf = bytearray()
    deadline = time.monotonic() + timeout
    completed = False
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
                break
    finally:
        sel.close()
        if proc.poll() is None:
            _kill_tree(proc)
        try:
            proc.stdout.close()
        except OSError:
            pass
    if not completed or len(buf) > max_bytes:
        return None
    return buf.decode(errors="replace")


def _clean(value, limit=MAX_STR):
    """Control-char-normalized, length-capped string from untrusted input."""
    s = str(value if value is not None else "")
    s = "".join(" " if (ord(c) < 32 or 127 <= ord(c) <= 159) else c for c in s)
    return s.strip()[:limit]


def _open_dir(path):
    """Descriptor for a directory — no symlinks, must be ours."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        os.close(fd)
        raise PermissionError(f"{path} is not a user-owned real directory")
    return fd


def _read_tail(dirfd, name, limit):
    """Last <=limit bytes of a no-follow, owned, regular file.

    Returns (data, seeked) — seeked marks that the head of the file was
    skipped, so the first returned line may be partial — or None on any
    anomaly.
    """
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dirfd)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
            return None
        seeked = st.st_size > limit
        if seeked:
            os.lseek(fd, st.st_size - limit, os.SEEK_SET)
        chunks = []
        remaining = limit
        while remaining > 0:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks), seeked
    except OSError:
        return None
    finally:
        os.close(fd)


def _read_capped(dirfd, name, limit):
    """Read a whole file bounded to limit bytes; None on anomaly."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dirfd)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
            return None
        data = b""
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)
        if len(data) > limit:
            return None
        return data
    except OSError:
        return None
    finally:
        os.close(fd)


def _publish(dirfd, name, payload):
    """Atomic 0600 publish: exclusive temp + rename, same directory."""
    tmp = "." + name + ".tmp"
    try:
        os.unlink(tmp, dir_fd=dirfd)
    except OSError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=dirfd)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    os.replace(tmp, name, src_dir_fd=dirfd, dst_dir_fd=dirfd)


def _iter_records(data, seeked):
    """Yield parsed JSON-object lines; the possibly-partial first tail line
    and any malformed lines are skipped — records are untrusted input."""
    lines = data.decode("utf-8", errors="replace").split("\n")
    if seeked and lines:
        lines = lines[1:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            yield rec


def _load_findings_tail(numbat_home):
    """-> (records|None, status) where status is ok | absent | untrusted."""
    try:
        dirfd = _open_dir(numbat_home)
    except PermissionError:
        return None, "untrusted"
    except OSError:
        return None, "absent"
    try:
        res = _read_tail(dirfd, FINDINGS_NAME, TAIL_BYTES)
    finally:
        os.close(dirfd)
    if res is None:
        return None, "absent"
    data, seeked = res
    return list(_iter_records(data, seeked)), "ok"


def _parse_ts(value):
    """ISO8601 (Z or numeric offset) or epoch seconds -> aware UTC datetime."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    if v[-1] in ("Z", "z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ts_of(rec):
    for field in TS_FIELDS:
        if field in rec:
            dt = _parse_ts(rec[field])
            if dt is not None:
                return dt
    return None


def _iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _within(dt, now):
    delta = (now - dt).total_seconds()
    return -FUTURE_SKEW_S <= delta <= WINDOW_S


def _agent_name(rec):
    return _clean(rec.get("source_agent") or rec.get("agent") or rec.get("agent_name"))


def _finding_name(rec):
    return _first_clean(rec, FINDING_NAME_FIELDS, 96)


def _first_clean(rec, fields, limit):
    """First non-empty control-normalized, length-capped field value."""
    for field in fields:
        if field in rec:
            s = _clean(rec[field], limit)
            if s:
                return s
    return ""


def _finding_item(rec, dt):
    item = {
        "rule": _finding_name(rec),
        "observed_at": _iso_z(dt),
        "agent": _agent_name(rec),
    }
    if "severity" in rec:
        item["severity"] = _clean(rec["severity"])
    return item


def _event_item(rec, dt):
    return {
        "observed_at": _iso_z(dt),
        "agent": _agent_name(rec),
        "kind": _first_clean(rec, EVENT_KIND_FIELDS, EVENT_STR),
        "summary": _first_clean(rec, EVENT_SUMMARY_FIELDS, EVENT_STR),
    }


def _summarize_records(records, now):
    """Fold raw records into a bounded summary dict for the cache + panel.

    Findings and events keep the newest MAX_* rows regardless of age so a
    stale tail still shows what numbat last saw; findings_24h counts the
    in-window subset, and active_agents only lists agents with in-window
    events.
    """
    findings, events, agents = [], [], {}
    findings_24h = 0
    for rec in records:
        rtype = rec.get("record_type")
        if rtype not in ("event", "finding"):
            continue
        dt = _ts_of(rec)
        if dt is None:
            continue
        if rtype == "event":
            events.append((dt, rec))
            if _within(dt, now):
                name = _agent_name(rec)
                if name and (name not in agents or dt > agents[name]):
                    agents[name] = dt
        else:
            findings.append((dt, rec))
            if _within(dt, now):
                findings_24h += 1
    findings.sort(key=lambda item: item[0], reverse=True)
    events.sort(key=lambda item: item[0], reverse=True)
    return {
        "findings": [_finding_item(rec, dt)
                     for dt, rec in findings[:MAX_FINDINGS]],
        "findings_24h": findings_24h,
        "events": [_event_item(rec, dt)
                   for dt, rec in events[:MAX_EVENTS]],
        "active_agents": [
            {"name": name, "last_event": _iso_z(dt)}
            for name, dt in sorted(agents.items(),
                                   key=lambda kv: kv[1],
                                   reverse=True)[:MAX_AGENTS]
        ],
    }


def _hooked_agents(binary, run):
    """Agent names with numbat-owned hooks installed (`numbat hook status`).

    Returns a sorted list (possibly empty) or None when the call failed.
    """
    out = run([binary, "hook", "status"], timeout=HOOKS_TIMEOUT_S,
              max_bytes=65536)
    if out is None:
        return None
    hooked = []
    for line in out.splitlines():
        line = line.strip().lower()
        if not line or line.startswith("agent"):
            continue
        # status rows look like: "codex    installed ..." or "x  not installed"
        if "install" in line and "not" not in line.split()[1:3]:
            name = line.split()[0]
            if name and name not in hooked:
                hooked.append(name)
    return hooked


def _scan_records(binary, run):
    """`numbat scan` NDJSON -> record list, or None on failure."""
    out = run([binary, "scan", "--emit", "all"], timeout=SCAN_TIMEOUT_S,
              max_bytes=SCAN_MAX_BYTES)
    if out is None:
        return None
    return list(_iter_records(out.encode(), False))


def _load_scan_cache(state_dir):
    """-> (dict|None): cached scan payload if present and parseable."""
    try:
        dirfd = _open_dir(state_dir)
    except (PermissionError, OSError):
        return None
    try:
        data = _read_capped(dirfd, CACHE_NAME, CACHE_MAX_BYTES)
    finally:
        os.close(dirfd)
    if data is None:
        return None
    try:
        obj = json.loads(data.decode("utf-8", errors="replace"))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    try:
        mtime = os.lstat(os.path.join(state_dir, CACHE_NAME)).st_mtime
    except OSError:
        return None
    obj["_mtime"] = mtime
    return obj


def _write_scan_cache(state_dir, payload):
    """Atomic 0600 publish of the scan cache; failure is non-fatal."""
    try:
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
        dirfd = _open_dir(state_dir)
    except (PermissionError, OSError):
        return
    try:
        _publish(dirfd, CACHE_NAME, json.dumps(payload).encode())
    except OSError:
        pass
    finally:
        os.close(dirfd)


def _fresh_enough(cache, now_ts):
    mtime = cache.get("_mtime")
    if not isinstance(mtime, (int, float)):
        return False
    return (now_ts - mtime) < SCAN_INTERVAL_S


def probe(tool=_tool, run=_run, numbat_home=None, state_dir=None, now=None):
    """Assemble the numbat data packet. All seams injectable for tests."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    home = numbat_home if numbat_home is not None else NUMBAT_HOME
    state = state_dir if state_dir is not None else STATE_DIR

    result = {
        "installed": False,
        "ok": False,
        "hooks_seen": False,
        "hooked_agents": [],
        "active_agents": [],
        "findings_24h": 0,
        "findings": [],
        "events": [],
        "scanned_at": None,
        "scan_error": None,
        "records_path": FINDINGS_PATH_DISPLAY,
        "error": None,
    }

    binary = tool("numbat")
    if not binary:
        return result
    result["installed"] = True

    tail, tail_status = _load_findings_tail(home)
    if tail_status == "untrusted":
        result["error"] = "untrusted ~/.numbat directory"
        return result

    # --- scan + hook-status on a stale-cache cycle ---
    cache = _load_scan_cache(state)
    if cache is None or not _fresh_enough(cache, time.time()):
        records = _scan_records(binary, run)
        hooked = _hooked_agents(binary, run)
        if records is not None:
            payload = {
                "scanned_at": _iso_z(now),
                "summary": _summarize_records(records, now),
                "hooked_agents": hooked if isinstance(hooked, list) else [],
            }
            _write_scan_cache(state, payload)
            cache = dict(payload)
            cache["_mtime"] = time.time()
            result["scanned_at"] = payload["scanned_at"]
        elif cache is not None:
            result["scan_error"] = "scan failed; showing cached data"
            result["scanned_at"] = cache.get("scanned_at")
        else:
            result["scan_error"] = "numbat scan failed"
    else:
        result["scanned_at"] = cache.get("scanned_at")

    summary = (cache.get("summary") or {}) if isinstance(cache, dict) else {}
    hooked = cache.get("hooked_agents", []) if isinstance(cache, dict) else []
    if isinstance(hooked, list):
        result["hooked_agents"] = [_clean(a, 32) for a in hooked][:32]
        result["hooks_seen"] = bool(result["hooked_agents"])

    # Live findings tail takes precedence (it is the hook sink); scan
    # findings fill in the retroactive picture.
    s_findings = summary.get("findings") or []
    s_events = summary.get("events") or []
    s_agents = summary.get("active_agents") or []

    live_findings = []
    if tail:
        lt = []
        for rec in tail:
            if rec.get("record_type") != "finding":
                continue
            dt = _ts_of(rec)
            if dt is not None:
                lt.append((dt, rec))
        lt.sort(key=lambda item: item[0], reverse=True)
        live_findings = [_finding_item(rec, dt) for dt, rec in lt]
        if tail_status == "ok" and lt:
            result["hooks_seen"] = True

    seen = set()
    merged = []
    for item in live_findings + s_findings:
        if not isinstance(item, dict):
            continue
        key = (item.get("rule"), item.get("observed_at"), item.get("agent"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= MAX_FINDINGS:
            break
    result["findings"] = merged
    result["findings_24h"] = sum(
        1 for item in merged
        if _within(_parse_ts(item.get("observed_at")) or now, now))
    result["events"] = s_events
    result["active_agents"] = s_agents
    result["ok"] = True
    return result


if __name__ == "__main__":
    # Become a session/group leader so the QML watchdog can SIGKILL the entire
    # probe tree (this process plus any helpers still running) via killpg.
    try:
        os.setsid()
    except OSError:
        pass
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)
    sys.stdout.write(json.dumps(probe())[:MAX_OUT_BYTES] + "\n")
