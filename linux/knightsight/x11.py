"""The desk on an X11 session: Composite for pictures of covered windows, XTEST for input,
and frame and badge as click-through windows of our own around the share."""

import ctypes
import math
import os
import threading
import time
from contextlib import contextmanager
from ctypes import byref

import cairo
from gi.repository import Gdk, GLib, Pango, PangoCairo

from . import picture, protocol, say, theme, xlib
from .glyphs import rounded
from .picker import RegionPicker
from .protocol import Rect, Refused

SKIPPED_TYPES = {"_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK"}
MODIFIER_KEYS = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L"}


class Share:
    def __init__(self, title, window=0, region=None):
        self.title = title
        self.window = window
        self.region = region
        # The window that took the last click inside a region. Keys only go there.
        self.focus = 0


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
        # The panel's thread and the request thread each get their own connection.
        self.ui = xlib.Display()
        self.work = xlib.Display()
        self.uiw = Windows(self.ui)
        self.workw = Windows(self.work)
        self.was_down = False
        self.polling = 0
        self.redirected = 0
        self.lent = 0
        self.scratch = None
        self.frame = Frame(self.ui)
        self.hotkey = self._grab_hotkey()

    def close(self):
        self.frame.hide()

    def _grab_hotkey(self):
        code = xlib.XKeysymToKeycode(self.ui.d, xlib.XStringToKeysym(b"x"))
        mods = xlib.ControlMask | xlib.Mod1Mask | xlib.ShiftMask
        # Caps Lock and Num Lock count as modifiers too, so each of their states needs its own grab.
        for extra in (0, xlib.LockMask, xlib.Mod2Mask, xlib.LockMask | xlib.Mod2Mask):
            xlib.XGrabKey(self.ui.d, code, mods | extra, self.ui.root, True, xlib.GrabModeAsync, xlib.GrabModeAsync)
        self.ui.failed()
        return code

    def hotkey_pressed(self):
        pressed = False
        event = xlib.XEvent()
        while xlib.XPending(self.ui.d):
            xlib.XNextEvent(self.ui.d, byref(event))
            if event.type == xlib.KeyPress and event.xkey.keycode == self.hotkey:
                pressed = True
        return pressed

    def bind_hotkey(self, _stop):
        pass

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
                chosen = Share(self.uiw.title(w), window=w)
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

    def pick_region(self, monitor, done):
        """Takes a still picture of the monitor the panel was on and lets the person drag over it."""
        scale = monitor.get_scale_factor()
        g = monitor.get_geometry()
        origin = (g.x * scale, g.y * scale)
        pixels = self.ui.image(self.ui.root, origin[0], origin[1], g.width * scale, g.height * scale)
        if pixels is None:
            done(None, None)
            return
        data, stride, _ = pixels
        shot = picture.surface(data, stride, g.width * scale, g.height * scale, False)

        def picked(r):
            if r is None:
                done(None, None)
                return
            self.release()
            region = Rect(origin[0] + r[0], origin[1] + r[1], r[2], r[3])
            done(Share(f"{say.REGION} {region.width} x {region.height}", region=region), None)

        RegionPicker(shot, monitor, picked).present()

    def title(self, share):
        return self.uiw.title(share.window) if share.window else share.title

    def area(self, share):
        return self.uiw.bounds(share.window) if share.window else share.region

    def gone(self, share):
        return bool(share.window) and self.ui.attributes(share.window) is None

    def hidden(self, share):
        return bool(share.window) and self.uiw.minimized(share.window)

    def minimized(self, share):
        return bool(share.window) and self.workw.minimized(share.window)

    def look(self, share):
        if share.window:
            shot = self._window_shot(share.window)
            reply = picture.encode(shot)
            reply["title"] = self.workw.title(share.window)
            return reply
        r = share.region
        with self._badge_away(r):
            pixels = self.work.image(self.work.root, r.x, r.y, r.width, r.height)
        if pixels is None:
            raise Refused("The region lies off the screen.")
        data, stride, _ = pixels
        reply = picture.encode(picture.surface(data, stride, r.width, r.height, False))
        reply["title"] = share.title
        return reply

    @contextmanager
    def _badge_away(self, r):
        """A region is copied off the screen, so a badge sitting inside it steps away for the shot."""
        if not self.frame.inside(r):
            yield
            return
        self.panel.badge_held = True
        hidden = threading.Event()
        GLib.idle_add(lambda: self.frame.hide_badge() or hidden.set())
        hidden.wait(1)
        time.sleep(0.04)
        try:
            yield
        finally:
            self.panel.badge_held = False

    def _window_shot(self, w):
        x, wins = self.work, self.workw
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

    def _point(self, share, args):
        area = self.workw.bounds(share.window) if share.window else share.region
        if area is None:
            raise Refused("The shared window has no size right now.")
        return protocol.to_area(area, args)

    def _root_for(self, share, x, y):
        if share.window:
            return share.window
        w = self.workw.at(x, y)
        if not w or self.workw.is_own(w):
            raise Refused("No window that takes input lies at this point.")
        share.focus = w
        return w

    def _key_root(self, share):
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
            act()
            xlib.XSync(self.work.d, False)
            time.sleep(0.15)
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
        x, y = self._point(share, args)
        w = self._root_for(share, x, y)
        right, twice = protocol.flag(args, "right"), protocol.flag(args, "double")
        self.panel.busy()

        def act():
            xlib.XTestFakeMotionEvent(self.work.d, -1, x, y, 0)
            self._button(3 if right else 1, 2 if twice else 1)

        return "Clicked, briefly in the foreground." + self._foreground(w, act)

    def scroll(self, share, args):
        x, y = self._point(share, args)
        notches = round(protocol.number(args, "amount"))
        w = self._root_for(share, x, y)
        self.panel.busy()

        def act():
            xlib.XTestFakeMotionEvent(self.work.d, -1, x, y, 0)
            self._button(5 if notches > 0 else 4, abs(notches))

        return "Scrolled, briefly in the foreground." + self._foreground(w, act)

    def type(self, share, text):
        w = self._key_root(share)
        self.panel.busy()

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
        self.frame.show(area, color, width, 0 if share.region else self.uiw.top(share.window), badge)

    def hide(self):
        self.frame.hide()


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

    def _window(self, argb=False):
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
            self.edges = [self._window() for _ in range(4)]
            for e in self.edges:
                self.x.set_prop(e, "_NET_WM_WINDOW_OPACITY", "CARDINAL", [int(0.9 * 0xFFFFFFFF)])
            self.badge = self._window(self.argb)
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
        xlib.XMoveResizeWindow(d, self.badge, *self.spot(r, size), *size)
        if size != self.badge_size:
            if not self.argb:
                self._shape(img)
            if not self.badge_size[0]:
                xlib.XMapRaised(d, self.badge)
            self.badge_size = size
        self._put(img)

    @staticmethod
    def spot(r, size):
        """Above the top right corner of the frame, or inside it when the share reaches the top of the screen."""
        shadow, gap, outer = 8, 6, 5
        x = r.right + outer - size[0] + shadow
        y = r.y - outer - gap - size[1] + shadow
        if y < 0:
            x = r.right - 10 - size[0] + shadow
            y = r.y + 10 - shadow
        return x, y

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
        shadow = 8
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

    def _shape(self, img):
        """Without a compositor the badge window is cut to the pill instead of being see-through."""
        w, h = img.get_width(), img.get_height()
        data, stride = img.get_data(), img.get_stride()
        row = (w + 7) // 8
        bits = bytearray(row * h)
        for y in range(h):
            for x in range(w):
                if data[y * stride + x * 4 + 3] >= 128:
                    bits[y * row + x // 8] |= 1 << (x % 8)
        mask = xlib.XCreateBitmapFromData(self.x.d, self.badge, bytes(bits), w, h)
        xlib.XShapeCombineMask(self.x.d, self.badge, xlib.ShapeBounding, 0, 0, mask, xlib.ShapeSet)
        xlib.XFreePixmap(self.x.d, mask)

    def _put(self, img):
        d = self.x.d
        w, h, stride = img.get_width(), img.get_height(), img.get_stride()
        buf = (ctypes.c_char * (stride * h)).from_buffer_copy(bytes(img.get_data()))
        depth = 32 if self.argb else xlib.XDefaultDepth(d, self.x.screen)
        visual = self.visual.visual if self.argb else xlib.XDefaultVisual(d, self.x.screen)
        ximage = xlib.XCreateImage(d, visual, depth, xlib.ZPixmap, 0, ctypes.addressof(buf), w, h, 32, stride)
        gc = xlib.XCreateGC(d, self.badge, 0, None)
        xlib.XPutImage(d, self.badge, gc, ximage, 0, 0, 0, 0, w, h)
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

