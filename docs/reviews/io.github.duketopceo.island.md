# Review: io.github.duketopceo.island (omarchy-island)

Reviewed: pending · verdict: PENDING

Initial scorecard for the Island panel plugin. Criteria match the family
scorecard keys; assessment deferred until after the live hover check.

## Scorecard

See docs/SCORECARD.md for semantics.

```scorecard
{
  "plugin": "io.github.duketopceo.island",
  "criteria": {
    "no_open_hm_findings": "pending",
    "plaintext_external_text": "pending",
    "exec_discipline": "pending",
    "envelope": "pending",
    "fixture_tests": "pending",
    "visibility_gating": "pending",
    "stale_backoff": "pending",
    "readme_claims": "pending"
  },
  "manual": {
    "spawn_measurement": {
      "date": null
    },
    "asahi_pass": {
      "date": null
    },
    "x86_64_pass": {
      "date": null
    }
  },
  "notes": "Initial state: not yet assessed against docs/SCORECARD.md."
}
```

## Notes

### U1 live probes

Run 2026-11-15 on omarchy-max, Hyprland 0.57.2, eDP-1 only (3456x2234, scale 2, logical 1728x1117; DP-3 not connected).

| Question | Answer | Branch |
|---|---|---|
| Pointer move command | `hyprctl dispatch 'hl.dsp.cursor.move({ x = X, y = Y })'` moves the pointer (confirmed with `hyprctl cursorpos`); `hyprctl eval` with the same Lua returns `ok` but does not move it | KTD11: use `dispatch` |
| Does the move produce hover enter/leave? | Yes, once unlocked: the probe logged `hovered=true` on entry and `hovered=false` on exit (the first attempt ran on the lock screen and saw nothing) | KTD11 live check is viable |
| Layer Top covered by a fullscreen window | Moot: the island unmaps under real fullscreen (see AE6 below) | KTD6 |
| Leave after the mask shrinks under a still pointer | Yes: shrinking the mask from card to pill with the pointer in the dropped area produced `hovered=false` 2 ms later | KTD3 cursor re-check fallback not needed; removed |
| `HyprlandFocusGrab` clears by itself | No (held 8 s). But while the grab is active Hyprland sends no pointer leave: the pointer moved outside and `hovered` stayed true | KTD5 fallback: `OnDemand` focus without a grab, so a focused card still closes on leave |
| Island vs bar stacking | The bar is a full-screen-sized layer-2 (Top) surface. A probe on Top drew above the bar's icons and took the pointer at the bar center (icon pixels measured pink under the 50% red probe), but only because it mapped after the bar; that order is not guaranteed across shell restarts. Overlay (level 3) sits above the bar by layer | KTD1 fallback: layer Overlay |

### Live verification (P1, eDP-1)

| Check | Result |
|---|---|
| Plugin loads | `omarchy-island` mapped on layer 3 at 744x392; no Island errors in the shell log |
| Pill | Time and short date ears render (screenshot) |
| AE1, AE2 hover open/close | `bin/island-hover-check --runs 20 --mode both`: 20/20 passed, single jumps and interpolated steps |
| AE3 click-open and pin, AE5 Esc with rearm | Not automated: needs `ydotoold` (disabled on this host); manual pass pending |
| AE4 keybinding/IPC open | `qs ipc call island toggle` opened with `summoned` and `focused`; closed by itself after 5 s untouched |
| AE6 fullscreen | Scratch window fullscreen: island hidden and its layer unmapped; restored on exit; maximized does not hide it |
| DP-3 | Not connected during this run |
| Settings save (U7) | Not exercised live (needs a click into the card); manual pass pending |

### Live verification (P2 live activities, eDP-1)

Run 2026-11-15 on omarchy-max, Hyprland 0.57.2, eDP-1 only, screen unlocked. Plan: `docs/plans/2026-11-15-1645-feat-island-live-activities-plan.md`. Actions were driven through `qs ipc call island act ...`, the same path the card's controls take, because no click injector runs on this host.

