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
  * `numbat scan --emit findings` reconstructs findings from on-disk
    agent artifacts (events come from the live record stream — an
    `--emit all` scan cannot fit this probe's byte/deadline caps at
    real-world artifact scale). It runs on a stale-cache
    cycle (SCAN_INTERVAL_S, stretched to LIVE_SCAN_INTERVAL_S while
    records.ndjson is flowing) under a state-dir lock so the service
    and panel never scan twice; results are cached under
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

JOB_DEADLINE_S = 62
SCAN_TIMEOUT_S = 55          # per-exec deadline for `numbat scan` —
                             # findings scan measured ~24s at ~220MB of
                             # live records on omarchy-max and grows with
                             # artifact history; 2x headroom
SCAN_INTERVAL_S = int(os.environ.get("NUMBAT_SCAN_INTERVAL_S", "600"))
# While records.ndjson is flowing (hooked agents active) a rescan only
# re-derives what the live stream carries, so the heavy scan stretches to
# this interval and the cycles in between do a cheap `hook status` check.
LIVE_SCAN_INTERVAL_S = int(os.environ.get("NUMBAT_LIVE_SCAN_INTERVAL_S",
                                          "3600"))
HOOKS_TIMEOUT_S = 3.0
MAX_OUT_BYTES = 262144
SCAN_MAX_BYTES = 32 * 1024 * 1024
# Live-tail read window for the record sinks. At a busy ~10MB/day write rate
# 256KiB covered ~40min of stream; 1MiB stretches that to ~2.5h while staying
# a bounded read. Findings older than the window still surface via the
# 10-min scan cache — this only widens the live feed.
TAIL_BYTES = 1024 * 1024
# records.ndjson is append-only with no upstream rotation; hint the user to
# rotate by hand once it passes half a gigabyte.
ROT_HINT_BYTES = 512 * 1024 * 1024
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
LOCK_NAME = "scan.lock"
# Longer than the longest legal scan cycle (job deadline covers the scan
# timeout + hook status + tails) so a live peer's lock is never mistaken
# for an abandoned one.
LOCK_STALE_S = JOB_DEADLINE_S + 15
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

    -> (findings_recs|None, records_recs|None, records_present, status,
        findings_stat, records_stat)
    where status is ok | absent | untrusted. A missing/unreadable sink
    yields None for its list; records_present marks that records.ndjson
    itself exists as an owned regular file (the --emit all hook sink) —
    an empty file still counts as present. *_stat are (bytes, mtime)
    from _stat_file, or None.
    """
    try:
        dirfd = _open_dir(numbat_home)
    except PermissionError:
        return None, None, False, "untrusted", None, None
    except OSError:
        return None, None, False, "absent", None, None
    try:
        findings_res = _read_tail(dirfd, FINDINGS_NAME, TAIL_BYTES)
        records_res = _read_tail(dirfd, RECORDS_NAME, TAIL_BYTES)
        f_stat = _stat_file(dirfd, FINDINGS_NAME)
        r_stat = _stat_file(dirfd, RECORDS_NAME)
    finally:
        os.close(dirfd)
    findings = (list(_iter_records(*findings_res))
                if findings_res is not None else None)
    records = (list(_iter_records(*records_res))
               if records_res is not None else None)
    return findings, records, records_res is not None, "ok", f_stat, r_stat


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
        # Table rows are "<name>  <status-word>  <description...>" where
        # status is the second whitespace-separated column. Parse that
        # column instead of scanning the whole line — description text may
        # itself contain words like "installed".
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "installed":
            if parts[0] not in hooked:
                hooked.append(parts[0])
    return hooked


def _scan_records(binary, run):
    """`numbat scan --emit findings` NDJSON -> record list, or None on
    failure. Findings only: events already stream via records.ndjson, and
    `--emit all` cannot fit this probe's byte/deadline caps once a machine
    accumulates real agent history (measured 48s/55MB on omarchy-max)."""
    out = run([binary, "scan", "--emit", "findings"],
              timeout=SCAN_TIMEOUT_S, max_bytes=SCAN_MAX_BYTES)
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


def _scan_lock(state_dir):
    """Try to own this scan cycle under state_dir.

    -> (dirfd, lockfd) held open on success — caller MUST _scan_unlock —
    or None when a live peer holds the lock or the dir is unusable. A
    lock older than LOCK_STALE_S is treated as abandoned and stolen.
    """
    try:
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
        dirfd = _open_dir(state_dir)
    except (PermissionError, OSError):
        return None
    for _ in range(2):
        try:
            fd = os.open(LOCK_NAME, os.O_WRONLY | os.O_CREAT |
                         os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dirfd)
            return dirfd, fd
        except FileExistsError:
            pass
        except OSError:
            break
        try:
            st = os.stat(LOCK_NAME, dir_fd=dirfd, follow_symlinks=False)
        except OSError:
            break
        if not stat.S_ISREG(st.st_mode) or \
                time.time() - st.st_mtime < LOCK_STALE_S:
            break
        try:
            os.unlink(LOCK_NAME, dir_fd=dirfd)
        except OSError:
            break
    os.close(dirfd)
    return None


def _scan_unlock(held):
    """Release a _scan_lock() hold: unlink, then close both descriptors."""
    dirfd, fd = held
    try:
        os.unlink(LOCK_NAME, dir_fd=dirfd)
    except OSError:
        pass
    os.close(fd)
    os.close(dirfd)


def _bump_scan_cache(state_dir):
    """Touch the cache mtime — a failed scan still consumes the cycle, so
    the retry waits a full interval instead of hot-looping every poll."""
    try:
        dirfd = _open_dir(state_dir)
    except (PermissionError, OSError):
        return
    try:
        os.utime(CACHE_NAME, dir_fd=dirfd, follow_symlinks=False)
    except OSError:
        pass
    finally:
        os.close(dirfd)


def _rate_bpd(sample, cur_stat, now_ts):
    """Bytes/day growth rate between a cached {bytes, at} size sample and
    the current (bytes, mtime) stat. None when not computable."""
    if not isinstance(sample, dict) or not isinstance(cur_stat, tuple):
        return None
    p_b, p_t = sample.get("bytes"), sample.get("at")
    if not isinstance(p_b, (int, float)) or not isinstance(p_t, (int, float)):
        return None
    dt = now_ts - p_t
    if dt <= 0:
        return None
    return max(0.0, (cur_stat[0] - p_b) / dt * 86400)


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
        "records_bytes": 0,
        "records_mtime": None,
        "records_rate_bpd": None,
        "records_rot_hint": False,
        "findings_bytes": 0,
        "findings_mtime": None,
        "error": None,
    }

    binary = tool("numbat")
    if not binary:
        return result
    result["installed"] = True

    f_tail, r_tail, live_present, tail_status, f_stat, r_stat = \
        _load_record_tails(home)
    if tail_status == "untrusted":
        result["error"] = "untrusted ~/.numbat directory"
        return result
    if live_present:
        result["live_records_path"] = RECORDS_PATH_DISPLAY
    if isinstance(r_stat, tuple):
        result["records_bytes"], result["records_mtime"] = r_stat
        result["records_rot_hint"] = r_stat[0] >= ROT_HINT_BYTES
    if isinstance(f_stat, tuple):
        result["findings_bytes"], result["findings_mtime"] = f_stat

    # --- scan + hook-status on a stale-cache cycle ---
    # Two probes (service + panel) run this helper on overlapping timers;
    # the state-dir lock makes sure only one `numbat scan` — a multi-
    # second, whole-core crawl of every agent transcript — runs per cycle.
    # While records.ndjson is fresh the live feed already carries what a
    # rescan would reconstruct, so the scan cadence stretches to
    # LIVE_SCAN_INTERVAL_S and intervening cycles do a cheap `hook status`
    # refresh instead.
    cache = _load_scan_cache(state)
    prev_sample = (cache.get("records_size_sample")
                   if isinstance(cache, dict) else None)
    now_ts = time.time()
    cache_age = (now_ts - cache["_mtime"]
                 if isinstance(cache, dict)
                 and isinstance(cache.get("_mtime"), (int, float))
                 else None)
    live_fresh = (isinstance(r_stat, tuple)
                  and (now_ts - r_stat[1]) < SCAN_INTERVAL_S)
    scan_due = (cache_age is None
                or cache_age >= (LIVE_SCAN_INTERVAL_S
                                 if live_fresh else SCAN_INTERVAL_S))
    if scan_due:
        held = _scan_lock(state)
        if held is None:
            # A peer probe owns this cycle — serve what we have; its fresh
            # cache lands for the next poll.
            if cache is not None:
                result["scanned_at"] = cache.get("scanned_at")
            else:
                result["scan_error"] = "scan in progress"
        else:
            try:
                records = _scan_records(binary, run)
                hooked = _hooked_agents(binary, run)
                if records is not None:
                    payload = {
                        "scanned_at": _iso_z(now),
                        "summary": _summarize_records(records, now),
                        "hooked_agents":
                            hooked if isinstance(hooked, list) else [],
                        "records_size_sample": {
                            "bytes": (r_stat[0]
                                      if isinstance(r_stat, tuple) else 0),
                            "at": time.time(),
                        },
                    }
                    _write_scan_cache(state, payload)
                    cache = dict(payload)
                    cache["_mtime"] = time.time()
                    result["scanned_at"] = payload["scanned_at"]
                elif cache is not None:
                    result["scan_error"] = "scan failed; showing cached data"
                    result["scanned_at"] = cache.get("scanned_at")
                    _bump_scan_cache(state)
                else:
                    result["scan_error"] = "numbat scan failed"
                    payload = {
                        "scanned_at": None,
                        "summary": {},
                        "hooked_agents": [],
                        "records_size_sample": {
                            "bytes": (r_stat[0]
                                      if isinstance(r_stat, tuple) else 0),
                            "at": now_ts,
                        },
                    }
                    _write_scan_cache(state, payload)
                    cache = dict(payload)
                    cache["_mtime"] = time.time()
            finally:
                _scan_unlock(held)
    elif live_fresh and cache_age >= SCAN_INTERVAL_S:
        # Cheap in-between refresh: `hook status` only, then bump the cache
        # TTL and size sample so a peer doesn't trigger the heavy path.
        hooked = _hooked_agents(binary, run)
        if isinstance(hooked, list):
            refreshed = {k: v for k, v in cache.items() if k != "_mtime"}
            refreshed["hooked_agents"] = hooked
            refreshed["records_size_sample"] = {"bytes": r_stat[0],
                                                "at": now_ts}
            _write_scan_cache(state, refreshed)
            cache = dict(refreshed)
            cache["_mtime"] = now_ts
        result["scanned_at"] = cache.get("scanned_at")
    else:
        result["scanned_at"] = cache.get("scanned_at")

    result["records_rate_bpd"] = _rate_bpd(prev_sample, r_stat, time.time())

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
