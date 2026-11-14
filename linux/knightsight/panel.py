"""The KnightSight window: choose a window or a region, start and stop sharing, see what goes on."""

import math
import time
import traceback

from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from . import glyphs, logo, say, theme

WIDTH, HEIGHT, BAR, GUTTER = 580, 212, 40, 16
CARD = (GUTTER, 0, WIDTH - 2 * GUTTER, HEIGHT - BAR - GUTTER)
# A request less than this long ago counts as work in progress: frame and badge stay lit
# through the pauses between the steps of one task.
WORK_SPAN = 5.0
PULSE_MS = 1400
BUSY_SPAN = 0.8


def _font(size, bold):
    f = Pango.FontDescription.from_string("Noto Sans")
    f.set_absolute_size(size * Pango.SCALE)
    if bold:
        f.set_weight(Pango.Weight.SEMIBOLD)
    return f


class Glyph(Gtk.DrawingArea):
    def __init__(self, name, size=16):
        super().__init__(content_width=size, content_height=size, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER)
        self.name = name
        self.set_draw_func(self._draw)

    def _draw(self, _area, ctx, width, _height):
        c = self.get_color()
        ctx.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        glyphs.draw(ctx, self.name, width)

    def show_glyph(self, name):
        self.name = name
        self.queue_draw()


def _button(glyph, text, width, height, *classes):
    b = Gtk.Button(css_classes=["soft", *classes], width_request=width, height_request=height)
    b.set_cursor(Gdk.Cursor.new_from_name("pointer"))
    box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    b.glyph = Glyph(glyph)
    box.append(b.glyph)
    b.label = None
    if text:
        b.label = Gtk.Label(label=text)
        box.append(b.label)
    b.set_child(box)
    # The icon's ink comes from the button's colour, which changes with hover and state.
    b.connect("state-flags-changed", lambda *_: b.glyph.queue_draw())
    return b


def _bar_button(glyph, name, action):
    b = Gtk.Button(css_classes=["soft", "blank"], width_request=44, height_request=BAR, tooltip_text=name)
    square = Gtk.CenterBox(css_classes=["square"], width_request=28, height_request=28, halign=Gtk.Align.CENTER,
                           valign=Gtk.Align.CENTER)
    b.glyph = Glyph(glyph)
    square.set_center_widget(b.glyph)
    b.set_child(square)
    b.connect("state-flags-changed", lambda *_: b.glyph.queue_draw())
    b.connect("clicked", lambda _b: action())
    return b