| Check | Result |
|---|---|
| Plugin loads | No Island warnings in the shell log after the binding-loop and FileView fixes |
| Media (R7) | mpv playing a tagged local file (null audio output): ear shows play glyph + title; card shows art placeholder, title, artist, scrub 0:15 of 10:00, prev/next dimmed (one track); `act media toggle` moved MPRIS PlaybackStatus Playing, Paused, Playing; paused media stayed in the ear |
| Dictation (R6, AE2) | Scratch foot window focused; `wordink dictation start` showed `0:02` in the ear with the media icon at the outer edge (KTD10); `act dictation stop` ended it (WordInk log: `discarded`, nothing was said, nothing pasted); the activity cleared |
| AE1 held order | Card open on media, then a dictation started: media stayed the top block, dictation took a row with its Stop control |
| Timer (R8, AE3) | `timer 2m` showed 1:59; `+1 min` gave 2:59; paused held 2:59 for 2 s; resume, cancel, `timer bogus` returned `invalid`; a 5 s timer showed `Done` then cleared; exactly one `Notify` ("Island", "Timer done") on the session bus |
| Charging (R13) | A real transition into Charging during the run showed `69% · 3h 28m to full` once and expired on its own |
| HUD (R9, AE4) | With `omarchy.osd` enabled a volume change showed nothing; after `omarchy-plugin-disable omarchy.osd` it showed `47%`, and a backlight change showed `26%`; `omarchy-plugin-enable omarchy.osd` restored it; shell.json identical to the pre-run copy, volume and brightness restored |
| Settings page | Opened by `open settings`: both delays and four toggles fit the card without clipping; the OSD hint shows while `omarchy.osd` is enabled |
| Hover regression | `bin/island-hover-check --runs 5 --mode both` with media live: 5/5 (AE1, AE2, jump and steps); pointer restored |
| Not run live | Clicking card controls (Stop, transport, scrub drag, toggles): needs a click injector; manual pass pending. A spoken dictation whose transcript lands in the focused window: needs a person speaking |

Findings fixed during the run:

- WordInk reports `listening` as its ready state after every dictation; only `dictating` is recording. The ear showed "Recording" forever until `Dictation.js` stopped mapping `listening` to recording.
- `FileView.reload()` is asynchronous; reading `text()` right after it returned the previous contents, so the brightness level lagged one change behind. Brightness and charging now read in `onLoaded`.
- `time_to_full_now` refuses reads unless the battery is charging; it is now read only then, which stopped a warning every 5 s.

### Live verification (Mac parity 0.3.0, eDP-1)

Run 2026-11-16 on omarchy-max, Hyprland 0.57.2, eDP-1 only (DP-3 not connected), screen unlocked. Plan: `docs/plans/2026-11-16-0053-feat-island-mac-parity-plan.md`. The plugin was linked from the branch worktree and the shell restarted with `omarchy-restart-shell` (a keepLoaded panel survives the plugin hot reload, so a restart is needed to load new code). Actions went through IPC, the same path as the card's controls; no click injector runs here.

| Check | Result |
|---|---|
| Plugin loads | No Island warnings in the shell log after each restart; the old `fullscreenNow` binding-loop warning is gone |
| AE1 black surface | Closed pill on eDP-1 drawn pure black (`presentation.surface: notch`); the open card uses the theme popup colors |
| Content width | Idle pill 298 px (ears 56); with a media title it grew to 426 px (ears capped at 120) |
| AE2 split bubble | Timer + mpv: ear shows the timer, a circular bubble right of the pill shows the media glyph; hot zone grew from 310 to 344 px to cover it |
| Equalizer | Four consecutive 130 ms captures of the ear differ while mpv plays |
| Art tint | `file:` art quantizes (`#e76f18` from an orange cover in a standalone Quickshell probe); mpv publishes `data:` art, which Quickshell's ColorQuantizer does not read, so mpv keeps the theme accent |
| AE3 alert | `preview charging` grew the island to the alert (ring, "Charging", "62% · 1h 12m to full") and it collapsed after about 3 s |
| AE3 fullscreen gate | Scratch `foot` fullscreen: island hidden, a `preview bluetooth` pushed then showed nothing then or after leaving fullscreen |
| AE4 hover wins | During a DND alert, resting the pointer on the pill ended the alert and opened the card; leaving closed it |
| AE5 screen recording | `omarchy-capture-screenrecording --fullscreen` showed the record glyph and `0:05` in the ear (media moved to the bubble); `act screenrec stop` stopped it through Omarchy's command (`--status` exit 1 after); the test file was deleted |
| AE6 mic dot | A scratch `pw-record` to /dev/null showed the orange dot right of the camera within 1.5 s and it cleared after exit; the always-on Asahi DSP capture streams did not count |
| DND | `omarchy-shell notifications setDnd on` showed the bell-off glyph and an alert; set back off (as found) |
| Settings page | Nine toggles in three columns plus both delays and the OSD hint fit the card without overlap |
| Hover regression | `bin/island-hover-check --runs 5 --mode both --allow-skip` with a timer and media live: first batch failed once in run 3 (the failing step was not captured: stderr was cut by `tail`); then 5/5, 5/5 and 10/10 consecutive passes |
| Not run live | Camera dot (observe-only rule: no capture was started; the watcher ran and reported not in use); Bluetooth activity and alert (no device connected; alert path checked with `preview bluetooth`); mic-mute alert (gated on `omarchy.osd` being disabled, which it is not here); clicks on the bubble, DND button and Stop (no click injector) |

