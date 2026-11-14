#!/bin/sh
# Gives smoke_wayland.py a session bus, settings and a runtime folder of its own, and keeps
# its pictures and logs in the folder named first, e2e by default.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "${1:-e2e}"
out=$(cd "${1:-e2e}" && pwd)
home=$(mktemp -d)
mkdir -m 700 "$home/run"
mkdir -p "$home/config/glib-2.0/settings" "$home/data/gnome-shell/extensions"
cp -r "$here/shell-helper" "$home/data/gnome-shell/extensions/smoke-helper@knightsight.test"
cat > "$home/config/glib-2.0/settings/keyfile" <<'EOF'
[org/gnome/shell]
enabled-extensions=['smoke-helper@knightsight.test']
disable-extension-version-validation=true
welcome-dialog-last-shown-version='999'

[org/gnome/desktop/interface]
enable-hot-corners=false

[org/gnome/desktop/session]
idle-delay=uint32 0

[org/gnome/desktop/screensaver]
lock-enabled=false

[org/gnome/TextEditor]
restore-session=false
EOF

unset DISPLAY
export HOME="$home" XDG_RUNTIME_DIR="$home/run" XDG_CONFIG_HOME="$home/config" XDG_DATA_HOME="$home/data" \
  XDG_CACHE_HOME="$home/cache" XDG_CURRENT_DESKTOP=GNOME XDG_SESSION_TYPE=wayland WAYLAND_DISPLAY=wayland-0 \
  GDK_BACKEND=wayland GSETTINGS_BACKEND=keyfile LANGUAGE=en SMOKE_OUT="$out"
exec dbus-run-session -- python3 "$here/smoke_wayland.py"
