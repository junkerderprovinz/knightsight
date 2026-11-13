#!/bin/sh
# Builds the plain download: knightsight/ with the program, install.sh and the licence, zipped.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=$(readlink -f "$1")
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

sh "$here/build.sh" "$stage/knightsight"
install -Dm755 "$here/install.sh" "$stage/knightsight/install.sh"
rm -f "$out"
(cd "$stage" && zip -qr "$out" knightsight)
echo "built $out"
