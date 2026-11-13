# Changelog

Every release is written by hand. The full notes for each release are in
[`.github/release-notes/`](.github/release-notes/) and on the
[releases page](https://github.com/junkerderprovinz/knightsight/releases).

## v1.1.0 (unreleased)

KnightSight on macOS and Linux, with the same MCP server for all three systems.

## ✨ Added

- **KnightSight for macOS 13 and newer**, one app for Apple silicon and Intel.
- **KnightSight for Linux on x64 and ARM**, as a zip and as a Flatpak, on X11 and Wayland.
- **Download buttons for macOS, Linux and Flatpak.**

## ⚡ Improved

- **The MCP server reaches the panel on its loopback port off Windows.**

## v1.0.0 (2026-11-13)

The first release of KnightSight: one window or one screen region, shared with a coding assistant and nothing else.

## ✨ Added

- **Pick a window with a click or a region with a dragged rectangle.** A grey frame marks the pick, a yellow one shows it is shared, and Ctrl+Alt+Shift+X or closing the program ends the share.
- **An MCP server with six tools:** `look`, `click`, `scroll`, `type`, `key` and `steps`.
- **Input goes straight to the shared window,** so it can lie behind other windows while you work.
- **Nothing outside the share.** A point outside it is refused, and so is the Windows key.
- **Reach it from another machine over SSH** with `KNIGHTSIGHT_SSH`.
- **English and German,** following the language Windows is set to.
- **One EXE for x64 and ARM.**
