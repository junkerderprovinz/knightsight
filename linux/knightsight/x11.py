"""The desk on an X11 session: Composite for pictures of covered windows, XTEST for input,
frame, badge and the assistant's arrow as click-through windows of our own around the share,
and the pinboard on it."""

import ctypes
import math
import os
import threading
import time
from contextlib import contextmanager
from ctypes import byref

import cairo
from gi.repository import Gdk, GLib, Pango, PangoCairo

from . import elements, picture, protocol, say, theme, xlib
from .glyphs import rounded
from .overlay import Overlay
from .picker import RegionPicker, ScreenPicker
from .pinboard import Pinboard
from .protocol import Rect, Refused

SKIPPED_TYPES = {"_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK"}
MODIFIER_KEYS = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L"}
STOP_KEY = (b"x", xlib.ControlMask | xlib.Mod1Mask | xlib.ShiftMask)
PINBOARD_KEY = (b"a", xlib.ControlMask | xlib.ShiftMask)
# Caps Lock and Num Lock count as modifiers too, so each of their states needs its own grab.
LOCKS = (0, xlib.LockMask, xlib.Mod2Mask, xlib.LockMask | xlib.Mod2Mask)
PROC = "/proc"
GONE = "The shared window has closed."
BADGE_SHADOW = 8
# The arrow's window leaves room around the tip for the ripple's widest ring.
CURSOR_SIZE, CURSOR_TIP = 52, 26
ARROW = ((0, 0), (0, 16.5), (4, 12.7), (6.8, 19.2), (9.6, 18), (6.9, 11.6), (12.2, 11.6))
CURSOR_INK = (22, 22, 22)
GLIDE_S = 0.22
RING_S = 0.4
RING_FROM, RING_TO = 6, 22
SECOND_RING_S = 0.15
IDLE_S = 4.0
RESTACK_S = 0.25


class Share:
    def __init__(self, title, window=0, region=None, owner=None, screen=False):
        self.title = title
        self.window = window
        self.region = region
        self.screen = screen
        # The process behind the window and when it started. The X server hands the id of a
        # closed window out again, so the id alone could later name a window of another program.
        self.owner = owner
        # The window that took the last click inside a region. Keys only go there.
        self.focus = 0
        # Where the last click went, from the share's top left corner, so the arrow knows
        # where typing lands.
        self.pointed = None


def stat_start(stat):
    """When a process started, from its line in /proc/<pid>/stat. The command name in
    brackets may itself hold spaces and brackets, so the fields count from the last one."""
    return int(stat[stat.rindex(")") + 2:].split()[19])


def started(pid):
    try:
        with open(f"{PROC}/{pid}/stat") as f:
            return stat_start(f.read())
    except (OSError, ValueError, IndexError):
        return None


def _keysym(key, is_char):
    if is_char:
        return Gdk.unicode_to_keyval(ord(key))
    return xlib.XStringToKeysym(key.encode())


class Windows:
    """Questions about the windows on one connection."""

    def __init__(self, x):
        self.x = x

    def client(self, top):
        """The application window inside a window manager's frame, found by its WM_STATE."""
        queue = [top]
        while queue:
            w = queue.pop(0)
            if self.x.prop(w, "WM_STATE") is not None:
                return w
            queue.extend(self.x.tree(w)[1])
        return top

    def top(self, w):
        """The child of the root that holds w, which is what the stacking order knows about."""
        while True:
            parent = self.x.tree(w)[0]
            if parent in (0, self.x.root):
                return w
            w = parent

    def at(self, x, y):
        """The application window showing at a point of the screen, or 0."""
        child = self.x.translate(self.x.root, self.x.root, x, y)[2]
        return self.client(child) if child else 0

    def is_own(self, w):
        return self.x.prop(w, "_NET_WM_PID") == [os.getpid()]

    def pid(self, w):
        value = self.x.prop(w, "_NET_WM_PID")
        return value[0] if value else None

    def owner(self, w):
        pid = self.pid(w)
        return None if pid is None else (pid, started(pid))

    def belongs(self, share):
        """Whether the shared window is still there and still the one that was chosen."""
        return self.x.attributes(share.window) is not None and self.owner(share.window) == share.owner

    def is_desktop(self, w):
        kinds = self.x.prop(w, "_NET_WM_WINDOW_TYPE") or []
        return any(self.x.atom(name) in kinds for name in SKIPPED_TYPES)

    def title(self, w):
        name = self.x.prop(w, "_NET_WM_NAME", self.x.atom("UTF8_STRING"))
        if name:
            return name.decode("utf-8", "replace")
        name = self.x.prop(w, "WM_NAME")
        return name.decode("latin-1") if name else say.UNTITLED

    def bounds(self, w):
        a = self.x.attributes(w)
        if a is None:
            return None
        x, y, _ = self.x.translate(w, self.x.root, 0, 0)
        return Rect(x, y, a.width, a.height)

    def minimized(self, w):
        state = self.x.prop(w, "WM_STATE", self.x.atom("WM_STATE"))
        hidden = self.x.atom("_NET_WM_STATE_HIDDEN") in (self.x.prop(w, "_NET_WM_STATE") or [])
        return hidden or bool(state) and state[0] == xlib.IconicState

    def popups(self, w):
        """Menus and tooltips of w, bottom first. They are windows of their own on the root."""
        pid = self.x.prop(w, "_NET_WM_PID")
        found = []
        for child in self.x.tree(self.x.root)[1]:
            a = self.x.attributes(child)
            if a is None or not a.override_redirect or a.map_state != 2:
                continue
            if pid and self.x.prop(child, "_NET_WM_PID") == pid or self.x.prop(child, "WM_TRANSIENT_FOR") == [w]:
                found.append(child)
        return found

    def active(self):
        value = self.x.prop(self.x.root, "_NET_ACTIVE_WINDOW")
        return value[0] if value else 0