Code review (ce-code-review, six lenses on Sonnet, no cross-model peer by owner rule): one finding, the charging alert built before time to full was read, reported by three lenses and fixed (the alert now waits for the read). Residuals also fixed: a default-microphone switch no longer reads as a mute, Bluetooth devices already connected at shell start are a baseline, and a pid change during a recording status check is re-checked. After the fixes: no Island log lines on a shell restart, no startup alert, and `bin/island-hover-check --runs 5 --mode both --allow-skip` passed 5/5 again.

## Now Playing redesign (0.3.1) live check

Run 2026-11-16 on omarchy-max, Hyprland 0.57.2, eDP-1, Spotify playing a podcast. Plugin linked from the branch worktree, shell restarted. Actions through IPC and grim screenshots only.

| Check | Result |
|---|---|
| Compact pill | Time left; right ear a rounded art thumbnail and five equalizer bars; pill 298 px wide (camera 186 + two 56 px ears, was 426); no title text |
| Remote art | `https:` art from the player's CDN loaded through Qt Image; the music glyph shows only while loading |
| Art tint | A 24 px canvas feeds `Palette.dominant()` and `Tint.pick()`; works for `https:` art, which ColorQuantizer could not read (`mediaTint` in `state`) |
| Open card | 266 px tall (was 380): time and date line, large rounded art, player icon and name, title, show, tinted progress with elapsed and remaining, borderless transport glyphs, compact page row; hot zone `cardRect` height matches the committed 266 |
| Settings page | Full height; "Load album art from the web" sits beside the delay fields |
| Pause and resume | `act media toggle` twice: paused then playing again |
| Hover check | Run 3 of 3 passes earlier in the session (two flaky runs while the owner used the pointer); stopped at the owner's request, not re-run on the final build |

### Verification (calendar and hover intent 0.3.2)

