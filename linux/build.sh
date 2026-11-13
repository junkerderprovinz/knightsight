#!/bin/sh
# Installs KnightSight under a prefix: bin/knightsight, lib/knightsight and the desktop
# entry, metainfo and icons under share. The zip and the Flatpak are both built with it.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
prefix=$1
id=io.github.junkerderprovinz.knightsight

install -Dm755 "$here/knightsight.sh" "$prefix/bin/knightsight"
for f in "$here"/knightsight/*.py; do
  install -Dm644 "$f" "$prefix/lib/knightsight/$(basename "$f")"
done
install -Dm644 "$here/data/$id.desktop" "$prefix/share/applications/$id.desktop"
install -Dm644 "$here/data/$id.metainfo.xml" "$prefix/share/metainfo/$id.metainfo.xml"
for size in 128 256 512; do
  dir="$prefix/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$dir"
  PYTHONPATH="$here" python3 -m knightsight.logo "$size" "$dir/$id.png"
done
install -Dm644 "$here/../LICENSE" "$prefix/share/licenses/$id/LICENSE"
