#!/usr/bin/python3
"""Opt-in upstream threat-intel refresh for io.github.duketopceo.bumblebee.

Perplexity's bumblebee ships advisories as threat_intel/*.json inside each
release's source tree; the CLI itself has no update path, so the plugin owns
refresh. This helper runs ONLY when invoked (panel button or CLI) — never on
a timer, never during status polls. Offline-by-default: nothing here runs
unless the user asks.

Integrity story: the fetch is pinned — fixed repo, fixed RELEASE_TAG (the
release whose threat_intel was seeded into catalog.d), HTTPS only. Upstream
ships no signature infra, so repo+tag+TLS is the documented boundary.

  https://github.com/perplexityai/bumblebee/archive/refs/tags/<TAG>.tar.gz

The download is byte-capped (~64MiB) under a hard timeout; only
threat_intel/*.json members are read — path traversal, absolute paths,
symlinks, devices and any non-regular member are rejected. Each entry is
validated against the 0.1.0 catalog schema ({id,name,ecosystem,package,
versions:[...]} — versions is a LIST) before it counts, then merged
atomically to ~/.config/omarchy/plugins-data/bumblebee/catalog.d/upstream.json
at 0600 (tmp+rename). Every failure lands in "error" and leaves catalog.d
untouched.

Contract — exactly one JSON object on stdout, exit 0:

  {"ok": bool, "entries_added": int, "entries_skipped": int,
   "entries_total": int, "tag": str, "refreshed_at": iso8601|null,
   "error": string|null}

Advisory bodies/names are never printed — counts only.
"""
import io
import json
import os
import signal
import stat
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

JOB_DEADLINE_S = 25           # whole-job backstop (panel allows 30s)
FETCH_TIMEOUT_S = 20          # connect+read wall clock for the tarball GET
UPSTREAM_REPO = "perplexityai/bumblebee"
RELEASE_TAG = "v0.1.2"        # release whose threat_intel seeded catalog.d
TARBALL_URL = ("https://github.com/" + UPSTREAM_REPO +
               "/archive/refs/tags/" + RELEASE_TAG + ".tar.gz")

MAX_TARBALL_BYTES = 64 * 1024 * 1024   # download cap (~64MiB)
MAX_MEMBER_BYTES = 4 * 1024 * 1024     # per threat_intel file cap
MAX_EXTRACT_BYTES = 32 * 1024 * 1024   # summed extracted-bytes cap
MAX_MEMBERS = 512                      # member-iteration bound
MAX_ENTRIES = 20000                    # advisory-entry bound
MAX_PREV_BYTES = 16 * 1024 * 1024      # prior upstream.json read cap
OUT_MAX_BYTES = 4 * 1024               # stdout payload is counts only

USER_CATALOG_REL = ".config/omarchy/plugins-data/bumblebee/catalog.d"
MERGED_NAME = "upstream.json"
SCHEMA_VERSION = "0.1.0"

try:
    HOME = Path.home()
except Exception:
    HOME = Path("/")


class FetchError(Exception):
    """Any download failure — message is a short, log-safe token."""


# --- fetch: HTTPS only, explicit timeout, hard byte cap (no shell) ---

def _fetch(url, timeout_s=FETCH_TIMEOUT_S, max_bytes=MAX_TARBALL_BYTES):
    """GET url -> bytes. Raises FetchError(short_reason) on any failure.

    urllib honours the caller's env (incl. proxies); the panel exec scrubs to
    a minimal env anyway. HTTPS is enforced again here so an injected seam
    can't downgrade the scheme.
    """
    if not isinstance(url, str) or not url.startswith("https://"):
        raise FetchError("scheme_not_https")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "omarchy-bumblebee-catalog-refresh",
            "Accept": "application/octet-stream",
        },
    )
    started = time.monotonic()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout_s)
    except urllib.error.HTTPError as exc:
        raise FetchError("http_%d" % exc.code) from None
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(_err_token(exc)) from None
    try:
        cl = resp.headers.get("Content-Length")
        if cl is not None:
            try:
                if int(cl) > max_bytes:
                    raise FetchError("too_large")
            except ValueError:
                pass
        buf = bytearray()
        while True:
            if time.monotonic() - started > timeout_s:
                raise FetchError("timeout")
            try:
                chunk = resp.read(min(1 << 20, max_bytes + 1 - len(buf)))
            except OSError as exc:
                raise FetchError(_err_token(exc)) from None
            if not chunk:
                break
            buf += chunk
            if len(buf) > max_bytes:
                raise FetchError("too_large")
    finally:
        try:
            resp.close()
        except Exception:
            pass
    return bytes(buf)


