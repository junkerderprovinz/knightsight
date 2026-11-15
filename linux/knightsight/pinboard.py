"""The pinboard window: a still picture of the share to mark spots on, the notes beside it.

KnightSight can't draw over other apps on Wayland, and its marks on X11 are bare Xlib windows
that take no typing, so on Linux the pinboard is a window of its own on both.
"""

import math
import os
import time

import cairo
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from . import glyphs, marks, notes, say, theme
from .protocol import Refused
from .widgets import bar_button, button

BAR, GAP, SIDE = 40, 16, 340
# Room left on the screen for the taskbar, the window's own edges and the like.
CHROME = 120
FLASH_S = 0.9
# Long enough for the desktop to show the share again without this window over it.
STEP_AWAY_MS = 300


def config_folder():
    return os.path.join(GLib.get_user_config_dir(), "knightsight")


class Pinboard(Gtk.Window):
    def __init__(self, panel, shot, closed):
        super().__init__(application=panel.get_application(), title=say.PINBOARD,
                         css_classes=["knightsight", "pinboard"])
        self.panel, self.board = panel, panel.board
        self.author = notes.load_author(config_folder())
        self.start = self.end = None
        self.dragging = False
        self.hot = None
        self.open = None
        self.draft = None
        self.kind = "wish"
        self.flash_note = None
        self.flash_start = 0.0
        self.flash_timer = 0

        bar = Gtk.WindowHandle(css_classes=["bar"], height_request=BAR)
        row = Gtk.Box(spacing=8)
        row.append(Gtk.Label(label=say.PINBOARD, css_classes=["heading"], margin_start=GAP))
        self.count = Gtk.Label(css_classes=["count"])
        row.append(self.count)
        row.append(Gtk.Box(hexpand=True))
        row.append(bar_button("close", say.CLOSE_PINBOARD, self.close, BAR))
        bar.set_child(row)
        self.set_titlebar(bar)

        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self.paint)
        self.area.set_cursor(Gdk.Cursor.new_from_name("crosshair"))
        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self.begin)
        drag.connect("drag-update", self.update)
        drag.connect("drag-end", self.finish)
        self.area.add_controller(drag)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _c, x, y: self.hover(x, y))
        motion.connect("leave", lambda _c: self.hover(None, None))
        self.area.add_controller(motion)
        refresh = button("refresh", say.NEW_PICTURE, 200, 32)
        refresh.set_halign(Gtk.Align.END)
        refresh.connect("clicked", lambda _b: self.refresh())
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        left.append(self.area)
        left.append(refresh)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP, width_request=SIDE)
        side.append(self.list_card())
        side.append(self.editor_card())
        body = Gtk.Box(spacing=GAP, margin_start=GAP, margin_end=GAP, margin_bottom=GAP)
        body.append(left)
        body.append(side)
        self.set_child(body)

        keys = Gtk.ShortcutController(scope=Gtk.ShortcutScope.GLOBAL)
        keys.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("<Control><Alt><Shift>p"),
                                       action=Gtk.CallbackAction.new(lambda *_: panel.toggle_pinboard() or True)))
        self.add_controller(keys)
        self.connect("close-request", lambda _w: closed() or False)
        self.connect("notify::is-active", lambda *_: panel.focus_moved())

        self.show_picture(shot)
        self.show_notes()

    def list_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, css_classes=["card"], vexpand=True)
        self.empty = Gtk.Label(label=say.EMPTY_BOARD, wrap=True, xalign=0, max_width_chars=32,
                               css_classes=["muted"], vexpand=True, valign=Gtk.Align.START)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.connect("row-activated", lambda _l, row: self.go_there(row.note))
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, min_content_height=120)
        scroller.set_child(self.list)
        self.scroller = scroller
        footer = Gtk.Box(spacing=8, homogeneous=True)
        save = button(None, say.SAVE_FILE, -1, 36)
        save.connect("clicked", lambda _b: self.save_file())
        self.done_button = button(None, say.DONE, -1, 36, "primary")
        self.done_button.connect("clicked", lambda _b: self.done())
        footer.append(save)
        footer.append(self.done_button)
        card.append(self.empty)
        card.append(scroller)
        card.append(footer)
        return card

    def editor_card(self):
        self.editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, css_classes=["card"], visible=False)
        head = Gtk.Box(spacing=8)
        self.editor_title = Gtk.Label(css_classes=["heading"], xalign=0, hexpand=True)
        close = button("close", "", 28, 28, "round")
        close.set_tooltip_text(say.CLOSE)
        close.connect("clicked", lambda _b: self.close_editor())
        head.append(self.editor_title)
        head.append(close)

        kinds = Gtk.Box(spacing=8, homogeneous=True)
        self.kind_buttons = {}
        for kind in notes.KINDS:
            b = button(None, say.KINDS[kind], -1, 32)
            b.connect("clicked", lambda _b, k=kind: self.choose_kind(k))
            kinds.append(b)
            self.kind_buttons[kind] = b

        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        self.text.get_buffer().connect("changed", lambda _b: self.text_changed())
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=96)
        scroller.set_child(self.text)
        field = Gtk.Overlay(css_classes=["field"])
        field.set_child(scroller)
        self.placeholder = Gtk.Label(label=say.NOTE_PLACEHOLDER, wrap=True, xalign=0, halign=Gtk.Align.FILL,
                                     valign=Gtk.Align.START, can_target=False, css_classes=["placeholder"])
        field.add_overlay(self.placeholder)
        self.author_entry = Gtk.Entry(placeholder_text=say.AUTHOR_PLACEHOLDER)

        actions = Gtk.Box(spacing=8)
        self.delete_button = button(None, say.DELETE, 112, 36)
        self.delete_button.connect("clicked", lambda _b: self.delete())
        self.save_button = button(None, say.SAVE, 112, 36, "primary")
        self.save_button.connect("clicked", lambda _b: self.save())
        actions.append(self.delete_button)
        actions.append(Gtk.Box(hexpand=True))
        actions.append(self.save_button)

        for part in (head, kinds, field, self.author_entry, actions):
            self.editor.append(part)
        # Ahead of the text field, which would take Return and Escape for itself.
        keys = Gtk.ShortcutController(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        for trigger, action in (("<Control>Return", self.save), ("Escape", self.close_editor)):
            keys.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string(trigger),
                                           action=Gtk.CallbackAction.new(lambda *_, act=action: act() or True)))
        self.editor.add_controller(keys)
        return self.editor

    def restyle(self):
        self.area.queue_draw()

    def show_picture(self, shot):
        """Shows shot as large as it is, or smaller where the screen has less room."""
        self.shot = shot
        g = self.panel.get_display().get_monitor_at_surface(self.panel.get_surface()).get_geometry()
        room_w, room_h = g.width - SIDE - 3 * GAP, g.height - BAR - 2 * GAP - 40 - CHROME
        w, h = shot.get_width(), shot.get_height()
        k = min(1, room_w / w, room_h / h)
        self.area.set_content_width(max(1, round(w * k)))
        self.area.set_content_height(max(1, round(h * k)))
        self.area.queue_draw()

    def fit(self, width=None, height=None):
        return notes.Fit.inside(self.shot.get_width(), self.shot.get_height(),
                                width or self.area.get_width(), height or self.area.get_height())

    def paint(self, _area, ctx, width, height):
        p = self.panel.palette
        fit = self.fit(width, height)
        pw, ph = self.shot.get_width() * fit.k, self.shot.get_height() * fit.k
        glyphs.rounded(ctx, 0, 0, width, height, 10)
        ctx.set_source_rgb(*theme.rgb(p.surface2))
        ctx.fill()
        ctx.save()
        glyphs.rounded(ctx, fit.x, fit.y, pw, ph, 6)
        ctx.clip()
        ctx.translate(fit.x, fit.y)
        ctx.scale(fit.k, fit.k)
        ctx.set_source_surface(self.shot)
        ctx.get_source().set_filter(cairo.FILTER_GOOD)
        ctx.paint()
        ctx.restore()
        ctx.rectangle(fit.x, fit.y, pw, ph)
        ctx.set_source_rgba(0, 0, 0, 0.08)
        ctx.fill()

        # A mark off a share that has shrunk since stays on the board, it just isn't shown,
        # while the badges of marks along the edge keep their full circle.
        ctx.rectangle(fit.x - marks.PIN, fit.y - marks.PIN, pw + 2 * marks.PIN, ph + 2 * marks.PIN)
        ctx.clip()
        for note in self.board.notes:
            if note is self.open:
                marks.draw(ctx, note, fit, 3, self.kind)
            else:
                marks.draw(ctx, note, fit, 3 if note is self.hot else 2)
        if self.draft is not None:
            marks.draw(ctx, self.draft, fit, 3, self.kind)
        if self.flash_note is not None:
            marks.flash(ctx, self.flash_note, fit, min(1, (time.monotonic() - self.flash_start) / FLASH_S))
        if self.dragging:
            marks.dragging(ctx, *self.start, *self.end)

    def begin(self, _gesture, x, y):
        self.start = self.end = (x, y)
        self.dragging = False

    def update(self, _gesture, dx, dy):
        self.end = (self.start[0] + dx, self.start[1] + dy)
        if not self.dragging and math.dist(self.start, self.end) >= notes.MIN_DRAG:
            self.dragging = True
        if self.dragging:
            self.area.queue_draw()

    def finish(self, gesture, dx, dy):
        self.update(gesture, dx, dy)
        moved, self.dragging = self.dragging, False
        fit = self.fit()
        under = notes.hit(self.board.notes, fit, *self.start)
        if not moved and under is not None:
            self.edit(under)
            return
        spot = notes.mark(fit, self.start, self.end, self.shot.get_width(), self.shot.get_height())
        if spot is None:
            self.area.queue_draw()
        else:
            self.new_note(spot)

    def hover(self, x, y):
        hot = None if x is None else notes.hit(self.board.notes, self.fit(), x, y)
        if hot is not self.hot:
            self.hot = hot
            self.area.set_cursor(Gdk.Cursor.new_from_name("pointer" if hot else "crosshair"))
            self.area.queue_draw()

    def new_note(self, mark):
        self.open = None
        self.draft = notes.Note(self.board.next, "wish", "", self.author, *mark)
        self.show_editor(say.NEW_NOTE, self.draft)

    def edit(self, note):
        self.draft = None
        self.open = note
        self.show_editor(say.note_title(note.number), note)

    def show_editor(self, title, note):
        self.editor_title.set_label(title)
        self.choose_kind(note.kind)
        self.text.get_buffer().set_text(note.text)
        self.text_changed()
        self.author_entry.set_text(note.author)
        self.delete_button.set_visible(self.open is not None)
        self.editor.set_visible(True)
        self.text.grab_focus()
        self.area.queue_draw()

    def close_editor(self):
        self.open = self.draft = None
        self.editor.set_visible(False)
        self.area.queue_draw()

    def choose_kind(self, kind):
        self.kind = kind
        for k, b in self.kind_buttons.items():
            if k == kind:
                b.add_css_class(k)
            else:
                b.remove_css_class(k)
        self.area.queue_draw()

    def typed(self):
        buffer = self.text.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()

    def text_changed(self):
        text = self.typed()
        self.placeholder.set_visible(not self.text.get_buffer().get_char_count())
        self.save_button.set_sensitive(bool(text))

    def save(self):
        text = self.typed()
        if not text:
            return
        author = self.author_entry.get_text().strip()
        if author != self.author:
            self.author = author
            # Remembering the name is a convenience, which must not cost the note itself.
            try:
                notes.save_author(config_folder(), author)
            except OSError:
                pass
        if self.open is not None:
            self.open.kind, self.open.text, self.open.author = self.kind, text, author
        else:
            d = self.draft
            self.board.add(self.kind, text, author, (d.x, d.y, d.width, d.height))
        self.close_editor()
        self.show_notes()

    def delete(self):
        self.board.remove(self.open)
        self.close_editor()
        self.show_notes()

    def show_notes(self):
        self.list.remove_all()
        for note in self.board.notes:
            self.list.append(self.note_row(note))
        have = bool(self.board.notes)
        self.count.set_label(str(len(self.board.notes)))
        self.empty.set_visible(not have)
        self.scroller.set_visible(have)
        self.done_button.set_sensitive(have)
        self.area.queue_draw()

    def note_row(self, note):
        row = Gtk.ListBoxRow()
        row.note = note
        row.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        line = Gtk.Box(spacing=10)
        badge = Gtk.DrawingArea(content_width=26, content_height=26, valign=Gtk.Align.CENTER)
        badge.set_draw_func(lambda _a, ctx, w, h: marks.badge(ctx, w / 2, h / 2, marks.BADGE, note.kind, note.number))
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        words.append(Gtk.Label(label=say.KINDS[note.kind], xalign=0, css_classes=["muted"]))
        # One line of the text however long it is, without widening the column.
        words.append(Gtk.Label(label=" ".join(note.text.split()), xalign=0, max_width_chars=1,
                               ellipsize=Pango.EllipsizeMode.END))
        go = Gtk.Label(label=say.GO_THERE, css_classes=["muted"], opacity=0)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: go.set_opacity(1))
        motion.connect("leave", lambda *_: go.set_opacity(0))
        row.add_controller(motion)
        line.append(badge)
        line.append(words)
        line.append(go)
        row.set_child(line)
        return row

    def go_there(self, note):
        self.edit(note)
        if not theme.animations():
            return
        self.flash_note, self.flash_start = note, time.monotonic()
        if not self.flash_timer:
            self.flash_timer = GLib.timeout_add(16, self.flash_step)

    def flash_step(self):
        if time.monotonic() - self.flash_start >= FLASH_S:
            self.flash_note, self.flash_timer = None, 0
            self.area.queue_draw()
            return False
        self.area.queue_draw()
        return True

    def capture(self, then):
        """Hands then a new picture of the share, or None. A region is copied off the screen,
        where this window may lie over it, so the window steps away for the shot."""
        share = self.panel.chosen

        def take():
            try:
                return self.panel.desk.still(share)
            except Refused:
                return None

        if share.region is None:
            then(take())
            return
        self.set_visible(False)

        def later():
            if self.panel.pinboard is self:
                then(take())
            return False

        GLib.timeout_add(STEP_AWAY_MS, later)

    def refresh(self):
        def taken(shot):
            if shot is not None:
                self.show_picture(shot)
            self.set_visible(True)

        self.capture(taken)

    def round(self, shot):
        w, h = shot.get_width(), shot.get_height()
        shown = self.board.notes
        return notes.assemble(self.panel.desk.title(self.panel.chosen), w, h, shown,
                              marks.render(shot, (0, 0, w, h), shown),
                              lambda note, box: marks.render(shot, box, [note]), notes.sent_now())

    def keep_open_note(self):
        """Saves the note open in the editor, so typed text goes along."""
        if self.editor.get_visible() and self.typed():
            self.save()

    def done(self):
        self.keep_open_note()
        self.close_editor()

        def taken(shot):
            self.panel.rounds.send(self.round(shot or self.shot))
            count = len(self.board.notes)
            self.board.clear()
            self.panel.sent(count)
            self.close()

        self.capture(taken)

    def save_file(self):
        self.keep_open_note()
        page = notes.page(self.round(self.shot), self.panel.rounds.count + 1)
        kind = Gtk.FileFilter(name=say.FILE_KIND)
        kind.add_suffix("html")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(kind)
        dialog = Gtk.FileDialog(title=say.SAVE_FILE, initial_name=say.FILE_NAME, modal=True, filters=filters,
                                default_filter=kind)

        def chosen(_dialog, result):
            try:
                file = dialog.save_finish(result)
            except GLib.Error:
                return
            file.replace_contents(page.encode("utf-8"), None, False, Gio.FileCreateFlags.REPLACE_DESTINATION, None)

        dialog.save(self, None, chosen)
