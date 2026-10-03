# Resource & Fan

A native Omarchy bar widget that shows how hard the machine is working and
what is doing the work: RAM, CPU, GPU, temperatures, disks, fans, and the
running processes grouped under plain names ("Chromium", "Claude Code",
"Docker", "Power monitor"), plus fan presets when the fan helper is installed.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-fan
omarchy plugin enable lukedaduke.fan
```

## What it shows

**Bar:** RAM used and percent, one temperature, and the fan mode letter
(`A`uto, `L`ow, `M`ed, `H`igh, `C`ustom). The temperature is the CPU sensor
when the machine has one; otherwise it is the hottest board sensor, and the
tooltip names it (Apple Silicon exposes no CPU temperature, so you see e.g.
"Charge Regulator Temp 47°C"). The tooltip also lists fan RPM.

**Panel:**

- **Overview** — CPU name, load and per-core bars; memory, swap and memory
  type; GPU name, load where the driver exposes it (NVIDIA, AMD
  `gpu_busy_percent`) or a plain reason why not, SoC power on Apple Silicon,
  and which apps hold the GPU; every labelled temperature sensor; disk usage.
- **Fans** — RPM per fan, the mode buttons (auto/low/med/high/custom with
  silent, balanced and performance custom presets) when the helper reports a
  controllable fan, or the install/update hint otherwise.
- **What's running** — processes grouped by app. Each row shows an icon for
  the kind (app, browser, dev, agent, desktop shell, system, plugin), the
  friendly name, a one-line description of what it is running, its CPU and
  memory, and how many processes it has. Busy groups (1% CPU or more) come
  first, then the rest by memory. Click a row (or press Enter) to see its top
  PIDs. A single-process group can be killed: press Kill (or `x`), then
  confirm within 5 seconds.

A "stale" label appears when the data is more than three refreshes old.

### Friendly names

Names are resolved in this order:

1. **Plugin helpers** — anything running from `.../plugins/<id>/` gets the
   plugin's name: Fan monitor, Power monitor, Hardware radar, Standby clock,
   Bumblebee scanner, Numbat watcher, Perplexity, Neo sidecar (other ids show
   as "<id> plugin").
2. **Agents and scripts** — Claude Code, Devin, Codex and Kurultai are
   recognised by binary or script name; other Python/Node/Bun/shell processes
   are named after the script they run, e.g. "home-index-mcp (python)".
3. **Known apps** — Omarchy shell, Hyprland (desktop), Xwayland, Chromium,
   Headless Chrome (agent browser), Brave, Firefox, VS Code, Cursor, Zed,
   Ollama (local AI), llama.cpp server, Audio (PipeWire), Voxtype dictation,
   Docker, Tailscale, systemd, Kernel, and a few more.
4. Otherwise the process's own name.

The table lives in one place, `bin/system_monitor_stats.py` (`PLUGIN_LABELS`,
`AGENTS`, `INTERPRETERS`, `KNOWN`).

Command lines are redacted before they leave the helper: values after flags
that mention key/token/secret/password/auth, `NAME=value` arguments, long
hex or base64 strings, and `sk-`/`ghp_`/`xox…` style tokens are replaced with
`…`.

### Cost

The bar runs `system_monitor_stats.py --bar` at most once a minute while it
is visible (not on a locked or powered-off screen): `/proc` and `/sys` reads
only, no process scan, no GPU query. The full collection runs every 5 seconds
only while the panel is open, plus once when it opens. Nothing spawns `ps`,
`df` or hardware-listing tools; CPU percentages come from the difference
between two `/proc` snapshots (cached in `$XDG_RUNTIME_DIR/omarchy-fan/`).
`nvidia-smi` runs only when an NVIDIA GPU is present and already awake; a
runtime-suspended GPU is never woken to read it. The fan mode badge follows
`/run/omarchy-fan/status.json` through a file watch, without spawning.

## Fan helper setup

Fan control is applied by the **`omarchy-fan-helper`** package, a root
service that runs `/usr/lib/omarchy-fan/omarchy-fan-daemon` (packaged from
`bin/omarchy-fan-daemon`). The plugin never installs, starts, or elevates
anything: it reads the helper's status from `/run/omarchy-fan/status.json`
and, when the helper is missing or older than the version the panel expects,
shows "install/update the omarchy-fan-helper package". Until then the panel
is telemetry-only.

Build and install the package from the umbrella repository
([`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins)):

