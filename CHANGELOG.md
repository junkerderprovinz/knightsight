# Changelog

Every release is written by hand. The full notes for each release are in
[`.github/release-notes/`](.github/release-notes/) and on the
[releases page](https://github.com/junkerderprovinz/knightsight/releases).

## v1.2.1 (2026-11-16)

Controls in every look, whole screens and a pointer that shows where your assistant acts.

## 🎨 Design

- **A roomier panel.** The window is wider and calmer: a larger live picture, a larger title, more space between the rows and taller buttons. Window, Region and Screen sit in one row, the pinboard and the share button below.

## ✨ Added

- **Controls in every look.** A look lists the buttons, fields, links and other controls the system reports inside the share, each with a ref such as e12, and click and scroll take that ref instead of a point. What someone typed into a field and anything in a password field stay out.
- **Wait for a control.** The new `wait` tool waits until a control with a given name shows up in the share and then returns a look, instead of looking again and again.
- **Share a whole screen.** A new Screen button shares one monitor. On Wayland the system dialog chooses it. Clicks of the assistant on KnightSight itself are refused.
- **See where your assistant acts.** A yellow pointer of its own glides to each spot before a click, a scroll or typing, with a small ripple on every click, and fades out when the work pauses. Your own pointer never moves for it. It lies right above the shared window, so it hides behind other windows like the window does, and the pictures your assistant gets leave it out. Wayland has no room for it, there the dot in the finder shows the last click.

## ⚡ Improved

- **Refusals say whether anything arrived.** When an action is refused after input went out, the reply says so, and your assistant looks before it tries again instead of clicking twice.
- **The share stays with its window.** KnightSight remembers which program a shared window belongs to and when it started, so a window number the system hands on to another program never takes over the share.

## v1.2.0 (2026-11-16)

A new panel with a finder, and minimized windows come back.

## 🎨 Design

- **A new panel with a finder.** The left side of the panel shows the shared window as a small live picture. It turns from grey to colour when the share starts and its corners snap in yellow. While your assistant works, a line sweeps over it and a dot marks where it just clicked. The share button is bigger, the pinboard has a full button with its name, the info button sits in the title bar, and the blacks and whites are a little warmer, in the dark and the light theme alike.

## ⚡ Improved

- **Minimized windows come back.** When your assistant asks for a minimized window, KnightSight restores it behind your other windows without taking the focus and gives it a moment to draw before the picture. This works on Windows, on macOS and on Linux with X11. Wayland offers no way to do it, so there a minimized window stays out of reach.

## 🐛 Fixed

- **On macOS, minimizing the shared window keeps the share.** The window server leaves a minimized window out when asked for it alone, and KnightSight took that for a closed window.

## v1.1.0 (2026-11-15)

Notes for your assistant, pinned right onto the share.

## ✨ Added

- **The pinboard.** While you share, Ctrl+Shift+A (Cmd+Shift+A on a Mac) or the pin button opens it over the share. Drag a box or click a pin, hold Shift to give one note several spots, write the note and mark it as a bug, a wish or a question. Done sends every note to your assistant, and Save as file keeps them as one HTML page. On Wayland it opens as a window with a picture of the share.
- **A seventh tool, `pinboard`,** which hands the assistant each note with the place of every spot, a picture of each spot and the whole share with labelled markers. With `wait` it waits for you to press Done.
- **The shortcut is only taken while you share,** so Ctrl+Shift+A stays free for other programs the rest of the time.

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
