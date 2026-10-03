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

After reviewing it, apply the migration with the atomic backup/rollback helper:

```sh
python3 scripts/apply-surface-migration.py --apply
```

The helper writes a mode-0600 shell snapshot under
`$XDG_STATE_HOME/omarchy-plugins/migrations/`, rescans the host, and restores
the snapshot automatically if the rescan fails. Roll back later with:

```sh
python3 scripts/apply-surface-migration.py --rollback <backup-directory>
```

The plan reports the exact bar IDs to remove/add/retain, requires a shell-layout
backup, and has no destructive actions. Before applying it, save the current
shell configuration and verify the two replacement widgets load. Roll back by
restoring that snapshot and rescanning; do not delete plugin data, keyring
entries, or user history as part of the migration.
