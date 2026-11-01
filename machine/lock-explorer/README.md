# Lock Screen Explorer: local changes

The lock screen is [Lock Screen Explorer](https://github.com/SirJul1337/omarchy-lock-explorer) (MIT), installed as `io.github.sirjul1337.lock-explorer`. These are the local changes kept on top of it.

| Patch | Applies to | Status |
|---|---|---|
| `01-session-lock-reacquire-2.0.11.patch` | v2.0.11 `Service.qml` | **Live.** When the compositor drops the lock surface while a lock is requested, re-acquire the lock instead of treating it as an unlock. Upstream still releases. |
| `01-session-lock-reacquire.patch` | v1.9.6 (`BASE`) | Superseded. Also changed `lock()`, `isLocked()` and `status()`; not ported, because 2.0.11's `lock()` keys on `lockRequested` so a lock during the unlock animation cancels it, and the old change would have answered "ok" without cancelling. |
| `02-qtquick-6.11-imports.patch` | v1.9.6 | Dropped. Pinned `import QtQuick 6.11` in 92 files; upstream and Omarchy 4.5 use the unversioned import. |

After `omarchy plugin update io.github.sirjul1337.lock-explorer`, the checkout must be clean to fast-forward: save `git diff` first, update, then re-apply `01-session-lock-reacquire-2.0.11.patch` (re-port by hand if the context moved) and `omarchy restart shell`.

**Escape route** when the lock screen is frozen: from SSH or a TTY run `omarchy-restart-shell` (or `~/bin/display-rescue`). It refuses while a healthy lock is up, and otherwise restarts the shell and re-locks so the password field works. `loginctl unlock-session` does nothing: no lock here listens for logind's Unlock signal.
