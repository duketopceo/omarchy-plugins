# WordInk — Omarchy bar widget

A mic icon in the Omarchy bar for [WordInk](https://github.com/duketopceo/WordInk),
the desktop dictation app. It only talks to the local `wordink` CLI: no network
calls, no stored keys.

- **Icon** follows WordInk's state: not running (dim, mic-off), idle, recording
  (urgent colour), transcribing (hourglass), error (alert, with the reason in
  the tooltip). It draws no recording overlay; WordInk's own pill stays the one
  on-screen indicator.
- **Left click** runs `wordink dictation toggle`. If WordInk is not running it
  starts the app in the background instead.
- **Right click** (or middle click) opens the panel:
  - engine and local model
  - microphone picker (`wordink devices`, set via `wordink settings set microphone`)
  - last three dictations with a Copy button (`wl-copy`)
  - this week's words and cost (`wordink usage`)
  - Open WordInk, Settings, Copy diagnostics

## Requirements

- `wordink` on `PATH` (`~/.local/bin` is checked too). Without it the panel shows
  the install line and nothing else:

  ```bash
  curl -fsSL https://github.com/duketopceo/WordInk/releases/latest/download/install.sh | sh
  ```

- `wl-copy` (`wl-clipboard`) for the copy buttons.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-wordink
# or from the omarchy-plugins umbrella checkout:
./scripts/install.sh --copy io.github.duketopceo.wordink
```

Then add the widget in Omarchy bar settings (Plugins -> WordInk). Default
section: right.

## How it works

`wordink logs -f -n 0` streams `live.ndjson` events; `state` events
(`listening`/`dictating`, `transcribing`/`stopping`, `sleeping`) move the icon.
When WordInk is not running (CLI exit 3) or the stream ends, the widget polls
`wordink status --json` every 5 s and restarts the stream when the app returns.
`bin/wordink-cli.sh` is a tiny launcher that resolves `wordink` with a fixed
`PATH`; exit 127 means not installed.