```bash
cd packaging/omarchy-fan-helper && yay -Bi .
sudo systemctl enable --now omarchy-fan-daemon.service
```

Installing the package replaces a hand-installed
`/etc/systemd/system/omarchy-fan-daemon.service` that ran the daemon from a
user-owned plugin folder, and starts the packaged unit in its place.

How it behaves:

- The helper polls `$XDG_RUNTIME_DIR/omarchy-fan/current_fan_mode` (written by
  `bin/omarchy-fan-set`) every 2 s and applies the silent auto curve, a fixed
  preset, or the custom curve. It only reads from the user runtime directory.
- Custom mode applies one of three preset curves (silent, balanced,
  performance) written to `~/.config/omarchy/fan_curve.json`; the panel shows
  the active curve as a read-only preview. There is no in-panel curve editor.
- Fixed presets (low/med/high) need a live shell: the panel writes
  `$XDG_RUNTIME_DIR/omarchy-fan/heartbeat` every 30 s (no process spawn), and a
  preset older than 120 s without a heartbeat falls back to the auto curve.
  Screen lock does not stop the heartbeat.
- Whenever the helper stops, crashes, or is removed, the fans go back to
  firmware control (`macsmc_hwmon` `fan_control=N`, `dell_smm`
  `pwmN_enable=2`).
- Control is offered only when the fan targets are actually writable; otherwise
  the badge shows `READ ONLY` and the mode buttons are hidden.
- The helper never writes the ACPI platform profile; power-profiles-daemon
  owns power profiles.

To remove fan control, remove the `omarchy-fan-helper` package (it stops the
service and hands the fans back). Removing the plugin does not delete user fan
history or unrelated system services.

## Data and privacy

The plugin reads local hardware telemetry and writes only the local fan-mode
request/curve state. It sends no telemetry, account data, or credentials to a
network service. The plugin requests no authorization; fan writes happen in the packaged helper.

### GPU telemetry on Apple Silicon (Asahi)

The Asahi `apple-agx`/`asahi` DRM driver exposes no `gpu_busy_percent`,
devfreq device, GPU hwmon sensor, or `drm-*` fdinfo counters, so the panel
says "Load not available" instead of guessing. It shows what does exist:

- **SoC power** — the `macsmc_hwmon` "Heatpipe Power" rail, a SoC-wide proxy
  (not GPU-isolated).
- **Using the GPU** — apps holding `/dev/dri/*` handles, by friendly name.

There is no die temperature sensor either, so no GPU temperature is shown.

## Usage

- **Left click** the bar text — open the panel
- **Right click** — cycle the fan mode (when fan control is available)
- **Middle click** — open `btop`
- **j / k** — move through the process list
- **Enter** — show a group's PIDs
- **x** — kill the selected single-process group (press again to confirm)
- **b** — open `btop`
- **Esc** — close the panel

## Requirements

- `python3` (all helpers are Python; the panel execs `/usr/bin/python3`)
- Linux with `/proc` and `hwmon` sensors (works without fans or a battery;
  missing sensors are shown as unavailable)
- For fan control: `macsmc_hwmon` (Apple Silicon) or `dell_smm` fan
  targets plus the `omarchy-fan-helper` package (see above)
- Optional: `btop` + `omarchy-launch-or-focus-tui` for the middle-click
  launcher

## License

MIT
