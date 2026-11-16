"""Drags a rectangle over a still picture of one screen, filling that screen, or chooses a
whole screen."""

import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from . import say, theme, widgets
from .glyphs import rounded

MIN_EDGE = 20
OUTLINE = 6


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


class ScreenPicker:
    """A window over each monitor with a still picture of it, dimmed, where a click shares that
    monitor whole. The one under the pointer is outlined in the accent colour."""

    def __init__(self, screens, done):
        """screens are pairs of a monitor and its picture. done gets the index of the chosen
        one, or None."""
        self.done = done
        self.hot = None
        self.finished = False
        self.font = widgets.font(20, True)
        self.windows = [self._window(i, monitor, shot) for i, (monitor, shot) in enumerate(screens)]

    def _window(self, i, monitor, shot):
        window = Gtk.Window(decorated=False)
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(lambda _a, ctx, width, height: self.paint(ctx, width, height, shot, i == self.hot))
        area.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        window.set_child(area)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self.point(i))
        motion.connect("motion", lambda *_: self.point(i))
        motion.connect("leave", lambda *_: self.point(None) if self.hot == i else None)
        area.add_controller(motion)
        click = Gtk.GestureClick(button=0)
        # On the release, so it does not fall on the window below once the picker is gone.
        click.connect("released", lambda g, *_: self.result(i if g.get_current_button() == Gdk.BUTTON_PRIMARY else None))
        area.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, key, *_: key == Gdk.KEY_Escape and self.result(None))
        window.add_controller(keys)
        window.connect("close-request", lambda _w: self.result(None) or False)
        window.fullscreen_on_monitor(monitor)
        return window

    def present(self):
        for window in self.windows:
            window.present()

    def point(self, i):
        if i != self.hot:
            self.hot = i
            for window in self.windows:
                window.get_child().queue_draw()

    def paint(self, ctx, width, height, shot, hot):
        k = min(width / shot.get_width(), height / shot.get_height())
        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()
        ctx.save()
        ctx.translate((width - shot.get_width() * k) / 2, (height - shot.get_height() * k) / 2)
        ctx.scale(k, k)
        ctx.set_source_surface(shot)
        ctx.paint()
        ctx.restore()
        ctx.set_source_rgba(0, 0, 0, 0.4)
        ctx.paint()

        layout = PangoCairo.create_layout(ctx)
        layout.set_font_description(self.font)
        layout.set_text(say.SCREEN_HINT, -1)
        layout.set_alignment(Pango.Alignment.CENTER)
        tw, th = layout.get_pixel_size()
        pw, ph = tw + 48, th + 28
        rounded(ctx, (width - pw) / 2, (height - ph) / 2, pw, ph, 10)
        ctx.set_source_rgba(0, 0, 0, 0.6)
        ctx.fill()
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to((width - tw) / 2, (height - th) / 2)
        PangoCairo.show_layout(ctx, layout)

        if hot:
            ctx.set_source_rgb(*theme.rgb(theme.ACCENT))
            ctx.set_line_width(OUTLINE)
            ctx.rectangle(OUTLINE / 2, OUTLINE / 2, width - OUTLINE, height - OUTLINE)
            ctx.stroke()

    def result(self, chosen):
        if self.finished:
            return
        self.finished = True
        self.done(chosen)
        for window in self.windows:
            window.destroy()