class Panel(Gtk.ApplicationWindow):
    def __init__(self, app, make_desk):
        super().__init__(application=app, title="KnightSight", resizable=False, css_classes=["knightsight"])
        self.chosen = None
        self.active = False
        self.picking = False
        self.notice = None
        self.doing = ""
        self.last_request = 0.0
        self.busy_until = 0.0
        self.working_now = False
        self.badge_held = False
        self.focused = False
        self.headline = self.subline = self.old_headline = self.old_subline = ""
        self.swap = 1.0
        self.pulse = 1.0
        self.badge_alpha = 0.0
        self.frame_color = theme.NEUTRAL
        self.frame_width = 3
        self.pick_hint = ""
        self.dot_color = theme.NEUTRAL
        self.last_tick = time.monotonic()
        self.last_error = None
        self.palette = theme.Palette(False)
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        bar = Gtk.WindowHandle(css_classes=["bar"], height_request=BAR)
        row = Gtk.Box()
        row.append(Gtk.Box(hexpand=True))
        row.append(_bar_button("minimise", say.MINIMISE, self.minimize))
        row.append(_bar_button("close", say.CLOSE, self.close))
        bar.set_child(row)
        self.set_titlebar(bar)

        cx, cy, cw, ch = CARD
        self.canvas = Gtk.DrawingArea(content_width=WIDTH, content_height=HEIGHT - BAR)
        self.canvas.set_draw_func(self.paint)
        theme.watch(self.restyle)
        fixed = Gtk.Fixed()
        fixed.put(self.canvas, 0, 0)
        buttons_y = cy + ch - 20 - 40
        self.pick_window = _button("window", say.PICK_WINDOW, 148, 36)
        self.pick_region = _button("region", say.PICK_REGION, 148, 36)
        self.toggle = _button("start", say.START_SHARE, 176, 40, "primary")
        self.info = _button("info", "", 28, 28, "round")
        fixed.put(self.pick_window, cx + 20, buttons_y + 2)
        fixed.put(self.pick_region, cx + 176, buttons_y + 2)
        fixed.put(self.toggle, cx + cw - 20 - 176, buttons_y)
        fixed.put(self.info, cx + cw - 20 - 28, cy + 18)
        self.info_left = cx + cw - 20 - 28
        self.info.set_cursor(Gdk.Cursor.new_from_name("help"))
        self.set_child(fixed)

        self.pick_window.connect("clicked", lambda _b: self.choose_window())
        self.pick_region.connect("clicked", lambda _b: self.choose_region())
        self.toggle.connect("clicked", lambda _b: self.stop() if self.active else self.start())

        keys = Gtk.ShortcutController(scope=Gtk.ShortcutScope.GLOBAL)
        keys.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("<Control><Alt><Shift>x"),
                                       action=Gtk.CallbackAction.new(lambda *_: self.stop() or True)))
        self.add_controller(keys)
        self.connect("notify::is-active", lambda *_: setattr(self, "focused", self.is_active()))
        self.connect("close-request", self.on_close)

        self.desk = make_desk(self)
        self.info.set_tooltip_text(self.desk.help)
        self.title_font = _font(16, True)
        self.body_font = _font(13, False)
        GLib.timeout_add(16, self.tick)
        self.show_state()

    def restyle(self, palette):
        self.palette = palette
        self.css.load_from_string(theme.css(palette))
        self.canvas.queue_draw()

    def on_close(self, _window):
        self.active = False
        self.desk.close()
        return False

    def show_state(self):
        c = self.chosen
        head = say.NOTHING_CHOSEN if c is None else self.desk.title(c)
        if self.picking:
            sub = self.pick_hint
        elif c is None:
            sub = self.notice or say.CHOOSE_TARGET
        elif self.active and self.working_now:
            sub = say.DOING + self.doing
        elif self.active:
            sub = say.SHARED
        else:
            sub = say.REGION_CHOSEN if c.region is not None else say.WINDOW_CHOSEN
        if (head, sub) != (self.headline, self.subline):
            self.old_headline, self.old_subline = self.headline, self.subline
            self.headline, self.subline = head, sub
            self.swap = 0.0
        self.pick_window.set_sensitive(not self.active)
        self.pick_region.set_sensitive(not self.active)
        self.toggle.set_sensitive(c is not None)
        self.toggle.label.set_label(say.STOP_SHARE if self.active else say.START_SHARE)
        self.toggle.glyph.show_glyph("stop" if self.active else "start")
        self.canvas.queue_draw()

    def choose_window(self):
        self.picking = True
        self.notice = None
        self.pick_hint = self.desk.pick_hint
        self.desk.pick_window(self.picked)
        self.show_state()

    def choose_region(self):
        self.desk.stop_pick()
        self.picking = not self.desk.overlay
        self.notice = None
        self.pick_hint = say.PICK_SCREEN_IN_DIALOG
        monitor = self.get_display().get_monitor_at_surface(self.get_surface())
        if self.desk.overlay:
            # Out of the picture before the screen is taken.
            self.set_visible(False)

            def later():
                self.desk.pick_region(monitor, self.picked)
                return False

            GLib.timeout_add(250, later)
        else:
            self.desk.pick_region(monitor, self.picked)
        self.show_state()

    def picked(self, share, notice):
        self.picking = False
        if share is not None:
            self.chosen = share
        self.notice = notice
        self.set_visible(True)
        self.present()
        self.show_state()

    def forget(self):
        self.chosen = None
        self.active = False
        self.desk.release()
        self.show_state()

    def start(self):
        if self.chosen is None:
            return
        self.active = True
        self.desk.bind_hotkey(self.stop)
        self.show_state()

    def stop(self):
        self.active = False
        self.show_state()

    def tick(self):
        # An exception would end the timer and freeze the card without a word. It comes back
        # every frame, so each one is printed once.
        try:
            self.advance()
        except Exception as e:
            if repr(e) != self.last_error:
                self.last_error = repr(e)
                traceback.print_exc()
        return True

    def advance(self):
        now = time.monotonic()
        elapsed = (now - self.last_tick) * 1000
        self.last_tick = now
        moving = theme.animations()
        if self.swap < 1:
            self.swap = theme.step(self.swap, 1, elapsed, theme.CONTENT_MS if moving else 0)
            self.canvas.queue_draw()
        if self.desk.hotkey_pressed():
            self.stop()

        working = self.active and now - self.last_request < WORK_SPAN
        ms = now * 1000 % PULSE_MS
        self.pulse = 0.5 - 0.5 * math.cos(2 * math.pi * ms / PULSE_MS) if moving else 1
        if working != self.working_now:
            self.working_now = working
            self.show_state()
        elif working and say.DOING + self.doing != self.subline:
            self.show_state()
        dot = (theme.NEUTRAL if not self.active else
               theme.mix(theme.ACCENT, theme.WARNING, self.pulse) if working else theme.ACCENT)
        if dot != self.dot_color or working:
            self.dot_color = dot
            self.canvas.queue_draw()

        c = self.chosen
        if c is None:
            self.desk.hide()
            return
        if self.desk.gone(c):
            self.forget()
            self.desk.hide()
            return
        if self.desk.hidden(c):
            self.desk.hide()
            return

        width = 3
        if not self.active:
            target = theme.NEUTRAL
        elif now < self.busy_until:
            target = theme.WARNING
        elif working:
            target = theme.mix(theme.ACCENT, theme.WARNING, self.pulse)
            width += round(2 * self.pulse)
        else:
            target = theme.ACCENT
        blend = 1 if not moving or working else min(1, elapsed / theme.CONTROL_MS)
        color = theme.mix(self.frame_color, target, blend)
        changed = color != self.frame_color or width != self.frame_width
        self.frame_color, self.frame_width = color, width
        self.badge_alpha = theme.step(self.badge_alpha, 1 if working else 0, elapsed,
                                      theme.CONTENT_MS if moving else 0)
        if self.desk.overlay:
            area = self.desk.area(c)
            if area is None:
                self.desk.hide()
                return
            badge = None
            if self.badge_alpha > 0 and not self.badge_held:
                badge = (self.doing, theme.ease(self.badge_alpha), self.pulse, self.palette)
            self.desk.show(c, area, color, width, badge)
        elif changed:
            self.canvas.queue_draw()

    def busy(self):
        self.busy_until = time.monotonic() + BUSY_SPAN

    def paint(self, _area, ctx, _width, _height):
        p = self.palette
        cx, cy, cw, ch = CARD
        glyphs.rounded(ctx, cx, cy, cw, ch, 10)
        ctx.set_source_rgb(*theme.rgb(p.surface))
        ctx.fill()
        if not self.desk.overlay and self.chosen is not None:
            # Without a frame on the screen, the card wears it.
            w = self.frame_width
            glyphs.rounded(ctx, cx + w / 2, cy + w / 2, cw - w, ch - w, 10 - w / 2)
            ctx.set_source_rgb(*theme.rgb(self.frame_color))
            ctx.set_line_width(w)
            ctx.stroke()

        size = 52
        logo.draw(ctx, cx + 20, cy + 18, size, self.get_scale_factor())
        tx = cx + 20 + size + 16
        ty, tw = cy + 20, self.info_left - 12 - tx
        d, dy = 8, ty + 26 + 10
        if self.working_now and theme.animations():
            ctx.set_source_rgba(*theme.rgb(theme.WARNING), 80 / 255 * self.pulse)
            ctx.arc(tx + d / 2, dy, d, 0, 2 * math.pi)
            ctx.fill()
        ctx.set_source_rgb(*theme.rgb(self.dot_color))
        ctx.arc(tx + d / 2, dy, d / 2, 0, 2 * math.pi)
        ctx.fill()
        # A new text slides up into place while the old one fades out above it.
        t, shift = theme.ease(self.swap), 6
        if t < 1:
            self.texts(ctx, tx, ty, tw, self.old_headline, self.old_subline, 1 - t, -shift * t)
        self.texts(ctx, tx, ty, tw, self.headline, self.subline, t, shift * (1 - t))

    def texts(self, ctx, x, y, width, head, sub, alpha, dy):
        p = self.palette
        indent = 16
        for text, font, color, top, w in ((head, self.title_font, p.text, y + dy, width),
                                          (sub, self.body_font, p.secondary, y + 26 + dy, width - indent)):
            layout = PangoCairo.create_layout(ctx)
            layout.set_font_description(font)
            layout.set_text(text, -1)
            layout.set_width(int(w * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            ctx.set_source_rgba(*theme.rgb(color), alpha)
            ctx.move_to(x + (indent if font is self.body_font else 0), top)
            PangoCairo.show_layout(ctx, layout)

    def share(self):
        c = self.chosen
        return c if c is not None and self.active else None

    def working(self, doing):
        self.doing = doing
        self.last_request = time.monotonic()
