#!/usr/bin/python3
"""Read-only numbat activity probe for the io.github.duketopceo.numbat panel.

Emits one JSON object on stdout describing numbat's presence and recent
signal: installed, hooks_seen, active_agents, findings_24h, findings.

This helper is an observe-only consumer: it never runs `numbat hook
install`, never writes under ~/.numbat, and never enables enforce mode.
Its only inputs are a bounded tail-read of ~/.numbat/records.ndjson and,
when no records exist, `numbat agents --all`.

All external tools run by absolute path under a fixed minimal environment
with a per-call byte budget and deadline; the whole job self-terminates at
JOB_DEADLINE_S. ~/.numbat is opened descriptor-relative with O_NOFOLLOW;
records are untrusted user-owned input — strings are control-char
normalized and length-capped before they reach the QML layer.
"""
import json, os, selectors, shutil, signal, stat, subprocess, sys, time
from datetime import datetime, timezone

JOB_DEADLINE_S = 8
MAX_OUT_BYTES = 262144
TAIL_BYTES = 256 * 1024
WINDOW_S = 24 * 3600
FUTURE_SKEW_S = 300
MAX_STR = 64
MAX_FINDINGS = 20
MAX_AGENTS = 10
MAX_AGENT_ITEMS = 64
AGENTS_TIMEOUT_S = 2.0
AGENTS_MAX_BYTES = 65536

SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:" + os.path.join(
    os.path.expanduser("~"), ".local", "bin")
SAFE_ENV = {"PATH": SAFE_PATH, "LC_ALL": "C", "LANG": "C"}

RECORDS_NAME = "records.ndjson"
RECORDS_PATH_DISPLAY = "~/.numbat/records.ndjson"
TS_FIELDS = ("observed_at", "ts", "timestamp")
AGENT_TS_FIELDS = ("last_event", "last_seen", "observed_at", "ts", "timestamp")


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


def _load_records(numbat_home):
    """-> (records|None, status) where status is ok | absent | untrusted."""
    try:
        dirfd = _open_dir(numbat_home)
    except PermissionError:
        return None, "untrusted"
    except OSError:
        return None, "absent"
    try:
        res = _read_tail(dirfd, RECORDS_NAME, TAIL_BYTES)
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


def _rule_name(rec):
    rule = rec.get("rule")
    if isinstance(rule, dict):
        rule = rule.get("id") or rule.get("name") or rule.get("title")
    elif rule is None:
        rule = rec.get("rule_id") or rec.get("rule_name")
    return _clean(rule)


def _agents_via_cli(binary, run):
    """Coarse discovery list from `numbat agents --all`.

    Returns a list (possibly empty) on success, or None when the call
    itself failed/timed out. Non-JSON output degrades to an empty list.
    """
    out = run([binary, "agents", "--all"], timeout=AGENTS_TIMEOUT_S, max_bytes=AGENTS_MAX_BYTES)
    if out is None:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return []
    if isinstance(data, dict):
        if isinstance(data.get("agents"), list):
            items = data["agents"]
        else:
            items = [
                dict(v, name=k) if isinstance(v, dict) else {"name": k}
                for k, v in data.items()
            ]
    elif isinstance(data, list):
        items = data
    else:
        return []
    agents = []
    for item in items[:MAX_AGENT_ITEMS]:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        name = _clean(
            item.get("name") or item.get("agent") or item.get("id") or item.get("source_agent")
        )
        if not name:
            continue
        last = ""
        for field in AGENT_TS_FIELDS:
            if field in item:
                dt = _parse_ts(item[field])
                if dt is not None:
                    last = _iso_z(dt)
                    break
        agents.append({"name": name, "last_event": last})
        if len(agents) >= MAX_AGENTS:
            break
    return agents


def probe(tool=_tool, run=_run, numbat_home=None, now=None):
    """Assemble the numbat data packet. All seams injectable for tests."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    home = numbat_home if numbat_home is not None else os.path.join(
        os.path.expanduser("~"), ".numbat"
    )

    result = {
        "installed": False,
        "ok": False,
        "hooks_seen": False,
        "active_agents": [],
        "findings_24h": 0,
        "findings": [],
        "records_path": RECORDS_PATH_DISPLAY,
        "error": None,
    }

    binary = tool("numbat")
    if not binary:
        return result
    result["installed"] = True

    records, status = _load_records(home)
    if status == "untrusted":
        result["error"] = "untrusted ~/.numbat directory"
        return result

    if records:
        result["hooks_seen"] = True
        findings = []
        agents = {}
        for rec in records:
            rtype = rec.get("record_type")
            if rtype not in ("event", "finding"):
                continue
            dt = _ts_of(rec)
            if dt is None or not _within(dt, now):
                continue
            if rtype == "finding":
                findings.append((dt, rec))
            else:
                name = _agent_name(rec)
                if name and (name not in agents or dt > agents[name]):
                    agents[name] = dt
        findings.sort(key=lambda item: item[0], reverse=True)
        result["findings_24h"] = len(findings)
        result["findings"] = [
            {
                "rule": _rule_name(rec),
                "observed_at": _iso_z(dt),
                "agent": _agent_name(rec),
            }
            for dt, rec in findings[:MAX_FINDINGS]
        ]
        result["active_agents"] = [
            {"name": name, "last_event": _iso_z(dt)}
            for name, dt in sorted(agents.items(), key=lambda kv: kv[1], reverse=True)[
                :MAX_AGENTS
            ]
        ]
        result["ok"] = True
        return result

    # records.ndjson absent/empty/unparseable -> coarse CLI discovery.
    agents = _agents_via_cli(binary, run)
    if agents is None:
        result["error"] = "numbat agents --all failed"
        return result
    result["active_agents"] = agents
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
