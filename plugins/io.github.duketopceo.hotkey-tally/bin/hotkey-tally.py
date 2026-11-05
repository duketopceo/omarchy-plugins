#!/usr/bin/env python3
"""Aggregate-only hotkey activation tally.

Design constraint: Hyprland fires no event when a *binding* is dispatched, so
nothing here observes keystrokes. This tool only records the activations that a
wrapped binding explicitly reports, which means:

  * it never sees text, clipboard contents, or unbound keys;
  * it writes nothing to the network;
  * it stores one line per activation: id, key, label, timestamp.

State lives in $XDG_STATE_HOME/hotkey-tally/uses.jsonl, append-only, pruned to
the most recent MAX_LINES rows.

`list --all` joins those counts against the live binding table from
`hyprctl binds -j`, so bindings that were never used still appear with x0.
"""

from __future__ import annotations

import argparse
import curses
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MAX_LINES = 50_000

MOD_BITS = ((64, "SUPER"), (4, "CTRL"), (8, "ALT"), (1, "SHIFT"))


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "hotkey-tally"


def uses_path() -> Path:
    return state_dir() / "uses.jsonl"


def binding_id(label: str) -> str:
    """Must match hotkey-tally.lua's id_for(): hash of the label only.

    Key formatting differs between the compositor's modmask and however a bind
    was written, so the label is the only stable join key.
    """
    total = 0
    for byte in str(label).encode("utf-8"):
        total = (total * 31 + byte) % 4_294_967_296
    return f"{total:08x}"


def _append(row: dict) -> None:
    path = uses_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _rows() -> list[dict]:
    path = uses_path()
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                # A torn tail from a killed writer is not worth losing the file over.
                continue
            if isinstance(row, dict) and row.get("id"):
                out.append(row)
    return out


def _prune(keep: int = MAX_LINES) -> int:
    rows = _rows()
    if len(rows) <= keep:
        return 0
    dropped = len(rows) - keep
    path = uses_path()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows[-keep:]:
            fh.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
    tmp.replace(path)
    return dropped


