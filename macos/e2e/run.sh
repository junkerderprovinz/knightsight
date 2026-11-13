#!/bin/sh
# Builds the target window and the driver and runs the driver against dist/KnightSight.app.
# The pictures and the logs land in the directory given.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$1"
out=$(cd "$1" && pwd)
bin=$(mktemp -d)
swiftc -O -o "$bin/target" "$here/Target.swift"
swiftc -O -o "$bin/drive" "$here/Drive.swift"
exec "$bin/drive" "$here/../dist/KnightSight.app" "$bin/target" "$here/../../mcp/knightsight-mcp.mjs" "$out"
