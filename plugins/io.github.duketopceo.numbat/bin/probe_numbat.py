#!/usr/bin/python3
"""Read-only numbat activity probe for the io.github.duketopceo.numbat panel.

Emits one JSON object on stdout describing numbat's presence and recent
signal: installed, hooks_seen, active_agents, findings_24h, findings,
events, events_live, live_records_path, scanned_at, error.

Data model (verified against numbat 0.2.0, schema 0.3.0):
  * `numbat hook install` writes findings-only hooks that append to
    ~/.numbat/findings.ndjson — tailed live on every call.
  * `numbat hook install --emit all` additionally streams events and
    findings to ~/.numbat/records.ndjson — tailed live on every call too;
    its events take precedence over the scan-cached feed (events_live)
    and its finding records merge into the findings list. The file may
    not exist until a hook fires — absence is empty, not an error.
  * `numbat scan` reconstructs events + findings from on-disk agent
    artifacts and emits NDJSON to stdout. It is run on a stale-cache
    cycle (SCAN_INTERVAL_S) and the parsed result is cached under
    ~/.local/state/omarchy/numbat/ — never under ~/.numbat.
  * `numbat hook status` reports which agents have installed hooks and
    is folded into the same cache cycle.
  * `probe_numbat.py tail` is the service's cheap poll: pure file stats
    (presence, size, mtime) for both record sinks — no content reads,
    no scan, no subprocesses.

This helper is an observe-only consumer: it never runs `numbat hook
install`, never writes under ~/.numbat, and never enables enforce mode.

All external tools run by absolute path under a fixed minimal environment
with a per-call byte budget and deadline; the whole job self-terminates at
JOB_DEADLINE_S. ~/.numbat and the state dir are opened descriptor-relative
with O_NOFOLLOW; records are untrusted user-owned input — strings are
control-char normalized and length-capped before they reach the QML layer.
"""
import json, os, re, selectors, shutil, signal, stat, subprocess, sys, time
from datetime import datetime, timedelta, timezone

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
RECORDS_NAME = "records.ndjson"
CACHE_NAME = "scan-cache.json"
FINDINGS_PATH_DISPLAY = "~/.numbat/findings.ndjson"
RECORDS_PATH_DISPLAY = "~/.numbat/records.ndjson"
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


def _load_record_tails(numbat_home):
    """Tail both record sinks in one descriptor-relative pass.

    -> (findings_recs|None, records_recs|None, records_present, status)
    where status is ok | absent | untrusted. A missing/unreadable sink
    yields None for its list; records_present marks that records.ndjson
    itself exists as an owned regular file (the --emit all hook sink) —
    an empty file still counts as present.
    """
    try:
        dirfd = _open_dir(numbat_home)
    except PermissionError:
        return None, None, False, "untrusted"
    except OSError:
        return None, None, False, "absent"
    try:
        findings_res = _read_tail(dirfd, FINDINGS_NAME, TAIL_BYTES)
        records_res = _read_tail(dirfd, RECORDS_NAME, TAIL_BYTES)
    finally:
        os.close(dirfd)
    findings = (list(_iter_records(*findings_res))
                if findings_res is not None else None)
    records = (list(_iter_records(*records_res))
               if records_res is not None else None)
    return findings, records, records_res is not None, "ok"