def _aggregate(rows: list[dict]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for row in rows:
        entry = by_id.setdefault(
            row["id"],
            {"id": row["id"], "key": "", "label": "", "count": 0, "last": 0},
        )
        entry["count"] += 1
        ts = int(row.get("ts") or 0)
        if ts > entry["last"]:
            entry["last"] = ts
        if row.get("key"):
            entry["key"] = row["key"]
        if row.get("label"):
            entry["label"] = row["label"]
    return by_id


def _counts() -> dict[str, dict]:
    return _aggregate(_rows())


def _key_name(bind: dict) -> str:
    mods = [name for bit, name in MOD_BITS if int(bind.get("modmask") or 0) & bit]
    key = str(bind.get("key") or "").replace("code:", "")
    parts = mods + ([key] if key else [])
    return " + ".join(parts)


def _key_map() -> dict[str, str]:
    """Label -> key text, from the same table `omarchy menu keybindings` shows.

    hyprctl alone cannot supply this: Lua binds report dispatcher "__lua" with
    no key and no keycode, so empty keys are common there.
    """
    try:
        raw = subprocess.run(
            ["omarchy", "menu", "keybindings", "--print"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "\u2192" not in line:
            continue
        left, _, label = line.partition("\u2192")
        label = label.strip()
        if label and label not in out:
            out[label] = left.strip()
    return out


def _live_binds() -> list[dict]:
    try:
        raw = subprocess.run(
            ["hyprctl", "binds", "-j"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
        binds = json.loads(raw)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    key_map = _key_map()
    out: list[dict] = []
    for bind in binds:
        label = str(bind.get("description") or "").strip()
        if not label or bind.get("mouse") or str(bind.get("key", "")).startswith("switch:"):
            continue
        key = key_map.get(label) or _key_name(bind)
        out.append({"key": key, "label": label})
    return out


def _joined(sort: str) -> list[dict]:
    counts = _counts()
    rows: list[dict] = []
    seen: set[str] = set()
    for bind in _live_binds():
        rid = binding_id(bind["label"])
        seen.add(rid)
        hit = counts.get(rid)
        rows.append(
            {
                "id": rid,
                "key": bind["key"] or (hit["key"] if hit else ""),
                "label": bind["label"],
                "count": hit["count"] if hit else 0,
                "last": hit["last"] if hit else 0,
            }
        )
    # Recorded activations whose binding no longer exists still deserve a line.
    for rid, hit in counts.items():
        if rid not in seen:
            rows.append({**hit, "label": (hit["label"] or hit["id"]) + " (gone)"})
    if sort == "used":
        rows.sort(key=lambda r: (-r["count"], r["key"].lower(), r["label"].lower()))
    else:
        # "config" reads as a stable a-z of the key, then the action name.
        rows.sort(key=lambda r: (r["key"].lower(), r["label"].lower()))
    return rows


def _fmt_age(ms: int) -> str:
    if not ms:
        return "-"
    delta = max(0, int(time.time() - ms / 1000))
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    if delta < 86_400:
        return f"{delta // 3600}h"
    return f"{delta // 86_400}d"


def cmd_record(args: argparse.Namespace) -> int:
    _append(
        {
            "ts": int(time.time() * 1000),
            "id": binding_id(args.label or args.id),
            "key": args.key or "",
            "label": args.label or args.id,
        }
    )
    if os.environ.get("HOTKEY_TALLY_PRUNE") == "1":
        _prune()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = _joined(args.sort) if args.all else list(_counts().values())
    if not args.all:
        rows.sort(key=lambda r: (-r["count"], (r["label"] or r["id"]).lower()))
    if args.search:
        needle = args.search.lower()
        rows = [r for r in rows if needle in r["label"].lower() or needle in r["key"].lower()]
    if args.limit:
        rows = rows[: args.limit]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("no bindings to show")
        return 0
    width = max(len(r["key"]) for r in rows)
    for r in rows:
        print(f"{r['key']:<{width}}  x{r['count']:<4} {_fmt_age(r['last']):>4}  {r['label']}")
    total = sum(r["count"] for r in rows)
    label = "a-z" if args.sort == "config" else "used"
    print(f"\n{len(rows)} bindings, {total} activations  (sort: {label})")
    return 0


def _draw(stdscr, rows: list[dict], sort: str, query: str, scroll: int) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    title = f" Hotkeys — {len(rows)} bindings · sort: {'a-z' if sort == 'config' else 'used'} "
    stdscr.addnstr(0, 0, title.ljust(width - 1), width - 1, curses.A_REVERSE)
    prompt = f" filter: {query}" + ("_" if True else "")
    stdscr.addnstr(1, 0, prompt[: width - 1], width - 1)

    visible = max(1, height - 4)
    window = rows[scroll : scroll + visible]
    key_w = min(30, max((len(r["key"]) for r in rows), default=8))
    for i, row in enumerate(window):
        y = 2 + i
        count = f"x{row['count']}"
        line = f" {row['key']:<{key_w}}  {count:>5}  {row['label']}"
        style = curses.A_BOLD if row["count"] else curses.A_DIM
        stdscr.addnstr(y, 0, line.ljust(width - 1), width - 1, style)
    footer = " s sort · / filter · r reload · q quit "
    stdscr.addnstr(height - 1, 0, footer.ljust(width - 1), width - 1, curses.A_REVERSE)
    stdscr.refresh()


def cmd_tui(args: argparse.Namespace) -> int:
    sort = args.sort
    query = ""
    scroll = 0

    def load() -> list[dict]:
        rows = _joined(sort)
        if query:
            needle = query.lower()
            rows = [r for r in rows if needle in r["label"].lower() or needle in r["key"].lower()]
        return rows

    def run(stdscr) -> None:
        nonlocal sort, query, scroll
        curses.curs_set(0)
        rows = load()
        while True:
            _draw(stdscr, rows, sort, query, scroll)
            ch = stdscr.getch()
            if ch in (ord("q"), 27):
                return
            if ch == ord("s"):
                sort = "config" if sort == "used" else "used"
                scroll = 0
                rows = load()
            elif ch == ord("r"):
                rows = load()
            elif ch == ord("/"):
                curses.curs_set(1)
                curses.echo()
                height, width = stdscr.getmaxyx()
                stdscr.addnstr(1, 0, " filter: ".ljust(width - 1), width - 1)
                raw = stdscr.getstr(1, 9, 60)
                curses.noecho()
                curses.curs_set(0)
                query = raw.decode("utf-8", "replace")
                scroll = 0
                rows = load()
            elif ch in (curses.KEY_DOWN, ord("j")):
                scroll = min(max(0, len(rows) - 1), scroll + 1)
            elif ch in (curses.KEY_UP, ord("k")):
                scroll = max(0, scroll - 1)

    curses.wrapper(run)
    return 0


def cmd_reset(_: argparse.Namespace) -> int:
    path = uses_path()
    if path.exists():
        path.unlink()
    print(f"cleared {path}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    print(f"pruned {_prune(args.keep)} rows")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hotkey-tally", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="record one binding activation")
    rec.add_argument("--id", default="", help="stable binding id (optional)")
    rec.add_argument("--key", default="", help="key combo, cosmetic")
    rec.add_argument("--label", default="", help="binding description")
    rec.set_defaults(func=cmd_record)

    lst = sub.add_parser("list", help="show counts")
    lst.add_argument("--json", action="store_true")
    lst.add_argument("--all", action="store_true", help="include never-used bindings")
    lst.add_argument("--sort", choices=["config", "used"], default="config")
    lst.add_argument("--limit", type=int, default=0)
    lst.add_argument("--search", default="")
    lst.set_defaults(func=cmd_list)

    tui = sub.add_parser("tui", help="interactive list (s sorts, / filters)")
    tui.add_argument("--sort", choices=["config", "used"], default="config")
    tui.set_defaults(func=cmd_tui)

    sub.add_parser("reset", help="delete all recorded activations").set_defaults(func=cmd_reset)

    prn = sub.add_parser("prune", help="keep only the newest N rows")
    prn.add_argument("--keep", type=int, default=MAX_LINES)
    prn.set_defaults(func=cmd_prune)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
