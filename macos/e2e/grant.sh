#!/bin/sh
# Allows the app Screen Recording and Accessibility without a prompt, the way the runner
# image allows its own agent: rows in both TCC databases, which only a Mac without System
# Integrity Protection lets anyone write. The rows carry the app's code requirement, which
# for an ad-hoc signature is the hash of this very build.
set -eu
app=$(cd "$1" && pwd)
id=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$app/Contents/Info.plist")
system="/Library/Application Support/com.apple.TCC/TCC.db"
user="$HOME/Library/Application Support/com.apple.TCC/TCC.db"

sw_vers
csrutil status || true
echo "columns of access:"
sudo sqlite3 "$system" "PRAGMA table_info(access)"

requirement=$(codesign -d -r- "$app" 2>&1 | sed -En 's/^(# )?designated => //p')
echo "designated requirement: $requirement"
work=$(mktemp -d)
echo "$requirement" | csreq -r- -b "$work/requirement"
csreq=$(xxd -p "$work/requirement" | tr -d '\n')
now=$(date +%s)

for service in kTCCServiceScreenCapture kTCCServiceAccessibility kTCCServicePostEvent; do
  row="INSERT OR REPLACE INTO access (service, client, client_type, auth_value, auth_reason, auth_version, csreq, flags, last_modified)
       VALUES ('$service', '$id', 0, 2, 4, 1, X'$csreq', 0, $now);"
  sudo sqlite3 "$system" "$row"
  sqlite3 "$user" "$row"
done
sudo sqlite3 "$system" "SELECT service, client, auth_value FROM access WHERE client = '$id'"

# From macOS 15 on, replayd asks again now and then before an app may capture without the
# system's picker. A date far ahead keeps that alert away.
approvals="$HOME/Library/Group Containers/group.com.apple.replayd/ScreenCaptureApprovals.plist"
mkdir -p "$(dirname "$approvals")"
defaults write "$approvals" "$app/Contents/MacOS/KnightSight" -date "3024-01-01 00:00:00 +0000"
killall cfprefsd 2>/dev/null || true
