#!/bin/sh
# Starts a throwaway X server and session bus for smoke_x11.py.
set -eu
cd "$(dirname "$0")"
exec dbus-run-session -- xvfb-run -a -s "-screen 0 1280x800x24" python3 smoke_x11.py
