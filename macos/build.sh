#!/bin/sh
# Builds KnightSight.app as one binary for Apple silicon and Intel and zips it for the
# download. Noto Sans comes from the same pinned commit as in build.ps1, and the icon is
# drawn by the same code as the logo in the panel. KNIGHTSIGHT_VERSION, when set, goes
# into the bundle as its version.
set -eu
cd "$(dirname "$0")"

noto=https://raw.githubusercontent.com/notofonts/notofonts.github.io/5c3913063bb189df4edc94b766584dfb4c04a187/fonts/NotoSans/hinted/ttf
work=.build/bundle
app=dist/KnightSight.app

swift build -c release --arch arm64 --arch x86_64
bin=$(swift build -c release --arch arm64 --arch x86_64 --show-bin-path)

rm -rf dist "$work/KnightSight.iconset"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources/Fonts" "$work"
cp "$bin/KnightSight" "$app/Contents/MacOS/"
cp Info.plist "$app/Contents/"
# A tag name such as v1.1.0 works too.
version=${KNIGHTSIGHT_VERSION:-}
version=${version#v}
if [ -n "$version" ]; then
  plutil -replace CFBundleShortVersionString -string "$version" "$app/Contents/Info.plist"
  plutil -replace CFBundleVersion -string "$version" "$app/Contents/Info.plist"
fi

for name in NotoSans-Regular.ttf NotoSans-SemiBold.ttf; do
  [ -f "$work/$name" ] || curl -fsSL -o "$work/$name" "$noto/$name"
  cp "$work/$name" "$app/Contents/Resources/Fonts/"
done

"$bin/KnightSight" --icon-set "$work/KnightSight.iconset"
iconutil -c icns -o "$app/Contents/Resources/KnightSight.icns" "$work/KnightSight.iconset"

# Without a Developer ID the bundle gets an ad-hoc signature, which Apple silicon needs to start it at all.
codesign --force --sign - "$app"
lipo "$app/Contents/MacOS/KnightSight" -verify_arch arm64 x86_64

ditto -c -k --keepParent "$app" dist/knightsight-macos-universal.zip
echo "built macos/dist/knightsight-macos-universal.zip"
