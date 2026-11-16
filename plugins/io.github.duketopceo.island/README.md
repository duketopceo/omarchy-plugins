# Island

A pill at the top center of every screen. It shows the time and what is
happening now, opens into a card when the pointer rests on it, and closes on
its own when the pointer leaves. On MacBook panels it sits on the camera
cutout; on other screens it is a virtual pill of the same shape.

P1 is the shell (pill, hover open and close, fixed-size card, fullscreen
step-aside, settings). P2 adds the live activities below. 0.3.0 brings it
close to Apple's Dynamic Island (see Presentation). 0.4.0 splits the card into
pages (see Pages).

## Pages

The card opens on Home. The chip row under it holds Home, Music, Agents,
System and More; a page shows only when its source is detected (Home, System
and More always). Shots, Messages and Dayflow are listed under More, and one
of them takes a chip before More while it has something live (an unseen
screenshot, an unread message, Dayflow recording or paused), in that order of
preference: Messages, Shots, Dayflow, never more than six chips. Settings is
under More. Every page is as tall as its content; the height and the chip row
are fixed when the card opens or the page changes, never while it is open.

| Page | Shows | Source | Detected when |
|---|---|---|---|
| Home | time, date, weather, battery, Tailscale and VPN dots, Do Not Disturb bell, mic and camera dots; the live activities as rows with their controls (next calendar event first, with Join); Do Not Disturb and mic-mute toggles | activities below; `bin/island-status home`; Omarchy's `omarchy-weather-status`; `wpctl` | always |
| Music | the Now Playing view (art, scrubber, controls) | MPRIS | a player has a track |
| Agents | herdr and Claude Code sessions, the ones that need you first; click focuses the terminal window | `bin/island-agents` (`herdr-app ls`, `~/.claude/sessions`, `hyprctl clients`) | `herdr-app` exists or `~/.claude/sessions` exists |
| System | battery, power profile, fan mode (with a button that opens the Resource & Fan panel), CPU, memory, network, Tailscale | `bin/island-status system` | always |
| Shots | the newest Snapdex screenshots and captions; click opens one | `~/Pictures/Screenshots/index.md` | `snapdex-ctl` exists |
| Messages | unread counts per chat (a group's name, or the handle's last four characters; never message text), Open Blip | Blip's `~/.local/state/blip/state.json` | that file exists |
| Dayflow | capture state, frames today, last frame, pending blocks, storage | `dayflow status --json` | `dayflow` exists |

- Weather runs Omarchy's own `omarchy-weather-status`, which asks the same
  service Omarchy's bar weather already polls. The Island runs it only while
  Omarchy's weather widget is in the bar and the Home page is open, at most
  every 30 minutes.
- System values are sampled every 2 s only while the System page is open;
  agents every 3 s only while Agents is open. Home, Shots, Messages and Dayflow
  sources read once per open (Blip's file is watched).
- An agent session's click runs `herdr-app do agent.focus --terminal <id>` for
  herdr sessions, then `hyprctl dispatch 'hl.dsp.focus({ window = "address:0x..." })'`.
  Claude Code background sessions have no window and no action. Approving or
  denying an agent's request is not here yet (it needs a hook socket).

## Presentation

- **Black on the notch.** On a MacBook panel with a camera cutout the closed
  pill (and the bubble) is pure black, so it merges with the cutout. Text and
  accents keep the theme's colors (the theme background is used for text when
  the theme's text would not read on black). The open card and alerts use the
  theme's popup colors on every screen; screens without a cutout keep the
  theme-colored pill.
- **Spring morph.** Opening, and an alert growing, overshoot slightly and
  settle; closing eases out. The pill's width follows its content (each ear
  56 to 120 px). With reduced motion (Hyprland animations off) everything
  snaps.
- **Split bubble.** With two live activities the second is a small circle to
  the right of the pill. Hovering it opens the card as usual; clicking it opens
  the card with that activity on top.
