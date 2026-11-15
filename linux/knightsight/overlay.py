"""The pinboard right on the share, for an X11 desktop with a compositor: a see-through veil
over the share that takes the mouse and shows the marks, and the notes in a small window
beside it, since a bare Xlib window takes no typing."""

import ctypes
import math
import time
from ctypes import byref

import cairo
import gi

gi.require_version("GdkX11", "4.0")
from gi.repository import GdkX11  # noqa: E402

from . import marks, notes, xlib  # noqa: E402
from .pinboard import GAP, SIDE, Window  # noqa: E402

# Black at 8 percent, as alpha of the premultiplied pixels the window keeps.
VEIL = 20
# Room around a mark for its badge, its highlight and the ring that flashes around it.
REACH = 40
RESTACK_S = 0.25
HEIGHT = 640
EVENTS = (xlib.ExposureMask | xlib.ButtonPressMask | xlib.ButtonReleaseMask | xlib.PointerMotionMask
          | xlib.LeaveWindowMask)
# The veil lies on the share pixel for pixel.
FIT = notes.Fit(1)


def _clamp(box, width, height):
    x, y, w, h = box
    left, top = max(0, math.floor(x)), max(0, math.floor(y))
    right, bottom = min(width, math.ceil(x + w)), min(height, math.ceil(y + h))
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


class Veil:
    """A window exactly over the share, dimmed a little, that takes the mouse for the pinboard
    and shows its marks. Shots of a region hold it back, so it stays out of them."""

    def __init__(self, x, visual):
        self.x = x
        d = x.d
        self.visual = visual.visual
        self.colormap = xlib.XCreateColormap(d, x.root, self.visual, 0)
        self.cursors = {False: xlib.XCreateFontCursor(d, xlib.XC_crosshair), True: xlib.XCreateFontCursor(d, xlib.XC_hand2)}
        a = xlib.XSetWindowAttributes()
        a.override_redirect = True
        # The server fills what nothing has been drawn on yet with the veil itself.
        a.background_pixel = VEIL << 24
        a.colormap = self.colormap
        a.event_mask = EVENTS
        a.cursor = self.cursors[False]
        mask = (xlib.CWOverrideRedirect | xlib.CWBackPixel | xlib.CWBorderPixel | xlib.CWColormap | xlib.CWEventMask
                | xlib.CWCursor)
        self.w = xlib.XCreateWindow(d, x.root, 0, 0, 1, 1, 0, 32, xlib.InputOutput, self.visual, mask, byref(a))
        x.set_prop(self.w, "_NET_WM_WINDOW_TYPE", "ATOM", [x.atom("_NET_WM_WINDOW_TYPE_NOTIFICATION")])
        self.gc = xlib.XCreateGC(d, self.w, 0, None)
        self.image = None
        self.spot = None
        self.mapped = False
        self.held = 0
        x.failed()

    def place(self, area):
        """Lays the window over area and shows it, unless a shot holds it back. True when it
        has just appeared."""
        if self.held:
            return False
        spot = (area.x, area.y, max(1, area.width), max(1, area.height))
        if spot != self.spot:
            xlib.XMoveResizeWindow(self.x.d, self.w, *spot)
            self.spot = spot
        if self.mapped:
            return False
        xlib.XMapRaised(self.x.d, self.w)
        self.mapped = True
        return True

    def stack(self, sibling, mode):
        changes = xlib.XWindowChanges(sibling=sibling, stack_mode=mode)
        xlib.XConfigureWindow(self.x.d, self.w, xlib.CWSibling | xlib.CWStackMode, byref(changes))

    def hide(self):
        if self.mapped:
            xlib.XUnmapWindow(self.x.d, self.w)
            xlib.XSync(self.x.d, False)
            self.mapped = False

    def hold(self):
        self.held += 1
        self.hide()

    def let_go(self):
        self.held -= 1

    def point(self, at_mark):
        xlib.XDefineCursor(self.x.d, self.w, self.cursors[at_mark])

    def paint(self, boxes, draw):
        """Redraws boxes of the window, all of it for None, with draw(ctx) laying the marks on
        the veil."""
        w, h = self.spot[2], self.spot[3]
        if self.image is None or (self.image.get_width(), self.image.get_height()) != (w, h):
            self.image = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            boxes = None
        if boxes is None:
            boxes = [(0, 0, w, h)]
        else:
            boxes = [b for b in (_clamp(b, w, h) for b in boxes) if b]
        if not boxes:
            return
        ctx = cairo.Context(self.image)
        for b in boxes:
            ctx.rectangle(*b)
        ctx.clip()
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, VEIL / 255)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)
        draw(ctx)
        self.image.flush()
        d = self.x.d
        stride = self.image.get_stride()
        pixels = (ctypes.c_char * (stride * h)).from_buffer(self.image.get_data())
        ximage = xlib.XCreateImage(d, self.visual, 32, xlib.ZPixmap, 0, ctypes.addressof(pixels), w, h, 32, stride)
        for x, y, bw, bh in boxes:
            xlib.XPutImage(d, self.w, self.gc, ximage, x, y, x, y, bw, bh)
        # The pixels belong to the cairo surface, so only the structure is freed.
        xlib.XFree(ximage)
        xlib.XFlush(d)

    def destroy(self):
        d = self.x.d
        xlib.XDestroyWindow(d, self.w)
        xlib.XFreeGC(d, self.gc)
        for cursor in self.cursors.values():
            xlib.XFreeCursor(d, cursor)
        xlib.XFreeColormap(d, self.colormap)
        self.mapped = False
        self.x.failed()


