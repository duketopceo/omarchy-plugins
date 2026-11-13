#!/usr/bin/env python3
"""agents-auth — report each agent CLI's login state as JSON.

Reads only what each CLI publishes about itself: its own `status`/`auth`
subcommand output and, where that does not exist, its version banner. Never
opens a credential file, never prints a token.

Emits:
  {"ok": true, "checked": <epoch>, "agents": [
      {"name":"claude","label":"Claude","lane":"personal",
       "state":"ok"|"expired"|"missing"|"unknown"|"broken",
       "identity":"luke.k@…","detail":"team plan",
       "lane_hint":"…"}, ...]}

`lane` is personal/work: Cursor is the only CLI on this machine that runs two
isolated profiles (personal ~/.config/cursor, work ~/.config/cursor-work), so it
reports twice. Everything else is single-lane and reported once.
"""
import json
import os
import re
import subprocess
import sys
import time

TIMEOUT = 22


def run(cmd, timeout=TIMEOUT):
    """Run a command, return (ok, combined_output)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"})
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "__timeout__"
    except FileNotFoundError:
        return False, "__missing__"
    except Exception as e:
        return False, f"__error__ {e}"


def clean(text, limit=90):
    t = re.sub(r"\s+", " ", (text or "")).strip()
    t = re.sub(r"\x1b\[[0-9;]*m", "", t)
    return t[:limit]


def masked_email(email):
    """Show enough of an address to tell accounts apart, not enough to leak."""
    if not email or "@" not in email:
        return None
    local, _, domain = email.partition("@")
    keep = local[:2] if len(local) > 2 else local[:1]
    return f"{keep}…@{domain}"


def mk(name, label, state, identity=None, detail="", lane="personal"):
    return {"name": name, "label": label, "lane": lane, "state": state,
            "identity": identity, "detail": detail}


# ---------------------------------------------------------------- probes


def check_claude():
    ok, out = run(["claude", "auth", "status"])
    if "__missing__" in out:
        return [mk("claude", "Claude Code", "missing")]
    if "__timeout__" in out:
        return [mk("claude", "Claude Code", "unknown", detail="timed out")]
    try:
        d = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        return [mk("claude", "Claude Code", "unknown", detail=clean(out, 60))]
    if not d.get("loggedIn"):
        return [mk("claude", "Claude Code", "expired", detail="not logged in")]
    plans = d.get("subscriptionType") or ""
    org = d.get("orgName") or ""
    return [mk("claude", "Claude Code", "ok", masked_email(d.get("email")),
               f"{org} · {plans}".strip(" ·"))]


def check_codex():
    ok, out = run(["codex", "login", "status"])
    if "__missing__" in out:
        return [mk("codex", "Codex", "missing")]
    if "__timeout__" in out:
        return [mk("codex", "Codex", "unknown", detail="timed out")]
    low = out.lower()
    if "not logged in" in low or "logged out" in low:
        return [mk("codex", "Codex", "expired", detail="not logged in")]
    if "logged in using chatgpt" in low:
        return [mk("codex", "Codex", "ok", "ChatGPT", "ChatGPT login")]
    if "api key" in low:
        return [mk("codex", "Codex", "ok", "API key", "key auth")]
    return [mk("codex", "Codex", "unknown", detail=clean(out, 60))]


def check_cursor(lane):
    """Cursor is the one CLI with two isolated profiles on this machine."""
    if lane == "work":
        cmd = [os.path.expanduser("~/bin/agent-work"), "status"]
    else:
        cmd = ["cursor-agent", "status"]
    ok, out = run(cmd, timeout=28)
    if "__missing__" in out:
        return [mk("cursor", "Cursor", "missing", lane=lane)]
    if "__timeout__" in out:
        return [mk("cursor", "Cursor", "unknown", lane=lane, detail="timed out")]
    low = out.lower()
    m = re.search(r"logged in as ([^\s,]+@[^\s,]+)", low)
    if m:
        return [mk("cursor", "Cursor", "ok", masked_email(m.group(1)), lane=lane)]
    if "not logged in" in low or "logged out" in low:
        return [mk("cursor", "Cursor", "expired", lane=lane, detail="not logged in")]
    return [mk("cursor", "Cursor", "unknown", lane=lane, detail=clean(out, 50))]


def check_devin():
    ok, out = run(["devin", "auth", "status"])
    if "__missing__" in out:
        return [mk("devin", "Devin", "missing")]
    if "__timeout__" in out:
        return [mk("devin", "Devin", "unknown", detail="timed out")]
    if "not logged in" in out.lower():
        return [mk("devin", "Devin", "expired", detail="not logged in")]
    email = re.search(r"Email:\s*(\S+@\S+)", out)
    tier = re.search(r"Tier:\s*(.+)", out)
    if email:
        return [mk("devin", "Devin", "ok", masked_email(email.group(1)),
                   clean(tier.group(1), 30) if tier else "")]
    return [mk("devin", "Devin", "unknown", detail=clean(out, 50))]


def check_gemini():
    ok, out = run(["gemini", "--version"])
    # `auth status` is what fails, but the version is what proves install
    ok2, out2 = run(["gemini", "auth", "status"])
    blob = (out + out2).lower()
    if "__missing__" in blob:
        return [mk("gemini", "Gemini", "missing")]
    if "ineligibletier" in blob or "no longer supported" in blob:
        return [mk("gemini", "Gemini", "broken",
                   detail="client unsupported; migrate to Antigravity")]
    if "not logged in" in blob or "authentication required" in blob:
        return [mk("gemini", "Gemini", "expired", detail="not logged in")]
    if ok2:
        return [mk("gemini", "Gemini", "ok")]
    return [mk("gemini", "Gemini", "unknown", detail=clean(out2 or out, 50))]


def check_copilot():
    ok, out = run(["copilot", "--version"])
    if "__missing__" in out:
        return [mk("copilot", "Copilot", "missing")]
    # Copilot CLI delegates auth to the gh CLI
    gh_ok, gh_out = run(["gh", "auth", "status"])
    m = re.search(r"account (\S+)", gh_out)
    if gh_ok and m:
        return [mk("copilot", "Copilot", "ok", m.group(1), "via gh")]
    if "not logged" in gh_out.lower():
        return [mk("copilot", "Copilot", "expired", detail="gh not logged in")]
    return [mk("copilot", "Copilot", "unknown", detail=clean(gh_out, 50))]


def check_amp():
    ok, out = run(["amp", "usage"])
    if "__missing__" in out:
        return [mk("amp", "Amp", "missing")]
    if "invalid or missing api key" in out.lower() or "login" in out.lower():
        return [mk("amp", "Amp", "expired", detail="no API key")]
    if ok:
        return [mk("amp", "Amp", "ok", detail=clean(out.splitlines()[0] if out else "", 40))]
    return [mk("amp", "Amp", "unknown", detail=clean(out, 50))]


def check_opencode():
    ok, out = run(["opencode", "auth", "list"])
    if "__missing__" in out:
        return [mk("opencode", "OpenCode", "missing")]
    if "__timeout__" in out:
        return [mk("opencode", "OpenCode", "unknown", detail="timed out")]
    providers = [l.split()[0] for l in out.splitlines()
                 if "stored" in l.lower() or "environment" in l.lower()]
    # collapse duplicates like "OpenRouter" appearing twice
    uniq = []
    for p in providers:
        if p.lower() not in [u.lower() for u in uniq]:
            uniq.append(p)
    if uniq:
        return [mk("opencode", "OpenCode", "ok", f"{len(uniq)} providers",
                   ", ".join(uniq[:3]))]
    return [mk("opencode", "OpenCode", "expired", detail="no providers configured")]


def check_droid():
    ok, out = run(["droid", "exec", "reply with just OK"], timeout=35)
    if "__missing__" in out:
        return [mk("droid", "Droid", "missing")]
    if "__timeout__" in out:
        return [mk("droid", "Droid", "unknown", detail="timed out")]
    low = out.lower()
    if "no active subscription" in low or "402" in out:
        return [mk("droid", "Droid", "expired", detail="no active subscription")]
    if "invalid api key" in low or "unauthorized" in low or "401" in out:
        return [mk("droid", "Droid", "expired", detail="invalid credentials")]
    if "ok" in low:
        return [mk("droid", "Droid", "ok")]
    return [mk("droid", "Droid", "unknown", detail=clean(out, 50))]


def check_pi():
    ok, out = run(["pi", "auth", "check", "--provider", "anthropic"])
    if "__missing__" in out:
        return [mk("pi", "Pi", "missing")]
    if "not_ready" in out:
        return [mk("pi", "Pi", "expired", detail="no provider ready")]
    if ok and "ready" in out.lower():
        return [mk("pi", "Pi", "ok")]
    return [mk("pi", "Pi", "unknown", detail=clean(out, 40))]


def check_grok():
    ok, out = run(["grok", "inspect"])
    if "__missing__" in out:
        return [mk("grok", "Grok", "missing")]
    m = re.search(r"Version:\s*(\S+)", out)
    if m:
        return [mk("grok", "Grok", "ok", None, f"v{m.group(1)}")]
    return [mk("grok", "Grok", "unknown", detail=clean(out, 40))]


def check_crush():
    ok, out = run(["crush", "--version"])
    if "__missing__" in out:
        return [mk("crush", "Crush", "missing")]
    return [mk("crush", "Crush", "ok" if ok else "unknown",
               None, clean(out, 30) if ok else "")]


def check_kilo():
    ok, out = run(["kilo", "--version"])
    if "__missing__" in out:
        return [mk("kilo", "Kilo", "missing")]
    return [mk("kilo", "Kilo", "ok" if ok else "unknown", None,
               clean(out.splitlines()[-1] if out else "", 20) if ok else "")]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd != "status":
        print(json.dumps({"ok": False, "error": f"unknown command {cmd}"}))
        return
    agents = []
    for fn in (check_claude, check_codex, check_devin, check_gemini, check_copilot,
               check_amp, check_opencode, check_pi, check_grok, check_crush,
               check_kilo, check_droid):
        try:
            agents.extend(fn())
        except Exception as e:
            agents.append(mk(fn.__name__, fn.__name__, "unknown", detail=str(e)[:50]))
    try:
        agents.extend(check_cursor("personal"))
        agents.extend(check_cursor("work"))
    except Exception as e:
        agents.append(mk("cursor", "Cursor", "unknown", detail=str(e)[:50]))

    order = {"broken": 0, "expired": 1, "missing": 2, "unknown": 3, "ok": 4}
    agents.sort(key=lambda a: (order.get(a["state"], 9), a["label"]))
    print(json.dumps({"ok": True, "checked": int(time.time()), "agents": agents}))


if __name__ == "__main__":
    main()
