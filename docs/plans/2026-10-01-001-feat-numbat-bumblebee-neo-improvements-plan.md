---
title: Numbat + Bumblebee + BrowserOS neo — improvement tracks
date: 2026-10-01
status: planned
type: feat
repos:
  - duketopceo/omarchy-plugins (authoring; subtree-publishes to omarchy-numbat, omarchy-bumblebee, and a new omarchy-neo standalone)
  - duketopceo/omarchy-browser (fork of browseros-ai/BrowserOS — upstream PR source)
  - ~/.local/share/browserclaw + ~/.config/systemd/user (local neo sidecar, not a git repo)
---

# Numbat + Bumblebee + BrowserOS neo — improvement tracks

Four tracks, one plan. Tracks A and B are Omarchy plugins authored in the
`omarchy-plugins` umbrella and subtree-published. Track C is a new plugin plus
local-sidecar discoverability. Track D is upstream work in the BrowserOS fork
and perplexityai repos.

## Constraints carried forward

- **Edit in the umbrella, publish via `scripts/publish.sh <name>`** — commits
  made directly to `omarchy-numbat`/`omarchy-bumblebee` standalone repos are
  deleted by the next subtree publish. This already happened once (Unit A1).
- QML can't be checked outside Omarchy (`qs.*` imports); validation is
  `python3 scripts/validate-manifests.py` + `python3 -m pytest tests/ -q` from
  the umbrella, plus `py_compile` on helpers.
- Helpers stay stdlib-only, bounded stdout, descriptor-relative file opens,
  `O_NOFOLLOW`, owner checks. Child `PATH` pinned, helpers exec'd by absolute
  path.
- `manifest.json` `id`, folder name, `moduleName`, `ipcTarget` all agree;
  `io.github.duketopceo.*` for the perplexityai-wrapped family.
- Bump `version` in `manifest.json` on behavior change.
- Plugins are observe-only for upstream data dirs — no writes under
  `~/.numbat/`; bumblebee writes only its own state dir.
- Neo sidecar must stay separate from the canonical main BrowserOS stack
  (:9200/:9107/:9108). Sidecar ports: MCP 9211, shim 49338, chromium 49337.
- `--disable-extensions-except=<claw ext>` is load-bearing on the sidecar —
  Omarchy force-installs 1Password via `/usr/share/chromium/extensions/` which
  deadlocks navigation on fresh profiles.

## Track A — Numbat (`plugins/io.github.duketopceo.numbat/`)

Live: enabled, numbat 0.2.0, 12 agents hooked, `records.ndjson` streaming.
Known problems: Jev feature already erased by a publish; record file is
111MB and unbounded; 256KB tail now covers ~40min of stream.

- [ ] **A1. Recover the Jev review tab into the umbrella.** Source of truth is
  the orphaned commit `392be0a` (branch `cursor/jev-agent-review-14fe` on
  `duketopceo/omarchy-numbat`) — `Panel.qml` +144 lines and new
  `bin/jev_review.py` (247 lines, TypeSafe Jev via OpenRouter decisions API).
  Cherry-pick into `plugins/io.github.duketopceo.numbat/`, verify against
  current Panel structure (it may conflict with post-Jev edits), add umbrella
  test coverage under `tests/`, republish. Version bump.
- [ ] **A2. Widen the live tail.** `TAIL_BYTES` 256KiB→1MiB in
  `bin/probe_numbat.py` (~40min → ~2.5h of stream at current ~9MB/day rate).
  Bounded already; comment update + test assert.
