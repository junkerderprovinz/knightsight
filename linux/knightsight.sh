#!/bin/sh
# The program lives in ../lib next to this script, whether it was unpacked from the zip,
# installed into the home folder or built into the Flatpak.
here=$(dirname "$(readlink -f "$0")")
PYTHONPATH="$(dirname "$here")/lib${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m knightsight "$@"
