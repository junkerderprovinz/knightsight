<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/knightsight-banner-dark.png">
    <img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/knightsight-banner.png" alt="KnightSight" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/junkerderprovinz/knightsight/actions/workflows/build.yml"><img src="https://img.shields.io/github/actions/workflow/status/junkerderprovinz/knightsight/build.yml?branch=main&label=Build&style=for-the-badge&logo=githubactions&logoColor=white" alt="Build" height="36"></a>&nbsp;
  <a href="https://github.com/junkerderprovinz/knightsight/releases/latest"><img src="https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-0078d4?style=for-the-badge" alt="Windows, macOS and Linux" height="36"></a>&nbsp;
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-Server-6e56cf?style=for-the-badge" alt="MCP server" height="36"></a>&nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue?style=for-the-badge&logo=gnu&logoColor=white" alt="License: AGPL-3.0" height="36"></a>
</p>

<br>

<p align="center">
<b>Show your coding assistant one window. Only that one.</b><br>
<br>
KnightSight is a small program for Windows, macOS and Linux. You click a window or drag a rectangle across the screen, and an assistant that speaks MCP can look at it, click in it and type into it. It sees nothing outside the frame, and nothing at all until it asks. Your mouse and keyboard stay with you the whole time, so you can get on with your own work while it pokes around.
</p>

<br>

<p><a id="table-of-contents" href="#table-of-contents"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/table-of-contents-dark.svg"><img src=".github/assets/sections/table-of-contents.svg" alt="Table of Contents" width="100%"></picture></a></p>