def _err_token(exc):
    """Short stable token for a network/OS error — no host/path leakage."""
    reason = getattr(exc, "reason", exc)
    name = type(reason).__name__.lower()
    for token in ("timeout", "refused", "resolve", "name", "reset",
                  "unreachable", "ssl", "cert"):
        if token in name or token in str(reason).lower():
            return "net_" + ("timeout" if "timed" in str(reason).lower()
                             or token == "timeout" else token)
    return "fetch_failed"


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


# --- tarball: threat_intel/*.json only, every member sanitized ---

def _member_ok(name):
    """True only for '<top>/threat_intel/<file>.json' with no traversal."""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    parts = name.split("/")
    if len(parts) != 3:
        return False
    if any(p in ("", ".", "..") for p in parts):
        return False
    return parts[1] == "threat_intel" and parts[2].endswith(".json")


def _iter_threat_intel(blob):
    """Yield (filename, bytes) for each sanitized threat_intel/*.json member.

    Raises FetchError on a corrupt tarball or an extract cap breach; simply
    skips members that fail the shape/size checks.
    """
    try:
        tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    except (tarfile.TarError, OSError, EOFError, ValueError):
        raise FetchError("bad_tarball") from None
    total = 0
    seen = 0
    with tf:
        for member in tf:
            seen += 1
            if seen > MAX_MEMBERS:
                raise FetchError("too_many_members")
            if not _member_ok(member.name):
                continue
            if not member.isreg():
                # Symlinks, hardlinks, devices, dirs: never followed/extracted.
                continue
            if member.size > MAX_MEMBER_BYTES:
                continue
            try:
                src = tf.extractfile(member)
            except (tarfile.TarError, OSError, KeyError):
                continue
            if src is None:
                continue
            try:
                data = src.read(MAX_MEMBER_BYTES + 1)
            except (tarfile.TarError, OSError):
                continue
            finally:
                try:
                    src.close()
                except Exception:
                    pass
            if len(data) > MAX_MEMBER_BYTES:
                continue
            total += len(data)
            if total > MAX_EXTRACT_BYTES:
                raise FetchError("too_large")
            yield member.name.split("/")[-1], data


# --- catalog entries: 0.1.0 schema check, invalid entries skipped ---

def _valid_entry(entry):
    """0.1.0 catalog entry: core fields present with the right types.

    versions is a LIST of strings (verified against upstream threat_intel).
    Extra keys (severity, source, indicators, ...) pass through — the scanner
    tolerates them and bumblebee may consume them.
    """
    if not isinstance(entry, dict):
        return False
    for key in ("id", "name", "ecosystem", "package"):
        v = entry.get(key)
        if not isinstance(v, str) or not v.strip():
            return False
    versions = entry.get("versions")
    if not isinstance(versions, list) or not versions:
        return False
    for v in versions:
        if not isinstance(v, str) or not v.strip():
            return False
    for key in ("severity", "source"):
        v = entry.get(key)
        if v is not None and not isinstance(v, str):
            return False
    return True


def _entries_from(data):
    """Pull the entries list out of a catalog file (dict or bare list)."""
    if isinstance(data, dict):
        entries = data.get("entries")
    elif isinstance(data, list):
        entries = data
    else:
        return []
    return entries if isinstance(entries, list) else []


# --- catalog.d: descriptor-relative reads, atomic 0600 publish ---

def _open_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        os.close(fd)
        raise PermissionError(f"{path} is not a user-owned real directory")
    return fd


def _publish(dirfd, name, data):
    """Write via exclusive same-dir temp file + atomic rename, mode 0600."""
    tmp = f".{name}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=dirfd)
    try:
        os.write(fd, data.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, name, src_dir_fd=dirfd, dst_dir_fd=dirfd)


