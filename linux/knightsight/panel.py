"""The KnightSight window: choose a window or a region, start and stop sharing, see what goes on."""

import math
import os
import threading
import time
import traceback

import cairo
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from . import glyphs, logo, notes, picture, say, theme, widgets
from .protocol import Refused
from .widgets import bar_button, button

WIDTH, HEIGHT, BAR, GUTTER = 720, 304, 44, 20
CARD = (GUTTER, 0, WIDTH - 2 * GUTTER, HEIGHT - BAR - GUTTER)
FINDER = (CARD[0] + 24, CARD[1] + 24, 252, CARD[3] - 48)
VIEW = (FINDER[0] + 18, FINDER[1] + 18, FINDER[2] - 36, FINDER[3] - 36)
SIDE = FINDER[0] + FINDER[2] + 28
SIDE_WIDTH = CARD[0] + CARD[2] - 24 - SIDE
# A request less than this long ago counts as work in progress: frame and badge stay lit
# through the pauses between the steps of one task.
WORK_SPAN = 5.0
PULSE_MS = 1400
BUSY_SPAN = 0.8
TOGGLE_SPAN = 0.4
PREVIEW_SPAN = 1.0
BREATHE_SPAN = 2.4
SWEEP_SPAN = 1.6
CLICK_SPAN = 2.5
RING_SPAN = 0.6


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
        # The finder's picture of the share, refreshed about once a second, and where its corners
        # stand: wide and breathing until the share starts, then snapped in close.
        self.preview = None
        self.preview_due = 0.0
        self.preview_busy = False
        self.lit = 0.0
        self.corners = 18.0
        self.corner_speed = 0.0
        # Where the assistant clicked last, across and down the share from 0 to 1, and when.
        self.last_click = None
        self.last_tick = time.monotonic()
        self.last_error = None
        self.board = notes.Board()
        self.rounds = notes.Rounds(os.path.join(GLib.get_user_state_dir(), "knightsight", "round.json"))
        self.pinboard = None
        self.toggle_gate = notes.Gate(TOGGLE_SPAN)
        self.board_notice = None
        self.awaiting_fetch = False
        # The controls of the last look in this share, where click and scroll find a ref.
        self.elements = None
        # KnightSight's windows the pointer is over right now. Wayland tells a program where the
        # pointer is only while it lies over one of its windows, and the assistant must not act on them.
        self.under_pointer = set()
        self.palette = theme.Palette(False)
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        bar = Gtk.WindowHandle(css_classes=["bar"], height_request=BAR)
        row = Gtk.Box()
        row.append(Gtk.Box(hexpand=True))
        self.info = bar_button("info", "", lambda: None, BAR)
        self.info.set_cursor(Gdk.Cursor.new_from_name("help"))
        row.append(self.info)
        row.append(bar_button("minimise", say.MINIMISE, self.minimize, BAR))
        row.append(bar_button("close", say.CLOSE, self.close, BAR))
        bar.set_child(row)
        self.set_titlebar(bar)

        bottom = CARD[1] + CARD[3]
        self.canvas = Gtk.DrawingArea(content_width=WIDTH, content_height=HEIGHT - BAR)
        self.canvas.set_draw_func(self.paint)
        theme.watch(self.restyle)
        fixed = Gtk.Fixed()
        fixed.put(self.canvas, 0, 0)
        small = (SIDE_WIDTH - 20) / 3
        row = []
        for i, (glyph, text, tip) in enumerate((("window", say.PICK_WINDOW, say.PICK_WINDOW_TIP),
                                                ("region", say.PICK_REGION, say.PICK_REGION_TIP),
                                                ("screen", say.PICK_SCREEN, say.PICK_SCREEN_TIP))):
            left = round(SIDE + i * (small + 10))
            b = button(glyph, text, round(SIDE + i * (small + 10) + small) - left, 40, "tall")
            b.set_tooltip_text(tip)
            fixed.put(b, left, bottom - 24 - 52 - 12 - 40)
            row.append(b)
        self.pick_window, self.pick_region, self.pick_screen = row
        self.pin = button("pin", say.PINBOARD, 132, 52, "tall")
        self.pin.set_tooltip_text(say.PINBOARD_TIP)
        fixed.put(self.pin, SIDE, bottom - 24 - 52)
        self.toggle = button("start", say.START_SHARE, SIDE_WIDTH - 142, 52, "primary", "large")
        fixed.put(self.toggle, SIDE + 142, bottom - 24 - 52)
        self.set_child(fixed)

        self.pick_window.connect("clicked", lambda _b: self.choose_window())
        self.pick_region.connect("clicked", lambda _b: self.choose_region())
        self.pick_screen.connect("clicked", lambda _b: self.choose_screen())
        self.toggle.connect("clicked", lambda _b: self.stop() if self.active else self.start())
        self.pin.connect("clicked", lambda _b: self.toggle_pinboard())

        keys = Gtk.ShortcutController(scope=Gtk.ShortcutScope.GLOBAL)
        keys.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("<Control><Alt><Shift>x"),
                                       action=Gtk.CallbackAction.new(lambda *_: self.stop() or True)))
        keys.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>a"),
                                       action=Gtk.CallbackAction.new(lambda *_: self.toggle_pinboard() or True)))
        self.add_controller(keys)
        self.connect("notify::is-active", lambda *_: self.focus_moved())
        self.connect("close-request", self.on_close)
        self.watch_pointer(self)

        self.desk = make_desk(self)
        self.info.set_tooltip_text(self.desk.help)
        self.title_font = widgets.font(18, True)
        self.body_font = widgets.font(14, False)
        GLib.timeout_add(16, self.tick)
        self.show_state()

    def watch_pointer(self, window):
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self.under_pointer.add(window))
        motion.connect("leave", lambda *_: self.under_pointer.discard(window))
        window.add_controller(motion)

    def restyle(self, palette):
        self.palette = palette
        self.css.load_from_string(theme.css(palette))
        self.canvas.queue_draw()
        if self.pinboard is not None:
            self.pinboard.restyle()

    def on_close(self, _window):
        self.active = False
        self.close_pinboard()
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
        elif self.pinboard is not None:
            sub = say.PINBOARD_ON
        elif self.active and self.board_notice:
            sub = self.board_notice
        elif self.active:
            sub = say.SHARED
        else:
            sub = say.WINDOW_CHOSEN if c.region is None else say.SCREEN_CHOSEN if c.screen else say.REGION_CHOSEN
        if (head, sub) != (self.headline, self.subline):
            self.old_headline, self.old_subline = self.headline, self.subline
            self.headline, self.subline = head, sub
            self.swap = 0.0
        self.pick_window.set_sensitive(not self.active)
        self.pick_region.set_sensitive(not self.active)
        self.pick_screen.set_sensitive(not self.active)
        self.toggle.set_sensitive(c is not None)
        self.toggle.label.set_label(say.STOP_SHARE if self.active else say.START_SHARE)
        self.toggle.set_css_classes(["soft", "large", "outline" if self.active else "primary"])
        self.toggle.glyph.show_glyph("stop" if self.active else "start")
        self.pin.set_sensitive(self.active)
        if self.pinboard is None:
            self.pin.remove_css_class("lit")
        else:
            self.pin.add_css_class("lit")
        self.canvas.queue_draw()

    def choose_window(self):
        self.picking = True
        self.notice = None
        self.pick_hint = self.desk.pick_hint
        self.desk.pick_window(self.picked)
        self.show_state()

    def choose_region(self):
        monitor = self.get_display().get_monitor_at_surface(self.get_surface())
        self.choose_on_screen(lambda: self.desk.pick_region(monitor, self.picked), say.PICK_SCREEN_IN_DIALOG)

    def choose_screen(self):
        self.choose_on_screen(lambda: self.desk.pick_screen(self.picked), say.PICK_WHOLE_SCREEN_IN_DIALOG)

    def choose_on_screen(self, pick, hint):
        self.desk.stop_pick()
        self.picking = not self.desk.overlay
        self.notice = None
        self.pick_hint = hint
        if self.desk.overlay:
            # Out of the picture before the screen is taken.
            self.set_visible(False)

            def later():
                pick()
                return False

            GLib.timeout_add(250, later)
        else:
            pick()
        self.show_state()

    def picked(self, share, notice):
        self.picking = False
        if share is not None:
            self.chosen = share
            self.preview = None
            self.preview_due = 0.0
            self.board.clear()
        self.notice = notice
        self.set_visible(True)
        self.present()
        self.show_state()

    def forget(self):
        self.chosen = None
        self.preview = None
        self.active = False
        self.close_pinboard()
        self.desk.unbind_hotkey()
        self.desk.release()
        self.show_state()

    def start(self):
        if self.chosen is None:
            return
        self.active = True
        self.board_notice = None
        self.elements = None
        self.desk.bind_hotkey(self.hotkey)
        self.show_state()

    def stop(self):
        self.active = False
        self.close_pinboard()
        self.desk.unbind_hotkey()
        self.show_state()

    def hotkey(self, name):
        if name == "stop":
            self.stop()
        elif name == "pinboard":
            self.toggle_pinboard()

    def toggle_pinboard(self):
        if not self.toggle_gate.open():
            return
        if self.pinboard is not None:
            self.close_pinboard()
            return
        if not self.active:
            return
        try:
            shot = self.desk.still(self.chosen)
        except Refused:
            self.board_notice = say.NO_PICTURE
            self.show_state()
            return
        self.board_notice = None
        self.pinboard = self.desk.pinboard(shot, self.pinboard_closed)
        self.watch_pointer(self.pinboard)
        self.pinboard.present()
        self.show_state()

    def close_pinboard(self):
        if self.pinboard is not None:
            self.pinboard.close()

    def pinboard_closed(self):
        self.under_pointer.discard(self.pinboard)
        self.pinboard = None
        self.focus_moved()
        self.show_state()

    def focus_moved(self):
        # Keys from the portal land wherever the focus is, so a note being written refuses them too.
        self.focused = self.is_active() or self.pinboard is not None and self.pinboard.is_active()

    def sent(self, count):
        self.board_notice = say.sent(count)
        self.awaiting_fetch = True
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
        self.hotkey(self.desk.hotkey_pressed())
        if self.awaiting_fetch and self.rounds.read:
            self.awaiting_fetch = False
            self.board_notice = say.FETCHED
            self.show_state()

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

        lit_to = 1 if self.active else 0
        breathe = 0.5 - 0.5 * math.cos(2 * math.pi * (now % BREATHE_SPAN) / BREATHE_SPAN) if moving else 0
        corners_to = 8 if self.active else 18 + 6 * breathe
        self.lit = theme.step(self.lit, lit_to, elapsed, theme.CONTENT_MS if moving else 0)
        if moving:
            # A spring, so the corners overshoot a little as they lock on.
            dt = min(elapsed, 50) / 1000
            self.corner_speed += ((corners_to - self.corners) * 260 - self.corner_speed * 20) * dt
            self.corners += self.corner_speed * dt
        else:
            self.corners = corners_to
        if moving or self.lit != lit_to:
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

        self.refresh_preview(c, now)
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

    def clicked(self, area, x, y):
        self.last_click = ((x - area.x) / area.width, (y - area.y) / area.height, time.monotonic())

    def refresh_preview(self, share, now):
        if now < self.preview_due or self.preview_busy:
            return
        self.preview_due = now + PREVIEW_SPAN
        self.preview_busy = True
        scale = self.get_scale_factor()
        threading.Thread(target=self.take_preview, args=(share, VIEW[2] * scale, VIEW[3] * scale),
                         daemon=True).start()

    def take_preview(self, share, width, height):
        # Off the panel's thread, since a picture of a busy window takes a moment.
        small = None
        try:
            small = picture.fitted(self.desk.preview(share), width, height)
        except Refused:
            pass
        finally:
            GLib.idle_add(self.preview_taken, share, small)

    def preview_taken(self, share, small):
        self.preview_busy = False
        if small is not None and share is self.chosen:
            self.preview = small
            self.canvas.queue_draw()
        return False

    def paint(self, _area, ctx, _width, _height):
        p = self.palette
        cx, cy, cw, ch = CARD
        glyphs.rounded(ctx, cx, cy, cw, ch, 16)
        ctx.set_source_rgb(*theme.rgb(p.surface))
        ctx.fill()
        if not self.desk.overlay and self.chosen is not None:
            # Without a frame on the screen, the card wears it.
            w = self.frame_width
            glyphs.rounded(ctx, cx + w / 2, cy + w / 2, cw - w, ch - w, 16 - w / 2)
            ctx.set_source_rgb(*theme.rgb(self.frame_color))
            ctx.set_line_width(w)
            ctx.stroke()

        self.paint_finder(ctx)
        logo.draw(ctx, SIDE, cy + 24, 32, self.get_scale_factor())
        # The state dot: grey until shared, accent while shared, pulsing while work goes on.
        d, mx, my = 8, SIDE, cy + 76
        if self.working_now and theme.animations():
            ctx.set_source_rgba(*theme.rgb(theme.WARNING), 80 / 255 * self.pulse)
            ctx.arc(mx + d / 2, my, d, 0, 2 * math.pi)
            ctx.fill()
        ctx.set_source_rgb(*theme.rgb(self.dot_color))
        ctx.arc(mx + d / 2, my, d / 2, 0, 2 * math.pi)
        ctx.fill()
        # A new text slides up into place while the old one fades out above it.
        t, shift = theme.ease(self.swap), 6
        if t < 1:
            self.texts(ctx, self.old_headline, self.old_subline, 1 - t, -shift * t)
        self.texts(ctx, self.headline, self.subline, t, shift * (1 - t))

    # The finder shows the share itself, grey while it is only chosen and in colour once it is
    # shared. A line sweeps over it while the assistant works, and a dot marks its last click.
    def paint_finder(self, ctx):
        p = self.palette
        fx, fy, fw, fh = FINDER
        glyphs.rounded(ctx, fx, fy, fw, fh, 12)
        ctx.set_source_rgb(*theme.rgb((18, 17, 16) if p.dark else p.surface2))
        ctx.fill()
        t = theme.ease(self.lit)
        shot = self.preview
        if self.chosen is None:
            layout = PangoCairo.create_layout(ctx)
            layout.set_font_description(self.body_font)
            layout.set_text(say.NO_TARGET, -1)
            layout.set_width(int(fw * Pango.SCALE))
            layout.set_alignment(Pango.Alignment.CENTER)
            ctx.set_source_rgb(*theme.rgb(p.muted))
            ctx.move_to(fx, fy + (fh - layout.get_pixel_extents()[1].height) / 2)
            PangoCairo.show_layout(ctx, layout)
        elif shot is not None:
            vx, vy, vw, vh = VIEW
            sw, sh = shot.get_width(), shot.get_height()
            k = min(vw / sw, vh / sh) * (0.94 + 0.06 * t)
            w, h = sw * k, sh * k
            x, y = vx + (vw - w) / 2, vy + (vh - h) / 2
            ctx.save()
            glyphs.rounded(ctx, x, y, w, h, 5)
            ctx.clip()
            ctx.push_group()
            ctx.translate(x, y)
            ctx.scale(k, k)
            ctx.set_source_surface(shot, 0, 0)
            ctx.paint()
            if t < 1:
                # A grey's saturation keeps each pixel's luminance, so this fades the picture to grey.
                ctx.set_operator(cairo.OPERATOR_HSL_SATURATION)
                ctx.set_source_rgb(0.5, 0.5, 0.5)
                ctx.paint_with_alpha(1 - t)
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.55 + 0.45 * t)
            if self.working_now and theme.animations():
                self.paint_work(ctx, x, y, w, h)
            ctx.restore()

        c, arm = self.corners, 20
        left, top, right, bottom = fx + c, fy + c, fx + fw - c, fy + fh - c
        ctx.set_source_rgb(*theme.rgb(theme.mix(p.muted, theme.ACCENT, t)))
        ctx.set_line_width(2)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        for x, y, sx, sy in ((left, top, 1, 1), (right, top, -1, 1), (left, bottom, 1, -1), (right, bottom, -1, -1)):
            ctx.move_to(x, y + sy * arm)
            ctx.line_to(x, y)
            ctx.line_to(x + sx * arm, y)
            ctx.stroke()

    def paint_work(self, ctx, x, y, w, h):
        now = time.monotonic()
        sweep = now % SWEEP_SPAN / SWEEP_SPAN
        r, g, b = theme.rgb(theme.ACCENT)
        line = cairo.LinearGradient(x, 0, x + w, 0)
        line.add_color_stop_rgba(0, r, g, b, 0)
        line.add_color_stop_rgba(0.5, r, g, b, 230 / 255 * min(1, min(sweep, 1 - sweep) * 6))
        line.add_color_stop_rgba(1, r, g, b, 0)
        ctx.rectangle(x, y + h * sweep - 1, w, 2)
        ctx.set_source(line)
        ctx.fill()
        click = self.last_click
        if click is None or now - click[2] > CLICK_SPAN:
            return
        fx, fy, when = click
        age = now - when
        px, py = x + w * fx, y + h * fy
        ctx.set_source_rgb(*theme.rgb(theme.WARNING))
        ctx.arc(px, py, 4, 0, 2 * math.pi)
        ctx.fill()
        if age < RING_SPAN:
            ctx.set_source_rgba(*theme.rgb(theme.WARNING), 150 / 255 * (1 - age / RING_SPAN))
            ctx.set_line_width(2)
            ctx.arc(px, py, 4 + 10 * age / RING_SPAN, 0, 2 * math.pi)
            ctx.stroke()

    def texts(self, ctx, head, sub, alpha, dy):
        p = self.palette
        cy = CARD[1]
        for text, font, color, x, top, w in ((head, self.title_font, p.text, SIDE + 44, cy + 28, SIDE_WIDTH - 44),
                                             (sub, self.body_font, p.secondary, SIDE + 18, cy + 66, SIDE_WIDTH - 18)):
            layout = PangoCairo.create_layout(ctx)
            layout.set_font_description(font)
            layout.set_text(text, -1)
            layout.set_width(int(w * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            ctx.set_source_rgba(*theme.rgb(color), alpha)
            ctx.move_to(x, top + dy)
            PangoCairo.show_layout(ctx, layout)

    def share(self):
        c = self.chosen
        return c if c is not None and self.active else None

    def working(self, doing):
        self.doing = doing
        self.board_notice = None
        self.last_request = time.monotonic()
