#!/bin/sh
# Puts KnightSight into the home folder: the program under ~/.local/share/knightsight, the
# command in ~/.local/bin, and the app menu entry with its icon where the desktop looks.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}
id=io.github.junkerderprovinz.knightsight

rm -rf "$data/knightsight"
mkdir -p "$data/knightsight" "$data/applications" "$HOME/.local/bin"
cp -r "$here/bin" "$here/lib" "$data/knightsight/"
ln -sf "$data/knightsight/bin/knightsight" "$HOME/.local/bin/knightsight"
cp -r "$here/share/icons" "$data/"
sed "s|^Exec=.*|Exec=$data/knightsight/bin/knightsight|" "$here/share/applications/$id.desktop" \
  > "$data/applications/$id.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$data/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$data/icons/hicolor" || true
echo "KnightSight is installed. Start it from the app menu, or run: knightsight"