def _read_prior_ids(catalog_d):
    """ids currently in upstream.json -> set ({} on absent/corrupt/oversized)."""
    path = catalog_d / MERGED_NAME
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return set()
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_size > MAX_PREV_BYTES):
            return set()
        raw = os.read(fd, MAX_PREV_BYTES)
    except OSError:
        return set()
    finally:
        os.close(fd)
    try:
        data = json.loads(raw)
    except ValueError:
        return set()
    ids = set()
    for e in _entries_from(data):
        if isinstance(e, dict) and isinstance(e.get("id"), str):
            ids.add(e["id"])
    return ids


def _base_payload():
    return {
        "ok": False,
        "entries_added": 0,
        "entries_skipped": 0,
        "entries_total": 0,
        "tag": RELEASE_TAG,
        "refreshed_at": None,
        "error": None,
    }


def refresh(fetch=None, home=None, now=None):
    """Fetch+validate+merge the pinned upstream catalog -> payload dict.

    fetch/home/now are injectable seams (tests fake the network and the fs).
    Every failure path returns ok=false with error set and catalog.d
    untouched: validation finishes before any write, and the write itself is
    tmp+rename atomic.
    """
    if now is None:
        now = time.time()
    home = Path(home) if home is not None else HOME
    if fetch is None:
        fetch = _fetch
    payload = _base_payload()

    try:
        blob = fetch(TARBALL_URL, FETCH_TIMEOUT_S, MAX_TARBALL_BYTES)
    except FetchError as exc:
        payload["error"] = str(exc)[:96]
        return payload
    except Exception:
        payload["error"] = "fetch_failed"
        return payload
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        payload["error"] = "fetch_failed"
        return payload
    if len(blob) > MAX_TARBALL_BYTES:
        payload["error"] = "too_large"
        return payload

    entries = {}
    skipped = 0
    try:
        members = list(_iter_threat_intel(bytes(blob)))
    except FetchError as exc:
        payload["error"] = str(exc)[:96]
        return payload
    except Exception:
        payload["error"] = "bad_tarball"
        return payload
    if not members:
        payload["error"] = "no_threat_intel"
        return payload
    for _name, data in members:
        try:
            doc = json.loads(data)
        except ValueError:
            continue
        for e in _entries_from(doc):
            if not _valid_entry(e):
                skipped += 1
                continue
            if len(entries) >= MAX_ENTRIES:
                break
            entries.setdefault(e["id"], e)
    if not entries:
        payload["error"] = "no_valid_entries"
        payload["entries_skipped"] = skipped
        return payload

    prior_ids = _read_prior_ids(home / USER_CATALOG_REL)
    merged = {
        "schema_version": SCHEMA_VERSION,
        "_comment": ("Upstream threat_intel merge — pinned release "
                     + RELEASE_TAG + " of " + UPSTREAM_REPO +
                     ". Written by refresh_catalog.py; edit via re-refresh, "
                     "or delete to drop upstream advisories."),
        "upstream_tag": RELEASE_TAG,
        "fetched_at": _iso(now),
        "entries": list(entries.values()),
    }
    catalog_d = home / USER_CATALOG_REL
    try:
        catalog_d.mkdir(mode=0o700, parents=True, exist_ok=True)
        dirfd = _open_dir(catalog_d)
    except (OSError, PermissionError):
        payload["error"] = "catalog_dir_unwritable"
        return payload
    try:
        _publish(dirfd, MERGED_NAME, json.dumps(merged))
    except OSError:
        payload["error"] = "publish_failed"
        return payload
    finally:
        os.close(dirfd)

    payload["ok"] = True
    payload["entries_added"] = sum(1 for i in entries if i not in prior_ids)
    payload["entries_skipped"] = skipped
    payload["entries_total"] = len(entries)
    payload["refreshed_at"] = _iso(now)
    return payload


def main():
    # Session/group leader + SIGALRM backstop so a wedged fetch can always be
    # group-killed and never outlives JOB_DEADLINE_S.
    try:
        os.setsid()
    except OSError:
        pass
    signal.signal(signal.SIGALRM, lambda *_: os._exit(124))
    signal.alarm(JOB_DEADLINE_S)
    try:
        payload = refresh()
    except Exception as exc:
        payload = _base_payload()
        payload["error"] = "internal: " + str(exc)[:96]
    sys.stdout.write(json.dumps(payload)[:OUT_MAX_BYTES] + "\n")


if __name__ == "__main__":
    main()
