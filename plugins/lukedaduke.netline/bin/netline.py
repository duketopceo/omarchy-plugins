#!/usr/bin/env python3
"""netline — local connection lineage tracker.

Architecture: the kernel already accounts every connection (conntrack), so we
poll that table instead of parsing packets. That is O(connections) rather than
O(packets), which keeps CPU near zero on a busy machine and adds no latency
whatsoever — we are never in the data path.

Names come from two cheap sources: DNS answers seen on port 53, and TLS SNI
read from ClientHellos only (a kernel BPF filter keeps everything else out of
userspace).

  netline daemon        poll + store (needs root for conntrack + raw sock)
  netline top [N]       busiest destinations, last 15 min
  netline chase X       everything that touched IP or hostname X
  netline flags         outlier flows
  netline pid N         what process N talked to
  netline live          tail newest flows
  netline prune [days]  retention
"""
import argparse
import json
import os
import re
import socket
import sqlite3
import struct
import subprocess
import sys
import threading
import time

POLL_S = 2

# The kernel truncates comm to 15 chars and some daemons name themselves with a
# trailing dash or a thread suffix. Normalise once, at the boundary, so no raw
# kernel string ever reaches the store or a UI.
COMM_ALIASES = {
    "docker-proxy": "docker",
    "cube-lifecycle-": "cube lifecycle",
    "browseros-claw-": "browseros",
    "node-MainThread": "node",
    "sshd-session": "ssh",
    "avahi-daemon": "avahi",
    "systemd-resolve": "resolver",
    "packagekitd": "packagekit",
    "gvfsd-network": "gvfs",
    "tracker-miner-f": "tracker",
    "chrome_crashpad": "chrome",
    "grok-bot": "grok",
    "Hermes": "hermes",
    "MainThread": "node",
}
IPV6_JUNK = "::"


def clean_proc(comm):
    """Readable process label, or None when the kernel gave nothing useful."""
    if not comm:
        return None
    c = comm.strip().rstrip("-")
    if not c or c in (IPV6_JUNK, "?") or set(c) == {"?"}:
        return None
    # thread-style suffixes: "node-MainThread" -> "node"
    if "-" in c:
        head, _, tail = c.partition("-")
        if tail[:1].isupper() or tail.replace("_", "").isalnum():
            c = head
    return COMM_ALIASES.get(comm.strip(), COMM_ALIASES.get(c, c))


def clean_host(host):
    """Hostname without the reverse-DNS suffix noise the kernel emits."""
    if not host:
        return None
    h = host.strip().rstrip(".")
    if h.endswith(".in-addr.arpa") or h.endswith(".ip6.arpa"):
        # netline sometimes names a reverse lookup; the IP is the honest label
        return None
    if h == "::" or h.startswith("0000:") or set(h.replace(":", "")) == {"0"}:
        return "unidentified"
    return h
BUCKET_S = 10
FLAG_NEW_DST_BYTES = 1_000_000
FLAG_RATIO = 10           # how many times typical counts as an outlier
FLAG_MIN_BYTES = 250_000  # ignore small bursts entirely
FLAG_MIN_SAMPLES = 5      # need history before "typical" means anything


def _db_path():
    """Single store for both the root daemon and the unprivileged CLI.

    The service runs as root (conntrack is root-only), but the CLI runs as the
    human user, so resolve to an explicit path rather than $HOME. Also cleans
    up the stray DB an older root-run version left in /root.
    """
    if os.environ.get("NETLINE_DB"):
        return os.environ["NETLINE_DB"]
    # Derive from the invoking home so the plugin installs on another machine.
    # The service runs as root, so fall back to the operator's home when $HOME
    # is /root.
    home = os.path.expanduser("~")
    if os.path.basename(home) == "root":
        home = os.environ.get("NETLINE_HOME") or home
    return os.path.join(home, ".local", "share", "netline", "netline.db")


DB = _db_path()


