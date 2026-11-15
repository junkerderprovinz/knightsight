"""The pinboard without its window: notes on spots of the share, the rounds handed to the
assistant through the `notes` command, and the file a round can be saved as.

Places are kept in share pixels, the ones look takes its picture in before scaling it down.
"""

import html
import json
import math
import os
import threading
import time
from dataclasses import dataclass

from . import protocol, say

KINDS = ("bug", "wish", "question")
# Wish wears the app's accent.
KIND_COLOURS = {"bug": (250, 77, 86), "wish": (252, 196, 25), "question": (29, 153, 243)}
INK = (22, 22, 22)
MARGIN = 24
PIN_BOX = 240
MIN_DRAG = 6
PIN_RADIUS = 12
BADGE_RADIUS = 11


@dataclass
class Note:
    number: int
    kind: str
    text: str
    author: str
    x: int
    y: int
    width: int = 0
    height: int = 0

    @property
    def pin(self):
        return self.width == 0 and self.height == 0


class Board:
    """The unsent notes. Their numbers keep counting across rounds."""

    def __init__(self):
        self.notes = []
        self.next = 1

    def add(self, kind, text, author, mark):
        note = Note(self.next, kind, text, author, *mark)
        self.next += 1
        self.notes.append(note)
        return note

    def remove(self, note):
        self.notes.remove(note)

    def clear(self):
        self.notes = []


class Gate:
    """Lets one call through per span of seconds. On Wayland one press of the pinboard key
    can arrive twice, from the desktop's shortcut and from the window's own."""

    def __init__(self, span, clock=time.monotonic):
        self.span, self.clock, self.last = span, clock, None

    def open(self):
        now = self.clock()
        if self.last is not None and now - self.last < self.span:
            return False
        self.last = now
        return True


class Fit:
    """How share pixels land in a view: scaled by k, then moved by x, y."""

    def __init__(self, k, x=0.0, y=0.0):
        self.k, self.x, self.y = k, x, y

    @classmethod
    def inside(cls, width, height, view_width, view_height):
        """The picture of a share of width x height, as large as it fits and centred."""
        k = min(view_width / width, view_height / height)
        return cls(k, (view_width - width * k) / 2, (view_height - height * k) / 2)

    def to_view(self, x, y):
        return self.x + x * self.k, self.y + y * self.k

    def to_share(self, x, y, width, height):
        """The share pixel under a point of the view, held to the share's edges."""
        return (max(0, min(width, round((x - self.x) / self.k))),
                max(0, min(height, round((y - self.y) / self.k))))


def mark(fit, start, end, width, height):
    """The mark a press at start and a release at end make: a pin for a short move, else a box.
    None for a click or a drag in the empty band beside the picture."""
    if math.dist(start, end) < MIN_DRAG:
        left, top = fit.to_view(0, 0)
        right, bottom = fit.to_view(width, height)
        if not (left <= start[0] <= right and top <= start[1] <= bottom):
            return None
        return (*fit.to_share(*start, width, height), 0, 0)
    (x0, y0), (x1, y1) = fit.to_share(*start, width, height), fit.to_share(*end, width, height)
    if x0 == x1 or y0 == y1:
        return None
    return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def hit(notes, fit, x, y):
    """The note whose mark lies under a point of the view, the newest on top."""
    for note in reversed(notes):
        left, top = fit.to_view(note.x, note.y)
        if note.pin:
            if math.dist((x, y), (left, top)) <= PIN_RADIUS + 2:
                return note
            continue
        right, bottom = left + note.width * fit.k, top + note.height * fit.k
        if left - 3 <= x <= right + 3 and top - 3 <= y <= bottom + 3:
            return note
        if math.dist((x, y), (left, top)) <= BADGE_RADIUS + 2:
            return note
    return None


def crop_box(note, width, height):
    """What a note's crop shows: the box with a margin around it, or a square around a pin,
    held to the share. None when the spot lies outside a share that has shrunk since."""
    if note.pin:
        half = PIN_BOX // 2
        left, top, right, bottom = note.x - half, note.y - half, note.x + half, note.y + half
    else:
        left, top = note.x - MARGIN, note.y - MARGIN
        right, bottom = note.x + note.width + MARGIN, note.y + note.height + MARGIN
    left, top = max(0, left), max(0, top)
    right, bottom = min(width, right), min(height, bottom)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def entry(note, scale):
    """A note as the protocol sends it, placed in the round's picture."""
    out = {"number": note.number, "kind": note.kind, "text": note.text, "author": note.author,
           "x": round(note.x * scale), "y": round(note.y * scale)}
    if note.pin:
        out["pin"] = True
    else:
        out["width"] = round(note.width * scale)
        out["height"] = round(note.height * scale)
    return out


