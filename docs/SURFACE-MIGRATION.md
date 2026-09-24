# Surface migration

The live bar migration is intentionally dry-run first. The current decisions
are encoded in `machine/bar-layout.json` and `machine/plugins.json`:

- Voxtype replaces Dim as the default voice control.
- The custom tray remains because it hosts Herdr and Hardware Nexus.
- The stock active-window widget replaces the custom clone after a layout smoke
  test; the clone remains available for rollback.

Generate the plan without changing the host:

```sh
python3 scripts/plan-surface-migration.py --format markdown
```

The plan reports the exact bar IDs to remove/add/retain, requires a shell-layout
backup, and has no destructive actions. Before applying it, save the current
shell configuration and verify the two replacement widgets load. Roll back by
restoring that snapshot and rescanning; do not delete plugin data, keyring
entries, or user history as part of the migration.