- [ ] **A3. Surface record-file health.** Log tab row: `records.ndjson` size +
  estimated growth/day + rotation hint text when size > 512MB ("numbat has no
  rotate command; `mv ~/.numbat/records.ndjson ~/.numbat/records.old` to reset
  — the plugin will never write there itself"). `tail` already emits
  `records_bytes`; Panel renders it.
- [ ] **A4. Agent drill-down via `numbat timeline`.** New helper mode wrapping
  `numbat timeline --agent <name>` (bounded 20s, MAX_OUT_BYTES), per-agent
  "session" view on Activity-tab agent click. Defer if upstream output shape
  proves unstable — verify against 0.2.0 first.
- [ ] **A5. Small robustness pass.** `_hooked_agents` `"not" not in
  split()[1:3]` is brittle — parse the status table structurally. Toast click
  currently dismisses; add a secondary action opening the panel dropdown.
- [ ] **A6. (stretch) `numbat ship` → Kurultai.** Upstream ships a tail-to-HTTP
  record forwarder — point it at the personal Kurultai lane so findings become
  knowledge atoms. Needs a Kurultai ingest endpoint decision first; plan unit
  is investigation + config, not plugin code.

## Track B — Bumblebee (`plugins/io.github.duketopceo.bumblebee/`)

Live: enabled, last scan today clean, catalog 2,151 entries (7 bundled +
upstream merged). Known gap: `refresh_catalog.py` exists but Service.qml never
calls it — catalog staleness depends on a human remembering.

- [ ] **B1. Catalog auto-refresh in the service.** On a stale threshold
  (catalog_refresh_age > 7d), exec `bin/refresh_catalog.py` with the same
  bounded-child contract (absolute path, scrubbed env, deadline, byte cap).
  Read-only merge into `catalog.d/` is within contract — it's plugin state,
  not upstream data. Guard: never block scans on refresh failure.
- [ ] **B2. Catalog visibility row.** Panel dropdown: entries count, sources
  split (bundled/catalog.d/upstream), `catalog_refreshed_at`, last-scan age.
  All fields already emitted by the helper — pure UI work.
- [ ] **B3. Scan-log surface.** `scan-log.json` (rolling 20) is emitted as
  `log[]` in the payload but likely unrendered — verify and add a compact
  Log/History section if missing.

## Track C — Neo local: bar plugin + agent discovery

Live: three user units (`browserclaw-{chromium,shim,server}`) on
49337/49338/9211, hardened, `WantedBy=default.target`, bounded
(StartLimit 5/60s, MemoryMax 2G/512M). MCP verified end-to-end.

- [ ] **C1. New plugin `io.github.duketopceo.neo`** (bar-widget + service, same
  dual pattern as numbat/bumblebee — service owns polling, panel renders).
  Helper `bin/probe_neo.py` (stdlib-only): systemd `--user` unit states via
  `systemctl`, port listeners via `/proc/net/tcp` or `ss`, sidecar.json parse.
  Dropdown: unit states, ports bound, restart/stop buttons (`systemctl --user
  restart browserclaw-*` via Process), "open cockpit" action
  (`chrome-extension://` newtab or `xdg-open` to the extension page), config
  file path display. Glyph tints when any unit is down.
- [ ] **C2. Agent discovery — MCP self-description gap.** Verified: the server
  already returns `instructions` on `initialize` (product description) — but
  nothing identifies *this machine's* deployment (ports, units, healthcheck,
  skill name). Options in order of preference: (a) a `neo` entry in the plugin
  panel (C1) that humans see, plus (b) a `browserclaw` section appended to the
  `browseros-neo` skill files documenting the healthcheck
  (`curl -sf http://127.0.0.1:9211/mcp` 406-expectation, unit names, restart
  commands), and (c) an AGENTS.md under `~/.local/share/browserclaw/` for
  repo-index-style discovery. The binary itself can't be patched — any
  richer MCP introspection would need a pass-through proxy, which is out of
  scope unless discovery gaps prove real.
- [ ] **C3. (stretch) Sidecar→main-browser wiring.** Point the hardened shim at
  the main BrowserOS chromium so neo drives real logged-in sessions. Blocked
  on a decision: agent traffic in the user's live browser. Document the
  toggle, don't enable by default.
- [ ] **C4. (stretch) Local arm64 branded build** — only if upstream #2794 is
  declined and a real need emerges; ~100GB checkout, hours of build on M1 Max.

## Track D — Upstream

- [ ] **D1. Port the shim hardening into `omarchy-browser`** — the three fixes
  proven in `~/.local/share/browserclaw/bin/cdp-shim.js`: (1) queue passthrough
  WS sends until upstream `open` (drops `Target.setDiscoverTargets` race),
  (2) numeric i64 tabId↔targetId mapping (serde rejects hex strings), (3)
  `isHidden` on `TabInfo`. Canonical shim lives in the browseros-agent
  package; per `packages/browseros-agent/CLAUDE.md`: `bun run check` +
  `bun run test` before push, Bun, extensionless TS imports. PR upstream to
  `browseros-ai/BrowserOS` after fork verification — this is the cheapest
  real "Linux option" contribution (stock-chromium compatibility).
- [ ] **D2. Monitor #2794 (arm64 linux lane).** If maintainers engage, the PR
  is a small matrix change (`arch: [x64, arm64]` + runner label) — contingent
  on their WarpBuild pool having arm64 runners.
- [ ] **D3. File perplexityai/numbat issue**: `records.ndjson` retention —
  no rotate/prune exists; ~9MB/day unbounded growth makes a built-in
  `numbat records prune`/rotation flag worth requesting.
- [ ] **D4. Document the force-extension deadlock** in the neo plugin README
  (C1) — Omarchy-style `/usr/share/chromium/extensions/` force-installs can
  stall fresh-profile navigation; `--disable-extensions-except` is the
  workaround. Optionally file against chromium/omarchy if reproducible
  minimal.

## Sequencing

1. **A1 first** — provenance leak: every day the Jev code isn't in the
   umbrella, a casual publish risks re-erasing it.
2. C1+C2 — new plugin, self-contained, visible payoff.
3. A2+A3+B1+B2+B3 — bounded improvements, one umbrella PR each track or one
   combined if they land same-day.
4. D1 — upstream contribution, needs its own review cycle.
5. A4, then stretches (A6, C3, C4) and D3/D4 as housekeeping.

## Verification

- Umbrella: `python3 scripts/validate-manifests.py`, `python3 -m pytest tests/ -q`,
  `python3 -m py_compile bin/*.py` per plugin.
- Live: plugins enabled; numbat Log tab shows STREAMED + file size row;
  bumblebee catalog row shows refreshed_at after B1 fires; neo glyph reflects
  `systemctl --user stop browserclaw-server` within one poll.
- Neo MCP: `initialize` → `tabs new` → snapshot on a real page (the harness
  used all session).
- D1: `bun run check && bun run test` in omarchy-browser; upstream PR body
  describes the three fixes with repro.
