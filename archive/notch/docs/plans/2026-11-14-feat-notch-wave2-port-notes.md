# Wave2 → Island port notes (Phase B)

Branch: `feat/notch-wave2-island` from `origin/main` (pre-#67). Rebase onto `origin/main` only after PR #67 merges. Do not touch `feature/island-activity-merge`. Do not merge `wip/notch-*`.

Source: `local/notch-wave2` (`aaabf60`), commits not in `origin/main`. Phase C (Dayflow, pxl, tray, Blip/time ears, stock slide) stays off this PR.

Island ears live in `Island.qml` (`activities` → `Island.visible` → `win.segments` / `win.idleSlot`), not in `Notch.qml`. Cherry-pick pure modules. Rewrite every `Notch.qml` hunk into `Island.qml`.

## B1 — Settings sections + hideable / labeled tabs

| Commit | Subject | Action |
| --- | --- | --- |
| `5a22021` | setup strip scrolls, Done stays visible | Rewrite `SettingsTab.qml`. Cherry-pick `tests/test_notch_settings.py` additions. `Settings.js` may apply with a small conflict (island tip differs by ~11 lines). |
| `91255c3` | four sections, one switch per feature, hints | Cherry-pick `Segmented.qml`, `Settings.js`, `tests/test_notch_settings.py`. Rewrite `SettingsTab.qml` and the `Tabs.js` hint (wave2 `Tabs.js` is not the island file). |
| `4a4aa09` | labels for selected and most-used tabs, hideable tabs | Cherry-pick `Tabs.js` usage/hide logic and `tests/test_notch_tabs.py`. Rewrite `ExpandedPanel.qml` (island copy diverged). Rewrite the `Notch.qml` `noteTabUse` timer onto the Island expanded `onTabSelected` path. |
| `1200c88` | on-state pill for Swift and Pxl | Skip. Pxl pill; Phase C. |

## B2 — Clipboard (cliphist)

| Commit | Subject | Action |
| --- | --- | --- |
| `e59a8a7` | clipboard history tab | Cherry-pick `Clipboard.js`, `ClipboardTab.qml`, `tests/test_notch_clipboard.py`, `bin/notch-probe` cliphist lines. Rewrite `Tabs.js` registration, `Capabilities.js` if it conflicts, and the `ExpandedPanel.qml` / `PluginsTab.qml` one-liners. |
| `aaabf60` | fixture binding + action field cursor | Cherry-pick the `ClipboardTab.qml` binding after B2. The `SettingsTab.qml` cursor hunk belongs with B6, not a blind pick. |

## B3 — Timer / pomodoro ear

| Commit | Subject | Action |
| --- | --- | --- |
| `2f3d66d` | countdown and pomodoro with ear readout | Cherry-pick `Timer.js`, `TimerActivity.qml`, `TimerTab.qml`, `PillButton.qml`, `tests/test_notch_timer.py`, settings/tab test lines. Rewrite `Notch.qml`: add `{ id: "timer", ... }` to Island `activities` (priority from `TimerActivity`), and append `"timer"` to `win.idleSlot` only while `timerAct.inSlot`. Right-ear text (`Island.qml` ~515) must show `timerAct.slot` for that idle slot. `sideNeed` must include the timer string. Do not take the `Tk.qml` one-line from this commit (no `Tk.qml` on the island tip). |

## B4 — Charging ear

| Commit | Subject | Action |
| --- | --- | --- |
| `b3f3347` | percent and time to full on plug-in | Cherry-pick `ChargingActivity.qml`, `ChargeBolt.qml`, the `Power.js` delta (`Power.js` matches the island parent), `tests/test_notch_power.py`, settings test lines. Rewrite `Notch.qml`: Island `activities` entry `{ id: "charging", ... }`, and a `ChargeBolt` in the compact right ear when `segments[0].id === "charging"`. Island has one ear text path, not Notch's notched + virtual duplicate. |

## B5 — Volume / brightness HUD

| Commit | Subject | Action |
| --- | --- | --- |
| `ef2e06a` | HUD in the ear; Omarchy or Notch owns it | Cherry-pick `Hud.js`, `HudActivity.qml`, `HudMeter.qml`, `tests/test_notch_hud.py`, `Settings.js` `hudOwner` (default stays Omarchy). Rewrite `Notch.qml`: activities entry `{ id: "hud", ... }` only when `settings.hudOwner === "notch"`, and `HudMeter` beside the right-ear text when that segment is showing. Widen `sideNeed` for the meter (~44px in Notch). |

## B6 — Pinned Home actions

| Commit | Subject | Action |
| --- | --- | --- |
| `13fdba7` | pinned quick-actions row | Cherry-pick `Actions.js`, `ActionsState.qml`, `tests/test_notch_actions.py`, `Settings.js` quick-action keys. Rewrite `HomeTab.qml` (wave2 Home has Dayflow/`Tk`; island Home does not). Rewrite the Settings editor into the B1 `SettingsTab.qml`. Host `ActionsState` on `Island.qml` (Notch.qml only added the instance). |

## B7 — Type tokens / contrast

Do not cherry-pick these. They sit on `Theme.js` / `Tk.qml` / pxl and touch `Notch.qml` and `DayflowTab.qml` (Phase C). Island text should stay on `Commons.Color` from Phase A.

| Commit | Subject | Action |
| --- | --- | --- |
| `7d4dc6f` | AA contrast + type floors | Rewrite the `ensureContrast` idea only if Island text still follows a light-theme foreground on the dark island after A3. Do not add `Theme.js` or `Tk.qml`. |
| `c89c659` | Home type tokens + weather empty copy | Rewrite the empty-state sentence into island `HomeTab.qml`. Skip `Tk.*` swaps. |
| `e8d4fba` | Network 10px → tokens | Rewrite floors in `NetworkTab.qml` with the island type size already used on dashboard tabs (no new 8–10px literals). |
| `c4133de` | Stocks chart/row tokens | Same for `StocksTab.qml` and `CandleChart.qml`. |
| `e6cfc05` | Messages tokens + offline cause | Same for `MessagesTab.qml`, keep the cause sentence. |
| `cdc87aa` | Power sub-11px labels | Same for `PowerTab.qml`. |
| `ab9877d` | AI usage tokens | Skip. `AiUsageTab.qml` is not on the island tip. |
| `978c5b0` | Agents tokens + empty copy | Rewrite `AgentsTab.qml` floors and the empty sentence. |
| `2bbc956` | System spark/ring tokens | Rewrite the two pixel sizes in `SystemRing.qml` and `SystemSpark.qml`. |

## Not Phase B

Leave on `local/notch-wave2`: `6242855` Dayflow, `31b2944` / `bc70c70` pxl, `5bf24ee` tray host, `c6a565c`–`ee11ec4` stock slide and ear padding, `a0a6d91` time+date left ear, `9eca1a5` Blip right ear, `12ce69a` Dayflow empty copy, `c49f853` / `cd8143b` 5D stock default (out of this finalize).

## After rebase

1. Cherry-pick pure files in order B4 → B3 → B5 → B1 → B2 → B6, dropping `Notch.qml` / `Tk.qml` / `Theme.js` from each pick (`git cherry-pick -n` or path checkout from the commit).
2. One Island wiring commit for charging, timer idle slot, and HUD meter.
3. B7 as a contrast/floor pass on existing island tabs only.
4. `pytest` the notch tests these commits add: `test_notch_settings.py`, `test_notch_tabs.py`, `test_notch_clipboard.py`, `test_notch_timer.py`, `test_notch_power.py`, `test_notch_hud.py`, `test_notch_actions.py`, plus `test_notch_island.py` so the ear list still matches.
