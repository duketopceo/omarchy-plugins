---
title: "feat: GPU monitoring in lukedaduke.fan panel"
date: 2026-09-20
type: feat
depth: standard
---

# feat: GPU monitoring in lukedaduke.fan panel

## Summary

Extend the `lukedaduke.fan` plugin's system stats so the panel shows real GPU
telemetry on this machine (Asahi `apple-agx` / t6001, M1 Max): utilization
percent when the kernel exposes it, GPU temperature, and SoC/heatpipe power as
context — alongside the existing CPU/RAM/fan rows. This is the first slice of a
broader resource-monitoring upgrade (RAM detail and a better process-kill view
are explicitly out of scope for this plan).

## Problem Frame

`bin/system_monitor_stats.py::gpu_info()` (line ~434) detects NVIDIA, AMD, and
Apple Silicon, but on Asahi it returns `(name, None, cpu_temp)` — the GPU row in
`Panel.qml` can never show utilization, and its temperature is just the shared
die temp. The user wants GPU usage "watched better" — a live utilization signal
and whatever power/thermal data the platform actually exposes.

Verified on-device telemetry (kernel 7.1.13-asahi, omarchy-max):

- DRM card: `/sys/class/drm/card1` (`apple,agx-t6001`), render node
  `/dev/dri/renderD128`.
- `/sys/class/devfreq/` — empty. No frequency/load sysfs surface.
- `macsmc_hwmon` (`/sys/class/hwmon/hwmon2`) — `power4_input` is
  "Heatpipe Power" (SoC package proxy); temps are NAND/battery/charger/WiFi
  only. No GPU-labelled sensor.
- `/proc/<pid>/fdinfo` on live `renderD128` clients shows no `drm-*` keys —
  asahi DRM fdinfo does not appear active on this build. Must be re-verified at
  implementation time; it is the only path to a true per-client busy%.

## Requirements

- R1. GPU row shows utilization % when a usable source exists on the host, not a
  hardcoded `--`.
- R2. GPU temp shown when any GPU-adjacent sensor exists; fall back to die temp
  with the same behavior as today.
- R3. Heatpipe/package power (watts) surfaced as GPU-adjacent context on Asahi.
- R4. Graceful degradation on non-Asahi hosts: NVIDIA/AMD paths unchanged, no
  new errors when a source is absent.
- R5. Stats payload remains bounded (existing `_clip`/`MAX_*` discipline) and
  the collector stays under its sampling budget.

## Key Technical Decisions

- **KTD1 — probe chain, not a single source.** `gpu_info()` becomes a small
  probe chain for Asahi: DRM fdinfo aggregate busy% → devfreq `load` → `None`.
  Rationale: Asahi's utilization surface varies by kernel build; probing keeps
  the panel correct everywhere instead of betting on one interface. Rejected:
  root-only debugfs (`/sys/kernel/debug/dri`) — the daemon and panel run
  unprivileged; rejected for security and portability.
- **KTD2 — fdinfo deltas sampled inside `collect()`.** If fdinfo keys exist,
  busy% = `Δ(drm-cycles) / Δ(wall) / num_engines` style aggregation across all
  clients holding `renderD128` fds. Rejected alternative: shelling out to
  `ashtop`/external tools — not installed, and `SAFE_PATH` discipline forbids
  environment-dependent helpers.
- **KTD3 — heatpipe power as the SoC-power readout.** `power4_input`
  ("Heatpipe Power") is the only GPU-adjacent power signal; reported as
  `gpu_power_w` (micro→watts), labelled honestly as package/heatpipe power, not
  a dedicated GPU rail. Rejected: calling it "GPU power" — it is not
  GPU-isolated.
- **KTD4 — new fields, same schema shape.** `collect()` gains
  `gpu_load` (int|None), `gpu_temp` (str), `gpu_power_w` (float|None),
  `gpu_engine` per-source note only if free; existing keys unchanged so older
  panels don't break.

## Implementation Units

### U1. Asahi GPU probe chain in `system_monitor_stats.py`

**Goal:** real `gpu_load` on Asahi when the kernel exposes it; power readout.

**Requirements:** R1, R2, R3, R4, R5

**Files:**
- `plugins/lukedaduke.fan/bin/system_monitor_stats.py` (modify)
- `tests/test_fan_stats.py` (extend)

