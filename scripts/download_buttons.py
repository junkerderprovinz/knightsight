"""The download buttons the README shows, read by gen_download_buttons.py.

Each entry names a button the generator knows and where it leads. The rows,
their order, the colours and the words are the generator's, the same in every
repository.
"""

REPO = "knightsight"
RELEASE = "https://github.com/junkerderprovinz/knightsight/releases/latest/download/"

BUTTONS = {
    # One AnyCPU file runs on both, so both segments lead to it
    # (.github/workflows/release.yml attaches it to every release).
    "windows": RELEASE + "KnightSight.exe",
    "windows-arm": RELEASE + "KnightSight.exe",
    "macos": RELEASE + "knightsight-macos-universal.zip",
    "linux": RELEASE + "knightsight-linux-amd64.zip",
    "linux-arm": RELEASE + "knightsight-linux-arm64.zip",
    "flatpak": RELEASE + "knightsight-linux-amd64.flatpak",
    "flatpak-arm": RELEASE + "knightsight-linux-arm64.flatpak",
}
