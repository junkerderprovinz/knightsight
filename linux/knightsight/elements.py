"""The controls a look lists, read from the window's accessibility tree over AT-SPI.

Everything here is optional: without gi's Atspi, or when the tree cannot be read, a look
goes out with its picture alone.
"""

import os
import time
import traceback

import gi
from gi.repository import GLib

from . import protocol

try:
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
except (ImportError, ValueError):
    Atspi = None

LIMIT = 150
NAME_LIMIT = 80
BUDGET = 1.5
# Milliseconds a single call may take, so one application that hangs cannot eat the budget.
CALL_TIMEOUT = 400
# The part of the budget that catching up on what changed in the tree may take.
DRAIN = 0.3

ROLES = {
    "button": "button", "push-button": "button", "toggle-button": "button", "push-button-menu": "button",
    "link": "link",
    "entry": "edit", "password-text": "edit", "spin-button": "edit",
    "check-box": "checkbox", "switch": "checkbox",
    "radio-button": "radio",
    "combo-box": "combobox",
    "menu-item": "menuitem", "check-menu-item": "menuitem", "radio-menu-item": "menuitem",
    "page-tab": "tab",
    "list-item": "listitem",
    "tree-item": "treeitem",
    "slider": "slider",
    "label": "text", "static": "text", "heading": "text",
}
FRAMES = {"frame", "window", "dialog"}
# How much larger than its frame a window from the portal may come, in all and from one
# axis to the other, as its shadow hangs a little lower than wide.
SHADOW, SHADOW_SKEW = 160, 24
# What these hold is part of them, such as a button's label, and would only be listed twice.
LEAVES = {"button", "link", "edit", "checkbox", "radio", "slider", "text"}


def kind(role, states):
    """The role a look reports for an AT-SPI role nick, or None for one it leaves out. A text
    that can be edited is a field, one that cannot is plain text."""
    if role == "text":
        return "edit" if "editable" in states else "text"
    return ROLES.get(role)


def worth_listing(role, name, states, inside):
    """Whether a control goes into a look: one without a name only while it can be used, and
    a text only when it says more than the control it sits in. GTK 4 marks a usable control
    sensitive without enabled."""
    if role == "text":
        return bool(name) and name != inside
    return bool(name) or bool(states & {"enabled", "sensitive"})


def clean(name):
    """The accessible name on one line, cut to the length a look sends."""
    return " ".join((name or "").split())[:NAME_LIMIT].rstrip()


def placed(rect, at, share, s):
    """rect, moved by at into a share of size share, clipped to it and scaled by s into the
    picture. None when nothing of it shows."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    left, top = max(0, x + at[0]), max(0, y + at[1])
    right, bottom = min(share[0], x + at[0] + w), min(share[1], y + at[1] + h)
    if right <= left or bottom <= top:
        return None
    px, py = round(left * s), round(top * s)
    return {"x": px, "y": py, "width": max(1, round(right * s) - px), "height": max(1, round(bottom * s) - py)}


def listed(found):
    """The controls top to bottom, then left to right, numbered as refs."""
    found = sorted(found, key=lambda e: (e["y"], e["x"]))[:LIMIT]
    return [{"ref": f"e{i}", **e} for i, e in enumerate(found, 1)]


def fits(extents, width, height):
    """Whether a frame shows in a picture of width x height: as large as the frame, or larger
    by a shadow about as wide on every side."""
    _, _, w, h = extents
    dw, dh = width - w, height - h
    return -2 <= dw <= SHADOW and -2 <= dh <= SHADOW and abs(dw - dh) <= SHADOW_SKEW


def pick_frame(frames, title, width, height):
    """The one of (name, extents, frame) that shows the window, or None while it stays
    unclear. A title, where there is one, decides between frames of the same size."""
    fitting = [f for f in frames if fits(f[1], width, height)]
    named = [f for f in frames if title is not None and f[0] == title]
    for group in ([f for f in named if f in fitting], named, fitting):
        if len(group) == 1:
            return group[0]
    if title is not None and len(frames) == 1:
        return frames[0]
    return None


def cast_offset(extents, width, height):
    """Where a frame's own coordinates start in a picture of its window from the portal. The
    cast keeps some of the shadow around the window, and the frame is taken to sit in its
    middle."""
    x, y, w, h = extents
    return (width - w) / 2 - x, (height - h) / 2 - y


_context = None
_reported = set()


def _ready(deadline):
    """Starts Atspi on a main context of its own, so its bookkeeping runs on the thread that
    walks and not beside it on the panel's. Each walk first catches up on what came in."""
    global _context
    if _context is None:
        _context = GLib.MainContext()
        Atspi.set_main_context(_context)
        Atspi.init()
        Atspi.set_timeout(CALL_TIMEOUT, CALL_TIMEOUT)
    until = min(deadline, time.monotonic() + DRAIN)
    while time.monotonic() < until and _context.iteration(False):
        pass


def _states(a):
    return {s.value_nick for s in a.get_state_set().get_states()}


def _box(a):
    r = a.get_extents(Atspi.CoordType.WINDOW)
    return r.x, r.y, r.width, r.height


def _frames(pid):
    """The frames of the application with this process id, or of every other application
    than the panel when there is none."""
    own = os.getpid()
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None:
            continue
        try:
            p = app.get_process_id()
            if p == own or pid is not None and p != pid:
                continue
            for j in range(app.get_child_count()):
                f = app.get_child_at_index(j)
                if f is not None and f.get_role().value_nick in FRAMES:
                    yield f.get_name() or "", _box(f), f
        except GLib.Error:
            continue


def _walk(frame, deadline):
    """(role, name, rect) for each control below the frame until the deadline, with rect in
    the frame's window coordinates. Whatever is not showing is left out with all it holds."""
    stack = [(frame, None)]
    while stack and time.monotonic() < deadline:
        a, inside = stack.pop()
        try:
            states = _states(a)
            if a is not frame and ("showing" not in states or "defunct" in states):
                continue
            nick = a.get_role().value_nick
            role = kind(nick, states)
            name = ""
            if role:
                name = "" if nick == "password-text" else clean(a.get_name())
                if worth_listing(role, name, states, inside):
                    yield role, name, _box(a)
                if role in LEAVES:
                    continue
            children = [a.get_child_at_index(i) for i in range(a.get_child_count())]
        except GLib.Error:
            continue
        stack.extend((c, name or inside) for c in reversed(children) if c is not None)


def controls(size, share, pid=None, title=None, at=None):
    """The numbered controls of a window of this size lying at at in the share, or None when
    the tree cannot be read. A window from the portal comes without process, title or place,
    so its frame is the one that fits the picture."""
    if Atspi is None:
        return None
    deadline = time.monotonic() + BUDGET
    try:
        _ready(deadline)
        frame = pick_frame(list(_frames(pid)), title, *size)
        if frame is None:
            return None
        if at is None:
            at = cast_offset(frame[1], *share)
        s = protocol.scale(*share)
        found = []
        for role, name, rect in _walk(frame[2], deadline):
            box = placed(rect, at, share, s)
            if box is not None:
                found.append({"role": role, "name": name, **box})
        return listed(found)
    # A look goes out without its controls rather than not at all, and each reason is
    # printed once for whoever wonders why.
    except Exception as e:
        if repr(e) not in _reported:
            _reported.add(repr(e))
            traceback.print_exc()
        return None