def _stat_file(dirfd, name):
    """-> (bytes, mtime) for a no-follow, owned, regular file; None on any
    anomaly. Stat only — no content is read."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dirfd)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
            return None
        return st.st_size, st.st_mtime
    except OSError:
        return None
    finally:
        os.close(fd)


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


_TS_TAG = re.compile(r"<timestamp>([^<]{8,80})</timestamp>")
_TS_TAG_FMT = "%A, %b %d, %Y, %I:%M %p"
_TZ_TAG = re.compile(r"\(UTC([+-])(\d{1,2})(?::(\d{2}))?\)")


def _ts_from_preview(rec):
    """Cursor transcripts carry no top-level timestamp — numbat leaves the
    event time inside content_preview as `<timestamp>Saturday, Sep 5, 2026,
    12:04 AM (UTC-6)</timestamp>`. Parse it; return None on any mismatch."""
    s = rec.get("content_preview")
    if not isinstance(s, str):
        return None
    m = _TS_TAG.search(s[:512])
    if not m:
        return None
    body = m.group(1).strip()
    tz = timezone.utc
    mtz = _TZ_TAG.search(body)
    if mtz:
        sign = 1 if mtz.group(1) == "+" else -1
        hours = int(mtz.group(2))
        mins = int(mtz.group(3) or 0)
        tz = timezone(sign * timedelta(hours=hours, minutes=mins))
        body = _TZ_TAG.sub("", body).strip()
    try:
        dt = datetime.strptime(body, _TS_TAG_FMT)
    except ValueError:
        return None
    return dt.replace(tzinfo=tz).astimezone(timezone.utc)


def _ts_from_artifact(rec, mtimes):
    """Fallback: lstat mtime of evidence.local_path — for a transcript file
    that approximates last activity. User-owned regular files only; each
    path is statted at most once per probe via the mtimes dict."""
    ev = rec.get("evidence")
    if not isinstance(ev, dict):
        return None
    path = ev.get("local_path")
    if not isinstance(path, str) or not path.startswith("/") or len(path) > 512:
        return None
    if path in mtimes:
        return mtimes[path]
    dt = None
    try:
        st = os.lstat(path)
        if st.st_uid == os.geteuid() and stat.S_ISREG(st.st_mode):
            dt = datetime.fromtimestamp(st.st_mtime, timezone.utc)
    except OSError:
        pass
    mtimes[path] = dt
    return dt


def _ts_of(rec, mtimes=None):
    for field in TS_FIELDS:
        if field in rec:
            dt = _parse_ts(rec[field])
            if dt is not None:
                return dt
    dt = _ts_from_preview(rec)
    if dt is not None:
        return dt
    if mtimes is not None:
        return _ts_from_artifact(rec, mtimes)
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
    findings, events, agents, seen = [], [], {}, {}
    findings_24h = 0
    mtimes = {}
    for rec in records:
        rtype = rec.get("record_type")
        if rtype not in ("event", "finding"):
            continue
        dt = _ts_of(rec, mtimes)
        if dt is None:
            continue
        if rtype == "event":
            events.append((dt, rec))
            name = _agent_name(rec)
            if name and (name not in seen or dt > seen[name]):
                seen[name] = dt
            if _within(dt, now):
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
        "agents_seen": [
            {"name": name, "last_event": _iso_z(dt)}
            for name, dt in sorted(seen.items(),
                                   key=lambda kv: kv[1],
                                   reverse=True)[:MAX_AGENTS]
        ],
    }


def _merge_agents(cached, live):
    """Union of cached {name,last_event} rows and a live {name: datetime}
    map — the newer timestamp wins per agent. Returns the bounded,
    newest-first wire list the panel consumes."""
    merged = dict(live)
    for entry in cached:
        if not isinstance(entry, dict):
            continue
        name = _clean(entry.get("name"))
        dt = _parse_ts(entry.get("last_event"))
        if not name or dt is None:
            continue
        if name not in merged or dt > merged[name]:
            merged[name] = dt
    return [
        {"name": name, "last_event": _iso_z(dt)}
        for name, dt in sorted(merged.items(),
                               key=lambda kv: kv[1],
                               reverse=True)[:MAX_AGENTS]
    ]


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


def tail(numbat_home=None):
    """Pure-stat signature of the two record sinks — the service's cheap
    5s poll. No content reads, no scan, no subprocesses: presence, size
    and mtime only, so it stays safe to run even while hooks write.

    `findings_count`/`records_count` are file-presence flags (0|1) — real
    line counts would need a content read this verb deliberately skips.
    `newest_finding_ts` is the newer of the two file mtimes: stat-only,
    it approximates "a finding may have landed as recently as this" and
    gives the service its silent-baseline watermark on first poll.
    """
    home = numbat_home if numbat_home is not None else NUMBAT_HOME
    out = {
        "findings_count": 0,
        "findings_bytes": 0,
        "findings_mtime": 0.0,
        "records_count": 0,
        "records_bytes": 0,
        "records_mtime": 0.0,
        "newest_finding_ts": 0.0,
    }
    try:
        dirfd = _open_dir(home)
    except (PermissionError, OSError):
        return out
    try:
        f_stat = _stat_file(dirfd, FINDINGS_NAME)
        r_stat = _stat_file(dirfd, RECORDS_NAME)
    finally:
        os.close(dirfd)
    if f_stat is not None:
        out["findings_count"] = 1
        out["findings_bytes"], out["findings_mtime"] = f_stat
    if r_stat is not None:
        out["records_count"] = 1
        out["records_bytes"], out["records_mtime"] = r_stat
    out["newest_finding_ts"] = max(out["findings_mtime"],
                                 out["records_mtime"])
    return out


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
        "agents_seen": [],
        "findings_24h": 0,
        "findings": [],
        "events": [],
        "events_live": False,
        "scanned_at": None,
        "scan_error": None,
        "records_path": FINDINGS_PATH_DISPLAY,
        "live_records_path": None,
        "error": None,
    }

    binary = tool("numbat")
    if not binary:
        return result
    result["installed"] = True

    f_tail, r_tail, live_present, tail_status = _load_record_tails(home)
    if tail_status == "untrusted":
        result["error"] = "untrusted ~/.numbat directory"
        return result
    if live_present:
        result["live_records_path"] = RECORDS_PATH_DISPLAY

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

    # Live record tails take precedence (they are the hook sinks); scan
    # findings/events fill in the retroactive picture. findings.ndjson is
    # the findings-only sink; records.ndjson (--emit all) carries events
    # and may carry findings too — both record types merge in below.
    s_findings = summary.get("findings") or []
    s_events = summary.get("events") or []
    s_agents = summary.get("active_agents") or []

    live_findings = []
    live_events = []
    rec_yielded_events = False
    lt, le = [], []
    mtimes = {}
    for rec in f_tail or []:
        rtype = rec.get("record_type")
        if rtype not in ("finding", "event"):
            continue
        dt = _ts_of(rec, mtimes)
        if dt is None:
            continue
        if rtype == "finding":
            lt.append((dt, rec))
        else:
            le.append((dt, rec))
    for rec in r_tail or []:
        rtype = rec.get("record_type")
        if rtype not in ("finding", "event"):
            continue
        dt = _ts_of(rec, mtimes)
        if dt is None:
            continue
        if rtype == "finding":
            lt.append((dt, rec))
        else:
            le.append((dt, rec))
            rec_yielded_events = True
    if lt or le:
        lt.sort(key=lambda item: item[0], reverse=True)
        le.sort(key=lambda item: item[0], reverse=True)
        live_findings = [_finding_item(rec, dt) for dt, rec in lt]
        live_events = [_event_item(rec, dt) for dt, rec in le]
        if tail_status == "ok":
            result["hooks_seen"] = True

    # findings_24h is the true in-window count, not the capped list length:
    # _summarize_records counted every in-window scan finding before the
    # MAX_FINDINGS display cap, so keep that count and add in-window live
    # findings the scan summary does not already account for. A live finding
    # duplicating a scan finding evicted past the top-20 can double-count —
    # bounded and far rarer than the previous guaranteed undercount.
    s_keys = {
        (item.get("rule"), item.get("observed_at"), item.get("agent"))
        for item in s_findings
        if isinstance(item, dict)
    }
    scan_24h = summary.get("findings_24h")
    if isinstance(scan_24h, bool) or not isinstance(scan_24h, (int, float)):
        scan_24h = sum(
            1 for item in s_findings
            if isinstance(item, dict)
            and _within(_parse_ts(item.get("observed_at")) or now, now))
    live_24h = 0
    seen = set()
    merged = []
    for item in live_findings:
        if not isinstance(item, dict):
            continue
        key = (item.get("rule"), item.get("observed_at"), item.get("agent"))
        if key in seen:
            continue
        seen.add(key)
        if len(merged) < MAX_FINDINGS:
            merged.append(item)
        if (key not in s_keys
                and _within(_parse_ts(item.get("observed_at")) or now, now)):
            live_24h += 1
    for item in s_findings:
        if not isinstance(item, dict):
            continue
        key = (item.get("rule"), item.get("observed_at"), item.get("agent"))
        if key in seen:
            continue
        seen.add(key)
        if len(merged) < MAX_FINDINGS:
            merged.append(item)
    result["findings"] = merged
    result["findings_24h"] = max(0, int(scan_24h)) + live_24h

    # Live events sort first — the streamed feed outranks scan backfill.
    # Dedupe on (agent, observed_at, kind): a hook event the last scan
    # also reconstructed collapses to the live copy.
    seen_events = set()
    merged_events = []
    for item in live_events + s_events:
        if not isinstance(item, dict):
            continue
        key = (item.get("agent"), item.get("observed_at"), item.get("kind"))
        if key in seen_events:
            continue
        seen_events.add(key)
        merged_events.append(item)
        if len(merged_events) >= MAX_EVENTS:
            break
    result["events"] = merged_events
    # events_live reports the --emit all records feed specifically: the
    # Log tab's STREAMED hint is true only when records.ndjson actually
    # produced event rows this poll.
    result["events_live"] = rec_yielded_events
    # Fold live-tail events into the agent maps — without this the Activity
    # tab lags the Log tab's stream by a whole scan cycle (SCAN_INTERVAL_S),
    # since the cached summary only refreshes when a scan reruns.
    live_seen, live_active = {}, {}
    for dt, rec in le:
        name = _agent_name(rec)
        if not name:
            continue
        if name not in live_seen or dt > live_seen[name]:
            live_seen[name] = dt
        if _within(dt, now) and (name not in live_active
                                 or dt > live_active[name]):
            live_active[name] = dt
    result["active_agents"] = _merge_agents(s_agents, live_active)
    result["agents_seen"] = _merge_agents(
        summary.get("agents_seen") or [], live_seen)
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
    if len(sys.argv) > 1 and sys.argv[1] == "tail":
        sys.stdout.write(json.dumps(tail()) + "\n")
    else:
        sys.stdout.write(json.dumps(probe())[:MAX_OUT_BYTES] + "\n")
