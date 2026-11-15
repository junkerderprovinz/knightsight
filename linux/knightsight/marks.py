"""The pinboard's marks, drawn the same on the board and into the pictures of a round."""

import math

import cairo
from gi.repository import Pango, PangoCairo

from . import notes, picture, theme

BADGE = 22
PIN = 24

_number_font = Pango.FontDescription.from_string("Noto Sans")
_number_font.set_absolute_size(12 * Pango.SCALE)
_number_font.set_weight(Pango.Weight.SEMIBOLD)


def colour(kind):
    return theme.rgb(notes.KIND_COLOURS[kind])


def badge(ctx, x, y, diameter, kind, number):
    """A circle in the kind's colour with the number, ringed in white, centred on x, y."""
    r = diameter / 2
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgb(*colour(kind))
    ctx.fill_preserve()
    ctx.set_source_rgb(1, 1, 1)
    ctx.set_line_width(2)
    ctx.stroke()
    layout = PangoCairo.create_layout(ctx)
    layout.set_font_description(_number_font)
    layout.set_text(str(number), -1)
    w, h = layout.get_pixel_size()
    ctx.set_source_rgb(*theme.rgb(notes.INK))
    ctx.move_to(x - w / 2, y - h / 2)
    PangoCairo.show_layout(ctx, layout)


def _shadow(ctx, x, y, r):
    for i in range(4, 0, -1):
        ctx.arc(x, y + 1.5, r + i * 1.2, 0, 2 * math.pi)
        ctx.set_source_rgba(0, 0, 0, 0.05)
        ctx.fill()


def draw(ctx, note, fit, stroke=2, kind=None, number=None):
    """One note's mark where fit places it. kind and number stand in while a note is edited."""
    kind = kind or note.kind
    number = note.number if number is None else number
    x, y = fit.to_view(note.x, note.y)
    if note.pin:
        _shadow(ctx, x, y, PIN / 2)
        badge(ctx, x, y, PIN, kind, number)
        if stroke > 2:
            ctx.arc(x, y, PIN / 2 + 3, 0, 2 * math.pi)
            ctx.set_source_rgb(*colour(kind))
            ctx.set_line_width(2)
            ctx.stroke()
        return
    w, h = note.width * fit.k, note.height * fit.k
    ctx.rectangle(x, y, w, h)
    ctx.set_source_rgba(*colour(kind), 0.14)
    ctx.fill_preserve()
    ctx.set_source_rgb(*colour(kind))
    ctx.set_line_width(stroke)
    ctx.stroke()
    badge(ctx, x, y, BADGE, kind, number)


def dragging(ctx, x0, y0, x1, y1):
    ctx.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
    ctx.set_source_rgba(*theme.rgb(theme.ACCENT), 0.1)
    ctx.fill_preserve()
    ctx.set_source_rgb(*theme.rgb(theme.ACCENT))
    ctx.set_line_width(2)
    ctx.set_dash([6, 4])
    ctx.stroke()
    ctx.set_dash([])


def flash(ctx, note, fit, t):
    """A ring that widens and fades around a mark as t goes from 0 to 1."""
    x, y = fit.to_view(note.x, note.y)
    grow = 4 + 12 * t
    if note.pin:
        ctx.arc(x, y, PIN / 2 + grow, 0, 2 * math.pi)
    else:
        ctx.rectangle(x - grow, y - grow, note.width * fit.k + 2 * grow, note.height * fit.k + 2 * grow)
    ctx.set_source_rgba(*colour(note.kind), 1 - t)
    ctx.set_line_width(3)
    ctx.stroke()


def render(source, box, shown):
    """The part box of the share, scaled as look scales it, with the marks of shown drawn in,
    as PNG base64."""
    x, y, w, h = box
    out = picture.scaled(source, box)
    k = out.get_width() / w
    ctx = cairo.Context(out)
    fit = notes.Fit(k, -x * k, -y * k)
    for note in shown:
        draw(ctx, note, fit)
    return picture.png(out)