**Approach:**
- Add `read_drm_fdinfo()` — iterate `/proc/[0-9]*/fd/*` symlinks matching
  `renderD*`/card nodes, read matching `fdinfo` entries, extract
  `drm-engine-*`/`drm-cycles-*` counters into `{fd: cycles}`. Skip silently on
  `PermissionError`/`FileNotFoundError`. Keep the scan cheap: resolve fd links,
  only read fdinfo for DRM fds.
- Keep a module-level `_PREV_GPU_CYCLES` snapshot (same pattern as
  `_read_cpu_stats`'s two-sample approach): first `collect()` call records
  counters, busy% computed on subsequent calls; within one call, do a
  `SAMPLE_SECONDS` two-sample read like `_read_cpu_stats` so a single CLI
  invocation still yields a number when counters move.
- Add `read_macsmc_heatpipe_power()` — glob `hwmon*/power*_input` whose label is
  "Heatpipe Power"; return watts. None if absent.
- Rewire `gpu_info()` Asahi branch (branch 3): name as today; `gpu_load` from
  fdinfo util → devfreq `load` (e.g. `*/load` `util@freq` format) → `None`;
  temp unchanged (die temp); return `gpu_power_w` via an expanded tuple or a
  dict — prefer a small dict return and update the two call sites.

**Patterns to follow:** `_read_cpu_stats` two-sample delta pattern; `_run` /
`_tool` SAFE_PATH helpers; `hwmon_paths` glob style.

**Test scenarios:**
- fdinfo fixture with two clients: second sample yields aggregate busy% in
  0–100; single-call path returns a number, not `None`, when counters move.
- fdinfo keys absent (current kernel reality): `gpu_load` is `None`, no
  exception, collect() completes.
- fdinfo present but all `PermissionError`: same graceful `None`.
- Heatpipe label present → watts float ≈ input/1e6; label absent → `None`.
- NVIDIA branch unchanged: mock `nvidia-smi` output still parses (existing
  tests must keep passing).
- Non-DRM fds (regular files) ignored by the fd scan.

**Verification:** `pytest tests/test_fan_stats.py` green; on-device
`bin/system_monitor_stats.py` emits `gpu_power_w` ≈ 15–20 W at idle and
`gpu_load` either a real % or `null` (documented which, from live output).

### U2. Panel.qml GPU row upgrade

**Goal:** show utilization and power in the GPU section; honest `--` when
utilization is unavailable.

**Requirements:** R1, R2, R3, R4

**Files:**
- `plugins/lukedaduke.fan/Panel.qml` (modify)

**Approach:**
- GPU row gains a utilization percentage (same meter style as CPU per-core
  bars) driven by `gpu_load`; render `--` when null rather than 0%.
- Secondary label: watts when `gpu_power_w` present (`"pkg 18.4 W"` style,
  matching existing compact label conventions), temp as today.
- Theme with `qs.Commons` `Color`/`Style` only — no hardcoded hex
  (repo rule).

**Test expectation:** none — QML panel has no test harness; verification is
visual on the live bar.

**Verification:** reload the panel on omarchy-max; GPU row shows real data
(power at minimum) and does not regress CPU/RAM/fan rows.

### U3. README/ROADMAP note

**Goal:** document which GPU signals exist on Asahi and their limits.

**Files:**
- `plugins/lukedaduke.fan/README.md` (modify, small)
- `plugins/lukedaduke.fan/ROADMAP.md` (modify, small)

**Approach:** one short section: GPU util = fdinfo-dependent (kernel build
dependent), power = heatpipe proxy, temp = die temp shared with CPU. Note the
RAM-detail and process-kill upgrades as next planned slices.

**Test expectation:** none — docs only.

## Scope Boundaries

- RAM detail view, cross-resource usage summary, and the better process-kill
  UX are **deferred to follow-up work** — user asked for GPU first, then a
  review stop.
- No changes to `omarchy-fan-daemon` fan-curve logic.
- No new external tool dependencies; everything via `/proc`/`/sys`.
- No root-required sources (debugfs).

## Open Questions

- Does this exact asahi kernel build emit `drm-*` fdinfo keys under load (e.g.
  a glxgears/vkcube run)? Implementation answers this; the plan handles both
  branches so either outcome ships.

## Risks

- fdinfo genuinely absent → `gpu_load` stays `null`; the deliverable then is
  power + honest display, and the plan still ships value. Mitigation: U1
  verifies on-device and the README states the reality.
- `/proc` fd scan cost: bounded — resolve fd links only, read fdinfo only for
  DRM fds, single pass per collect cycle (~1s cadence).
