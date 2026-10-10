---
title: "feat: GNOME-card polish + app aliasing for lukedaduke.fan"
date: 2026-10-10
type: feat
depth: standard
---

# feat: GNOME-card polish + app aliasing for lukedaduke.fan

## Summary

Rework the Resource & Fan panel (`plugins/lukedaduke.fan`) toward a
GNOME/Mission-Center visual language — rounded cards per metric, big
numerals, filled graphs — while turning the process list into a trustworthy
kill tool: every process gets a friendly alias, disambiguated backends
(Ollama's spawned `llama-server` vs. the user's own `llama.cpp` builds get
different names), hover reveals the technical identity, and the kill path
shows exactly which process dies. Picked over btop-dense and
Activity-Monitor-table directions from an HTML mock board.

## Problem Frame

v2.4.0 shipped friendly names, `/` find, and kill-by-`x`. Residual gaps:

- The panel is section-stack QML from before the redesign — functional but
  plain; the user wants the card look.
- `FRIENDLY_NAMES` is a flat `comm → label` map (~35 entries). Two
  `llama-server` processes with different owners (Ollama backend vs.
  `~/src/llama.cpp` wisp fleet) get the same label — wrong when the list
  is also the kill surface.
- Raw `comm` is burned into every row's second text span, spending
  horizontal space to show identity continuously. Better: friendly name in
  the row, full technical identity on hover.
- Kill has no confirmation. `x` / `Ctrl+X` SIGTERMs the selected row
  immediately; with look-alike backend processes that's a footgun.
- No history or I/O surfaces: temps/load are point-in-time; net and disk
  rates are absent entirely.

## Requirements

- **R1** — Visual language: rounded cards per metric group (Memory, CPU,
  Thermals, Fan, Processes), big numerals with small units, small filled
  sparkline where history exists, color-dot process rows. All theming via
  `qs.Commons` `Color`/`Style` — no hardcoded hex (AGENTS.md rule).
- **R2** — Every process row shows a friendly alias. Unknown comms keep the
  raw name (title-cased light transform acceptable), never an empty label.
- **R3** — Rule-based disambiguation: display name resolution may match on
  `comm`, `exe` path, and `cmdline` patterns — Ollama's runner renders as
  "Ollama Backend"; the user's llama.cpp servers render as
  "llama.cpp {model-basename} (:port)" derived from their own argv.
- **R4** — Hover on a process name shows technical identity: `comm`, exe
  path, pid, RSS, and clipped cmdline. Row keeps only the alias + values.
- **R5** — Kill is armed-confirm: activating kill (button or `x`/`Ctrl+X`)
  first switches the row into a confirm state naming the exact target
  (alias + `comm` + pid); a second activation sends SIGTERM. Confirm
  expires after ~3 s. Identity is visible at the kill point — no hidden
  footgun.
- **R6** — New sensors, gracefully degraded: network up/down rates
  (`/proc/net/dev`), disk read/write rates (`/proc/diskstats`), and a
  collector-side ring buffer (~60 samples) so CPU/load/temp sparklines
  have history. Absent sources degrade to `--`, never errors.
- **R7** — `resources.json` `names` map stays backward compatible:
  `"comm": "Label"` still works; additionally accept
  `"rules": [{"match": {"comm"|"exe"|"arg": "…"}, "name": "…"}]`
  evaluated before built-ins.
- **R8** — Bounded payload discipline holds (`_clip`, `MAX_*`); collector
  stays in its sampling budget; helpers remain `/usr/bin/python3`
  absolute-exec with pinned PATH.

## Key Technical Decisions

- **KTD1 — identity resolution order.** `display_name(comm, exe, args)`:
  user rules → built-in rules → built-in comm map → title-case(comm).
  Built-in rules are data, not code: a `NAMING_RULES` list of
  `{"comm": ..., "exe_contains": ..., "arg_contains": ..., "name": ... or
  callable}` entries. Ollama detection: `exe`/`cmdline` contains
  `ollama` → "Ollama Backend". llama.cpp: `comm == llama-server` and exe
  contains `llama.cpp` → derive `llama.cpp {basename -m model}` +
  `(:--port)` when present. Rejected: name-by-port alone — model name is
  more informative and equally parseable.
