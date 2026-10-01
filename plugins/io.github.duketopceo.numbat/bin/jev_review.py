#!/usr/bin/python3
"""Jev-powered review of recent agent activity from numbat records.

Reads the tail of ~/.numbat/records.ndjson (or findings.ndjson), builds a
compact state summary, and asks TypeSafe Jev (OpenRouter decisions API) to
flag useless tool calls, wrong thinking, and the primary issue type.

Contract — one JSON object on stdout, exit 0:

  {"ok": bool, "reviewed_at": iso8601, "event_count": int,
   "agent": str|null, "answers": {...}|null, "model": str|null,
   "summary": str|null, "error": str|null}

Usage:
  jev_review.py [--agent NAME] [--limit N]

Env: OPENROUTER_API_KEY (or ~/.config/openrouter/keys.json api_key field).
Never writes under ~/.numbat — read-only consumer like probe_numbat.py.
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

JEV_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "typesafe/jev-1.13"
NUMBAT_HOME = pathlib.Path.home() / ".numbat"
RECORDS = NUMBAT_HOME / "records.ndjson"
FINDINGS = NUMBAT_HOME / "findings.ndjson"
TAIL_BYTES = 128 * 1024
MAX_EVENTS = 40
MAX_STR = 120

JEV_QUESTIONS = {
    "useless_tools": {
        "type": "noul",
        "instructions": "Did the agent make useless, redundant, or clearly wrong tool calls?",
        "true": "Repeated reads of the same file, wrong paths, noop shell commands, or tools that did not advance the task",
        "false": "Tool use was purposeful and each call moved the task forward",
    },
    "wrong_thinking": {
        "type": "noul",
        "instructions": "Did the agent show confused, circular, or clearly wrong reasoning?",
        "true": "Contradictory plans, ignoring tool errors, looping on the same mistake, or hallucinating file contents",
        "false": "Reasoning was coherent and adapted to tool results",
    },
    "issue_type": {
        "type": "choice",
        "instructions": "What is the primary quality issue in this session, if any?",
        "criteria": {
            "none": "No significant issue — agent behavior looks reasonable",
            "redundant_reads": "Re-read the same files or grep results unnecessarily",
            "wrong_target": "Edited or searched the wrong file, repo, or component",
            "tool_spam": "Too many low-value tool calls for the progress made",
            "stuck_loop": "Repeated the same failing approach without adapting",
            "overthinking": "Long reasoning chains without corresponding action",
        },
    },
    "severity": {
        "type": "score",
        "instructions": "How costly was the bad behavior for the user's time?",
        "criteria": ["Negligible", "Minor waste", "Moderate waste", "Major waste"],
    },
}


def _clean(value, limit=MAX_STR):
    s = str(value if value is not None else "")
    s = "".join(" " if ord(c) < 32 or 127 <= ord(c) <= 159 else c for c in s)
    return s.strip()[:limit]


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    keys_file = pathlib.Path.home() / ".config" / "openrouter" / "keys.json"
    if keys_file.is_file():
        try:
            data = json.loads(keys_file.read_text())
            return data.get("api_key", "")
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def _tail_lines(path: pathlib.Path, limit=TAIL_BYTES):
    if not path.is_file():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit))
            raw = f.read()
    except OSError:
        return []
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if size > limit and lines:
        lines = lines[1:]
    out = []
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _event_summary(rec):
    kind = _clean(rec.get("observed_event_type") or rec.get("event_type")
                  or rec.get("kind") or rec.get("record_type") or "event")
    agent = _clean(rec.get("source_agent") or rec.get("agent") or rec.get("agent_name"))
    summary = _clean(rec.get("summary") or rec.get("detail") or rec.get("message")
                  or rec.get("content_preview") or rec.get("observed_content_preview"), 200)
    return {"agent": agent, "kind": kind, "summary": summary}


def _build_state(records, agent_filter=None):
    events = []
    for rec in records:
        if rec.get("record_type") not in ("event", "finding", None):
            continue
        item = _event_summary(rec)
        if agent_filter and item["agent"] and item["agent"] != agent_filter:
            continue
        if item["summary"] or item["kind"] not in ("event", ""):
            events.append(item)
    events = events[-MAX_EVENTS:]
    if not events:
        return None, 0
    lines = []
    for i, e in enumerate(events, 1):
        lines.append(f"{i}. [{e['agent'] or 'unknown'}] {e['kind']}: {e['summary']}")
    return "\n".join(lines), len(events)


def _ask_jev(state: str, model: str, api_key: str) -> dict:
    payload = json.dumps({
        "model": model,
        "state": state,
        "questions": JEV_QUESTIONS,
    }).encode()
    req = urllib.request.Request(
        JEV_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/duketopceo/omarchy-numbat",
            "X-Title": "numbat-jev-review",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read())


def _human_summary(answers: dict) -> str:
    if not answers:
        return "No review available."
    parts = []
    ut = answers.get("useless_tools", {})
    wt = answers.get("wrong_thinking", {})
    it = answers.get("issue_type", {})
    sev = answers.get("severity", {})
    if isinstance(ut, dict) and ut.get("noul", 0) >= 0.7:
        parts.append("Useless tool calls detected")
    if isinstance(wt, dict) and wt.get("noul", 0) >= 0.7:
        parts.append("Wrong or circular thinking detected")
    choice = it.get("choice") if isinstance(it, dict) else None
    if choice and choice != "none":
        parts.append(f"Issue: {choice.replace('_', ' ')}")
    score = sev.get("score") if isinstance(sev, dict) else None
    if score is not None and score >= 0.66:
        parts.append("High time waste")
    if not parts:
        return "Agent behavior looks reasonable."
    return "; ".join(parts)


def review(agent_filter=None, limit=MAX_EVENTS, model=DEFAULT_MODEL):
    global MAX_EVENTS
    MAX_EVENTS = max(1, min(limit, 40))
    records = _tail_lines(RECORDS)
    if not records:
        records = _tail_lines(FINDINGS)
    state, count = _build_state(records, agent_filter)
    out = {
        "ok": False,
        "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_count": count,
        "agent": agent_filter,
        "answers": None,
        "model": None,
        "summary": None,
        "error": None,
    }
    if not state:
        out["error"] = "no agent events found in numbat records"
        return out
    api_key = _api_key()
    if not api_key:
        out["error"] = "OPENROUTER_API_KEY not set"
        return out
    try:
        resp = _ask_jev(state, model, api_key)
    except urllib.error.HTTPError as exc:
        out["error"] = f"Jev HTTP {exc.code}: {exc.read().decode()[:160]}"
        return out
    except Exception as exc:
        out["error"] = _clean(str(exc), 160)
        return out
    out["ok"] = True
    out["answers"] = resp.get("answers")
    out["model"] = resp.get("model")
    out["summary"] = _human_summary(out["answers"] or {})
    return out


def main():
    agent = None
    limit = MAX_EVENTS
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--agent" and i + 1 < len(args):
            agent = args[i + 1]
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1
    sys.stdout.write(json.dumps(review(agent_filter=agent, limit=limit)) + "\n")


if __name__ == "__main__":
    main()
