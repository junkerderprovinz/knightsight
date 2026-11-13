# Changelog

Every release is written by hand. The full notes for each release are in
[`.github/release-notes/`](.github/release-notes/) and on the
[releases page](https://github.com/junkerderprovinz/knightsight/releases).

## v1.0.0 (2026-11-13)

The first release of KnightSight: one window or one screen region, shared with a coding assistant and nothing else, on Windows, macOS and Linux.

## ✨ Added

- **Pick a window with a click or a region with a dragged rectangle.** A grey frame marks the pick, a yellow one shows it is shared, and Ctrl+Alt+Shift+X or closing the program ends the share.
- **An MCP server with six tools:** `look`, `click`, `scroll`, `type`, `key` and `steps`, the same for every system.
- **Nothing outside the share.** A point outside it is refused, and so are the Windows and Super keys.
- **Windows on x64 and ARM**, one EXE that sends input straight to the shared window.
- **macOS 13 and newer**, one app for Apple silicon and Intel.
- **Linux on x64 and ARM**, as a zip and as a Flatpak, on X11 and Wayland.
- **Reach it from another machine over SSH** with `KNIGHTSIGHT_SSH`.
- **English and German,** following the language your system is set to.