def db_open():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS flows(
          id INTEGER PRIMARY KEY,
          bucket INTEGER NOT NULL,
          ts_first INTEGER, ts_last INTEGER,
          proto TEXT, pid INTEGER, comm TEXT,
          src TEXT, sport INTEGER, dst TEXT, dport INTEGER,
          bytes_out INTEGER DEFAULT 0, bytes_in INTEGER DEFAULT 0,
          state TEXT, dns TEXT, sni TEXT, host TEXT,
          flagged INTEGER DEFAULT 0, flag_reason TEXT,
          UNIQUE(bucket, proto, src, sport, dst, dport)
        );
        CREATE INDEX IF NOT EXISTS idx_dst  ON flows(dst);
        CREATE INDEX IF NOT EXISTS idx_host ON flows(host);
        CREATE INDEX IF NOT EXISTS idx_ts   ON flows(ts_last);
        CREATE INDEX IF NOT EXISTS idx_pid  ON flows(pid);
        CREATE INDEX IF NOT EXISTS idx_flag ON flows(flagged) WHERE flagged=1;
        CREATE TABLE IF NOT EXISTS seen_dst(pid INTEGER, dst TEXT, PRIMARY KEY(pid,dst));
        CREATE TABLE IF NOT EXISTS baseline(pid INTEGER, dst TEXT, median REAL,
                                            n INTEGER DEFAULT 0, PRIMARY KEY(pid,dst));
        CREATE TABLE IF NOT EXISTS hostmap(ip TEXT PRIMARY KEY, name TEXT, ts INTEGER);
        """
    )
    # CREATE TABLE IF NOT EXISTS never alters an existing table, so columns
    # added later need an explicit migration.
    cols = {r[1] for r in con.execute("PRAGMA table_info(baseline)")}
    if "n" not in cols:
        con.execute("ALTER TABLE baseline ADD COLUMN n INTEGER DEFAULT 0")
        con.commit()
    return con


# ---------------------------------------------------------------- attribution


class ProcMap:
    """socket inode -> pid, refreshed in the background."""

    def __init__(self):
        self.key_pid = {}   # (proto, client_port) -> (pid, comm)
        self.pid_comm = {}
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                self._refresh()
            except Exception:
                pass
            time.sleep(3)

    def _refresh(self):
        inode_pid, pid_comm = {}, {}
        for p in os.listdir("/proc"):
            if not p.isdigit():
                continue
            pid = int(p)
            try:
                for fd in os.listdir(f"/proc/{p}/fd"):
                    try:
                        link = os.readlink(f"/proc/{p}/fd/{fd}")
                    except OSError:
                        continue
                    if link.startswith("socket:["):
                        inode_pid[int(link[8:-1])] = pid
                with open(f"/proc/{p}/comm") as f:
                    pid_comm[pid] = f.read().strip()[:32]
            except OSError:
                continue
        key_pid = {}
        for tag, path in (("tcp", "/proc/net/tcp"), ("tcp6", "/proc/net/tcp6"),
                          ("udp", "/proc/net/udp"), ("udp6", "/proc/net/udp6")):
            try:
                with open(path) as f:
                    next(f)
                    for line in f:
                        parts = line.split()
                        if len(parts) < 10:
                            continue
                        port = int(parts[1].partition(":")[2], 16)
                        pid = inode_pid.get(int(parts[9]))
                        if pid:
                            key_pid[(tag, port)] = (pid, pid_comm.get(pid))
            except OSError:
                continue
        self.key_pid, self.pid_comm = key_pid, pid_comm

    def lookup(self, proto, port):
        return self.key_pid.get((proto, port), (None, None))


# ---------------------------------------------------------------- names


def parse_dns(payload):
    """(qname, [A addresses]) from a DNS payload."""
    try:
        if len(payload) < 12:
            return None, []
        flags = struct.unpack("!H", payload[2:4])[0]
        qd, an = struct.unpack("!HH", payload[4:8])
        if qd == 0:
            return None, []
        i, labels = 12, []
        while i < len(payload) and payload[i] != 0 and len(labels) < 8:
            n = payload[i]
            if n > 63:
                return None, []
            labels.append(payload[i + 1:i + 1 + n].decode("ascii", "ignore"))
            i += n + 1
        name = ".".join(labels)
        if not name or "." not in name:
            return None, []
        i += 5
        addrs = []
        if flags & 0x8000:
            for _ in range(min(an, 8)):
                if i >= len(payload):
                    break
                if payload[i] & 0xC0 == 0xC0:
                    i += 2
                else:
                    while i < len(payload) and payload[i] != 0:
                        i += payload[i] + 1
                    i += 1
                if i + 10 > len(payload):
                    break
                rtype = struct.unpack("!H", payload[i:i + 2])[0]
                rdlen = struct.unpack("!H", payload[i + 8:i + 10])[0]
                i += 10
                if rtype == 1 and rdlen == 4 and i + 4 <= len(payload):
                    addrs.append(socket.inet_ntoa(payload[i:i + 4]))
                i += rdlen
        return name, addrs
    except Exception:
        return None, []


def parse_sni(b):
    """SNI from a TLS ClientHello."""
    try:
        if len(b) < 45 or b[0] != 0x16 or b[5] != 0x01:
            return None
        p = 9 + 2 + 32
        p += 1 + b[p]
        p += 2 + int.from_bytes(b[p:p + 2], "big")
        p += 1 + b[p]
        ext_end = min(len(b), p + 2 + int.from_bytes(b[p:p + 2], "big"))
        p += 2
        while p + 4 <= ext_end:
            etype = int.from_bytes(b[p:p + 2], "big")
            elen = int.from_bytes(b[p + 2:p + 4], "big")
            if etype == 0x0000 and p + 9 <= len(b):
                nlen = int.from_bytes(b[p + 7:p + 9], "big")
                name = b[p + 9:p + 9 + nlen].decode("ascii", "ignore")
                return name if "." in name else None
            p += 4 + elen
        return None
    except Exception:
        return None


def name_reader(store):
    """Watch DNS and TLS ClientHello only.

    No BPF: SO_ATTACH_FILTER returns EINVAL on this kernel. Instead the parser
    exits on the first few header bytes, which is a handful of integer reads —
    far cheaper than the old full per-packet parse. Everything else returns
    before any allocation or dict work.
    """
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    s.settimeout(1.0)
    while True:
        try:
            data, addr = s.recvfrom(65535)
        except (socket.timeout, OSError):
            continue
        if addr[1] != 0x0800 or len(data) < 14 + 20:
            continue
        ip = data[14:]
        if ip[0] != 0x45:                      # v4, no options
            continue
        proto = ip[9]
        if proto != 17 and proto != 6:
            continue
        ihl = 20
        sport, dport = struct.unpack("!HH", ip[ihl:ihl + 4])
        if proto == 17:
            if dport != 53 and sport != 53:
                continue
            name, addrs = parse_dns(ip[ihl + 8:])
            if not name:
                continue
            for a in addrs:
                store.hostmap[a] = name
            store.hostmap[name] = name
        else:
            if dport != 443:
                continue
            off = ihl + (ip[ihl + 12] >> 4) * 4
            payload = ip[off:]
            if payload[:1] != b"\x16" or len(payload) < 50 or payload[5] != 1:
                continue
            sni = parse_sni(payload)
            if sni:
                store.hostmap[socket.inet_ntoa(ip[16:20])] = sni


# ---------------------------------------------------------------- capture


class Snapshot:
    """Read the kernel connection table: already byte-accounted."""

    def __init__(self):
        self.locals = set()
        self.refresh_locals()

    def refresh_locals(self):
        out = subprocess.run(["ip", "-o", "addr"], capture_output=True, text=True, timeout=5).stdout
        locs = {"127.0.0.1", "::1"}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) > 3:
                locs.add(parts[3].split("/")[0])
        self.locals = locs

    def read(self):
        try:
            with open("/proc/net/nf_conntrack") as f:
                lines = f.readlines()
        except OSError:
            return []
        rows, now = [], int(time.time())
        for line in lines:
            parts = line.split()
            if len(parts) < 8:
                continue
            proto = ""
            if "tcp" in parts[:5]:
                proto = "tcp"
            elif "udp" in parts[:5]:
                proto = "udp"
            if not proto:
                continue
            state = ""
            for p in parts:
                if p.isupper() and p.isalpha() and p not in ("ASSURED", "SEEN_REPLY", "CONFIRMED"):
                    state = p
                    break
            s_ip = s_port = d_ip = d_port = None
            o_ip = o_port = od_ip = od_port = None
            o_bytes = r_bytes = 0
            seen = 0
            for p in parts:
                k, _, v = p.partition("=")
                if k == "src":
                    if seen == 0:
                        s_ip = v
                    else:
                        o_ip = v
                elif k == "dst":
                    if seen == 0:
                        d_ip = v
                    else:
                        od_ip = v
                elif k == "sport":
                    if seen == 0:
                        s_port = v
                    else:
                        o_port = v
                elif k == "dport":
                    if seen == 0:
                        d_port = v
                    else:
                        od_port = v
                elif k == "bytes":
                    seen = 1
                    if o_bytes == 0:
                        o_bytes = int(v)
                    else:
                        r_bytes = int(v)
            if not (s_ip and d_ip and s_port and d_port):
                continue
            if s_ip in self.locals and d_ip not in self.locals:
                c_ip, c_port, sv_ip, sv_port = s_ip, s_port, d_ip, d_port
                out_b, in_b = o_bytes, r_bytes
            elif d_ip in self.locals and s_ip not in self.locals:
                c_ip, c_port, sv_ip, sv_port = d_ip, d_port, s_ip, s_port
                out_b, in_b = r_bytes, o_bytes
            else:
                c_ip, c_port, sv_ip, sv_port = s_ip, s_port, d_ip, d_port
                out_b, in_b = o_bytes, r_bytes
            rows.append(dict(proto=proto, state=state, src=c_ip, sport=int(c_port),
                             dst=sv_ip, dport=int(sv_port),
                             bytes_out=out_b, bytes_in=in_b, ts=now))
        return rows


class Store:
    def __init__(self):
        self.hostmap = {}
        self.con = db_open()
        self.prev = {}

    def run(self):
        snap = Snapshot()
        threading.Thread(target=name_reader, args=(self,), daemon=True).start()
        threading.Thread(target=self._hostmap_flush, daemon=True).start()
        print(f"[netline] conntrack polling, db={DB}")
        last_refresh = time.time()
        while True:
            rows = snap.read()
            if time.time() - last_refresh > 300:
                snap.refresh_locals()
                last_refresh = time.time()
            self.apply(rows)
            time.sleep(POLL_S)

    def _hostmap_flush(self):
        # SQLite connections are thread-bound; this thread owns its own.
        con = db_open()
        while True:
            time.sleep(2)
            if not self.hostmap:
                continue
            batch, self.hostmap = self.hostmap, {}
            now = int(time.time())
            try:
                con.executemany(
                    "INSERT INTO hostmap(ip,name,ts) VALUES(?,?,?) "
                    "ON CONFLICT(ip) DO UPDATE SET name=excluded.name, ts=excluded.ts",
                    [(ip, name, now) for ip, name in batch.items() if name])
                con.commit()
            except Exception as e:
                print(f"[netline] hostmap: {e}", file=sys.stderr)

    def apply(self, rows):
        cur = self.con.cursor()
        nums = [r["dst"] for r in rows] + [r["src"] for r in rows]
        names = {}
        if nums:
            placeholders = ",".join("?" * len(set(nums)))
            for ip, name in cur.execute(
                    f"SELECT ip,name FROM hostmap WHERE ip IN ({placeholders})", tuple(set(nums))):
                names[ip] = name
        for r in rows:
            key = (r["proto"], r["src"], r["sport"], r["dst"], r["dport"])
            prev_out, prev_in = self.prev.get(key, (0, 0))
            d_out = max(0, r["bytes_out"] - prev_out)
            d_in = max(0, r["bytes_in"] - prev_in)
            self.prev[key] = (max(prev_out, r["bytes_out"]), max(prev_in, r["bytes_in"]))
            if d_out == 0 and d_in == 0:
                continue
            bucket = r["ts"] // BUCKET_S
            host = clean_host(names.get(r["dst"]) or names.get(r["src"]) or r.get("host"))
            pid, comm = self.procmap_lookup(r)
            comm = clean_proc(comm)
            flagged, reason = self.classify(cur, pid, r["dst"], d_out + d_in)
            cur.execute(
                "INSERT INTO flows(bucket,ts_first,ts_last,proto,pid,comm,src,sport,dst,dport,"
                "bytes_out,bytes_in,state,dns,sni,host,flagged,flag_reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(bucket,proto,src,sport,dst,dport) DO UPDATE SET "
                "ts_last=excluded.ts_last, state=excluded.state, "
                "bytes_out=MAX(flows.bytes_out,excluded.bytes_out), "
                "bytes_in=MAX(flows.bytes_in,excluded.bytes_in), "
                "pid=COALESCE(flows.pid,excluded.pid), "
                "host=COALESCE(excluded.host,flows.host), "
                "flagged=MAX(flows.flagged,excluded.flagged), "
                "flag_reason=COALESCE(excluded.flag_reason,flows.flag_reason)",
                (bucket, r["ts"], r["ts"], r["proto"], pid, comm, r["src"], r["sport"],
                 r["dst"], r["dport"], d_out, d_in, r["state"],
                 host if r["dport"] == 53 else None,
                 host if r["dport"] != 53 else None, host, flagged, reason))
        self.con.commit()

    def procmap_lookup(self, r):
        return self.proc.lookup(r["proto"], r["sport"])

    def classify(self, cur, pid, dst, total):
        """Decide whether this transfer is anomalous, and say why truthfully.

        Two guards learned the hard way: the reason string must describe the
        comparison that actually fired (an EMA updated after the check, so the
        ratio shown is the real one), and small bursts must not qualify. A
        2-second delta against a near-zero baseline produces absurd ratios for
        ordinary 100 KB API responses, so both an absolute floor and a
        minimum sample count are required.
        """
        if not pid:
            return 0, None
        cur.execute("SELECT 1 FROM seen_dst WHERE pid=? AND dst=?", (pid, dst))
        new = cur.fetchone() is None
        if new:
            cur.execute("INSERT OR IGNORE INTO seen_dst(pid,dst) VALUES(?,?)", (pid, dst))
            if total > FLAG_NEW_DST_BYTES:
                return 1, f"first contact with {human(total)} pulled"

        cur.execute("SELECT median, n FROM baseline WHERE pid=? AND dst=?", (pid, dst))
        row = cur.fetchone()
        prev, n = (row[0], row[1]) if row else (0, 0)
        ratio = (total / prev) if prev > 0 else 0
        med = total if not prev else prev * 0.8 + total * 0.2
        cur.execute(
            "INSERT INTO baseline(pid,dst,median,n) VALUES(?,?,?,1) "
            "ON CONFLICT(pid,dst) DO UPDATE SET median=excluded.median, n=baseline.n+1",
            (pid, dst, med))

        # Need enough history that the baseline means something, a transfer
        # big enough to matter on its own, and a real ratio.
        if n >= FLAG_MIN_SAMPLES and total >= FLAG_MIN_BYTES and ratio >= FLAG_RATIO:
            return 1, f"{ratio:.0f}x typical ({human(prev)} → {human(total)})"
        return 0, None


# ---------------------------------------------------------------- CLI


def human(n):
    n = float(n or 0)
    for u in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{u}"
        n /= 1024
    return f"{n:.0f}T"


def cmd_top(n, include_loopback=False):
    con = db_open()
    since = int(time.time()) - 900
    clause = "" if include_loopback else (
        " AND dst NOT LIKE '127.%' AND dst NOT LIKE '172.1%'"
        " AND dst NOT LIKE '172.2%' AND dst NOT LIKE '100.%'")
    rows = con.execute(
        "SELECT COALESCE(host,dst) h, dst, SUM(bytes_out) o, SUM(bytes_in) i, "
        "COUNT(*) c, GROUP_CONCAT(DISTINCT comm) FROM flows WHERE ts_last>?" + clause +
        " GROUP BY h,dst ORDER BY (o+i) DESC LIMIT ?", (since, n)).fetchall()
    print(f"{'DEST':38} {'OUT':>9} {'IN':>9} {'FLOWS':>6} PROCESS")
    for h, dst, o, i, c, comm in rows:
        label = h if h != dst else dst
        if len(label) > 60 and ":" in label:
            # conntrack reports some v4-mapped v6 addrs; show the tail
            label = "v6:" + label.replace("0000:", "").replace(":", "")[:30]
        extra = "" if h == dst else f" ({dst})"
        procs = ", ".join(sorted({disp_proc(x) for x in (comm or "").split(",") if x}))[:40]
        print(f"{(label + extra)[:38]:38} {human(o):>9} {human(i):>9} {c:>6} {procs}")


def disp_proc(c):
    return clean_proc(c) or "unattributed"


def cmd_chase(needle):
    con = db_open()
    rows = con.execute(
        "SELECT ts_last,proto,pid,comm,src,sport,dst,dport,bytes_out,bytes_in,"
        "host,flagged,flag_reason FROM flows WHERE dst=? OR host=? OR dns=? "
        "ORDER BY ts_last DESC LIMIT 60", (needle, needle, needle)).fetchall()
    if not rows:
        print("no flows for", needle)
        return
    for (ts, proto, pid, comm, src, sp, dst, dp, o, i, host, fl, reason) in rows:
        when = time.strftime("%H:%M:%S", time.localtime(ts))
        flag = f"  FLAG[{reason}]" if fl else ""
        print(f"{when} {proto:3} {(disp_proc(comm)):<18} "
              f"{src}:{sp} -> {dst}:{dp} out={human(o)} in={human(i)} {host or ''}{flag}")


def cmd_flags():
    con = db_open()
    rows = con.execute(
        "SELECT ts_last,pid,comm,dst,dport,host,bytes_out,bytes_in,flag_reason "
        "FROM flows WHERE flagged=1 ORDER BY ts_last DESC LIMIT 50").fetchall()
    if not rows:
        print("no flagged flows")
        return
    for ts, pid, comm, dst, dp, host, o, i, reason in rows:
        when = time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
        print(f"{when} {disp_proc(comm):<18} -> {clean_host(host) or dst}:{dp} "
              f"out={human(o)} in={human(i)}  {reason}")


def cmd_pid(pid):
    con = db_open()
    for host, dp, o, i, c in con.execute(
            "SELECT COALESCE(host,dst), dport, SUM(bytes_out), SUM(bytes_in), COUNT(*) "
            "FROM flows WHERE pid=? GROUP BY 1,2 ORDER BY 3+4 DESC LIMIT 40", (pid,)):
        print(f"{host:45}:{dp:<6} out={human(o):>8} in={human(i):>8} flows={c}")


def cmd_live():
    con = db_open()
    last = con.execute("SELECT COALESCE(MAX(id),0) FROM flows").fetchone()[0]
    while True:
        for (fid, ts, proto, comm, dst, dp, o, i, host, fl, reason) in con.execute(
                "SELECT id,ts_last,proto,comm,dst,dport,bytes_out,bytes_in,host,flagged,flag_reason "
                "FROM flows WHERE id>? ORDER BY id LIMIT 200", (last,)):
            last = fid
            when = time.strftime("%H:%M:%S", time.localtime(ts))
            flag = f" FLAG[{reason}]" if fl else ""
            print(f"{when} {proto} {disp_proc(comm):<16} -> {clean_host(host) or dst}:{dp} "
                  f"out={human(o)} in={human(i)}{flag}")
        time.sleep(1)


def cmd_prune(days):
    con = db_open()
    cutoff = int(time.time()) - days * 86400
    before = con.execute("SELECT COUNT(*) FROM flows").fetchone()[0]
    con.execute("DELETE FROM flows WHERE ts_last < ?", (cutoff,))
    con.execute("DELETE FROM hostmap WHERE ts < ?", (cutoff,))
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM flows").fetchone()[0]
    con.execute("VACUUM")
    print(f"pruned {before - after} flows older than {days}d ({after} remain)")


def main():
    ap = argparse.ArgumentParser(prog="netline")
    ap.add_argument("cmd", choices=["daemon", "top", "chase", "flags", "pid", "live", "prune"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.cmd == "daemon":
        st = Store()
        st.proc = ProcMap()
        st.run()
    elif a.cmd == "top":
        cmd_top(int(a.arg or 20), include_loopback=a.all)
    elif a.cmd == "chase":
        if not a.arg:
            sys.exit("chase needs an IP or hostname")
        cmd_chase(a.arg)
    elif a.cmd == "flags":
        cmd_flags()
    elif a.cmd == "pid":
        cmd_pid(int(a.arg))
    elif a.cmd == "live":
        cmd_live()
    elif a.cmd == "prune":
        cmd_prune(int(a.arg or 7))


if __name__ == "__main__":
    main()