| Check | Result |
|---|---|
| Hover intent | Node tests only: `Intent.js` speed cases, the `Hover.js` open-timer gate, and a combined simulation of the hover check's stepped move (opens at enter + 140 ms, unchanged), a 1 px/ms pass (never opens) and a pointer that slows and stops (opens once it settles) |
| Calendar helper | `bin/island-calendar` run by hand on omarchy-max: `{"source": "omarchy", "events": []}` (Omarchy's calendar file exists but holds no events; khal, gcalcli and evolution-data-server are not installed). khal, gcalcli and the allowlist are fixture-tested; the evolution-data-server path is untested (not installed) |
| Not run live | At the owner's request no pointer was moved and `bin/island-hover-check` was not run. Not installed live either (another branch owns the live install): the calendar row and Join button render, the ten-toggle Settings page fit, and the hover check against this branch wait for install |

### Live verification (Home dashboard, 0.4.0)

Run 2026-11-16 on omarchy-max, Hyprland 0.57.2, lid closed at the owner's work desk (work dock, ethernet, USB camera and mic; not the home Odyssey ultrawide): HDMI-A-1 (Dell S2721NX, 1920x1080, scale 1) at x 0 and DP-3 (Samsung LS27A800U, 3840x2160, scale 1) at x 1920; eDP-1 off. Copy install, shell restarted. Actions through IPC and grim screenshots only; no pointer moves.

| Check | Result |
|---|---|
| Owner report | Home showed only the clock when nothing was live: the old Home drew only the header and two toggles |
| Home tiles | `open home` on DP-3: Now Playing, Up next and a glance tile with battery (100% charging), CPU, memory meters and the agents summary ("1 done · 2 working") |
| Empty states | No player: "Nothing playing"; no calendar events: "Nothing in the next 24 h" |
| Now Playing tile | Silent mpv track (null audio output): player name, title, artist, art placeholder, transport with previous and next dimmed (one track); `act media toggle` returned ok; the Music chip joined the page row |
| Live rows | A 3 min timer showed as a row under the tiles with pause, +1 min and cancel; media and calendar are not repeated as rows |
| Multi-display | One Island per screen: HDMI-A-1 origin 588 and DP-3 origin 3468, both 744x392; the open card landed on DP-3 |
| Not run live | Join on an Up next meeting (no events in the calendar); clicks on the tiles (no click injector, owner rule against pointer moves) |

### Polish and Blip (0.4.x)

Run 2026-11-16 on omarchy-max, same two-display setup as the Home run (HDMI-A-1 at x 0, DP-3 at x 1920, scale 1). Copy install, shell restarted, no Island warnings in the journal. IPC and `grim` screenshots only, saved to `~/Inbox/claude/island-polish/`; no pointer was moved, no input injected, `bin/island-hover-check` not run. The open card landed on HDMI-A-1 (origin 588).

Owner report: "almost no page is polished enough ... each part is rocky and rough"; wants hover feedback, and Blip in the Island.

| Change | How it was checked |
|---|---|
| One control, `HoverButton.qml`, replaces the ad-hoc MouseAreas: chips, Pin, bell, action buttons, tiles, list and agent rows, transport keys, Join, Open fan panel | Code review; `Controls.js` look and hint-position rules node-tested (`tests/test_island_controls.py`) |
| Hint drawn inside the card (`HintBubble.qml`, hosted by `Card.qml`) after a 400 ms rest; never a separate window, never takes the pointer | Code review and the position tests (above, below, clamped to the card) |
| One type scale (`Txt.qml`: heading, body, caption) and one empty state (`EmptyNote.qml`) on Home tiles, Music, Agents, System, Messages, Shots, Dayflow and alerts | Screenshots `home.png`, `music-media.png`, `agents.png`, `system.png`, `more.png`, `settings.png`, `messages.png` |
| Messages: unread rows are buttons that run `qs -p /usr/share/omarchy/shell ipc call nixfred.blip notified <chat>` (argv list; the handle is checked against Blip's own character set); muted chats listed last and dimmed; "Open Blip" button | `blipChatArgv` node-tested with safe and unsafe ids (fixtures only); `messages.png` shows the page on the live Blip state (labels are the last four characters of a handle) |
| Home header shows "N unread" (accent, opens Messages), nothing at zero | `home.png` (6 unread) |
| Pill: one 6 px accent dot beside the time while unmuted unread exists; the time stays in the left ear | `home.png`, `home-media.png`, `home-timer.png` |
| Home Now Playing tile split so the open-Music area and the transport keys never overlap | `home-media.png` (silent mpv), `home-timer.png` (3 min timer), `music-media.png` |
| KTD2 | Every page keeps its committed height: empty notes fill the rows the page already reserved; Music's empty note takes the media block's height |

Not verified live:

- Hover, pressed and disabled looks, the cursor shape and the hint bubble were never seen: they need the pointer. Covered by code review and the node tests only.
- Clicking a chat row did not run (it would open Blip on the owner's screen). The argv it builds is tested; Blip's `notified` handler was read in `BarWidget.qml`, not called.
- Join on a meeting (no events), the Agents focus click, the Shots page (no captioned screenshots) and the light theme were not shot.
- The split-presentation bubble got a pointer cursor and a press scale but no hint, since it sits outside the card.
- The Settings page uses the shell's own `qs.Ui` Toggle and NumberField, which already have hover and focus styles; they were not changed.

## Visual redesign (0.4.2)

Run 2026-11-16 on omarchy-max, one display (eDP-1, logical 1728 wide, origin 492, window 744x392). Copy install (`scripts/install.sh --copy`), shell restarted, version 0.4.2 confirmed in the live manifest, no Island QML warnings in the journal beyond the existing Pill binding-loop notice (present before this change). IPC `open <page>` plus `grim` only, saved to `~/Inbox/claude/island-redesign/`; no pointer was moved, no input injected, `bin/island-hover-check` not run.

Owner report: "good hover, agents, system, dayflow, and the last one. all of those are just words. ui is a typewriter its crap. there is no UX. no simplicity its just words."

| Change | Evidence |
|---|---|
| One UI face: `Fonts.js` + `Face.qml` (text) and `Txt.qml` (scale: display, heading, body, caption); the window `stage` publishes `uiFont`. `sansFont` setting (default on) picks Adwaita Sans, else the shell font; glyph text keeps the shell font | `home.png`, `agents.png`, `system.png`, `dayflow.png`, `more.png` (live, sans); harness render with the setting off keeps the monospace face; `tests/test_island_redesign.py` (family choice) |
| Agents: three-column tiles, icon (theme icon for Codex and OpenCode, lettered circle for Claude and Antigravity, which ship none here), name, host, status mark; header count pills; idle folds into "+N idle" | `agents.png` (live: 1 working, 1 done, 6 idle); `state-agents2.png` (fixture: needs you, working, done, idle, "+3 idle") |
| System: Battery, CPU, Memory rings with a one-word caption; bolt while charging; network, Tailscale and fan chips; power-profile segmented control | `system.png` (live); `state-system2.png` (fixture: charging battery, CPU at 93 percent in the urgent color, profile control shown) |
| Dayflow: recording indicator and Pause or Resume (no Open Dayflow button: Dayflow has no open command, so none was added), three stat tiles, pending only above zero | `dayflow.png` (live, recording); `state-dayflow2.png` (fixture: paused, 3 pending) |
| More: launcher grid, icon over name, Messages count badge, dot on Shots while unseen | `more.png` (live); badge and dot in the fixture render only |
| Messages: avatar (initials or person glyph), name, unread badge, "Open Blip" | `state-messages-fixture.png` (invented names; the live state had no unread chats, so no live Messages shot with real data was saved) |
| Home keeps its layout; sans face and the rounder tile plates match the new pages | `home.png` |

Gates: manifests, plugin contract, qmllint syntax and pytest all run before the push (see the PR).

Not verified live:

- The power-profile control was never exercised: power-profiles-daemon is inactive on this machine, so the control is hidden (and the helper skips the profile read instead of stalling on D-Bus activation for seconds). Set-profile argv building is node-tested (listed names only); the click and the re-read were not run.
- Pause and Resume were not clicked (rule against changing Dayflow state); the argv is tested (`dayflow pause`, `dayflow resume` only).
- Hover and pressed looks, hints on the new tiles, and the working-dot pulse and recording halo (animation) were not seen: they need the pointer or motion, and stills cannot show them.
- Messages with real chats, the needs-you tile and the charging ring come from a fixture harness (the same page files with fake data), not from the live shell.
- No second display this run (only eDP-1 was connected); the card is 720 wide at most, so a 1920 screen draws the same card.
- Shots still uses the old list page (not in the redesign scope); it picks up only the new face.

## Follow-ups (0.4.3)

Run 2026-11-17 on omarchy-max (HDMI-A-1 live, window 744 wide). Copy install, shell restarted, live manifest 0.4.3, no Island warnings in the journal. IPC `open <page>` plus `grim` only, saved to `~/Inbox/claude/island-followups/`; no pointer moved, no input injected, `bin/island-hover-check` not run. Screenshots of Messages use invented names (fixture harness); no real contact, number or message text was saved.

| Item | Result | Evidence |
|---|---|---|
| CodeRabbit comments on PR #80 | 22 inline plus 1 outside-diff comment checked against main; 13 fixed, 10 skipped as already fixed or optional (table in the PR) | PR body, tests |
| Agent logos | Claude and Antigravity now show Omarchy's own agent marks, found at run time under `/usr/share/omarchy/shell/plugins/agents/assets/` (`claude.svg`, `agy.svg`, `-light` twins for light cards); nothing is copied into this repo; the lettered circle stays the fallback. Codex, OpenCode, Cursor and Gemini keep their theme icons | `agents.png` (live) |
| Shots tiles | New `ShotsPage.qml`: two rows of four rounded thumbnails, newest first, decoded at 320x200 asynchronously; caption is the hover hint; click opens (name checked by `More.shotFile`); the unseen dot is unchanged. `ListPage.qml` removed (no users left) | `shots-fixture.png`, `shots-empty-fixture.png` (fixture) |
| Messages names | One-on-one chats take a name from `groups[*].participantNames` in Blip's `state.json`, which the Island already reads; raw numbers and emails are not names. Blip keeps no other stored name file (the contact dump is a 60 s runtime cache of the whole address book, not read). Coverage is partial: only people who share a group with the owner | `messages-names-fixture.png` (fixture) |

Not verified live:

- Shots: this machine has no `snapdex-ctl`, so the page is not available live; the thumbnail grid and the empty state were rendered from the fixture harness (same page file, invented data). The click to open a screenshot was not run.
- Messages names: only the fixture was shot; the live state has one unread chat whose person is in no stored group name, so it still reads "Chat ending NNNN".
- Pressed-scale change in `HoverButton` (scale on the visuals only): no pointer input allowed, so hover and press were not exercised.
- Dayflow Pause and Resume through the new `Process` were not clicked.
- Light card surface (the `-light` agent mark order) was not shot.

### Owner checks (2026-11-16)

| Check | Result |
|---|---|
| Clicks on the bubble, the Do Not Disturb bell and play/pause | Owner clicked them by hand on 0.4.2: "seems they were good". Closes the "clicks on the bubble, DND button and Stop" gap left in the Mac parity 0.3.0 run |
| Hover, press and hint looks | Owner moused over 0.4.1: "good hover" |
| Bluetooth activity and alert | Dropped by the owner for now ("no bluetooth as of now"); only `preview bluetooth` has run |
| Odyssey ultrawide on DP-3 | Not run: the multi-display run used the work dock (Dell on HDMI-A-1, Samsung LS27A800U 4K on DP-3). Waits for the home dock |
| WordInk pill alongside the Island | WordInk's own bottom pill (layer `hex-hud`, 304x80) had stopped drawing after several dock and undock cycles while WordInk kept running; a `wordink.service` restart brought it back (seen in a test dictation stopped with `--print`). The Island does not touch WordInk settings. Lasting fix belongs in WordInk's HUD (recreate the surface when its output goes away) |

## Omacontrol shortcuts (0.4.4)

Run 2026-11-19 on omarchy-max (eDP-1, HDMI-A-1 and DP-3 live; the card opened on HDMI-A-1, origin x 2316, window 744x392). Island dir copied live with `rsync` (not `install.sh --copy`, so the live netline and hotkey-tally fixes stay), shell restarted, live manifest 0.4.4. IPC `open settings|more|state|close` plus `grim` only, saved to `~/Inbox/claude/island-omacontrol/`; no pointer moved, no input injected, `bin/island-hover-check` not run.

| Control | Argv | How verified |
|---|---|---|
| Settings row: Network, Bluetooth, Sound, Displays, Power, Keyboard, Appearance, All settings | `qs -p /usr/share/omarchy/shell ipc call omacontrol showPage <network\|bluetooth\|audio\|displays\|power\|keyboard\|theme\|overview>` | `island act omacontrol <page>` (same allowlist and code path as the click) returned `ok`, an `omacontrol` layer appeared in `hyprctl -j layers`, the Island card was closed, then `omacontrol hide` |
| More tile "Omacontrol" | `... ipc call omacontrol open` | argv run by hand: layer appeared, `hide` removed it; tile drawn in `more.png`. The click itself was not made |
| Unknown id (`x;reboot`) | none | `act omacontrol 'x;reboot'` returned `unknown`; node tests refuse 9 bad ids |

Findings:
- `qs ipc call omacontrol show` does not open the window: the `qs` client reads a bare `show` itself and prints the target listing. The More tile uses `open`, which works.
- KTD2: with the row added the Settings page overflowed the 380 px card and clipped it. The sixteen toggles now use `controlHeight + lg` instead of `controlHeight + huge`; row, labels and all toggles fit (`settings.png`).
- With Omacontrol unavailable (manifest missing or in `disabledPlugins`) the row and tile are not drawn; `Omacontrol.available()` is node-tested, the live "missing" state was not exercised.
- The first shell restart after the layout changed logged `Binding loop detected for property "height"` on `Pill` (IslandWindow.qml:381). Pill geometry was not touched by this change; not investigated.

Not verified live: a real pointer click on a shortcut or the tile (clicks avoided by rule), the unavailable state, light theme.
