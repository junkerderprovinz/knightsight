"""Drags a rectangle over a still picture of one screen, filling that screen."""

import cairo
from gi.repository import Gdk, Gtk

MIN_EDGE = 20


class RegionPicker(Gtk.Window):
    def __init__(self, shot, monitor, done):
        """shot is the screen in its own pixels. done gets x, y, w, h in those pixels, or None."""
        super().__init__(decorated=False)
        self.shot, self.done = shot, done
        self.start = self.end = None
        self.finished = False
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(self.paint)
        area.set_cursor(Gdk.Cursor.new_from_name("crosshair"))
        self.set_child(area)

        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self.begin)
        drag.connect("drag-update", self.update)
        drag.connect("drag-end", self.finish)
        area.add_controller(drag)
        other = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        other.connect("pressed", lambda *_: self.result(None))
        area.add_controller(other)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, key, *_: key == Gdk.KEY_Escape and self.result(None))
        self.add_controller(keys)
        self.connect("close-request", lambda _w: self.result(None) or False)

        if monitor:
            self.fullscreen_on_monitor(monitor)
        else:
            self.fullscreen()

    def fit(self, width, height):
        """Scale and offset of the picture inside the window, which may differ in pixels and shape."""
        k = min(width / self.shot.get_width(), height / self.shot.get_height())
        return k, (width - self.shot.get_width() * k) / 2, (height - self.shot.get_height() * k) / 2

    def selection(self, width, height):
        if not self.start:
            return None
        k, ox, oy = self.fit(width, height)
        iw, ih = self.shot.get_width(), self.shot.get_height()
        (x0, y0), (x1, y1) = self.start, self.end

        def to_shot(v, offset, limit):
            return max(0, min(limit, round((v - offset) / k)))

        left, right = sorted((to_shot(x0, ox, iw), to_shot(x1, ox, iw)))
        top, bottom = sorted((to_shot(y0, oy, ih), to_shot(y1, oy, ih)))
        return left, top, right - left, bottom - top

    def paint(self, _area, ctx, width, height):
        k, ox, oy = self.fit(width, height)
        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()
        ctx.save()
        ctx.translate(ox, oy)
        ctx.scale(k, k)
        ctx.set_source_surface(self.shot)
        ctx.paint()
        ctx.restore()
        ctx.set_source_rgba(0, 0, 0, 0.4)
        ctx.rectangle(0, 0, width, height)
        chosen = self.selection(width, height)
        if chosen and chosen[2] > 0:
            x, y, w, h = chosen
            ctx.rectangle(ox + x * k, oy + y * k, w * k, h * k)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.fill()
        if chosen and chosen[2] > 0:
            ctx.set_source_rgb(1, 1, 1)
            ctx.set_line_width(2)
            ctx.rectangle(ox + x * k, oy + y * k, w * k, h * k)
            ctx.stroke()

    def begin(self, _gesture, x, y):
        self.start = self.end = (x, y)

    def update(self, gesture, dx, dy):
        self.end = (self.start[0] + dx, self.start[1] + dy)
        self.get_child().queue_draw()

    def finish(self, gesture, dx, dy):
        self.update(gesture, dx, dy)
        child = self.get_child()
        chosen = self.selection(child.get_width(), child.get_height())
        self.result(chosen if chosen[2] >= MIN_EDGE and chosen[3] >= MIN_EDGE else None)

    def result(self, chosen):
        if self.finished:
            return
        self.finished = True
        self.done(chosen)
        self.destroy()
