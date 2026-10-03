#!/usr/bin/python3
"""Resource telemetry for the lukedaduke.fan panel, emitted as the R13 envelope.

Two modes:

  system_monitor_stats.py --bar   RAM, one temperature, fan RPM and mode. Reads
                                  /proc and /sys only; no process scan, no GPU.
  system_monitor_stats.py         Full panel data: CPU and per-core load, RAM,
                                  GPU, temperatures, disks, fans, and running
                                  processes grouped under friendly names.

No process, disk or hardware-listing tool is spawned. CPU percentages come from
the jiffies delta between this run and the previous one, cached (0600) in
$XDG_RUNTIME_DIR/omarchy-fan/procs.json. nvidia-smi runs only when an NVIDIA GPU
is present and already awake, so a runtime-suspended dGPU is never woken.
Command lines are redacted before anything leaves the helper.
"""

from __future__ import annotations

import json
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _omplug import envelope, fsio, proc, sysfs  # noqa: E402
from _omplug.text import clean_text  # noqa: E402

SCHEMA = 1
JOB_DEADLINE_S = 8
MAX_OUT_BYTES = 256 * 1024
MAX_GROUPS = 12
MAX_PIDS = 3
MAX_TEMPS = 8
MAX_DISKS = 16
MAX_FANS = 6
MAX_CORES = 128
DETAIL_MAX = 60
LABEL_MAX = 40
BUSY_PCT = 1.0  # groups at or above this CPU% sort before the memory-ranked rest