def sent_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def assemble(title, width, height, notes, picture, crop, sent):
    """The fields of a round from a share of width x height. picture is the marked frame as
    PNG base64, crop(note, box) gives a note's crop the same way."""
    scale = protocol.scale(width, height)
    entries = []
    for note in notes:
        e = entry(note, scale)
        box = crop_box(note, width, height)
        if box:
            e["image"] = crop(note, box)
        entries.append(e)
    pw, ph = protocol.picture_size(width, height)
    return {"sent": sent, "title": title, "width": pw, "height": ph, "image": picture, "notes": entries}


class Rounds:
    """The latest round and whether the assistant has fetched it. The request thread reads it
    while the panel's thread sends."""

    def __init__(self):
        self.lock = threading.Lock()
        self.latest = None
        self.count = 0
        self.read = False

    def send(self, fields):
        with self.lock:
            self.count += 1
            self.latest = {"ok": True, "round": self.count, **fields}
            self.read = False
            return self.count

    def answer(self, unread):
        with self.lock:
            if self.latest is None or unread and self.read:
                return {"ok": True, "round": self.count}
            self.read = True
            return self.latest


def load_author(folder):
    try:
        with open(os.path.join(folder, "pinboard.json"), encoding="utf-8") as f:
            value = json.load(f).get("author")
    except (OSError, ValueError, AttributeError):
        return ""
    return value if isinstance(value, str) else ""


def save_author(folder, author):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "pinboard.json"), "w", encoding="utf-8") as f:
        json.dump({"author": author}, f)


PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading}</title>
<style>
:root {{ color-scheme: light dark; --ground: #f4f4f4; --surface: #ffffff; --text: #161616; --muted: #6f6f6f; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ground: #161616; --surface: #262626; --text: #f4f4f4; --muted: #8d8d8d; }}
}}
body {{ margin: 0; padding: 32px 16px; background: var(--ground); color: var(--text);
  font: 15px/1.5 "Noto Sans", system-ui, sans-serif; }}
main {{ max-width: 1000px; margin: 0 auto; }}
h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 4px; }}
.muted {{ color: var(--muted); font-size: 13px; }}
img {{ display: block; max-width: 100%; height: auto; border-radius: 6px; }}
.card {{ background: var(--surface); border-radius: 10px; padding: 16px; margin-top: 16px; }}
.note {{ display: grid; grid-template-columns: 28px 1fr; gap: 4px 12px; }}
.badge {{ width: 24px; height: 24px; border-radius: 50%; color: {ink}; font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; box-shadow: 0 0 0 2px #fff; }}
.note p {{ margin: 0; white-space: pre-wrap; }}
.note img {{ grid-column: 2; margin-top: 8px; }}
</style>
</head>
<body>
<main>
<h1>{heading}</h1>
<div class="muted">{round} &middot; {sent}</div>
<div class="card"><img src="data:image/png;base64,{image}" alt="{title}"></div>
{notes}
</main>
</body>
</html>
"""

NOTE = """<div class="card note">
<div class="badge" style="background: {colour}">{number}</div>
<div><div class="muted">{kind}{author}</div><p>{text}</p></div>
{crop}</div>"""


def _web(colour):
    return "#%02x%02x%02x" % colour


def page(fields, number):
    """The round as one HTML file with its pictures inside, labelled in the person's language."""
    parts = []
    for n in fields["notes"]:
        author = " &middot; " + html.escape(say.from_author(n["author"])) if n["author"] else ""
        crop = f'<img src="data:image/png;base64,{n["image"]}" alt="">' if "image" in n else ""
        parts.append(NOTE.format(colour=_web(KIND_COLOURS[n["kind"]]), number=n["number"],
                                 kind=html.escape(say.KINDS[n["kind"]]), author=author, text=html.escape(n["text"]),
                                 crop=crop))
    sent = fields["sent"].replace("T", " ").replace("Z", " UTC")
    return PAGE.format(lang="de" if say.GERMAN else "en", heading=html.escape(say.file_heading(fields["title"])),
                       round=html.escape(say.round_label(number)), sent=sent, image=fields["image"],
                       title=html.escape(fields["title"]), ink=_web(INK), notes="\n".join(parts))