- **Alerts.** For about 3 s the island grows to say: charging started
  (battery ring and percent), timer done, a Bluetooth audio device connected
  (name and battery), Do Not Disturb on or off, and microphone muted or on.
  An alert never takes keyboard focus, never shows under a fullscreen window
  (it is dropped, not saved for later) or while the card is open, and ends
  as soon as the pointer comes to rest on the pill. The mic-mute alert follows
  the volume HUD's rule: it shows only after you disable `omarchy.osd`,
  because Omarchy's OSD already shows mic mute.
- **Hover intent.** The card opens when the pointer arrives and rests, not
  when it passes over. When the open delay runs out while the pointer is
  still moving fast (0.5 px/ms or more over the last 80 ms), the Island looks
  again 40 ms later instead of opening; a pointer that leaves first never
  opens it. Clicking the pill still opens it at once.

## Live activities

What is happening now shows in the pill's right ear (glyph and a short form,
such as `0:12` or `46%`); with nothing live the ear shows the date. A second
live activity shows as the split bubble beside the pill. On the card's Home
page up to three activities get a row each with their controls (the timer keeps
pause or resume, +1 min and cancel); the media row opens Music. While the card
is open nothing moves under the pointer: a new activity takes a free row, never
the top.

| Activity | Source | Card controls | Priority |
|---|---|---|---|
| Dictation | the local `wordink` CLI | Stop (transcribes and pastes, like the shortcut) | 90 |
| Screen recording | Omarchy's recorder (`omarchy screenrecord`) | elapsed time, Stop (`omarchy-capture-screenrecording --stop-recording`) | 88 |
| Volume and brightness (opt-in) | PipeWire default sink, internal backlight | level bar, about 1.6 s | 80 |
| Timer | the Island's own | pause or resume, +1 min, cancel | 70 |
| Media | MPRIS | art, title and artist, scrub, previous, play or pause, next | 50 |
| Calendar | `bin/island-calendar` (see below) | next event title and time, Join for a meeting link | 40 |
| Charging | `/sys/class/power_supply` | percent and time to full, about 6 s | 30 |
| Bluetooth audio | BlueZ through Quickshell | name and battery; card only, never the ear or bubble | 20 |

- Media stays for 10 minutes after a player pauses. The pill shows the album
  art as a rounded thumbnail on the left and equalizer bars on the right (still
  and dim when paused), with no title text, so it stays narrow: the camera plus
  the two small ears on a notch screen, a tight pill elsewhere. The card is as
  tall as the Now Playing block needs: large rounded art, the player's icon and
  name, title, artist (or album, which is the show for podcasts), a progress bar
  with elapsed and remaining time, and large previous, play or pause, next
  glyphs, on a wash of the art's color.
- Album art loads from `file:` and `data:` URLs always, and from the player's
  `https:` URL (Spotify, browsers) when "Load album art from the web" is on
  (default). That is one image request to the host in the URL, held in memory
  only (see `docs/data-lifecycle.json`, `island_album_art`). URLs with
  credentials, `http:`, loopback or IP-literal hosts are never loaded. While the
  art loads, or if it fails or the setting is off, a music glyph stands in.
- The charging notice shows when the battery starts charging. With a charge
  limit, plugging in at or above the limit reports "Not charging", so no
  notice shows.
- The equalizer and progress bar take a color from the loaded art (any art
  that loads, including `https:` and `data:`); with no art they use the theme
  accent.
- A missing tool hides its activity and shows no error.

### Calendar

`bin/island-calendar` reads the next 24 hours of timed events (all-day events
are skipped) from the first source that exists, in this order: Omarchy's
calendar file (`~/.local/state/omarchy/calendar-events.json`, written by
`omarchy-calendar-sync-all`), `khal`, `gcalcli`, then evolution-data-server.
That source is used even when nothing is due, so later sources are not run
on every poll; only a tool that fails falls through to the next. It is
read-only and makes no network call of its own; `gcalcli` talks to Google as
it always does. The Island runs it once a minute, or every 10 minutes while
no source exists.