class Desk:
    overlay = True
    help = say.HELP_X11
    pick_hint = say.CLICK_TARGET

    def __init__(self, panel):
        self.panel = panel
        # The panel's thread, the request thread and the finder's pictures each get their own connection.
        self.ui = xlib.Display()
        self.work = xlib.Display()
        self.uiw = Windows(self.ui)
        self.workw = Windows(self.work)
        self.peekw = Windows(xlib.Display())
        self.was_down = False
        self.polling = 0
        self.redirected = 0
        self.lent = 0
        self.scratch = None
        self.frame = Frame(self.ui)
        self.cursor = Cursor(self.frame)
        # The open pinboard while it lies on the share.
        self.board = None
        self.hotkeys = {}
        self.released = {}
        self._grab(STOP_KEY, "stop")
        self.pinboard_key = 0

    def close(self):
        self.frame.hide()
        self.cursor.vanish()

    def _grab(self, key, name):
        """Takes a hotkey for the whole screen and gives back its keycode."""
        keysym, mods = key
        code = xlib.XKeysymToKeycode(self.ui.d, xlib.XStringToKeysym(keysym))
        for extra in LOCKS:
            xlib.XGrabKey(self.ui.d, code, mods | extra, self.ui.root, True, xlib.GrabModeAsync, xlib.GrabModeAsync)
        self.ui.failed()
        self.hotkeys[code] = name
        return code

    def hotkey_pressed(self):
        """The name of the hotkey pressed since the last call, or None. The pinboard's veil gets
        its events on the way."""
        pressed = None
        event = xlib.XEvent()
        while xlib.XPending(self.ui.d):
            xlib.XNextEvent(self.ui.d, byref(event))
            key = event.xkey
            if event.type == xlib.KeyRelease:
                self.released[key.keycode] = key.time
            elif event.type == xlib.KeyPress:
                # A held key repeats as a release and a press at the same moment, which would
                # open and close the pinboard over and over.
                if key.time - self.released.get(key.keycode, 0) > 1:
                    pressed = self.hotkeys.get(key.keycode, pressed)
            elif self.board is not None:
                self.board.handle(event)
        return pressed

    def bind_hotkey(self, _pressed):
        """Other programs use Ctrl+Shift+A too, so the pinboard holds it only while something
        is shared."""
        if not self.pinboard_key:
            self.pinboard_key = self._grab(PINBOARD_KEY, "pinboard")

    def unbind_hotkey(self):
        if not self.pinboard_key:
            return
        for extra in LOCKS:
            xlib.XUngrabKey(self.ui.d, self.pinboard_key, PINBOARD_KEY[1] | extra, self.ui.root)
        self.ui.failed()
        del self.hotkeys[self.pinboard_key]
        self.pinboard_key = 0

    def pinboard(self, shot, closed):
        """The pinboard right on the share where a compositor can make its veil see-through,
        else the window with a picture of the share."""
        if not self.frame.argb:
            return Pinboard(self.panel, shot, closed)

        def gone():
            self.board = None
            closed()

        self.board = Overlay(self.panel, shot, gone, self.uiw, self.frame.visual)
        return self.board

    def pick_window(self, done):
        """Waits for the person to click a window, the way the Windows panel polls the mouse."""
        self.stop_pick()
        self.was_down = bool(self.ui.pointer()[3] & xlib.Button1Mask)

        def poll():
            chosen = self._poll_pick()
            if chosen is None:
                return True
            self.polling = 0
            done(chosen, None)
            return False

        self.polling = GLib.timeout_add(15, poll)

    def stop_pick(self):
        if self.polling:
            GLib.source_remove(self.polling)
            self.polling = 0

    def _poll_pick(self):
        _, _, child, mask = self.ui.pointer()
        down = bool(mask & xlib.Button1Mask)
        chosen = None
        if self.was_down and not down and child:
            w = self.uiw.client(child)
            if not self.uiw.is_own(w) and not self.uiw.is_desktop(w):
                chosen = Share(self.uiw.title(w), window=w, owner=self.uiw.owner(w))
                self._redirect(w)
        self.was_down = down
        return chosen

    def _redirect(self, w):
        """Keeps the window drawing into a picture of its own, so a look sees it even when covered."""
        self.release()
        self.redirected = self.uiw.top(w)
        xlib.XCompositeRedirectWindow(self.ui.d, self.redirected, xlib.CompositeRedirectAutomatic)
        self.ui.failed()

    def release(self):
        if self.redirected:
            xlib.XCompositeUnredirectWindow(self.ui.d, self.redirected, xlib.CompositeRedirectAutomatic)
            self.ui.failed()
            self.redirected = 0

    def _monitor_shot(self, monitor):
        """A monitor's bounds in the screen's pixels and a still picture of it, or None."""
        scale = monitor.get_scale_factor()
        g = monitor.get_geometry()
        r = Rect(g.x * scale, g.y * scale, g.width * scale, g.height * scale)
        pixels = self.ui.image(self.ui.root, r.x, r.y, r.width, r.height)
        if pixels is None:
            return None
        data, stride, _ = pixels
        return r, picture.surface(data, stride, r.width, r.height, False)

    def pick_region(self, monitor, done):
        """Takes a still picture of the monitor the panel was on and lets the person drag over it."""
        taken = self._monitor_shot(monitor)
        if taken is None:
            done(None, None)
            return
        bounds, shot = taken

        def picked(r):
            if r is None:
                done(None, None)
                return
            self.release()
            region = Rect(bounds.x + r[0], bounds.y + r[1], r[2], r[3])
            done(Share(f"{say.REGION} {region.width} x {region.height}", region=region), None)

        RegionPicker(shot, monitor, picked).present()

    def pick_screen(self, done):
        """Takes a still picture of every monitor and lets the person click the one to share."""
        monitors = self.panel.get_display().get_monitors()
        screens = [monitors.get_item(i) for i in range(monitors.get_n_items())]
        taken = [self._monitor_shot(m) for m in screens]
        if not taken or None in taken:
            done(None, None)
            return

        def picked(i):
            if i is None:
                done(None, None)
                return
            self.release()
            r = taken[i][0]
            done(Share(say.screen(i + 1, r.width, r.height), region=r, screen=True), None)

        ScreenPicker([(m, shot) for m, (_, shot) in zip(screens, taken)], picked).present()

    def title(self, share):
        return self.uiw.title(share.window) if share.window else share.title

    def area(self, share):
        return self.uiw.bounds(share.window) if share.window else share.region

    def gone(self, share):
        return bool(share.window) and not self.uiw.belongs(share)

    def _there(self, share):
        if share.window and not self.workw.belongs(share):
            raise Refused(GONE)

    def hidden(self, share):
        return bool(share.window) and self.uiw.minimized(share.window)

    def minimized(self, share):
        return bool(share.window) and self.workw.minimized(share.window)

    def unminimize(self, share):
        """A minimized window draws nothing. Mapping it again brings it back, and a restack
        request puts it below the others, behind whatever the person is working in."""
        w = share.window
        active = self.work.prop(self.work.root, "_NET_ACTIVE_WINDOW")
        xlib.XMapWindow(self.work.d, w)
        self.work.send_root(w, "_NET_RESTACK_WINDOW", 2, 0, 1)
        for _ in range(40):
            if not self.workw.minimized(w):
                break
            time.sleep(0.025)
        self.work.send_root(w, "_NET_RESTACK_WINDOW", 2, 0, 1)
        # Window managers that focus a window as it maps get the old one handed back.
        if active and active[0] and active[0] != w:
            self.work.send_root(active[0], "_NET_ACTIVE_WINDOW", 2, 0, 0)
        if self.workw.minimized(w):
            return False
        time.sleep(0.3)
        return True

    def look(self, share):
        self._there(share)
        if share.window:
            reply = picture.encode(self._window_shot(share.window, self.workw))
            reply["title"] = self.workw.title(share.window)
            found = self._controls(share.window, self.workw.bounds(share.window))
        else:
            r = share.region
            with self._out_of_shot(r):
                shot = self._region_shot(r, self.work)
            reply = picture.encode(shot)
            reply["title"] = share.title
            w = self.workw.at(r.x + r.width // 2, r.y + r.height // 2)
            found = self._controls(w, r) if w and not self.workw.is_own(w) else None
        if found is not None:
            reply["elements"] = found
        return reply

    def _controls(self, w, area):
        """The controls of window w, placed into the share's area."""
        b = self.workw.bounds(w)
        if b is None or area is None:
            return None
        return elements.controls((b.width, b.height), (area.width, area.height), self.workw.pid(w),
                                 self.workw.title(w), (b.x - area.x, b.y - area.y))

    def still(self, share):
        """The share in full resolution for the pinboard, taken on the panel's own connection."""
        if share.window:
            return self._window_shot(share.window, self.uiw)
        r = share.region
        if not self.frame.inside(r) and not self.cursor.inside(r):
            return self._region_shot(r, self.ui)
        self.frame.hide_badge()
        self.cursor.hold()
        time.sleep(0.04)
        try:
            return self._region_shot(r, self.ui)
        finally:
            self.cursor.let_go()

    def preview(self, share):
        """The share for the panel's finder, with whatever lies over a region left in."""
        if share.window:
            return self._window_shot(share.window, self.peekw)
        return self._region_shot(share.region, self.peekw.x)

    @staticmethod
    def _region_shot(r, x):
        pixels = x.image(x.root, r.x, r.y, r.width, r.height)
        if pixels is None:
            raise Refused("The region lies off the screen.")
        data, stride, _ = pixels
        return picture.surface(data, stride, r.width, r.height, False)

    @contextmanager
    def _out_of_shot(self, r):
        """A region is copied off the screen, so a badge or the arrow sitting inside it and the
        pinboard over it step away for the shot."""
        board = self.board
        if board is None and not self.frame.inside(r) and not self.cursor.inside(r):
            yield
            return
        self.panel.badge_held = True
        hidden = threading.Event()
        went = []

        def away():
            self.frame.hide_badge()
            self.cursor.hold()
            if board is not None:
                went.append(board.keep_out(r))
            hidden.set()

        GLib.idle_add(away)
        hidden.wait(1)
        time.sleep(0.04)
        try:
            yield
        finally:
            self.panel.badge_held = False
            GLib.idle_add(self.cursor.let_go)
            if went:
                GLib.idle_add(board.bring_back, went[0])

    @staticmethod
    def _window_shot(w, wins):
        x = wins.x
        area = wins.bounds(w)
        if area is None or area.width <= 0 or area.height <= 0:
            raise Refused("The shared window has no size right now.")
        top = wins.top(w)
        ox, oy, _ = x.translate(w, top, 0, 0)
        pixmap = xlib.XCompositeNameWindowPixmap(x.d, top)
        pixels = None if x.failed() else x.image(pixmap, ox, oy, area.width, area.height)
        if pixmap:
            xlib.XFreePixmap(x.d, pixmap)
            x.failed()
        if pixels is None:
            pixels = x.image(w, 0, 0, area.width, area.height)
        if pixels is None:
            raise Refused("The shared window cannot be read right now.")
        data, stride, depth = pixels
        shot = picture.surface(data, stride, area.width, area.height, depth == 32)
        ctx = cairo.Context(shot)
        for popup in wins.popups(w):
            b = wins.bounds(popup)
            if b is None:
                continue
            got = x.image(popup, 0, 0, b.width, b.height)
            if got is None:
                continue
            ctx.set_source_surface(picture.surface(got[0], got[1], b.width, b.height, False), b.x - area.x, b.y - area.y)
            ctx.paint()
        shot.mark_dirty()
        return shot

    def _area(self, share):
        self._there(share)
        area = self.workw.bounds(share.window) if share.window else share.region
        if area is None:
            raise Refused("The shared window has no size right now.")
        return area

    def _point(self, share, args):
        return protocol.to_area(self._area(share), args)

    def _root_for(self, share, x, y):
        """The window a click or scroll at x, y goes to. Clicks pass through the badge, but
        one under it would seem to land on it, so it counts as KnightSight's like the pinboard."""
        board = self.board
        ours = [self.frame.badge_box()]
        if board is not None:
            ours += [board.veil.box(), board.box]
        protocol.clear_of(x, y, ours)
        if share.window:
            return share.window
        w = self.workw.at(x, y)
        if w and self.workw.is_own(w):
            raise Refused(protocol.ON_US)
        if not w:
            raise Refused("No window that takes input lies at this point.")
        share.focus = w
        return w

    def _point_at(self, x, y, w):
        """Lets the assistant's arrow glide to x, y over window w before the input goes out."""
        time.sleep(self.cursor.aim(x, y, self.workw.top(w)))

    def _point_at_keys(self, share, w):
        """Typing points where the last click went, or at the middle of the share."""
        area = self._area(share)
        dx, dy = share.pointed or (area.width // 2, area.height // 2)
        self._point_at(area.x + dx, area.y + dy, w)

    def _key_root(self, share):
        self._there(share)
        if share.window:
            return share.window
        if not share.focus or self.work.attributes(share.focus) is None:
            raise Refused("Keys go to the window last clicked inside the region, and nothing has been clicked there yet.")
        return share.focus

    def _activate(self, w):
        x = self.work
        if self.workw.active() == w:
            return True
        x.send_root(w, "_NET_ACTIVE_WINDOW", 2, 0, 0)
        for _ in range(50):
            if self.workw.active() == w:
                return True
            time.sleep(0.02)
        return False

    def _foreground(self, w, act):
        """XTEST input lands where the pointer and the focus are. So this waits for a pause in the
        person's own input, brings the window to the front for a moment and then gives the front
        and the pointer back."""
        give_up = time.monotonic() + 8
        while (idle := self.work.idle_ms()) is not None and idle < 1200:
            if time.monotonic() > give_up:
                raise Refused("This window needs the foreground for a moment, but the mouse or keyboard is in use.")
            time.sleep(0.1)
        px, py, _, _ = self.work.pointer()
        front = self.lent or self.workw.active()
        if not self._activate(w):
            raise Refused("The shared window cannot be brought to the front.")
        try:
            with protocol.delivering():
                act()
                xlib.XSync(self.work.d, False)
                time.sleep(0.15)
                if self.work.attributes(w) is None:
                    raise Refused("The window closed while the input went to it.")
        finally:
            xlib.XTestFakeMotionEvent(self.work.d, -1, px, py, 0)
            xlib.XFlush(self.work.d)
        # A menu that just opened would close when the focus leaves, so it keeps the front until it does.
        if self.workw.popups(w):
            self.lent = front
            return " A menu is open, so the window stays in front until it closes."
        self.lent = 0
        if front and front != w:
            self._activate(front)
        return ""

    def _button(self, button, times):
        d = self.work.d
        for _ in range(times):
            xlib.XTestFakeButtonEvent(d, button, True, 0)
            xlib.XFlush(d)
            time.sleep(0.03)
            xlib.XTestFakeButtonEvent(d, button, False, 0)
            xlib.XFlush(d)
            time.sleep(0.03)

    def click(self, share, args):
        area = self._area(share)
        x, y = protocol.to_area(area, args)
        w = self._root_for(share, x, y)
        right, twice = protocol.flag(args, "right"), protocol.flag(args, "double")
        self.panel.clicked(area, x, y)
        self.panel.busy()
        share.pointed = (x - area.x, y - area.y)
        self._point_at(x, y, w)

        def act():
            xlib.XTestFakeMotionEvent(self.work.d, -1, x, y, 0)
            self.cursor.ripple(2 if twice else 1)
            self._button(3 if right else 1, 2 if twice else 1)

        return "Clicked, briefly in the foreground." + self._foreground(w, act)

    def scroll(self, share, args):
        x, y = self._point(share, args)
        notches = round(protocol.number(args, "amount"))
        w = self._root_for(share, x, y)
        self.panel.busy()
        self._point_at(x, y, w)

        def act():
            xlib.XTestFakeMotionEvent(self.work.d, -1, x, y, 0)
            self._button(5 if notches > 0 else 4, abs(notches))

        return "Scrolled, briefly in the foreground." + self._foreground(w, act)

    def type(self, share, text):
        w = self._key_root(share)
        self.panel.busy()
        self._point_at_keys(share, w)

        def act():
            for key, is_char in protocol.text_keys(text):
                self._stroke([], _keysym(key, is_char))

        try:
            return "Typed, briefly in the foreground." + self._foreground(w, act)
        finally:
            self._unmap_scratch()

    def key(self, share, keys):
        combo = protocol.parse_combo(keys)
        w = self._key_root(share)
        self.panel.busy()
        self._point_at_keys(share, w)
        held = [MODIFIER_KEYS[m] for m in combo.held]

        def act():
            self._stroke(held, _keysym(combo.key, combo.is_char))

        try:
            return "Pressed, briefly in the foreground." + self._foreground(w, act)
        finally:
            self._unmap_scratch()

    def _keycode(self, keysym):
        """The key for a keysym and whether it needs Shift. A keysym the layout lacks is put on a
        free key for the moment, the way xdotool does."""
        d = self.work.d
        code = xlib.XKeysymToKeycode(d, keysym)
        if code:
            if xlib.XkbKeycodeToKeysym(d, code, 0, 0) == keysym:
                return code, False
            if xlib.XkbKeycodeToKeysym(d, code, 0, 1) == keysym:
                return code, True
        if self.scratch is None:
            self.scratch = self._free_keycode()
        if self.scratch is None:
            raise Refused("This keyboard has no free key to type that character with.")
        syms = (ctypes.c_ulong * 2)(keysym, keysym)
        xlib.XChangeKeyboardMapping(d, self.scratch, 2, syms, 1)
        xlib.XSync(d, False)
        time.sleep(0.05)
        return self.scratch, False

    def _free_keycode(self):
        d = self.work.d
        low, high, per = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        xlib.XDisplayKeycodes(d, byref(low), byref(high))
        count = high.value - low.value + 1
        syms = xlib.XGetKeyboardMapping(d, low.value, count, byref(per))
        try:
            for i in range(count - 1, -1, -1):
                if not any(syms[i * per.value + j] for j in range(per.value)):
                    return low.value + i
        finally:
            xlib.XFree(syms)
        return None

    def _unmap_scratch(self):
        if self.scratch is not None:
            syms = (ctypes.c_ulong * 2)(0, 0)
            xlib.XChangeKeyboardMapping(self.work.d, self.scratch, 2, syms, 1)
            xlib.XSync(self.work.d, False)
            self.scratch = None

    def _stroke(self, held, keysym):
        d = self.work.d
        code, shift = self._keycode(keysym)
        mods = [self._keycode(xlib.XStringToKeysym(m.encode()))[0] for m in held]
        if shift and "Shift_L" not in held:
            mods.append(self._keycode(xlib.XStringToKeysym(b"Shift_L"))[0])
        for m in mods:
            xlib.XTestFakeKeyEvent(d, m, True, 0)
        xlib.XTestFakeKeyEvent(d, code, True, 0)
        xlib.XTestFakeKeyEvent(d, code, False, 0)
        for m in reversed(mods):
            xlib.XTestFakeKeyEvent(d, m, False, 0)
        xlib.XSync(d, False)
        time.sleep(0.01)

    def show(self, share, area, color, width, badge):
        above = 0 if share.region else self.uiw.top(share.window)
        self.frame.show(area, color, width, above, badge)
        self.cursor.step(self.panel.active)
        if self.board is not None:
            self.board.follow(area, above)

    def hide(self):
        self.frame.hide()
        self.cursor.vanish()
        if self.board is not None:
            self.board.veil.hide()


def _pixel(c):
    return (c[0] << 16) | (c[1] << 8) | c[2]


class Frame:
    """Four thin windows around the share, so nothing covers what is shared, and the badge that
    says what is being done in it. All of them let clicks pass through."""

    def __init__(self, x):
        self.x = x
        self.edges = []
        self.badge = None
        self.badge_size = (0, 0)
        self.badge_at = None
        self.mapped = False
        self.last = None
        self.restacked = 0
        self.font = Pango.FontDescription.from_string("Noto Sans SemiBold")
        self.font.set_absolute_size(13 * Pango.SCALE)
        self.font.set_weight(Pango.Weight.SEMIBOLD)
        cm = self.x.atom(f"_NET_WM_CM_S{self.x.screen}")
        visual = xlib.XVisualInfo()
        self.argb = bool(xlib.XGetSelectionOwner(x.d, cm)) and bool(
            xlib.XMatchVisualInfo(x.d, x.screen, 32, xlib.TrueColor, byref(visual)))
        self.visual = visual

    def window(self, argb=False):
        """A click-through window of our own on the root, see-through where argb is set."""
        a = xlib.XSetWindowAttributes()
        a.override_redirect = True
        mask = xlib.CWOverrideRedirect | xlib.CWBackPixel | xlib.CWBorderPixel
        depth, visual = xlib.XDefaultDepth(self.x.d, self.x.screen), None
        if argb:
            a.colormap = xlib.XCreateColormap(self.x.d, self.x.root, self.visual.visual, 0)
            mask |= xlib.CWColormap
            depth, visual = 32, self.visual.visual
        w = xlib.XCreateWindow(self.x.d, self.x.root, 0, 0, 1, 1, 0, depth, xlib.InputOutput, visual, mask, byref(a))
        xlib.XShapeCombineRectangles(self.x.d, w, xlib.ShapeInput, 0, 0, None, 0, xlib.ShapeSet, 0)
        self.x.set_prop(w, "_NET_WM_WINDOW_TYPE", "ATOM", [self.x.atom("_NET_WM_WINDOW_TYPE_NOTIFICATION")])
        return w

    def show(self, r, color, width, above, badge):
        if not self.edges:
            self.edges = [self.window() for _ in range(4)]
            for e in self.edges:
                self.x.set_prop(e, "_NET_WM_WINDOW_OPACITY", "CARDINAL", [int(0.9 * 0xFFFFFFFF)])
            self.badge = self.window(self.argb)
        sides = [
            (r.x - width, r.y - width, r.width + 2 * width, width),
            (r.x - width, r.bottom, r.width + 2 * width, width),
            (r.x - width, r.y, width, r.height),
            (r.right, r.y, width, r.height),
        ]
        state = (tuple(sides), color)
        d = self.x.d
        if state != self.last:
            for e, (x, y, w, h) in zip(self.edges, sides):
                xlib.XMoveResizeWindow(d, e, x, y, max(1, w), max(1, h))
                if not self.last or self.last[1] != color:
                    xlib.XSetWindowBackground(d, e, _pixel(color))
                    xlib.XClearWindow(d, e)
            self.last = state
        if not self.mapped:
            for e in self.edges:
                xlib.XMapRaised(d, e)
            self.mapped = True
        self._badge(r, badge)
        now = time.monotonic()
        if now - self.restacked > 0.25:
            self.restacked = now
            self._stack(above)
        self.x.failed()

    def _stack(self, above):
        """Right above a shared window: high enough to show, no higher, so a window the person
        lays over the share stays clear of the marks. A region keeps them on top."""
        marks = list(self.edges) + ([self.badge] if self.badge_size[0] else [])
        if not above:
            for m in marks:
                xlib.XRaiseWindow(self.x.d, m)
            return
        changes = xlib.XWindowChanges(sibling=above, stack_mode=xlib.Above)
        for m in marks:
            xlib.XConfigureWindow(self.x.d, m, xlib.CWSibling | xlib.CWStackMode, byref(changes))

    def _badge(self, r, badge):
        d = self.x.d
        if badge is None:
            if self.badge_size[0]:
                xlib.XUnmapWindow(d, self.badge)
                self.badge_size = (0, 0)
            return
        text, alpha, pulse, palette = badge
        if not self.argb and alpha < 0.5:
            self._badge(r, None)
            return
        img, size = self._render(text, alpha, pulse, palette)
        self.badge_at = self.spot(r, size)
        xlib.XMoveResizeWindow(d, self.badge, *self.badge_at, *size)
        if size != self.badge_size:
            if not self.argb:
                self.cut(self.badge, img)
            if not self.badge_size[0]:
                xlib.XMapRaised(d, self.badge)
            self.badge_size = size
        self.put(self.badge, img, self.argb)

    @staticmethod
    def spot(r, size):
        """Above the top right corner of the frame, or inside it when the share reaches the top of the screen."""
        shadow, gap, outer = BADGE_SHADOW, 6, 5
        x = r.right + outer - size[0] + shadow
        y = r.y - outer - gap - size[1] + shadow
        if y < 0:
            x = r.right - 10 - size[0] + shadow
            y = r.y + 10 - shadow
        return x, y

    def badge_box(self):
        """Where the badge's pill lies on the screen while it shows, else None."""
        if not self.badge_size[0]:
            return None
        (x, y), (w, h) = self.badge_at, self.badge_size
        return Rect(x + BADGE_SHADOW, y + BADGE_SHADOW, w - 2 * BADGE_SHADOW, h - 2 * BADGE_SHADOW)

    def inside(self, r):
        if not self.badge_size[0]:
            return False
        _, y = self.spot(r, self.badge_size)
        return y + self.badge_size[1] > r.y and y < r.bottom

    def _render(self, text, alpha, pulse, palette):
        probe = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        layout = PangoCairo.create_layout(cairo.Context(probe))
        layout.set_font_description(self.font)
        layout.set_text(text, -1)
        tw = layout.get_pixel_size()[0]
        shadow = BADGE_SHADOW
        w, h = math.ceil(tw + 40 + 2 * shadow), 30 + 2 * shadow
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(img)
        ctx.push_group()
        px, py, pw, ph = shadow, shadow, w - 2 * shadow, h - 2 * shadow
        if self.argb:
            for i in range(4, 0, -1):
                g = i * 1.5
                rounded(ctx, px - g, py - g + 2, pw + 2 * g, ph + 2 * g, ph / 2 + g)
                ctx.set_source_rgba(0, 0, 0, 14 / 255)
                ctx.fill()
        rounded(ctx, px, py, pw, ph, ph / 2)
        ctx.set_source_rgb(*theme.rgb(palette.surface))
        ctx.fill()
        cx, cy, dot = px + 14, py + ph / 2, 8
        ctx.set_source_rgba(*theme.rgb(theme.WARNING), 90 / 255 * pulse)
        ctx.arc(cx, cy, dot * 0.9, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(*theme.rgb(theme.mix(theme.ACCENT, theme.WARNING, pulse)))
        ctx.arc(cx, cy, dot / 2, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(*theme.rgb(palette.text))
        th = layout.get_pixel_size()[1]
        ctx.move_to(px + 26, py + (ph - th) / 2)
        PangoCairo.update_layout(ctx, layout)
        PangoCairo.show_layout(ctx, layout)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha if self.argb else 1)
        img.flush()
        return img, (w, h)

    def cut(self, window, img):
        """Without a compositor a mark is cut to the shape of its picture instead of being see-through."""
        w, h = img.get_width(), img.get_height()
        data, stride = img.get_data(), img.get_stride()
        row = (w + 7) // 8
        bits = bytearray(row * h)
        for y in range(h):
            for x in range(w):
                if data[y * stride + x * 4 + 3] >= 128:
                    bits[y * row + x // 8] |= 1 << (x % 8)
        mask = xlib.XCreateBitmapFromData(self.x.d, window, bytes(bits), w, h)
        xlib.XShapeCombineMask(self.x.d, window, xlib.ShapeBounding, 0, 0, mask, xlib.ShapeSet)
        xlib.XFreePixmap(self.x.d, mask)

    def put(self, window, img, argb):
        d = self.x.d
        w, h, stride = img.get_width(), img.get_height(), img.get_stride()
        buf = (ctypes.c_char * (stride * h)).from_buffer_copy(bytes(img.get_data()))
        depth = 32 if argb else xlib.XDefaultDepth(d, self.x.screen)
        visual = self.visual.visual if argb else xlib.XDefaultVisual(d, self.x.screen)
        ximage = xlib.XCreateImage(d, visual, depth, xlib.ZPixmap, 0, ctypes.addressof(buf), w, h, 32, stride)
        gc = xlib.XCreateGC(d, window, 0, None)
        xlib.XPutImage(d, window, gc, ximage, 0, 0, 0, 0, w, h)
        xlib.XFreeGC(d, gc)
        xlib.XSync(d, False)
        # The pixels belong to buf, so only the structure is freed.
        xlib.XFree(ximage)

    def hide_badge(self):
        self._badge(None, None)
        xlib.XSync(self.x.d, False)

    def hide(self):
        if self.mapped:
            for e in self.edges:
                xlib.XUnmapWindow(self.x.d, e)
            self._badge(None, None)
            self.mapped = False
            xlib.XFlush(self.x.d)


def glided(start, goal, t):
    """Where the arrow stands after the part t of its glide, slowing towards the goal."""
    k = theme.ease(min(1.0, max(0.0, t)))
    return start[0] + (goal[0] - start[0]) * k, start[1] + (goal[1] - start[1]) * k


def rings(starts, now):
    """Radius and opacity of each ripple ring at now, from the moments the rings began."""
    out = []
    for began in starts:
        t = (now - began) / RING_S
        if 0 <= t < 1:
            out.append((RING_FROM + (RING_TO - RING_FROM) * theme.ease(t), 1 - t))
    return out


class Cursor:
    """The assistant's arrow at the spot of its next action, in a click-through window right
    above the window it points into, so it hides behind whatever covers that window. The
    request thread aims it, the panel's tick moves and draws it."""

    def __init__(self, frame):
        self.frame = frame
        self.x = frame.x
        self.w = 0
        self.lock = threading.Lock()
        self.tip = None
        self.glide = None
        self.above = 0
        self.starts = []
        self.last = 0.0
        self.alpha = 0.0
        self.moving = True
        self.stepped = time.monotonic()
        self.held = 0
        self.mapped = False
        self.spot = None
        self.drawn = None
        self.img = None
        self.restacked = 0.0

    def aim(self, x, y, above):
        """Sends the arrow to x, y over the top level window above and tells how long it takes
        to get there. Where it does not show yet it fades in at the spot."""
        with self.lock:
            self.last = now = time.monotonic()
            if above != self.above:
                self.above, self.restacked = above, 0.0
            if self.tip is None or self.alpha == 0 or not self.moving:
                self.tip, self.glide = (x, y), None
                return 0
            self.glide = (self.tip, (x, y), now)
            return GLIDE_S

    def ripple(self, times):
        with self.lock:
            if self.moving:
                now = time.monotonic()
                self.starts += [now + i * SECOND_RING_S for i in range(times)]

    def step(self, active):
        now = time.monotonic()
        elapsed, self.stepped = (now - self.stepped) * 1000, now
        self.moving = theme.animations()
        if not active:
            self.vanish()
            return
        with self.lock:
            if self.tip is None:
                return
            if self.glide is not None:
                start, goal, began = self.glide
                self.tip = glided(start, goal, (now - began) / GLIDE_S)
                if now - began >= GLIDE_S:
                    self.glide = None
            wanted = 1 if now - self.last < IDLE_S else 0
            self.alpha = theme.step(self.alpha, wanted, elapsed, theme.CONTENT_MS if self.moving else 0)
            self.starts = [b for b in self.starts if now - b < RING_S]
            tip, alpha, above, ripple = self.tip, self.alpha, self.above, rings(self.starts, now)
            if alpha == 0 and not wanted:
                self.tip = None
        if self.held or alpha == 0 or not self.frame.argb and alpha < 0.5:
            self.hide()
            return
        self._show(tip, alpha, ripple, above, now)

    def _show(self, tip, alpha, ripple, above, now):
        d = self.x.d
        if not self.w:
            self.w = self.frame.window(self.frame.argb)
            xlib.XStoreName(d, self.w, b"KnightSight cursor")
        drawn = (round(alpha, 2), tuple((round(r), round(o, 2)) for r, o in ripple))
        if drawn != self.drawn:
            self.img = self._render(alpha, ripple)
            if not self.frame.argb:
                self.frame.cut(self.w, self.img)
            self.drawn = drawn
        spot = (round(tip[0]) - CURSOR_TIP, round(tip[1]) - CURSOR_TIP)
        if spot != self.spot:
            xlib.XMoveResizeWindow(d, self.w, *spot, CURSOR_SIZE, CURSOR_SIZE)
            self.spot = spot
        if not self.mapped:
            xlib.XMapWindow(d, self.w)
            self.mapped = True
            self.restacked = 0.0
        if now - self.restacked > RESTACK_S:
            self.restacked = now
            if above:
                changes = xlib.XWindowChanges(sibling=above, stack_mode=xlib.Above)
                xlib.XConfigureWindow(d, self.w, xlib.CWSibling | xlib.CWStackMode, byref(changes))
            else:
                xlib.XRaiseWindow(d, self.w)
        # Drawn again every tick, since without a compositor a window forgets its pixels
        # wherever another one covered it.
        self.frame.put(self.w, self.img, self.frame.argb)
        self.x.failed()

    def _render(self, alpha, ripple):
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, CURSOR_SIZE, CURSOR_SIZE)
        ctx = cairo.Context(img)
        ctx.push_group()
        ctx.set_line_width(2)
        for radius, opacity in ripple:
            ctx.arc(CURSOR_TIP, CURSOR_TIP, radius, 0, 2 * math.pi)
            ctx.set_source_rgba(*theme.rgb(theme.ACCENT), opacity)
            ctx.stroke()
        ctx.translate(CURSOR_TIP, CURSOR_TIP)
        ctx.set_line_join(cairo.LINE_JOIN_MITER)
        if self.frame.argb:
            for spread in (4, 2.5, 1):
                self._arrow(ctx, 0.8, 1.6)
                ctx.set_source_rgba(0, 0, 0, 0.07)
                ctx.set_line_width(spread * 2)
                ctx.stroke_preserve()
                ctx.fill()
        self._arrow(ctx, 0, 0)
        ctx.set_source_rgb(*theme.rgb(theme.ACCENT))
        ctx.fill_preserve()
        ctx.set_source_rgb(*theme.rgb(CURSOR_INK))
        ctx.set_line_width(1.5)
        ctx.stroke()
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha if self.frame.argb else 1)
        img.flush()
        return img

    @staticmethod
    def _arrow(ctx, dx, dy):
        ctx.move_to(ARROW[0][0] + dx, ARROW[0][1] + dy)
        for x, y in ARROW[1:]:
            ctx.line_to(x + dx, y + dy)
        ctx.close_path()

    def inside(self, r):
        if not self.mapped:
            return False
        x, y = self.spot
        return x < r.right and x + CURSOR_SIZE > r.x and y < r.bottom and y + CURSOR_SIZE > r.y

    def hold(self):
        """Keeps the arrow off the screen for a shot, until let_go."""
        self.held += 1
        self.hide()

    def let_go(self):
        self.held -= 1

    def hide(self):
        if self.mapped:
            xlib.XUnmapWindow(self.x.d, self.w)
            xlib.XSync(self.x.d, False)
            self.mapped = False

    def vanish(self):
        """Hides the arrow at once, so it fades in again at the next action."""
        with self.lock:
            self.tip, self.glide, self.starts, self.alpha = None, None, [], 0.0
        self.hide()