- **KTD2 — collector emits identity fields per row.** `top_mem` and
  `--find` rows gain `comm`, `exe` (basename of `/proc/pid/exe` or
  `ps -o comm`+args already collected), `args` (clipped), `unit` (cgroup
  leaf when cheaply readable — skip if it costs a second proc call).
  Tooltip and kill-confirm render from these — no second lookup at hover
  time. Rejected: lazy per-row proc reads in QML (spawns processes on
  hover in the long-lived shell).
- **KTD3 — tooltip is a QML overlay, not shell tooltipText.** `Ui.Button`'s
  built-in tooltip is button-scoped; rows are Text delegates. A small
  reusable hover overlay (`MouseArea` + `Timer` delay ~350 ms + anchored
  Rectangle using `Color.tooltip.*` tokens) gives consistent placement for
  name-hover AND the armed-kill hint.
- **KTD4 — armed-confirm in-row, no modal.** First kill activation toggles
  row into `armed` state (row tint → warn/bad token, label swaps to
  `Kill {alias} · {comm} · pid {n}?`); second activation within 3 s
  execs `kill_proc.py`. This keeps the keyboard path (`x`, `Ctrl+X`) and
  mouse path (× button) semantically identical — both arm first.
  Rejected: a separate dialog — heavier in Quickshell panels and breaks
  the keyboard flow.