- When a long event is already under way, the next meeting still gets its
  countdown and Join; the long event shows only when nothing else is coming.

- Within 10 minutes of the start the ear counts down (`in 8m`), then shows
  `now` for the event's first 10 minutes. Otherwise the event is a card row
  only: `Title · 09:30`.
- **Join** shows when the event's link, location or notes hold an https
  Zoom (`zoom.us` and its subdomains), Google Meet or Microsoft Teams link,
  matched on the exact host (a plain hostname only: no user part, backslash
  or escapes). It opens the link with `xdg-open`.
- With no calendar source the activity never shows.

### Indicators

Indicators do not count as activities and never take the ear.

- **Mic and camera in use:** an orange dot (microphone) and a green dot
  (camera) right of the camera cutout. The microphone counts PipeWire capture
  streams the way Omarchy's bar does, minus passive and monitor streams (the
  Asahi DSP always captures); the camera counts the owner's processes holding a
  `/dev/video*` capture device open (`bin/island-camera`, one long-running
  watcher; codec nodes such as `avd` do not count). The hues are Apple's; their
  saturation and lightness come from the theme's urgent color.
- **Do Not Disturb:** a bell-off glyph beside the time while Omarchy's
  notifications are silenced. The card's Do Not Disturb button runs
  `omarchy-toggle-notification-silencing`. Both hide when `omarchy.notifications`
  is disabled.

### Timer

Start it by IPC or from a keybinding you add yourself:

```bash
qs -p /usr/share/omarchy/shell ipc call island timer 5m   # also 90s, 1h30m, or 10 (minutes); up to 24 h
```

For example, in your own `~/.config/hypr/bindings.lua` (the Island never edits
it):

```lua
o.bind("SUPER + ALT + T", "Island timer 5 min", "/usr/bin/qs -p /usr/share/omarchy/shell ipc call island timer 5m")
```

When it reaches zero the ear shows `Done` for 8 s and one desktop notification
is sent through Omarchy's notification service (when `notify-send` exists). A
timer lives in memory: restarting the shell drops it.

### Volume and brightness HUD

Off unless you turn off Omarchy's own OSD; the Island never does that for you:

```bash
omarchy-plugin-disable omarchy.osd
```

Disabling `omarchy.osd` also drops its microphone-mute, keyboard-brightness
and media popups; the Island shows only output volume, mute and the internal
backlight. `omarchy-plugin-enable omarchy.osd` brings Omarchy's OSD back and
the Island's HUD stops. The HUD only reads; it never changes either level.

## Install

```bash
./scripts/install.sh --link
omarchy plugin enable io.github.duketopceo.island
```

## Settings

Settings live in this plugin's own entry in `shell.json` (`plugins[]`); the
Island writes nothing else there.

