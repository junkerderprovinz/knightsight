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
# Each mark of a note gets a letter of its own.
MAX_MARKS = 26


@dataclass
class Mark:
    x: int
    y: int
    width: int = 0
    height: int = 0

    @property
    def pin(self):
        return self.width == 0 and self.height == 0


@dataclass
class Note:
    number: int
    kind: str
    text: str
    author: str
    marks: list

    def label(self, index):
        """The number for a note's only mark, with a letter in the order they were made for several."""
        if len(self.marks) == 1:
            return str(self.number)
        return f"{self.number}{chr(ord('a') + index)}"


def kind_line(note):
    if len(note.marks) == 1:
        return say.KINDS[note.kind]
    return f"{say.KINDS[note.kind]}, {say.spots(len(note.marks))}"


class Board:
    """The unsent notes. Their numbers keep counting across rounds. Every change also goes to
    the file, so the notes come back after KnightSight ended or crashed. restored says they
    did and no share has taken them over yet."""

    def __init__(self, file=None):
        self.file = file
        self.notes = _pinned(file)
        self.next = max((n.number for n in self.notes), default=0) + 1
        self.restored = bool(self.notes)

    def add(self, kind, text, author, marks):
        note = Note(self.next, kind, text, author, list(marks))
        self.next += 1
        self.notes.append(note)
        self._keep()
        return note

    def update(self, note, kind, text, author, marks):
        note.kind, note.text, note.author, note.marks = kind, text, author, list(marks)
        self._keep()

    def remove(self, note):
        self.notes.remove(note)
        self._keep()

    def clear(self):
        self.notes = []
        self._keep()

    def forget(self):
        """Drops the notes when another share is chosen. The ones from the last run go to the
        first share chosen, most likely the one they were pinned to."""
        if self.restored:
            self.restored = False
        else:
            self.notes = []
        self._keep()

    def _keep(self):
        if self.file is not None:
            _write(self.file, {"notes": [{"number": n.number, "kind": n.kind, "text": n.text, "author": n.author,
                                          "marks": [vars(m) for m in n.marks]} for n in self.notes]})


def _pinned(file):
    if file is None:
        return []
    try:
        with open(file, encoding="utf-8") as f:
            return [Note(int(n["number"]), _kind(n["kind"]), str(n["text"]), str(n["author"]),
                         [Mark(int(m["x"]), int(m["y"]), int(m["width"]), int(m["height"])) for m in n["marks"]])
                    for n in json.load(f)["notes"]]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _kind(kind):
    if kind not in KINDS:
        raise ValueError(kind)
    return kind


def _write(file, content):
    """Written beside the file and then swapped in, so a crash in between leaves the old
    content or the new one, never half of it. Should the disk refuse, it still waits in memory."""
    part = file + ".part"
    try:
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(part, "w", encoding="utf-8") as f:
            json.dump(content, f)
        os.replace(part, file)
    except OSError:
        pass


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
        return Mark(*fit.to_share(*start, width, height))
    (x0, y0), (x1, y1) = fit.to_share(*start, width, height), fit.to_share(*end, width, height)
    if x0 == x1 or y0 == y1:
        return None
    return Mark(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))


def _under(m, fit, x, y):
    left, top = fit.to_view(m.x, m.y)
    if m.pin:
        return math.dist((x, y), (left, top)) <= PIN_RADIUS + 2
    right, bottom = left + m.width * fit.k, top + m.height * fit.k
    return (left - 3 <= x <= right + 3 and top - 3 <= y <= bottom + 3
            or math.dist((x, y), (left, top)) <= BADGE_RADIUS + 2)


def hit(notes, fit, x, y):
    """The note and its mark under a point of the view, the newest on top, or None."""
    for note in reversed(notes):
        for m in reversed(note.marks):
            if _under(m, fit, x, y):
                return note, m
    return None


def gesture(shown, editing, fit, start, end, width, height, shift):
    """What a press at start and a release at end do on a share of width x height, as
    ("edit", note), ("new", mark), ("add", mark) or ("drop", mark), or None for nothing.

    shown are the notes on the share with editing, the one open in the editor, among them.
    Shift adds marks to that note and takes them off again, down to the last.
    """
    moved = math.dist(start, end) >= MIN_DRAG
    under = None if moved else hit(shown, fit, *start)
    if shift and editing is not None:
        if under is not None and under[0] is editing:
            return ("drop", under[1]) if len(editing.marks) > 1 else None
        spot = mark(fit, start, end, width, height)
        if spot is None or len(editing.marks) >= MAX_MARKS:
            return None
        return "add", spot
    if under is not None:
        return None if under[0] is editing else ("edit", under[0])
    spot = mark(fit, start, end, width, height)
    return None if spot is None else ("new", spot)


def beside(area, size, screen, gap):
    """Where a window of size goes next to the share on a screen of that size: right of it,
    else left of it, else over its right edge, and level with its top as far as the screen allows."""
    width, height = size
    if area.right + gap + width <= screen[0]:
        x = area.right + gap
    elif area.x - gap - width >= 0:
        x = area.x - gap - width
    else:
        x = screen[0] - gap - width
    return x, max(0, min(area.y, screen[1] - height))


def overlaps(a, b):
    return a.x < b.right and b.x < a.right and a.y < b.bottom and b.y < a.bottom


