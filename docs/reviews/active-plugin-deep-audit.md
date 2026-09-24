# Active plugin estate — deep audit

Snapshot: 2026-09-23 22:03 local time
Mode: read-only audit; no host-owned Omarchy source or external checkout was modified.

This report complements the generated [`active-plugin-estate.md`](active-plugin-estate.md)
inventory. It records runtime ownership, migration state, host integration, and
owner handoffs without committing raw paths, command output, credentials, or
user data.

## Executive result

- **70** plugin IDs are discovered, **49** are registry-enabled, **29** are in
  the direct bar layout, **20** are enabled non-bar surfaces, and **2** are
  hosted by the custom tray.
- **0** duplicate manifest IDs and **0** inventory warnings remain after the
  supported installer migration.
- The fixed service probe reports six active owners: Dayflow, Voxtype,
  Omaphones, Hyprmoncfg, the fan system helper, and EasyEffects.
- Voxtype is the active default voice owner; Dim is installed but its service is
  inactive. This preserves the one-voice-owner policy without a second recorder.
- The host integration check is healthy across audio, Bluetooth, display, and
  input. This is dependency health, not proof that every plugin's own data
  refresh is healthy.
- Legacy plugin backups now live in the state backup area rather than the
  discovery root. Three rollback artifacts are retained there; no `*.bak.*` or
  hidden backup directory remains discoverable.
- The owned umbrella contract scan has **0 errors** and **2 intentional
  warnings**. A broad non-backup external/local scan has **706 findings**; those
  remain owner handoffs, not changes to make in this repository.

## Runtime ownership

`active` below means `systemctl is-active` returned `active`; it does not imply
that a service has successfully refreshed remote data or completed a UI-level
workflow. The collector intentionally keeps that distinction in the health
model.

| Plugin ID | Unit | Scope | Observed state | Interpretation / next action |
|---|---|---|---|---|
| `hancore.voxtype-enhance` | `voxtype.service` | user | active | Default voice owner; keep microphone ownership exclusive. |
| `io.github.duketopceo.dayflow` | `dayflow-capture.service` | user | active | Capture is live; owner review still required for retention, storage, and optional egress. |
| `io.github.duketopceo.dim` | `dimd.service` | user | inactive | Alternate voice stack is stopped and must remain opt-in. |
| `io.github.ncr.omaphones` | `bt-agent.service` | user | active | Bluetooth battery/ANC helper is loaded; continue BlueZ/hidpp lifecycle testing. |
| `crmne.hyprmoncfg` | `hyprmoncfgd.service` | user | active | Display manager is loaded; retain explicit managed/unmanaged state. |
| `lukedaduke.fan` | `omarchy-fan-daemon.service` | system | active | Root writes belong to the separately owned system/polkit boundary; the plugin remains the telemetry surface. |
| `ssupt.audio-control` | `easyeffects.service` | user | active | DSP dependency is loaded; preserve a basic-audio fallback if EasyEffects fails. |

The user/system scope split is intentional. A healthy user service does not
prove that a privileged system unit is installed or running, and the fan
control path must not be auto-installed by opening a panel.

## Migration and source integrity

- The supported `scripts/install.sh --link` path moved the legacy hidden Dayflow
  backup and the older `lukedaduke.connections` / `lukedaduke.power` backups to
  the external state backup root, then rescanned the shell.
- The live inventory now resolves one discoverable manifest per owned plugin.
  Backup directories remain available for rollback but cannot compete with the
  active source tree.
- The source-status probe marks these external/local checkouts as dirty:
  `akitaonrails.ai-usagebar`, `crmne.hyprmoncfg`,
  `io.github.duketopceo.dayflow`, `mohamedmansour.finance`, and `omaplug`.
  These are owner worktrees or release candidates, not permission to reset,
  stash, or overwrite them.
- Symlinked owned plugins may inherit the umbrella worktree's dirty status;
  that status must not be mistaken for proof that a separate standalone
  repository is clean. Release checks still need a fresh non-symlink copy.

## Host integration

The read-only host check returned overall `healthy`:

- **Audio:** PipeWire, WirePlumber, `wpctl`, and EasyEffects are healthy.
- **Bluetooth:** the adapter and `bt-agent.service` are healthy.
- **Display:** Hyprland monitor state and `hyprmoncfgd.service` are healthy.
- **Input:** accessible input-device entries are present.

A future check should add service-to-plugin recovery tests (stop/restart,
missing optional binary, stale data, and permission loss) without editing host
source or treating a healthy dependency as proof of plugin correctness.

## Contract and release posture

The broad external/local contract scan covers 23 non-backup plugin checkouts,
including disabled checkouts so stale copies cannot disappear from review:

| Rule | Findings | Handoff |
|---|---:|---|
| PlainText coverage | 611 | Patch owning QML; prioritize device, remote, configuration, and LLM text. |
| Timer budget review | 75 | Document bounded one-shot/UI lifetime or reduce permanent polling. |
| Fixed executable path | 18 | Replace ambient interpreter/shell invocation in the owning helper. |
| Minimal environment | 1 | Remove inherited secret-bearing environment from the helper. |
| HTTPS-only network code | 1 | Replace executable-code URL or document the safe boundary. |

The full owner breakdown and reproducibility command are in
[`active-plugin-contract.md`](active-plugin-contract.md). Raw findings remain
out of the repository because they can contain local paths or user-specific
values.

## Priority follow-ups

1. **Dayflow privacy and retention:** verify frame/database/backup budgets,
   pause/delete/export behavior, and optional summarization egress before any
   capture expansion.
2. **External text trust boundaries:** reduce the 611 PlainText findings in
   the owning repositories, starting with high-volume lock, audio, calendar,
   finance, and voice surfaces.
3. **Voice arbitration:** preserve Voxtype as the default, keep Dim stopped by
   default, and make any opt-in microphone handoff explicit and reversible.
4. **Release provenance:** produce clean non-symlink copies for dirty external
   candidates and reconcile the unused Tailscale clone with restore guidance.
5. **Privileged fan boundary:** keep telemetry unprivileged, require an
   explicit policy-gated action for root writes, and retain the documented
   stop/disable/remove rollback path.
6. **Contract scope:** decide whether disabled external checkouts should remain
   in the standing handoff or be moved to a separate archival report.

## Evidence commands

```sh
uvx --with pytest python -m pytest tests/ -q
python3 scripts/audit-live-plugins.py --format markdown \
  --output docs/reviews/active-plugin-estate.md
python3 scripts/check-host-integration.py --strict
python3 scripts/check-plugin-contract.py --format json
python3 scripts/check-plugin-contract.py \
  --plugin-root <live-plugin-root> --format json
```

The live inventory and host checks are intentionally read-only. The audit does
not claim a deployment, external pull-request approval, native UI screenshot,
or a change to any third-party repository.