class Overlay(Window):
    """The pinboard over the share itself: the marks on the veil, the notes in this window beside
    it. The X11 desk moves both along with the share and hands over the veil's events.
    wins asks about the windows on the desk's connection."""

    def __init__(self, panel, shot, closed, wins, visual):
        super().__init__(panel, shot, closed)
        self.wins = wins
        self.veil = Veil(wins.x, visual)
        root = wins.x.attributes(wins.x.root)
        self.screen = (root.width, root.height)
        self.share_size = (shot.get_width(), shot.get_height())
        self.start = self.end = None
        self.dragging = False
        self.drag_shown = None
        self.dirty = []
        self.everything = True
        self.placed = None
        self.above = False
        self.restacked = 0.0
        # How many shots keep this window off the screen.
        self.out = 0

        self.column.set_margin_start(GAP)
        self.column.set_margin_end(GAP)
        self.column.set_margin_bottom(GAP)
        self.set_child(self.column)
        self.set_default_size(SIDE + 2 * GAP, HEIGHT)
        self.connect("close-request", lambda _w: self.veil.destroy() or False)
        self.column.show_notes()

    def redraw(self, *changed):
        if not changed:
            self.everything = True
        for note in changed:
            self.dirty += [(m.x - REACH, m.y - REACH, m.width + 2 * REACH, m.height + 2 * REACH) for m in note.marks]

    def restyle(self):
        self.redraw()

    def size(self):
        return self.share_size

    def keep_out(self, region):
        """Takes the veil off the screen for a shot of region, and this window too where it lies
        over the region. Tells whether the window went."""
        self.veil.hold()
        if not self.out and not notes.overlaps(self.wins.bounds(self.wins.top(self.xid())), region):
            return False
        self.out += 1
        self.set_visible(False)
        # The shot comes from another thread, which must not find it still on the screen.
        self.get_display().flush()
        return True

    def bring_back(self, went):
        self.veil.let_go()
        if not went:
            return
        self.out -= 1
        if not self.out:
            # The window manager forgets place and state of a window taken off the screen.
            self.placed, self.above = None, False
            self.set_visible(True)

    def picture(self, then):
        """A fresh picture of the share for a file, since the marks lie on the share itself."""
        self.capture(lambda shot: then(shot or self.shot))

    def xid(self):
        return GdkX11.X11Surface.get_xid(self.get_surface())

    def follow(self, area, above):
        """Keeps the veil over area and this window beside it, every tick. above is the top
        window of a shared window, 0 for a region."""
        self.share_size = (area.width, area.height)
        appeared = self.veil.place(area)
        now = time.monotonic()
        if appeared or now - self.restacked > RESTACK_S:
            self.restacked = now
            side = self.wins.top(self.xid())
            # Right above a shared window, as the frame is. Over a region the veil keeps under
            # this window, which lies on the share when there is no room beside it.
            if above:
                self.veil.stack(above, xlib.Above)
            else:
                self.veil.stack(side, xlib.Below)
            self.place(area, side)
        self.paint()
        self.wins.x.failed()

    def place(self, area, side):
        """Moves this window beside the share whenever the share moves."""
        a = self.wins.x.attributes(side)
        if a.map_state != xlib.IsViewable:
            return
        target = notes.beside(area, (a.width, a.height), self.screen, GAP)
        if target != self.placed:
            xlib.XMoveWindow(self.wins.x.d, self.xid(), *target)
            self.placed = target
        if not self.above:
            # The notes are typed only here, so other windows must not bury this one.
            self.wins.x.send_root(self.xid(), "_NET_WM_STATE", 1, self.wins.x.atom("_NET_WM_STATE_ABOVE"), 0, 1)
            self.above = True

    def paint(self):
        if not self.veil.mapped:
            return
        drag = self.drawn() if self.dragging else None
        if drag != self.drag_shown:
            self.dirty += [b for b in (self.drag_shown, drag) if b is not None]
            self.drag_shown = drag
        if self.everything or self.dirty:
            self.veil.paint(None if self.everything else self.dirty, self.draw)
            self.everything, self.dirty = False, []

    def draw(self, ctx):
        self.column.paint(ctx, FIT)
        if self.dragging:
            marks.dragging(ctx, *self.start, *self.end)

    def drawn(self):
        """Where the box being dragged is drawn, its line included."""
        (x0, y0), (x1, y1) = self.start, self.end
        return min(x0, x1) - 3, min(y0, y1) - 3, abs(x1 - x0) + 6, abs(y1 - y0) + 6

    def handle(self, event):
        kind = event.type
        if kind == xlib.Expose:
            self.redraw()
        elif kind == xlib.ButtonPress and event.xbutton.button == 1:
            self.start = self.end = (event.xbutton.x, event.xbutton.y)
        elif kind == xlib.MotionNotify:
            m = event.xmotion
            if self.start is None:
                self.hover(m.x, m.y)
            else:
                self.drag(m.x, m.y)
        # A press from before the veil appeared has no start.
        elif kind == xlib.ButtonRelease and event.xbutton.button == 1 and self.start is not None:
            b = event.xbutton
            self.drag(b.x, b.y)
            self.finish(bool(b.state & xlib.ShiftMask), b.time)
        elif kind == xlib.LeaveNotify and self.start is None:
            self.hover(None, None)

    def drag(self, x, y):
        self.end = (x, y)
        if not self.dragging and math.dist(self.start, self.end) >= notes.MIN_DRAG:
            self.dragging = True

    def finish(self, shift, when):
        self.dragging = False
        self.column.press(FIT, self.start, self.end, shift)
        self.start = None
        if self.column.draft is not None:
            # A click on the veil moves no focus, and the note is typed in this window.
            self.present_with_time(when)

    def hover(self, x, y):
        if self.column.hover(FIT, x, y):
            self.veil.point(self.column.hot is not None)