1. [Download](#1-download)
2. [Support](#2-support)
3. [What it looks like](#3-what-it-looks-like)
4. [What it does](#4-what-it-does)
5. [Getting started](#5-getting-started)
6. [Building from source](#6-building-from-source)
7. [How AI is used here](#7-how-ai-is-used-here)

<br>

<p><a id="1-download" href="#1-download"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/1-download-dark.svg"><img src=".github/assets/sections/1-download.svg" alt="1. Download" width="100%"></picture></a></p>

<!-- download-buttons: written by scripts/gen_download_buttons.py -->
<p align="center">
  <picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/group-desktop-dark.svg"><img src=".github/assets/sections/group-desktop.svg" alt="Desktop" width="100%"></picture>
</p>
<p align="center">
  <a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/KnightSight.exe"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(0,0,841.9,245.3))" alt="Download for Windows" width="160" height="46.618"></a><a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/KnightSight.exe"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(866,0,457.783,245.3))" alt="Download for Windows on ARM" width="87" height="46.618"></a>
  &nbsp;
  <a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/knightsight-macos-universal.zip"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(1348,0,841.9,245.3))" alt="Download for macOS" width="160" height="46.618"></a>
  &nbsp;
  <a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/knightsight-linux-amd64.zip"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(2214,0,841.9,245.3))" alt="Download for Linux" width="160" height="46.618"></a><a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/knightsight-linux-arm64.zip"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(3080,0,457.783,245.3))" alt="Download for Linux on ARM" width="87" height="46.618"></a>
</p>
<p align="center">
  <a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/knightsight-linux-amd64.flatpak"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(3562,0,841.9,245.3))" alt="Download the Flatpak" width="160" height="46.618"></a><a href="https://github.com/junkerderprovinz/knightsight/releases/latest/download/knightsight-linux-arm64.flatpak"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(4428,0,457.783,245.3))" alt="Download the Flatpak for ARM" width="87" height="46.618"></a>
</p>
<!-- /download-buttons -->

<br>

<p><a id="2-support" href="#2-support"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/2-support-dark.svg"><img src=".github/assets/sections/2-support.svg" alt="2. Support" width="100%"></picture></a></p>

<p align="center">
A one-knight job: I build it, keep it running, work through the issues and add what people ask for, until nothing is missing. It is free, with no accounts, no telemetry, no ads and no paid tier. No asterisk anywhere. Forged on evenings and weekends, with heart and stubbornness.
</p>

<p align="center">
If it has earned a place on your computer, toss a coin to your knight: it helps cover the costs and keeps the project alive. It also makes this knight's heart beat a little faster. Three ways below, whichever suits you.
</p>

<!-- give-buttons: written by scripts/gen_download_buttons.py -->
<p align="center">
  <a href="https://buymeacoffee.com/junkerderprovinz"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(4910,0,841.9,245.3))" alt="Buy me a coffee" width="160" height="46.618"></a>
  &nbsp;
  <a href="https://www.paypal.com/donate/?hosted_button_id=76FVV52TKXTUS"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(5776,0,841.9,245.3))" alt="PayPal" width="160" height="46.618"></a>
  &nbsp;
  <a href="https://junkerderprovinz.github.io/junkerderprovinz/"><img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/download-buttons/buttons.svg?v=c0bf84ea9ac0#svgView(viewBox(6642,0,841.9,245.3))" alt="Donate with crypto" width="160" height="46.618"></a>
</p>
<!-- /give-buttons -->

<br>

<p><a id="3-what-it-looks-like" href="#3-what-it-looks-like"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/3-what-it-looks-like-dark.svg"><img src=".github/assets/sections/3-what-it-looks-like.svg" alt="3. What it looks like" width="100%"></picture></a></p>

The app and the quests in these pictures are made up.

<p align="center">
  <img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/screenshots/pick.png" alt="A made-up to-do app in a grey frame next to the KnightSight panel, which names the chosen window and says it is not shared yet" width="100%">
  <br><em>Choose a window and a grey frame marks it. KnightSight shares nothing until you click Start sharing.</em>
</p>

<br>

<p align="center">
  <img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/screenshots/share.png" alt="The same app in a yellow frame with a label reading Taking a screenshot above its corner, and the panel showing the same activity next to a Stop sharing button" width="100%">
  <br><em>Once shared, the frame turns yellow. It pulses while the assistant works, and a label at its corner says what it's doing.</em>
</p>

<br>

<p align="center">
  <img src="https://raw.githubusercontent.com/junkerderprovinz/knightsight/main/.github/assets/screenshots/region.png" alt="A yellow frame around part of the to-do app while text appears in its input field, a label reading Typing, and the panel showing Region 585 x 364" width="100%">
  <br><em>Drag a rectangle to share part of the screen. Here the assistant types into the field inside the box.</em>
</p>

<br>

<p><a id="4-what-it-does" href="#4-what-it-does"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/4-what-it-does-dark.svg"><img src=".github/assets/sections/4-what-it-does.svg" alt="4. What it does" width="100%"></picture></a></p>

- **You pick what it sees.** Click a window or drag a rectangle over part of the screen. A grey frame marks your pick, and it turns yellow once you start sharing.
- **Six tools for the assistant.** `look` takes a picture, `click`, `scroll`, `type` and `key` act inside the share, and `steps` runs several of them in one go with a picture at the end if asked.
- **Your pointer stays where you left it.** Clicks and keys go straight to the shared window, even when it sits behind other windows. Store apps only listen to real input, so they come to the front for a moment once mouse and keyboard have rested for about a second.
- **Nothing outside the frame.** A click outside the share is refused, and so are the Windows and Super keys. A picture of a shared window shows that window alone, whatever lies on top of it.
- **You can see when it works.** The frame pulses while the assistant is busy, and a small label at its top right corner says what it is doing, such as "Typing" or "Taking a screenshot".
- **One shortcut to stop.** Ctrl+Alt+Shift+X ends the share at once, and so does closing KnightSight.
- **A few things stay out of reach.** A minimized window can't be shared, and a window running as administrator takes no input from it.
- **Small and quiet.** One EXE on Windows, one app on macOS, a zip or a Flatpak on Linux. It speaks English, or German when your system does.

### On macOS and Linux

A few things work a little differently there.

- **macOS 13 or newer:** KnightSight asks for Screen Recording and Accessibility the first time you share. It types into the shared window in the background, even while it is covered. For a click, a scroll or a shortcut with Cmd, it waits until mouse and keyboard have rested for about a second, brings the window to the front for a moment and then puts your pointer and your previous app back. If a click opens a menu, the window stays in front until the menu closes. Windows that are hidden, minimized or on another desktop stay out of reach.
- **Linux on X11:** the frame, the label and pictures of covered windows work as on Windows. For a click or a key, KnightSight waits until you have rested for about a second, brings the shared window forward for a moment and then hands your window and pointer back.
- **Linux on Wayland:** your desktop asks which window or screen to share and shows its own sharing indicator. KnightSight can't draw on top of other apps there, so the frame goes around its own card instead. Clicks move your real pointer and land on whatever is visible at that spot, so keep the shared window uncovered. Keys go where the keyboard focus is.

<br>

<p><a id="5-getting-started" href="#5-getting-started"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/5-getting-started-dark.svg"><img src=".github/assets/sections/5-getting-started.svg" alt="5. Getting started" width="100%"></picture></a></p>

1. Download KnightSight for your system and `knightsight-mcp.mjs` from the [latest release](https://github.com/junkerderprovinz/knightsight/releases/latest).
2. Start KnightSight, choose a window or a region and click **Start sharing**.
3. Add the MCP server to your assistant. It needs [Node.js](https://nodejs.org) 18 or newer. Most clients read a config like this one:

```json
{
  "mcpServers": {
    "knightsight": {
      "command": "node",
      "args": ["C:\\Tools\\knightsight-mcp.mjs"]
    }
  }
}
```

Clients with a command line usually have an `mcp add` command that takes the same name and command in one line.

Then ask your assistant to take a look. While nothing is shared, it gets a short note saying so and nothing else.

### First start on macOS and Linux

- **macOS:** the app isn't notarized, so the first start needs a nudge. On macOS 13 and 14, Control-click `KnightSight.app` in Finder and choose **Open**. On macOS 15 and newer, open it once, close the warning, then click **Open Anyway** under **System Settings > Privacy & Security**. Allow Screen Recording and Accessibility when you start sharing. After an update macOS may ask for both again.
- **Linux zip:** unzip it and run `knightsight/bin/knightsight`, or `sh knightsight/install.sh` for a menu entry and a `knightsight` command. It needs GTK 4 and GStreamer with PipeWire from your system, on Debian and Ubuntu `python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-gstreamer-1.0 gstreamer1.0-pipewire`. If something is missing, KnightSight names the packages for Fedora and Arch too.
- **Flatpak:** `flatpak install --user knightsight-linux-amd64.flatpak` (or the ARM file), then `flatpak run io.github.junkerderprovinz.knightsight`. The runtime comes from Flathub.

### From another machine

The assistant can also run somewhere else, in a VM or on a server, and reach KnightSight over SSH. KnightSight listens on `127.0.0.1:47613` only, never on the network, so the MCP server opens one SSH tunnel to it and keeps it open. Set `KNIGHTSIGHT_SSH` to the machine KnightSight runs on, the way `ssh` takes it, as `me@desktop` or an alias from `~/.ssh/config`:

```json
{
  "mcpServers": {
    "knightsight": {
      "command": "node",
      "args": ["/opt/knightsight/knightsight-mcp.mjs"],
      "env": { "KNIGHTSIGHT_SSH": "me@desktop" }
    }
  }
}
```

That machine needs an SSH server, and the login has to work with a key, since the MCP server cannot type a password. If you switch between several machines, `KNIGHTSIGHT_SSH_MODULE` can name a module of your own instead. Its `desk()` returns `{ host, user }` or `null` and is asked before every call.

<br>

<p><a id="6-building-from-source" href="#6-building-from-source"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/6-building-from-source-dark.svg"><img src=".github/assets/sections/6-building-from-source.svg" alt="6. Building from source" width="100%"></picture></a></p>

```powershell
.\build.ps1
```

The script compiles `src\KnightSight.cs` with the .NET Framework compiler that comes with Windows, so there is nothing to install. It fetches Noto Sans once from a pinned commit into `obj\` and embeds it, draws the icon with the same code as the logo in the window and writes `dist\KnightSight.exe`. `-Out` puts the EXE somewhere else.

```sh
macos/build.sh
```

On a Mac with the Xcode command line tools, this builds `KnightSight.app` for Apple silicon and Intel and zips it into `macos/dist/`. `swift test --package-path macos` runs the tests.

```sh
sh linux/package.sh knightsight-linux.zip
```

This packs the Linux program into a zip. The Flatpak manifest is `linux/flatpak/io.github.junkerderprovinz.knightsight.yml`, and `python3 -m unittest discover -s linux/tests` runs the tests.

<br>

<p><a id="7-how-ai-is-used-here" href="#7-how-ai-is-used-here"><picture><source media="(prefers-color-scheme: dark)" srcset=".github/assets/sections/7-how-ai-is-used-here-dark.svg"><img src=".github/assets/sections/7-how-ai-is-used-here.svg" alt="7. How AI is used here" width="100%"></picture></a></p>

One knight builds this, and AI is one of the tools I work with, the same way I work with an editor or a compiler. It helps me write code and documentation and it checks my work, and that saves me a good many evenings. It does not make the decisions, though. I read and understand everything before it ships, and if something here breaks, that is on me and not on the tool.

You do not have to take my word for it. The code is open and every release note is written by hand. The issue tracker shows how problems actually get handled, including the ones I got wrong the first time. If you find something that is not right, open an issue and I will look at it.

<br>

Bugs, ideas or feature requests? Please [open a GitHub issue](https://github.com/junkerderprovinz/knightsight/issues).

KnightSight is released under the [GNU Affero General Public License v3.0](LICENSE). It embeds [Noto Sans](https://notofonts.github.io), which is under the SIL Open Font License 1.1. The name KnightSight and its logo are not part of the licence, so a fork needs a name of its own.
