#!/bin/sh
# Builds the AppImage: the program with the Python, GTK 4, GStreamer and AT-SPI of this
# system, so build it on the oldest system it is meant to start on. linuxdeploy leaves glibc,
# the graphics drivers, libpipewire and the libraries every desktop has to the system.
#
#     sh linux/appimage.sh knightsight-linux-amd64.AppImage
#
# Needs what the zip needs, plus gstreamer1.0-plugins-base, gir1.2-girepository-2.0,
# dconf-gsettings-backend, curl and glib-compile-schemas.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=$(readlink -f "$1")
id=io.github.junkerderprovinz.knightsight
arch=$(uname -m)
sys=/usr/lib/$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("MULTIARCH"))')
py=$(python3 -c 'import sys; print("python%d.%d" % sys.version_info[:2])')
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
app=$stage/KnightSight.AppDir

# The checksums are the ones GitHub lists for these release files.
case $arch in
  x86_64)
    linuxdeploy_sum=c20cd71e3a4e3b80c3483cef793cda3f4e990aca14014d23c544ca3ce1270b4d
    appimagetool_sum=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
    runtime_sum=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d ;;
  aarch64)
    linuxdeploy_sum=620095110d693282b8ebeb244a95b5e911cf8f65f76c88b4b47d16ae6346fcff
    appimagetool_sum=f0837e7448a0c1e4e650a93bb3e85802546e60654ef287576f46c71c126a9158
    runtime_sum=00cbdfcf917cc6c0ff6d3347d59e0ca1f7f45a6df1a428a0d6d8a78664d87444 ;;
  *) echo "no AppImage tools for $arch" >&2; exit 1 ;;
esac
fetch() {
  curl -fsSL --retry 3 -o "$stage/$1" "$2"
  echo "$3  $stage/$1" | sha256sum -c --quiet
  chmod +x "$stage/$1"
}
fetch linuxdeploy "https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20251107-1/linuxdeploy-$arch.AppImage" "$linuxdeploy_sum"
fetch appimagetool "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-$arch.AppImage" "$appimagetool_sum"
fetch runtime "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-$arch" "$runtime_sum"
# The tools are AppImages themselves, and containers often have no FUSE to mount them.
export APPIMAGE_EXTRACT_AND_RUN=1

sh "$here/build.sh" "$app/usr"

# Python with the standard library, less the parts nothing here imports, and the bindings.
install -Dm755 "$(readlink -f /usr/bin/python3)" "$app/usr/bin/python3"
mkdir -p "$app/usr/lib/$py" "$app/usr/lib/python3/dist-packages"
tar -C "/usr/lib/$py" -cf - --exclude=__pycache__ --exclude=test --exclude=idlelib --exclude=tkinter \
  --exclude=turtledemo --exclude=lib2to3 --exclude=ensurepip --exclude='config-*' --exclude=dist-packages \
  --exclude=site-packages --exclude=sitecustomize.py . | tar -C "$app/usr/lib/$py" -xf -
tar -C /usr/lib/python3/dist-packages -cf - --exclude=__pycache__ gi cairo |
  tar -C "$app/usr/lib/python3/dist-packages" -xf -

# The typelibs the program asks for and the ones they build on, and the libraries of the
# first. linuxdeploy follows those to the rest and leaves out what it leaves to the system.
mkdir -p "$app/usr/lib/girepository-1.0"
python3 - "$app/usr/lib/girepository-1.0" > "$stage/libraries" <<'EOF'
import shutil
import sys

import gi

gi.require_version("GIRepository", "2.0")
from gi.repository import GIRepository

repo = GIRepository.Repository.get_default()
wanted = ["Gtk-4.0", "GdkX11-4.0", "PangoCairo-1.0", "Gst-1.0", "Atspi-2.0"]
todo, seen = list(wanted), set()
while todo:
    name, version = todo.pop().rsplit("-", 1)
    if name in seen:
        continue
    seen.add(name)
    repo.require(name, version, 0)
    shutil.copy(repo.get_typelib_path(name), sys.argv[1])
    if f"{name}-{version}" in wanted:
        print("\n".join(repo.get_shared_library(name).split(",")))
    todo += repo.get_dependencies(name)
EOF

# pipewiresrc ! videoconvert ! capsfilter ! appsink, as stream.py builds it.
mkdir -p "$app/usr/lib/gstreamer-1.0"
for plugin in pipewire videoconvert coreelements app; do
  cp "$sys/gstreamer-1.0/libgst$plugin.so" "$app/usr/lib/gstreamer-1.0/"
done
install -Dm755 "$sys/gstreamer1.0/gstreamer-1.0/gst-plugin-scanner" "$app/usr/libexec/gst-plugin-scanner"

# GTK's own settings, and dconf, so the file chooser remembers its folder.
mkdir -p "$app/usr/share/glib-2.0/schemas"
cp /usr/share/glib-2.0/schemas/org.gtk.gtk4.*.gschema.xml "$app/usr/share/glib-2.0/schemas/"
glib-compile-schemas "$app/usr/share/glib-2.0/schemas"
install -Dm644 "$sys/gio/modules/libdconfsettings.so" "$app/usr/lib/gio/modules/libdconfsettings.so"

set --
for library in $(sort -u "$stage/libraries") libXtst.so.6 libXcomposite.so.1 libXext.so.6; do
  set -- "$@" --library "$sys/$library"
done
for elf in "$app/usr/bin/python3" "$app/usr/libexec/gst-plugin-scanner" "$app/usr/lib/$py/lib-dynload" \
  "$app/usr/lib/python3/dist-packages/gi" "$app/usr/lib/python3/dist-packages/cairo" \
  "$app/usr/lib/gstreamer-1.0" "$app/usr/lib/gio/modules"; do
  set -- "$@" --deploy-deps-only "$elf"
done
"$stage/linuxdeploy" --appdir "$app" "$@" --custom-apprun "$here/AppRun" \
  --desktop-file "$app/usr/share/applications/$id.desktop" \
  --icon-file "$app/usr/share/icons/hicolor/256x256/apps/$id.png"

rm -f "$out"
ARCH=$arch "$stage/appimagetool" --runtime-file "$stage/runtime" "$app" "$out"
echo "built $out"