| Key | Default | Range | Meaning |
|---|---|---|---|
| `openDelay` | 140 | 0-600 ms | pointer rest time before the card opens |
| `closeDelay` | 450 | 150-1500 ms | time outside the hot zone before the card closes |
| `cameraWidth` | 0 | 0-4000 px | logical camera width override, 0 = auto |
| `dictation` | true | true/false | show the WordInk dictation activity |
| `media` | true | true/false | show the MPRIS media activity |
| `webArt` | true | true/false | load album art from the web (the player's `https:` art URL) |
| `charging` | true | true/false | show the charging notice |
| `hud` | true | true/false | show the volume and brightness level once `omarchy.osd` is disabled |
| `screenRecording` | true | true/false | show Omarchy's screen recording |
| `privacy` | true | true/false | show the mic and camera dots |
| `dnd` | true | true/false | show Do Not Disturb and its card button |
| `bluetooth` | true | true/false | show Bluetooth audio devices |
| `calendar` | true | true/false | show the next calendar event (off stops the poll) |
| `alerts` | true | true/false | show transient alerts |
| `weather` | true | true/false | show the weather on Home (only while Omarchy's weather widget is in the bar) |
| `agents` | true | true/false | show the Agents page (off stops its reads) |
| `messages` | true | true/false | show the Messages page from Blip's unread counts |
| `dayflow` | true | true/false | show the Dayflow page |
| `shots` | true | true/false | show the Shots page |

The Settings page in the card edits all of these.

## The bar clock

The pill covers the center of the bar, where the stock clock sits. To hide the
clock, run this yourself:

```bash
omarchy plugin disable omarchy.clock
```

The Island never runs it and never edits the bar layout.

## Probe

`bin/island-probe` prints one JSON object (platform, which optional tools
exist, including Omarchy's own commands in `/usr/share/omarchy/bin`, display
cutouts, device model, battery and backlight names). It checks existence only
and makes no network calls.

## IPC

One target, `island`. Calls act on the screen under the pointer (read once
from `hyprctl cursorpos -j`; the focused monitor only when that fails), except
`close` and `state`, which cover every screen.

```bash
qs -p /usr/share/omarchy/shell ipc call island toggle
qs -p /usr/share/omarchy/shell ipc call island open agents     # home, music, agents, system, more,
                                                               # shots, messages, dayflow, settings; now = home
qs -p /usr/share/omarchy/shell ipc call island focus
qs -p /usr/share/omarchy/shell ipc call island close
qs -p /usr/share/omarchy/shell ipc call island state           # JSON, one object per screen
qs -p /usr/share/omarchy/shell ipc call island timer 5m        # "ok" or "invalid"
qs -p /usr/share/omarchy/shell ipc call island act media toggle
qs -p /usr/share/omarchy/shell ipc call island preview charging # sample alert
```

`act <id> <action>` does what the matching card control does and returns `ok`
or `unknown`: `dictation stop`; `screenrec stop`; `media toggle|next|previous`;
`timer pause|resume|add|cancel` (`add` is +1 min). `preview <kind>` shows a
sample alert (`charging`, `timer`, `bluetooth`, `dnd`, `mic`) and returns `ok`,
`off` (alerts disabled) or `unknown`.

`open <page>` opens that page when it exists and Home otherwise.
`open`, `toggle` and `focus` give the card keyboard focus. An IPC-opened card
stays until the pointer has entered and left it, or 5 s pass untouched.
`state` reports per screen: `screen`, `state`, `flags`, the hot-zone `rect`
(and `pillRect`, `cardRect` (the open card's committed height), `origin`,
`window`, `pinCenter`, `hidden`, `mediaTint`), the
`top` and `second` activity ids, the card's `held` order, `activities`
(every live activity's `id`, `priority`, `text` and `card`), `presentation`
(`mode`: compact, split, alert or expanded; `surface`; pill and ear width;
`bubble`), the shown `alert`, the card's `page`, `chips` and `more` list (as
committed when it last opened), and `indicators` (`mic`, `camera`, `dnd`,
`dndAvailable`, `recording`, `micMuted`).

## Hover check

`bin/island-hover-check` is a live check, not part of CI. It moves the real
pointer with `hyprctl dispatch 'hl.dsp.cursor.move({ x = X, y = Y })'`, reads
`island state` after each step, and walks the open, stay-open, click/pin and
Esc cases (AE1, AE2, AE3, AE5) on every screen, with single jumps and with
interpolated steps. It repeats 20 times, exits non-zero on the first mismatch,
and puts the pointer back where it started.

```bash
bin/island-hover-check                                      # 20 runs, all screens
bin/island-hover-check --runs 3 --screens eDP-1 --mode steps
```

Run it on an unlocked desktop with the Island loaded; it refuses to start when
it cannot read the island state or the session reports locked. The click and
Esc cases need `ydotool` (with `ydotoold` running) and `wtype`; without them
those cases are reported as skipped and the exit status is 2 (`--allow-skip`
makes it 0). Pass `--open-delay` and `--close-delay` if you changed the
settings, and `--qs-args` to select a different running shell. Exit status:
0 passed, 1 mismatch, 2 refused or skipped, 3 the `--deadline` ran out.
