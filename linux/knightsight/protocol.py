"""The wire protocol shared with mcp/knightsight-mcp.mjs and the Windows panel.

One JSON object per line in, one per line out. Nothing here touches the desktop, so
the refusals can be tested without a display.
"""

import json
from dataclasses import dataclass

from . import say

PORT = 47613
MAX_EDGE = 1568


class Refused(Exception):
    pass


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def contains(self, x, y):
        return self.x <= x < self.right and self.y <= y < self.bottom


def text(args, key):
    value = args.get(key)
    if not isinstance(value, str):
        raise Refused(f"Missing {key}.")
    return value


def number(args, key):
    value = args.get(key)
    if value is None:
        raise Refused(f"Missing {key}.")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise Refused(f"{key} is not a number.") from None


def flag(args, key):
    return args.get(key) is True


def scale(width, height):
    return min(1.0, MAX_EDGE / max(width, height))


def picture_size(width, height):
    s = scale(width, height)
    return max(1, round(width * s)), max(1, round(height * s))


def to_area(area, args):
    """Maps a point in the picture from look back into the share, refused outside it."""
    s = scale(area.width, area.height)
    x = area.x + round(number(args, "x") / s)
    y = area.y + round(number(args, "y") / s)
    if not area.contains(x, y):
        raise Refused("The point lies outside the share.")
    return x, y


NAMED = {
    "enter": "Return", "tab": "Tab", "esc": "Escape", "escape": "Escape", "space": "space",
    "backspace": "BackSpace", "delete": "Delete", "del": "Delete", "insert": "Insert",
    "home": "Home", "end": "End", "pageup": "Page_Up", "pagedown": "Page_Down",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
}
MODIFIERS = {"ctrl": "ctrl", "control": "ctrl", "strg": "ctrl", "alt": "alt", "shift": "shift"}
SYSTEM_KEYS = {"win", "windows", "meta", "super"}


@dataclass
class Combo:
    held: list
    # An X keysym name such as Return or F5, or a single character.
    key: str
    is_char: bool


def parse_combo(combo):
    """Reads ctrl+l, shift+tab or a single key into the modifiers and the key."""
    held, key, is_char = [], None, False
    for raw in combo.lower().split("+"):
        part = raw.strip()
        if part in SYSTEM_KEYS:
            raise Refused("The Super key, the one with the Windows logo, acts on the whole system and is refused.")
        if part in MODIFIERS:
            if MODIFIERS[part] not in held:
                held.append(MODIFIERS[part])
            continue
        if key is not None:
            raise Refused("Only one key besides Ctrl, Alt and Shift: " + combo)
        if part in NAMED:
            key = NAMED[part]
        elif len(part) > 1 and part[0] == "f" and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            key = "F" + str(int(part[1:]))
        elif len(part) == 1:
            key, is_char = part, True
        else:
            raise Refused("Unknown key: " + part)
    if key is None:
        raise Refused("The key itself is missing: " + combo)
    return Combo(held, key, is_char)


def text_keys(value):
    """The text as characters to type, with line breaks and tabs as their keys."""
    out = []
    for c in value:
        if c == "\r":
            continue
        if c == "\n":
            out.append(("Return", False))
        elif c == "\t":
            out.append(("Tab", False))
        else:
            out.append((c, True))
    return out


def key_name(combo):
    parts = []
    for raw in combo.split("+"):
        p = raw.strip().lower()
        parts.append(say.KEY_NAMES.get(p) or (p[:1].upper() + p[1:]))
    return "+".join(parts)


def describe(cmd, args):
    """What the panel says is being done, in the person's language."""
    if cmd == "look":
        return say.LOOKING
    if cmd == "click":
        return say.RIGHT_CLICKING if flag(args, "right") else say.DOUBLE_CLICKING if flag(args, "double") else say.CLICKING
    if cmd == "scroll":
        return say.SCROLLING
    if cmd == "type":
        return say.TYPING
    if cmd == "key":
        keys = args.get("keys")
        return say.PRESSING + key_name(keys) if isinstance(keys, str) else say.PRESSING_KEY
    return cmd


NOTHING_SHARED = "Nothing is shared right now. Choose a window or a region in the KnightSight window and start sharing."


def reply(line, panel):
    """Answers one request line. The panel holds the share, its desk acts on it."""
    out = {}
    try:
        args = json.loads(line)
        if not isinstance(args, dict):
            raise Refused("A request is one JSON object.")
        share = panel.share()
        if share is None:
            raise Refused(NOTHING_SHARED)
        desk = panel.desk
        if desk.minimized(share):
            raise Refused("The shared window is minimized.")
        cmd = text(args, "cmd")
        panel.working(describe(cmd, args))
        if cmd == "look":
            out.update(desk.look(share))
        elif cmd == "click":
            out["message"] = desk.click(share, args)
        elif cmd == "scroll":
            out["message"] = desk.scroll(share, args)
        elif cmd == "type":
            out["message"] = desk.type(share, text(args, "text"))
        elif cmd == "key":
            out["message"] = desk.key(share, text(args, "keys"))
        else:
            raise Refused("Unknown command: " + cmd)
        out["ok"] = True
    except Refused as e:
        out = {"ok": False, "error": str(e)}
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return json.dumps(out)
