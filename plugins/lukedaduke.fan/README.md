# Resource & Fan

A native Omarchy bar widget that turns your top bar into a compact laptop resource monitor: RAM, CPU load, CPU/GPU/NVMe thermals, fan RPM, and top processes, plus manual and automatic fan-curve control.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-fan
omarchy plugin enable lukedaduke.fan
```

## Features

- Real-time RAM and CPU load
- GPU section: utilization % where the driver exposes it (NVIDIA, AMD `gpu_busy_percent`, DRM fdinfo when the kernel supports it), plus package/heatpipe power and a live list of GPU client processes on Apple Silicon
- CPU, GPU, and NVMe temperatures via `hwmon`
- Laptop fan RPM readout
- Top memory/CPU processes with `j`/`k` selection and kill support
- Fan modes: auto, low, medium, high, plus a user-editable custom curve
- `omarchy-fan-daemon` runs the auto/custom curves and drives fan hwmon (`fan*_target` on Apple Silicon `macsmc_hwmon`, `pwm*` on `dell_smm`)

## Fan daemon setup

Fan control is applied by `bin/omarchy-fan-daemon`, which must run as
root to write `/sys/class/hwmon/*/fan*_target` / `pwm*`. The widget wires
it for you: click **⚡ Start Daemon** in the panel (or just pick a fan
mode — the first change auto-starts it). That runs
`bin/omarchy-fan-daemon-start` via `pkexec`, which installs the shipped
`omarchy-fan-daemon.service` into `/etc/systemd/system/` and starts it.

To install it by hand instead:

```bash
pkexec ~/.config/omarchy/plugins/lukedaduke.fan/bin/omarchy-fan-daemon-start
```

The daemon polls `$XDG_RUNTIME_DIR/omarchy-fan/current_fan_mode`
(written by `bin/omarchy-fan-set`) every 2 s and applies the matching
curve/preset. On hardware with no daemon-driveable fan (no
`macsmc_hwmon`/`dell_smm` fan targets) and no running daemon, the widget
degrades to read-only honestly: stats and fan RPM still render, the mode
badge shows `READ`, and the preset buttons are disabled.

### GPU telemetry on Apple Silicon (Asahi)

The Asahi `apple-agx`/`asahi` DRM driver exposes no `gpu_busy_percent`,
devfreq device, or GPU hwmon sensor, and current kernels do not emit
`drm-*` fdinfo counters — so a true GPU busy% is not available
unprivileged today. The panel therefore shows what does exist:

- **Package power** — the `macsmc_hwmon` "Heatpipe Power" rail, a
  SoC-wide proxy (not GPU-isolated).
- **GPU clients** — processes holding `/dev/dri/*` handles, i.e. what's
  actually on the GPU right now.
- **Temperature** — the shared die temp (unified SoC; CPU temp doubles
  as GPU temp).

If a future kernel wires up asahi fdinfo, `gpu_load` starts reporting
automatically — the probe is already in place.

## Usage

- **Left click** the bar text — open the panel
- **Right click** the bar text — cycle fan mode
- **Middle click** — open `btop`
- **j / k** — move process list
- **x** — kill selected process
- **Esc** — close panel

The custom curve is editable from the panel when the daemon is running.

## Requirements

- `python3` (all helpers are Python; the panel execs `/usr/bin/python3`)
- A Linux laptop with `hwmon` thermal/fan sensors
- For fan control: `macsmc_hwmon` (Apple Silicon) or `dell_smm` fan
  targets plus `pkexec` to install/start the daemon (see above)
- Optional: `btop` + `omarchy-launch-or-focus-tui` for the middle-click
  launcher

## License

MIT