CLK_TCK = os.sysconf("SC_CLK_TCK")
PAGE_KB = max(1, os.sysconf("SC_PAGE_SIZE") // 1024)

SNAP_NAME = "procs.json"
STATIC_NAME = "static.json"
SNAP_MAX_BYTES = 1 << 20
STATIC_MAX_BYTES = 4096
SNAP_STALE_S = 30.0  # an older snapshot measures history, not "now"
WARM_SAMPLE_S = 0.5  # in-process second sample when no fresh snapshot exists

FAN_MODES = {"auto", "low", "med", "high", "custom"}

# --- friendly names -----------------------------------------------------------
#
# One place for every alias. Order of resolution (classify):
#   1. our own plugin helpers (argv containing /plugins/<id>/)
#   2. agents by binary or script name; interpreters by the script they run
#   3. known binaries
#   4. the process's own comm

PLUGIN_LABELS = {
    "lukedaduke.fan": "Fan monitor",
    "lukedaduke.power": "Power monitor",
    "lukedaduke.nexus": "Hardware radar",
    "lukedaduke.standby": "Standby clock",
    "io.github.duketopceo.bumblebee": "Bumblebee scanner",
    "io.github.duketopceo.numbat": "Numbat watcher",
    "io.github.duketopceo.pplx": "Perplexity",
    "io.github.duketopceo.neo": "Neo sidecar",
}

AGENTS = {
    "claude": "Claude Code",
    "claude-code": "Claude Code",
    "devin": "Devin",
    "codex": "Codex",
    "kurultai": "Kurultai",
}

INTERPRETERS = {
    "python": "python", "python3": "python",
    "node": "node", "node-mainthread": "node", "nodejs": "node",
    "bun": "bun", "deno": "deno", "ruby": "ruby", "perl": "perl",
    "sh": "shell", "bash": "shell", "zsh": "shell", "dash": "shell", "fish": "shell",
    "npm": "npm", "npx": "npm",
}

HEADLESS_CHROME = ("Headless Chrome (agent browser)", "browser")

KNOWN: dict[str, tuple[str, str]] = {
    "quickshell": ("Omarchy shell", "shell"),
    "qs": ("Omarchy shell", "shell"),
    "hyprland": ("Hyprland (desktop)", "shell"),
    "xwayland": ("Xwayland", "shell"),
    "chromium": ("Chromium", "browser"),
    "chrome": ("Chromium", "browser"),
    "chrome_crashpad": ("Chromium", "browser"),
    "chrome_crashpad_handler": ("Chromium", "browser"),
    "chrome-headless": HEADLESS_CHROME,
    "chrome-headless-shell": HEADLESS_CHROME,
    "headless_shell": HEADLESS_CHROME,
    "brave": ("Brave", "browser"),
    "firefox": ("Firefox", "browser"),
    "code": ("VS Code", "dev"),
    "cursor": ("Cursor", "dev"),
    "zed": ("Zed", "dev"),
    "zeditor": ("Zed", "dev"),
    "ollama": ("Ollama (local AI)", "app"),
    "llama-server": ("llama.cpp server", "app"),
    "pipewire": ("Audio (PipeWire)", "system"),
    "pipewire-pulse": ("Audio (PipeWire)", "system"),
    "wireplumber": ("Audio (PipeWire)", "system"),
    "voxtype": ("Voxtype dictation", "app"),
    "docker": ("Docker", "system"),
    "dockerd": ("Docker", "system"),
    "docker-proxy": ("Docker", "system"),
    "containerd": ("Docker", "system"),
    "containerd-shim": ("Docker", "system"),
    "containerd-shim-runc-v2": ("Docker", "system"),
    "tailscaled": ("Tailscale", "system"),
    "1password": ("1Password", "app"),
    "dbus-broker": ("D-Bus", "system"),
    "dbus-broker-launch": ("D-Bus", "system"),
    "dbus-daemon": ("D-Bus", "system"),
    "foot": ("Terminal", "dev"),
    "alacritty": ("Terminal", "dev"),
    "kitty": ("Terminal", "dev"),
    "ghostty": ("Terminal", "dev"),
}

KNOWN_PREFIXES: tuple[tuple[str, tuple[str, str]], ...] = (
    ("systemd", ("systemd", "system")),
    ("kworker/", ("Kernel", "system")),
    ("ksoftirqd/", ("Kernel", "system")),
    ("irq/", ("Kernel", "system")),
    ("chrome-headless", HEADLESS_CHROME),
)

# Path components that identify an agent install even when an interpreter runs it.
AGENT_PATH_PARTS = {"claude-code": "Claude Code", "codex": "Codex", "devin": "Devin", "kurultai": "Kurultai"}

_PLUGIN_RE = re.compile(r"/plugins/([A-Za-z0-9][A-Za-z0-9_.-]{0,80})/")
_SCRIPT_EXT_RE = re.compile(r"\.(py|js|mjs|cjs|ts|mts|rb|pl|sh)$")
_PYTHON_RE = re.compile(r"^python[0-9.]*$")
_NPM_SUBCOMMANDS = {"exec", "run", "run-script", "x", "start", "dlx"}


def _base(path: str) -> str:
    return path.rstrip("/").rsplit("/", 1)[-1]


def _split_argv(argv: list[str]) -> list[str]:
    """Chromium-style processes rewrite argv into one space-joined string."""
    if len(argv) == 1 and " " in argv[0]:
        return argv[0].split()
    return list(argv)


def _agent(name: str) -> str | None:
    stem = _SCRIPT_EXT_RE.sub("", name.lower())
    return AGENTS.get(stem) or AGENTS.get(stem.split("-", 1)[0])


def _interpreter(name: str) -> str | None:
    n = name.lower()
    if _PYTHON_RE.match(n):
        return "python"
    return INTERPRETERS.get(n)


def _script_arg(args: list[str], lang: str) -> str | None:
    """The script, module or package an interpreter is running, if any."""
    skip_subcommand = lang == "npm"
    i = 0
    while i < len(args):
        a = args[i]
        if lang == "python" and a == "-m" and i + 1 < len(args):
            return args[i + 1]
        if a == "-c" or a == "-e":
            return "inline script"
        if a == "-":
            return "stdin script"
        if a.startswith("-"):
            i += 1
            continue
        if skip_subcommand and a in _NPM_SUBCOMMANDS:
            skip_subcommand = False
            i += 1
            continue
        return a
    return None


def _known(name: str, argv: list[str]) -> tuple[str, str] | None:
    n = name.lower()
    hit = KNOWN.get(n)
    if hit is None:
        for prefix, value in KNOWN_PREFIXES:
            if n.startswith(prefix):
                hit = value
                break
    if hit and hit[1] == "browser" and any(a.startswith("--headless") for a in argv):
        return HEADLESS_CHROME
    return hit


def classify(comm: str, argv: list[str]) -> dict[str, str]:
    """Friendly {label, kind} for one process."""
    comm = clean_text(comm, 32) or "?"
    argv = _split_argv([a for a in argv if a])
    if not argv:
        # Kernel threads (and zombies) have an empty command line.
        return {"label": "Kernel", "kind": "system"}

    for a in argv:
        m = _PLUGIN_RE.search(a)
        if m:
            pid = m.group(1)
            return {"label": PLUGIN_LABELS.get(pid, f"{clean_text(pid, LABEL_MAX - 7)} plugin"), "kind": "plugin"}

    base0 = _base(argv[0])
    agent = _agent(base0) or _agent(comm)
    if agent:
        return {"label": agent, "kind": "agent"}

    lang = _interpreter(base0) or _interpreter(comm)
    if lang:
        script = _script_arg(argv[1:], lang)
        if script:
            for part in script.split("/"):
                if part in AGENT_PATH_PARTS:
                    return {"label": AGENT_PATH_PARTS[part], "kind": "agent"}
            name = _base(script)
            agent = _agent(name)
            if agent:
                return {"label": agent, "kind": "agent"}
            name = clean_text(_redact_token(name), LABEL_MAX - 10) or "script"
            return {"label": f"{name} ({lang})", "kind": "dev"}
        return {"label": clean_text(base0, LABEL_MAX) or comm, "kind": "dev"}

    hit = _known(base0, argv) or _known(comm, argv)
    if hit:
        return {"label": hit[0], "kind": hit[1]}
    return {"label": comm, "kind": "app"}


# --- redaction -----------------------------------------------------------------

REDACTED = "…"
_SECRET_NAME = re.compile(r"(key|token|secret|passw|auth|credential)", re.I)
_ENV_ARG = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PREFIXED = re.compile(r"(sk-|sk_|ghp_|gho_|ghs_|ghu_|ghr_|github_pat_|xox[a-z]-|glpat-|AKIA)[A-Za-z0-9_\-]{4,}")
_NAMED_VALUE = re.compile(r"(?i)([A-Za-z0-9_.-]*(?:key|token|secret|passw|auth|credential)[A-Za-z0-9_.-]*)=([^&\s]+)")
_BLOB = re.compile(r"[A-Za-z0-9+_-]{24,}={0,2}")


def _redact_token(value: str) -> str:
    s = _PREFIXED.sub(REDACTED, value)
    s = _NAMED_VALUE.sub(lambda m: f"{m.group(1)}={REDACTED}", s)
    # Long base64/hex-looking runs carry digits; plain hyphenated words do not.
    return _BLOB.sub(lambda m: REDACTED if re.search(r"\d", m.group(0)) else m.group(0), s)


def redact_args(argv: list[str]) -> list[str]:
    """argv with secret values replaced; flag names and ordinary args survive."""
    out: list[str] = []
    drop_next = False
    for a in _split_argv(list(argv)):
        if drop_next and not a.startswith("-"):
            out.append(REDACTED)
            drop_next = False
            continue
        drop_next = False
        if a.startswith("-"):
            name, eq, _value = a.partition("=")
            if _SECRET_NAME.search(name):
                if eq:
                    out.append(f"{name}={REDACTED}")
                else:
                    out.append(name)
                    drop_next = True
                continue
        elif _ENV_ARG.match(a):
            out.append(a.split("=", 1)[0] + "=" + REDACTED)
            continue
        out.append(_redact_token(a))
    return out


_HOME = os.path.expanduser("~").rstrip("/")


def _home_short(value: str) -> str:
    if _HOME and _HOME != "~" and (value == _HOME or value.startswith(_HOME + "/")):
        return "~" + value[len(_HOME):]
    return value


def summarize_argv(argv: list[str], limit: int = DETAIL_MAX) -> str:
    """One redacted, plain line: binary basename plus its arguments."""
    args = redact_args(argv)
    if not args:
        return ""
    parts = [_base(args[0])] + [_home_short(a) for a in args[1:]]
    text = clean_text(" ".join(p for p in parts if p), 4096)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + REDACTED
    return text


# --- /proc scan and the jiffies cache ---------------------------------------------

def _read_bytes(path: Path, limit: int = 65536) -> bytes | None:
    try:
        with open(path, "rb") as fh:
            return fh.read(limit)
    except OSError:
        return None


def _parse_stat(raw: str) -> tuple[str, int, int, int] | None:
    """(comm, ppid, utime+stime, starttime) from /proc/<pid>/stat."""
    try:
        close = raw.rindex(")")
        comm = raw[raw.index("(") + 1:close]
        fields = raw[close + 2:].split()
        return comm, int(fields[1]), int(fields[11]) + int(fields[12]), int(fields[19])
    except (ValueError, IndexError):
        return None


def scan_processes(proc_root: Path, skip_pid: int | None = None) -> dict[int, dict[str, Any]]:
    """pid -> {comm, start, jiffies, rss_kb, argv} read straight from /proc."""
    rows: dict[int, dict[str, Any]] = {}
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return rows
    for name in entries:
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == skip_pid:
            continue
        base = proc_root / name
        raw = _read_bytes(base / "stat", 4096)
        if raw is None:
            continue
        parsed = _parse_stat(raw.decode(errors="replace"))
        if parsed is None:
            continue
        comm, _ppid, jiffies, start = parsed
        statm = _read_bytes(base / "statm", 512)
        try:
            rss_kb = int(statm.split()[1]) * PAGE_KB if statm else 0
        except (ValueError, IndexError):
            rss_kb = 0
        cmd = _read_bytes(base / "cmdline", 8192) or b""
        argv = [a.decode(errors="replace") for a in cmd.split(b"\0") if a]
        rows[pid] = {"pid": pid, "comm": comm, "start": start, "jiffies": jiffies, "rss_kb": rss_kb, "argv": argv}
    return rows


def _read_cpu_times(proc_root: Path) -> dict[str, list[int]]:
    """{cpu|cpuN: [total, idle]} from /proc/stat."""
    out: dict[str, list[int]] = {}
    raw = _read_bytes(proc_root / "stat", 1 << 16)
    if raw is None:
        return out
    for line in raw.decode(errors="replace").splitlines():
        parts = line.split()
        if not parts or not parts[0].startswith("cpu"):
            continue
        try:
            values = [int(p) for p in parts[1:]]
            # idle + iowait count as idle.
            out[parts[0]] = [sum(values), values[3] + (values[4] if len(values) > 4 else 0)]
        except (ValueError, IndexError):
            continue
    return out


def _state_fd(state_dir: Path | None) -> int | None:
    if state_dir is None:
        return None
    try:
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
        return fsio.open_dir(state_dir)
    except OSError:
        return None


def _load_json(dirfd: int | None, name: str, limit: int) -> dict | None:
    if dirfd is None:
        return None
    raw = fsio.read_capped(dirfd, name, limit)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _save_json(dirfd: int | None, name: str, payload: dict) -> None:
    if dirfd is None:
        return
    try:
        fsio.publish(dirfd, name, json.dumps(payload, separators=(",", ":")))
    except (OSError, ValueError):
        pass


def _snapshot(at: float, procs: dict[int, dict[str, Any]], cpu: dict[str, list[int]]) -> dict:
    return {"v": 1, "at": at, "cpu": cpu,
            "procs": {str(pid): [r["start"], r["jiffies"]] for pid, r in procs.items()}}


def _proc_rates(prev: dict, procs: dict[int, dict[str, Any]], span: float) -> dict[int, float]:
    rates: dict[int, float] = {}
    prev_procs = prev.get("procs") if isinstance(prev.get("procs"), dict) else {}
    for pid, row in procs.items():
        old = prev_procs.get(str(pid))
        # A reused pid has a different start time: no delta against the old process.
        if not isinstance(old, list) or len(old) != 2 or old[0] != row["start"]:
            continue
        delta = row["jiffies"] - old[1]
        if delta > 0:
            rates[pid] = delta / CLK_TCK / span * 100.0
    return rates


def _cpu_load(prev_cpu: dict, cur_cpu: dict[str, list[int]]) -> tuple[int, list[dict[str, int]]]:
    def pct(key: str) -> int | None:
        a, b = prev_cpu.get(key), cur_cpu.get(key)
        if not (isinstance(a, list) and len(a) == 2 and b):
            return None
        dt, di = b[0] - a[0], b[1] - a[1]
        if dt <= 0:
            return None
        return max(0, min(100, round(100 * (1 - di / dt))))

    load = pct("cpu") or 0
    cores = []
    for key in sorted((k for k in cur_cpu if k[3:].isdigit()), key=lambda k: int(k[3:])):
        value = pct(key)
        cores.append({"core": int(key[3:]), "percent": value if value is not None else 0})
    return load, cores[:MAX_CORES]


def _sample(proc_root: Path, state_dir: Path | None, now: float | None, warm_sample_s: float):
    """Current scan plus the CPU deltas against the cached (or a warm) snapshot."""
    dirfd = _state_fd(state_dir)
    try:
        skip = os.getpid() if proc_root == Path("/proc") else None
        at = time.monotonic() if now is None else now
        procs = scan_processes(proc_root, skip)
        cpu = _read_cpu_times(proc_root)
        prev = _load_json(dirfd, SNAP_NAME, SNAP_MAX_BYTES)
        prev_at = prev.get("at") if prev else None
        fresh = isinstance(prev_at, (int, float)) and 0 < at - prev_at <= SNAP_STALE_S
        if not fresh and warm_sample_s > 0:
            prev = _snapshot(at, procs, cpu)
            time.sleep(warm_sample_s)
            at = time.monotonic()
            procs = scan_processes(proc_root, skip)
            cpu = _read_cpu_times(proc_root)
            fresh = True
        _save_json(dirfd, SNAP_NAME, _snapshot(at, procs, cpu))
    finally:
        if dirfd is not None:
            os.close(dirfd)
    if fresh and prev:
        span = at - prev["at"]
        rates = _proc_rates(prev, procs, span)
        load, cores = _cpu_load(prev.get("cpu") or {}, cpu)
    else:
        rates = {}
        load, cores = _cpu_load({}, cpu)
    return procs, rates, load, cores, bool(fresh and prev)


# Killing these ends the desktop session or is impossible; the panel never
# offers a kill for them.
PROTECTED_KINDS = frozenset({"shell"})
PROTECTED_LABELS = frozenset({"systemd", "Kernel"})


def group_processes(rows: list[dict[str, Any]], limit: int = MAX_GROUPS) -> list[dict[str, Any]]:
    """Merge rows sharing a label: summed CPU/RSS, count, top pids, kill target."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(row["label"], []).append(row)
    groups = []
    for label, members in buckets.items():
        members.sort(key=lambda r: (r["cpu"], r["rss_kb"]), reverse=True)
        top = members[0]
        count = len(members)
        cpu = sum(r["cpu"] for r in members)
        rss_kb = sum(r["rss_kb"] for r in members)
        detail = top.get("detail") or ""
        if count > 1:
            detail = f"{detail} · {count} processes" if detail else f"{count} processes"
        protected = top["kind"] in PROTECTED_KINDS or label in PROTECTED_LABELS
        killable = count == 1 and not protected
        groups.append({
            "label": label,
            "kind": top["kind"],
            "detail": detail,
            "cpu": round(cpu, 1),
            "mem_mb": round(rss_kb / 1024, 1),
            "count": count,
            "pids": [r["pid"] for r in members[:MAX_PIDS]],
            "kill_pid": top["pid"] if killable else 0,
            "kill_start": top.get("start", 0) if killable else 0,
            "protected": protected,
        })
    groups.sort(key=lambda g: (g["cpu"] < BUSY_PCT, -g["cpu"] if g["cpu"] >= BUSY_PCT else 0, -g["mem_mb"]))
    return groups[:limit]


def _rows(procs: dict[int, dict[str, Any]], rates: dict[int, float]) -> list[dict[str, Any]]:
    rows = []
    for pid, p in procs.items():
        named = classify(p["comm"], p["argv"])
        rows.append({
            "pid": pid,
            "start": p["start"],
            "label": named["label"],
            "kind": named["kind"],
            "cpu": rates.get(pid, 0.0),
            "rss_kb": p["rss_kb"],
            "detail": summarize_argv(p["argv"]) if p["argv"] else clean_text(p["comm"], DETAIL_MAX),
        })
    return rows


def process_groups(proc_root: "str | os.PathLike[str]" = "/proc", state_dir: "Path | None" = None,
                   now: float | None = None, warm_sample_s: float = 0.0):
    """(groups, meta) for the running processes; meta["warm"] is False on a first scan."""
    procs, rates, _load, _cores, warm = _sample(Path(proc_root), state_dir, now, warm_sample_s)
    return group_processes(_rows(procs, rates)), {"warm": warm}


# --- memory ----------------------------------------------------------------------

def read_meminfo(proc_root: Path) -> dict[str, Any]:
    info: dict[str, int] = {}
    raw = _read_bytes(proc_root / "meminfo", 1 << 16)
    for line in (raw or b"").decode(errors="replace").splitlines():
        key, _, value = line.partition(":")
        try:
            info[key.strip()] = int(value.split()[0])
        except (ValueError, IndexError):
            continue
    gb = 1024 * 1024
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - avail)
    swap_total = info.get("SwapTotal", 0)
    swap_used = max(0, swap_total - info.get("SwapFree", 0))
    return {
        "pct": round(used * 100 / total) if total else 0,
        "used_gb": round(used / gb, 1),
        "avail_gb": round(avail / gb, 1),
        "total_gb": round(total / gb, 1),
        "swap_used_gb": round(swap_used / gb, 1),
        "swap_total_gb": round(swap_total / gb, 1),
        "swap_pct": round(swap_used * 100 / swap_total) if swap_total else 0,
    }


# --- hwmon: temperatures, fans, power ----------------------------------------------

# (hwmon name, sensor label) in priority order; None = first temp sensor.
CPU_TEMP_SENSORS = (
    ("coretemp", "Package id 0"),
    ("k10temp", "Tctl"),
    ("k10temp", "Tdie"),
    ("zenpower", "Tdie"),
    ("zenpower", "Tctl"),
    ("dell_smm", "CPU"),
    ("thinkpad", "CPU"),
    ("cpu_thermal", None),
    ("coretemp", None),
)
BATTERY_HWMON = re.compile(r"(battery|^BAT\d)", re.I)


def _suspended(dev: sysfs.HwmonDevice) -> bool:
    """A runtime-suspended device (e.g. a sleeping dGPU) is never read: it would wake."""
    return sysfs.read_attr(dev.path / "device" / "power" / "runtime_status") == "suspended"


def _awake_devices(root) -> list[sysfs.HwmonDevice]:
    return [d for d in sysfs.hwmon_devices(root) if not _suspended(d)]


def _celsius(sensor: sysfs.Sensor) -> int | None:
    value = sensor.value
    if value is None:
        return None
    c = round(value / 1000)
    return c if -20 <= c <= 130 else None


def temperatures(devices: list[sysfs.HwmonDevice]) -> dict[str, Any]:
    """CPU temperature when a CPU sensor exists, plus every labelled board sensor."""
    cpu = None
    for name, label in CPU_TEMP_SENSORS:
        for dev in devices:
            if dev.name != name:
                continue
            sensors = dev.sensors("temp")
            pick = next((s for s in sensors if label is None or s.label == label), None)
            if pick is not None:
                cpu = _celsius(pick)
            if cpu is not None:
                break
        if cpu is not None:
            break
    temps = []
    for dev in devices:
        for s in dev.sensors("temp"):
            c = _celsius(s)
            if c is None:
                continue
            label = s.label if s.label != s.key else f"{dev.name} {s.key}"
            temps.append({"label": clean_text(label, 40), "c": c, "device": clean_text(dev.name, 32)})
    temps.sort(key=lambda t: -t["c"])
    if cpu is not None:
        headline = {"c": cpu, "source": "cpu", "label": "CPU"}
    else:
        board = [t for t in temps if not BATTERY_HWMON.search(t["device"])] or temps
        headline = ({"c": board[0]["c"], "source": "board", "label": board[0]["label"]}
                    if board else {"c": None, "source": "none", "label": ""})
    return {"cpu": cpu, "headline": headline, "temps": temps[:MAX_TEMPS]}


def nvme_temp(devices: list[sysfs.HwmonDevice]) -> int | None:
    for dev in devices:
        if dev.name == "macsmc_hwmon":
            s = dev.sensor("NAND Flash Temperature", "temp")
            if s is not None and _celsius(s) is not None:
                return _celsius(s)
    found = [c for dev in devices if dev.name in ("nvme", "drivetemp")
             for s in dev.sensors("temp")[:1] if (c := _celsius(s)) is not None]
    return max(found) if found else None


def fans(devices: list[sysfs.HwmonDevice]) -> list[dict[str, Any]]:
    out = []
    for dev in devices:
        for s in dev.sensors("fan"):
            rpm = s.value
            if rpm is None or rpm < 0:
                continue
            label = s.label if s.label != s.key else f"{dev.name} {s.key}"
            out.append({"label": clean_text(label, 32), "rpm": rpm})
    return out[:MAX_FANS]


def soc_power_w(devices: list[sysfs.HwmonDevice]) -> float | None:
    """macsmc 'Heatpipe Power' rail: a SoC-wide proxy, not GPU-isolated."""
    for dev in devices:
        if dev.name == "macsmc_hwmon":
            s = dev.sensor("Heatpipe Power", "power")
            if s is not None and s.value is not None:
                return round(s.value / 1e6, 1)
    return None


def fan_control_available(devices: list[sysfs.HwmonDevice]) -> bool:
    """True only when the daemon's interface exposes a target it can drive."""
    for dev in devices:
        try:
            names = os.listdir(dev.path)
        except OSError:
            continue
        if dev.name == "macsmc_hwmon" and any(re.match(r"fan\d+_target$", n) for n in names):
            return True
        if dev.name == "dell_smm" and any(re.match(r"pwm\d+$", n) for n in names):
            return True
    return False


# --- GPU -----------------------------------------------------------------------------

def _runtime_status(card: sysfs.DrmCard) -> str | None:
    return sysfs.read_attr(card.path / "device" / "power" / "runtime_status")


def _nvidia_smi() -> tuple[int, int | None, str] | None:
    smi = proc.tool("nvidia-smi")
    if not smi:
        return None
    res = proc.run([smi, "--query-gpu=utilization.gpu,temperature.gpu,name",
                    "--format=csv,noheader,nounits"], timeout=1.5, max_bytes=8192)
    if not res.ok or not res.out.strip():
        return None
    try:
        load, temp, name = [p.strip() for p in res.out.strip().splitlines()[0].split(",", 2)]
        return (max(0, min(100, round(float(load)))),
                round(float(temp)) if temp else None,
                clean_text(name, 48))
    except ValueError:
        return None


def gpu_info(root, devices: list[sysfs.HwmonDevice], cpu_name: str) -> dict[str, Any]:
    gpu: dict[str, Any] = {"name": "", "load": None, "temp": None, "reason": "No GPU found",
                           "power_w": soc_power_w(devices), "clients": []}
    cards = sysfs.drm_cards(root)
    drivers = {c.driver for c in cards}
    for card in cards:
        if card.driver == "nvidia" or card.vendor == "0x10de":
            gpu["name"] = "NVIDIA GPU"
            if _runtime_status(card) != "active":
                gpu["reason"] = "NVIDIA GPU is asleep; not woken to read it"
                continue
            smi = _nvidia_smi()
            if smi is None:
                gpu["reason"] = "nvidia-smi not available"
                continue
            gpu["load"], gpu["temp"], name = smi
            gpu["name"] = name or "NVIDIA GPU"
            gpu["reason"] = ""
            return gpu
    for card in cards:
        if _runtime_status(card) == "suspended":
            continue
        busy = sysfs.read_int(card.path / "device" / "gpu_busy_percent")
        if busy is not None:
            gpu.update(name="AMD GPU", load=max(0, min(100, busy)), reason="")
            for dev in devices:
                if dev.name == "amdgpu":
                    s = dev.sensor("edge", "temp")
                    gpu["temp"] = _celsius(s) if s is not None else None
                    break
            return gpu
    if drivers & {"asahi", "apple-agx"}:
        gpu["name"] = f"{cpu_name} GPU" if cpu_name.startswith("Apple") else "Apple GPU"
        gpu["reason"] = "Load not available: the Asahi GPU driver exposes no utilization counter"
    elif "amdgpu" in drivers:
        gpu["name"] = gpu["name"] or "AMD GPU"
        gpu["reason"] = "Load not available: amdgpu exposes no gpu_busy_percent here"
    elif drivers & {"i915", "xe"}:
        gpu["name"] = gpu["name"] or "Intel GPU"
        if gpu["reason"] == "No GPU found":
            gpu["reason"] = "Load not available: no utilization counter for this driver"
    elif cards and gpu["reason"] == "No GPU found":
        gpu["name"] = "GPU"
        gpu["reason"] = "Load not available for this driver"
    for dev in devices:
        if dev.name == "amdgpu" and gpu["temp"] is None:
            s = dev.sensor("edge", "temp")
            gpu["temp"] = _celsius(s) if s is not None else None
    return gpu


def gpu_clients(proc_root: Path, procs: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Friendly names of processes holding /dev/dri handles (what is on the GPU)."""
    counts: dict[str, int] = {}
    for pid, p in procs.items():
        fd_dir = proc_root / str(pid) / "fd"
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd_dir / fd)
            except OSError:
                continue
            if target.startswith("/dev/dri/"):
                label = classify(p["comm"], p["argv"])["label"]
                counts[label] = counts.get(label, 0) + 1
                break
    return [{"label": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))][:8]


# --- disks ----------------------------------------------------------------------------

ALLOWED_FS = {
    "ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "zfs", "jfs", "reiserfs",
    "nilfs2", "bcachefs", "vfat", "exfat", "ntfs", "ntfs3", "hfsplus", "ufs",
}


def _unescape_mount(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)


def disk_usage(proc_root: Path) -> list[dict[str, Any]]:
    """Real filesystems from /proc/mounts, one row per device (shortest mount)."""
    raw = _read_bytes(proc_root / "mounts", 1 << 20)
    by_device: dict[str, dict[str, Any]] = {}
    for line in (raw or b"").decode(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] not in ALLOWED_FS:
            continue
        device, mount = parts[0], _unescape_mount(parts[1])
        if device in by_device and len(mount) >= len(by_device[device]["mount"]):
            continue
        try:
            st = os.statvfs(mount)
        except OSError:
            continue
        total = st.f_blocks * st.f_frsize
        if total <= 0:
            continue
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        avail = st.f_bavail * st.f_frsize
        gb = 1024 ** 3
        by_device[device] = {
            "mount": clean_text(mount, 64),
            "used_gb": round(used / gb, 1),
            "total_gb": round(total / gb, 1),
            "percent": round(used * 100 / (used + avail)) if used + avail else 0,
        }
    rows = sorted(by_device.values(), key=lambda d: (d["mount"] != "/", d["mount"]))
    return rows[:MAX_DISKS]


# --- static facts (cached per boot) ----------------------------------------------------

def cpu_name(root) -> str:
    model = sysfs.read_attr(Path(root) / "sys/firmware/devicetree/base/model")
    if model:
        model = model.replace("\x00", "").strip()
        m = re.search(r"Apple.*?\((?:[^,]+,\s*)?(M\d+(?:\s+(?:Pro|Max|Ultra))?)(?:,\s*\d+)?\)", model, re.I)
        if m:
            return f"Apple {m.group(1).strip()}"
        if model.startswith("Apple "):
            return model.split("(")[0].strip()
        return clean_text(model, 32)
    raw = _read_bytes(Path(root) / "proc/cpuinfo", 1 << 18)
    for line in (raw or b"").decode(errors="replace").splitlines():
        key, _, value = line.partition(":")
        key = key.strip()
        if key == "model name":
            name = re.sub(r"\((R|TM)\)", "", value, flags=re.I)
            name = re.sub(r"\s*CPU\s*@\s*[\d.]+\s*GHz", "", name, flags=re.I)
            name = re.sub(r"\d+-Core Processor.*", "", name, flags=re.I)
            return clean_text(" ".join(name.split()), 48) or "CPU"
        if key in ("Hardware", "Model") and value.strip():
            return clean_text(value.strip(), 48)
    return "CPU"


def ram_type(name: str) -> str:
    """Only what is knowable without root: Apple unified memory by chip family."""
    if re.fullmatch(r"Apple M1", name):
        return "LPDDR4X unified"
    if re.fullmatch(r"Apple M1 (Pro|Max|Ultra)", name) or re.match(r"Apple M[2-9]", name):
        return "LPDDR5 unified"
    if name.startswith("Apple"):
        return "Unified memory"
    return ""


def static_facts(root, state_dir: Path | None) -> dict[str, str]:
    dirfd = _state_fd(state_dir)
    try:
        cached = _load_json(dirfd, STATIC_NAME, STATIC_MAX_BYTES)
        if cached and cached.get("v") == 1 and isinstance(cached.get("cpu_name"), str):
            return {"cpu_name": clean_text(cached["cpu_name"], 48),
                    "ram_type": clean_text(cached.get("ram_type", ""), 32)}
        name = cpu_name(root)
        facts = {"cpu_name": name, "ram_type": ram_type(name)}
        _save_json(dirfd, STATIC_NAME, {"v": 1, **facts})
        return facts
    finally:
        if dirfd is not None:
            os.close(dirfd)


# --- fan mode and curve --------------------------------------------------------------------

def _runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.join(os.path.expanduser("~"), ".local", "run")
    return Path(base) / "omarchy-fan"


def read_fan_mode(path: Path | None = None) -> str:
    """The requested mode (written by omarchy-fan-set); anything odd reads as auto."""
    mode_path = Path(path) if path is not None else _runtime_dir() / "current_fan_mode"
    raw = fsio.read_capped(str(mode_path.parent), mode_path.name, 64)
    if raw is None:
        return "auto"
    mode = raw.decode(errors="replace").strip().lower()
    return mode if mode in FAN_MODES or re.fullmatch(r"custom-[a-z]{1,24}", mode) else "auto"


def read_fan_curve() -> list[list[int]]:
    raw = fsio.read_capped(str(Path.home() / ".config" / "omarchy"), "fan_curve.json", 256 * 1024)
    if raw is None:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list) and all(isinstance(p, list) and len(p) == 2 for p in data):
            return [[int(p[0]), int(p[1])] for p in data][:64]
    except (ValueError, TypeError):
        pass
    return []


# --- entry -------------------------------------------------------------------------------------

def build(mode: str = "full", root="/", proc_root=None, state_dir: Path | None = None,
          warm_sample_s: float = 0.0, now: float | None = None):
    """(data, capabilities) for the envelope. state_dir=None disables caching."""
    root = Path(root)
    proc_root = Path(proc_root) if proc_root is not None else root / "proc"
    devices = _awake_devices(root)
    temps = temperatures(devices)
    mode_file = (Path(state_dir) if state_dir is not None else _runtime_dir()) / "current_fan_mode"
    common = {
        "mem": read_meminfo(proc_root),
        "temp": temps["headline"],
        "fans": fans(devices),
        "fan_mode": read_fan_mode(mode_file),
    }
    caps = {"fan_control": fan_control_available(devices), "cpu_temp": temps["cpu"] is not None}
    if mode == "bar":
        return {"mode": "bar", **common}, caps

    facts = static_facts(root, Path(state_dir) if state_dir is not None else None)
    procs, rates, load, cores, warm = _sample(proc_root, Path(state_dir) if state_dir is not None else None,
                                              now, warm_sample_s)
    gpu = gpu_info(root, devices, facts["cpu_name"])
    gpu["clients"] = gpu_clients(proc_root, procs)
    common["mem"]["type"] = facts["ram_type"]
    data = {
        "mode": "full",
        **common,
        "cpu": {"name": facts["cpu_name"], "load": load, "cores": cores, "temp": temps["cpu"]},
        "temps": temps["temps"],
        "nvme_temp": nvme_temp(devices),
        "gpu": gpu,
        "disks": disk_usage(proc_root),
        "groups": group_processes(_rows(procs, rates)),
        "warm": warm,
        "fan_curve": read_fan_curve(),
    }
    caps.update(gpu_load=gpu["load"] is not None, process_scan=True)
    return data, caps


def main(argv: list[str] | None = None) -> int:
    # Hard wall-clock backstop, shorter than the panel's 9 s kill deadline.
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)
    args = sys.argv[1:] if argv is None else argv
    mode = "bar" if "--bar" in args else "full"
    return envelope.main(lambda: build(mode, state_dir=_runtime_dir(), warm_sample_s=WARM_SAMPLE_S),
                         schema=SCHEMA)


if __name__ == "__main__":
    raise SystemExit(main())
