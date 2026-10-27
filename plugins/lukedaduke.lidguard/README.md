# Lid Guard

Timed lid-close stay-awake for Omarchy. Arm a `handle-lid-switch`
inhibitor for 1h / 2h / 4h / 8h / ∞ and the machine keeps running —
agents, VMs, builds, downloads — with the lid shut. Releases
automatically when the timer expires.

This is different from Omarchy's idle toggle ("Stay Awake"), which only
gates the idle daemon (screensaver/lock/idle-suspend). Closing the lid
is a hardware event handled by logind directly; Lid Guard blocks that
event for a bounded time.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-lidguard
```

Then add **Lid Guard** to the bar (System category).

## Remove

```bash
omarchy plugin remove lukedaduke.lidguard
```

Any armed inhibitor dies with the plugin process tree; worst case it
self-releases at its expiry.

## Notes

- Runs as a transient `systemd --user` unit (`lidguard.service`) wrapping
  `systemd-inhibit`. No root, no config files, nothing persists across
  reboot.
- Closing the lid while armed still powers off the internal display and
  gates the keyboard/trackpad through the normal lid path — the machine
  just doesn't suspend.
- Battery still drains — plug in for long sessions.
