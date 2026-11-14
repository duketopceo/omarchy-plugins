# Native Island 0.2 prototype

An independent Quickshell experiment inspired by IslandCN. It displays the local clock and date, and reads the active MPRIS player for media information and controls. It does not load or replace the Notch plugin.

Run it in an Omarchy Wayland session with:

```bash
qs -p prototypes/island-v02/shell.qml
```

Click the island to expand it; use the close control or Escape to collapse it. Stop the process to remove the prototype. If Notch is also enabled, both surfaces occupy the top of the screen.

This is a prototype, not the integrated plugin: camera width is calibrated for `omarchy-max`, and the activity integrations and accessibility work are described in `docs/plans/2026-11-13-feat-island-activity-merge-plan.md`.