def crop_box(m, width, height):
    """What a mark's crop shows: the box with a margin around it, or a square around a pin,
    held to the share. None when the spot lies outside a share that has shrunk since."""
    if m.pin:
        half = PIN_BOX // 2
        left, top, right, bottom = m.x - half, m.y - half, m.x + half, m.y + half
    else:
        left, top = m.x - MARGIN, m.y - MARGIN
        right, bottom = m.x + m.width + MARGIN, m.y + m.height + MARGIN
    left, top = max(0, left), max(0, top)
    right, bottom = min(width, right), min(height, bottom)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def place(m, scale):
    """A mark as the protocol sends it, placed in the round's picture."""
    out = {"x": round(m.x * scale), "y": round(m.y * scale)}
    if m.pin:
        out["pin"] = True
    else:
        out["width"] = round(m.width * scale)
        out["height"] = round(m.height * scale)
    return out


def sent_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def assemble(title, width, height, notes, picture, crop, sent):
    """The fields of a round from a share of width x height. picture is the marked frame as
    PNG base64, crop(note, box) gives the crop around one of its marks the same way."""
    scale = protocol.scale(width, height)
    entries = []
    for note in notes:
        spots = []
        for i, m in enumerate(note.marks):
            spot = {"label": note.label(i), **place(m, scale)}
            box = crop_box(m, width, height)
            if box:
                spot["image"] = crop(note, box)
            spots.append(spot)
        entries.append({"number": note.number, "kind": note.kind, "text": note.text, "author": note.author,
                        "marks": spots})
    pw, ph = protocol.picture_size(width, height)
    return {"sent": sent, "title": title, "width": pw, "height": ph, "image": picture, "notes": entries}


class Rounds:
    """The rounds sent and which the assistant has. The request thread reads them while the
    panel's thread sends. Each one also waits in a file of the folder until the assistant
    confirms it has read it, so KnightSight ending or crashing before then does not lose it.
    An assistant that does not confirm gets a round once."""

    def __init__(self, folder=None):
        self.lock = threading.Lock()
        self.folder = folder
        self.waiting = _waiting(folder)
        self.latest = self.waiting[-1][0] if self.waiting else None
        self.count = self.latest["round"] if self.latest else 0
        self.handed = 0

    @property
    def read(self):
        with self.lock:
            return self.latest is not None and self.handed >= self.latest["round"]

    def send(self, fields):
        with self.lock:
            self.count += 1
            self.latest = {"ok": True, "round": self.count, **fields}
            file = None
            if self.folder is not None:
                file = os.path.join(self.folder, "sent", f"{self.count}.json")
                _write(file, self.latest)
            self.waiting.append((self.latest, file))
            return self.count

    def answer(self, unread, confirms=False):
        """The oldest round not confirmed yet. Without one, unread answers with the number of
        the last round alone, which is what the MCP server waits on, and a plain ask brings
        the last round again."""
        with self.lock:
            if not self.waiting:
                return {"ok": True, "round": self.count} if unread or self.latest is None else self.latest
            fields = self.waiting[0][0]
            self.handed = max(self.handed, fields["round"])
            if not confirms:
                self._settle(fields["round"])
            return fields

    def confirm(self, number):
        with self.lock:
            self._settle(number)

    def _settle(self, number):
        for fields, file in [w for w in self.waiting if w[0]["round"] <= number]:
            self.waiting.remove((fields, file))
            if file is not None:
                try:
                    os.remove(file)
                except OSError:
                    pass


def _waiting(folder):
    """The rounds in the folder, oldest first. round.json is where 1.1.2 kept its single round."""
    if folder is None:
        return []
    files = [os.path.join(folder, "round.json")]
    sent = os.path.join(folder, "sent")
    if os.path.isdir(sent):
        files += [os.path.join(sent, name) for name in os.listdir(sent) if name.endswith(".json")]
    found = []
    for file in files:
        try:
            with open(file, encoding="utf-8") as f:
                fields = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(fields, dict) and isinstance(fields.get("round"), int):
            found.append((fields, file))
    return sorted(found, key=lambda w: w[0]["round"])


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
.badge {{ min-width: 24px; height: 24px; padding: 0 6px; box-sizing: border-box; border-radius: 12px; color: {ink};
  font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 0 2px #fff; }}
.note p {{ margin: 0; white-space: pre-wrap; }}
.crop {{ grid-column: 2; margin: 8px 0 0; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }}
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
{crops}</div>"""

CROP = """<figure class="crop"><div class="badge" style="background: {colour}">{label}</div>
<img src="data:image/png;base64,{image}" alt="{label}"></figure>"""


def _web(colour):
    return "#%02x%02x%02x" % colour


def page(fields, number):
    """The round as one HTML file with its pictures inside, labelled in the person's language."""
    parts = []
    for n in fields["notes"]:
        author = " &middot; " + html.escape(say.from_author(n["author"])) if n["author"] else ""
        colour = _web(KIND_COLOURS[n["kind"]])
        crops = "\n".join(CROP.format(colour=colour, label=m["label"], image=m["image"])
                          for m in n["marks"] if "image" in m)
        parts.append(NOTE.format(colour=colour, number=n["number"], kind=html.escape(say.KINDS[n["kind"]]),
                                 author=author, text=html.escape(n["text"]), crops=crops))
    sent = fields["sent"].replace("T", " ").replace("Z", " UTC")
    return PAGE.format(lang="de" if say.GERMAN else "en", heading=html.escape(say.file_heading(fields["title"])),
                       round=html.escape(say.round_label(number)), sent=sent, image=fields["image"],
                       title=html.escape(fields["title"]), ink=_web(INK), notes="\n".join(parts))
