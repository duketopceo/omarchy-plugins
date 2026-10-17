# Roadmap

Program roadmap written 2026-10-11 (written directly; the `ce-plan` pipeline was skipped as too heavy
for a single-plugin repo). Design direction: [DESIGN.md](DESIGN.md).

Current state: v1.0.4, installable and submitted to the marketplace (checked in the old roadmap).

## Now

### U1: Real preview.png in red-tint and low-brightness modes

- Status: Open in old roadmap
- Evidence: Old roadmap launch checklist
- Depends on: none
- Verification: Image added; legible when viewed in a dark room
- **Difficulty**: easy: capture only
- **Feasibility**: Needs a running shell and an overlay summon on the owner machine
- **Simpler alternative**: Use one image in default mode

### U2: Document the weather-location settings file

- Status: Not started
- Evidence: `bin/standby-data` `load_weather_location()` already reads a latitude, longitude, name file; the old roadmap lists "configurable weather location" as future work, so it is half-built
- Depends on: none
- Verification: README names the file path and keys; a test covers a malformed file
- **Difficulty**: easy
- **Feasibility**: none
- **Simpler alternative**: This is the simplification: document the existing file instead of building a settings UI

### U3: Add the word "awake" next to the caffeine indicator

- Status: Not started
- Evidence: `Standby.qml` line 405 colours the label with `Color.urgent` only
- Depends on: none
- Verification: Visible text change
- **Difficulty**: easy
- **Feasibility**: none
- **Simpler alternative**: none

## Next

### U4: Calendar next-event line from `~/.local/state/omarchy/calendar-events.json`

- Status: Not started
- Evidence: Old roadmap; `~/.config/omarchy` ships calendar sync files on this machine
- Depends on: U2
- Verification: Event shows only when the file exists; capped and sanitised like other helpers
- **Difficulty**: medium
- **Feasibility**: File format is host-owned and may change
- **Simpler alternative**: Skip; keep the overlay minimal

### U5: Refresh interval setting for weather

- Status: Not started
- Evidence: Old roadmap
- Depends on: none
- Verification: Manual
- **Difficulty**: easy
- **Feasibility**: none
- **Simpler alternative**: Fixed 15 min is fine

## Later

### U6: Alarm or timer mode

- Status: Not started
- Evidence: Old roadmap
- Depends on: none
- Verification: n/a
- **Difficulty**: hard: audio, persistence, wake behaviour
- **Feasibility**: Scope creep versus the "do nothing but be a clock" product
- **Simpler alternative**: Recommend not building; use a dedicated timer tool

### U7: Custom background with pure-black guardrails

- Status: Not started
- Evidence: Old roadmap
- Depends on: none
- Verification: n/a
- **Difficulty**: medium
- **Feasibility**: OLED burn-in risk
- **Simpler alternative**: Recommend not building

---

## Earlier notes (kept)

## Current status

Installable and validated, and submitted to the marketplace. The registry does not list it yet.

## Launch checklist

- [x] Add a `preview.png` of the overlay
- [x] Submit to https://plugins.omarchy.org/publish.html
- [x] Set GitHub repo topics
- [ ] Set GitHub social preview
- [ ] Write a short release / social post
- [ ] Optional: make a short screen recording of the toggle keys

## Future work

- [ ] Configurable weather location / refresh interval
- [ ] Calendar events from `~/.local/state/omarchy/calendar-events.json`
- [ ] Alarm / timer mode
- [ ] Optional custom background with still-pure-black guardrails
