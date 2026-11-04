#!/bin/sh
# Thin launcher: finds the local `wordink` CLI without relying on the shell's
# ambient PATH, then execs it. Exit 127 = not installed (the panel shows the
# install line); every other code is wordink's own (3 = not running).
PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
command -v wordink >/dev/null 2>&1 || exit 127
exec wordink "$@"