- **KTD5 — rates are delta-sampled in the collector.** Net/disk counters
  need `(now - prev)/dt`; the collector is a long-lived sampler so it owns
  prev state. History ring: deque(maxlen=60) for cpu_load, cpu_temp,
  mem_used — emitted as bounded int arrays (`MAX_LIST` discipline).
  Rejected: panel-side history (panel isn't always open; gaps would lie).
- **KTD6 — keep the current data contract shape.** New fields are additive
  keys on existing JSON objects; the panel treats missing keys as absent
  (degradation), so an older collector against a newer panel can't crash
  and vice versa.

## Implementation Units

### U1 — Collector: identity model, rules, new sensors

**Files:**
- `plugins/lukedaduke.fan/bin/system_monitor_stats.py`
- `plugins/lukedaduke.fan/README.md` (config contract section)
- `tests/test_fan_stats.py` (+ new test module if cleaner)

**Approach:**
- Add `NAMING_RULES` (data-driven, per KTD1); rewrite `_display_name` to
  `display_name(comm, exe, args)` with the four-level resolution order.
- Extend `top_mem`/`--find` row builders to include `comm`, `exe`,
  clipped `args`, optional `unit`.
- Parse `resources.json` `rules` list alongside `names` (KTD7); malformed
  rules are skipped with the rule index in a stderr warning, never fatal.
- Add `/proc/net/dev` and `/proc/diskstats` delta samplers + the 60-sample
  ring buffer; emit `net`, `disk`, `history` keys when computable.
- Broaden `FRIENDLY_NAMES` toward full coverage of the machine's real
  fleet (the user's actual top-20 comms — chromium, qemu, devin, cursor,
  llama-server, quickshell, wispd, wispr-flow, node, python, docker,
  tailscaled, steam, spotify/spotifast, hermes, grok-bot, easyeffects,
  solaar, hyprland, Hyprland, freerdp/xfreerdp, nautilus, foot, gh, codex,
  claude, agy, gemini, 1password, thunderbird/slack-class browsers…).

**Test scenarios:**
- `display_name("llama-server", exe="…/ollama", args=…)` → "Ollama Backend"
- `display_name("llama-server", exe="~/src/llama.cpp/…", args="-m …/qwen3-4b-instruct-q4km.gguf … --port 8091")` → "llama.cpp qwen3-4b-instruct (:8091)"
- `display_name("unknown-thing", exe="…", args=…)` → falls through to `comm`
- User rule overrides built-in rule and built-in map
- Malformed `rules` entry → skipped, other rules still applied
- `net`/`disk`/`history` keys present on second sample, absent→`--` path intact
- Payload stays under `MAX_*` bounds with 32 find results

### U2 — Panel: GNOME cards, hover identity, armed-kill

**Files:**
- `plugins/lukedaduke.fan/Panel.qml`

**Approach:**
- Restructure `mainColumn` sections into card `Rectangle`s (radius from
  `Style`, `panel2`-equivalent surface token, inner padding): Memory
  (big numeral + filled bar), CPU (big % + per-core grid stays inside
  card, sparkline if `history` present), Thermals, Fan (big rpm +
  segmented preset row), Processes (search row + rows).
- Process delegate → dot + alias + cpu/mem values + ×. Dot color: cycle a
  small token palette (or severity-ish: bad when cpu≥50 as today).
- Hover overlay (KTD3): on name-hover, delayed identity card — `comm`,
  exe, pid, rss, clipped cmdline — styled from `Color.tooltip.*`.
- Armed-kill (KTD4): `armedPid` property; ×/`x`/`Ctrl+X` sets it (row
  shows confirm text + warn tint); second hit calls existing
  `killProcess()`; `Timer` clears after 3 s; Esc cancels arm.
- Net/disk mini-cards rendered only when keys present (degradation R6).

**Test scenarios:**
- Live shell reload clean (`hyprctl`/`omarchy-restart-shell` — QML has no
  standalone linter; reload is the parser per AGENTS.md)
- Panel within bounds: no text escapes card borders at min width (the
  v2.4.0 elastic-column bug must not regress — keep `Text.ElideRight`)
- Hover shows identity; leave/scroll dismisses
- Arm → confirm kills the right pid (verify via a sacrificial `sleep 999`)
- Arm → timeout → returns to normal row, no kill sent
- Find mode: armed row hidden when filter changes (arm clears on filter
  edit)
- Missing `net`/`disk`/`history` keys → cards absent, no errors

### U3 — Ship: version, docs, deploy

**Files:**
- `plugins/lukedaduke.fan/manifest.json` (2.4.0 → 2.5.0)
- `plugins/lukedaduke.fan/ROADMAP.md` (tick shipped items)
- `plugins/lukedaduke.fan/README.md` (screenshot/preview refresh note)
- `~/.config/omarchy/resources.json` on omarchy-max (deploy-side only —
  add `rules` example for Ollama vs llama.cpp if desired)

**Approach:**
- Bump manifest version (behavior change per AGENTS.md).
- Deploy umbrella→live plugin dir; `omarchy-restart-shell`; verify panel.
- `python3 scripts/validate-manifests.py && python3 -m pytest tests/ -q`.

**Test scenarios:**
- validate-manifests clean; pytest suite green (57 existing + new U1)
- Live panel renders cards, aliases, hover, armed-kill against real procs

## Deferred

- Per-process GPU-client highlighting (needs asahi fdinfo — tracked in
  `docs/plans/2026-09-20-001-feat-gpu-monitoring-plan.md`)
- Sort toggle (cpu vs mem) — ROADMAP already lists it; this batch is full
- Fan-curve editor / GPU-specific curves / hibernation-aware auto curve
- Pressure/PSI deep RAM view
- Marketplace submission preview.png refresh (blocked on visual settle)

## Risks

- **Tooltip overlay vs. panel clipping** — the dropdown clips children;
  identity card must anchor inside the panel surface, not float outside.
  Mitigate: anchor to row edge inside the scroll view, capped width.
- **Rule matching on `args`** — cmdline can be huge/sensitive; keep
  `_clip` at same bounds as today, and match only on basename/first arg
  where possible.
- **Armed-kill + find-results race** — list reorders on each sample;
  arm state keyed by `pid`, not index, or a resort silently re-arms the
  wrong row. Tested in U2 scenario list.
- **Collector ring buffer growth** — 60-sample deques are bounded; do not
  let history keys exceed `MAX_LIST` (they're small ints — fine, but keep
  the discipline explicit).
