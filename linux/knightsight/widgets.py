"""The buttons and icons the panel and the pinboard share."""

from gi.repository import Gdk, Gtk, Pango

from . import glyphs


def font(size, bold):
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


def button(glyph, text, width, height, *classes):
    b = Gtk.Button(css_classes=["soft", *classes], width_request=width, height_request=height)
    b.set_cursor(Gdk.Cursor.new_from_name("pointer"))
    box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    b.glyph = None
    if glyph:
        b.glyph = Glyph(glyph)
        box.append(b.glyph)
        # The icon's ink comes from the button's colour, which changes with hover and state.
        b.connect("state-flags-changed", lambda *_: b.glyph.queue_draw())
    b.label = None
    if text:
        b.label = Gtk.Label(label=text)
        box.append(b.label)
    b.set_child(box)
    return b


def bar_button(glyph, name, action, height):
    b = Gtk.Button(css_classes=["soft", "blank"], width_request=44, height_request=height, tooltip_text=name)
    square = Gtk.CenterBox(css_classes=["square"], width_request=28, height_request=28, halign=Gtk.Align.CENTER,
                           valign=Gtk.Align.CENTER)
    b.glyph = Glyph(glyph)
    square.set_center_widget(b.glyph)
    b.set_child(square)
    b.connect("state-flags-changed", lambda *_: b.glyph.queue_draw())
    b.connect("clicked", lambda _b: action())
    return b
