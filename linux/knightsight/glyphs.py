"""Line icons drawn in the button's ink, so they follow hover, theme and disabled state."""

import math

import cairo


def rounded(ctx, x, y, w, h, radius):
    r = min(radius, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _corner(ctx, points):
    ctx.move_to(*points[0])
    for p in points[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def draw(ctx, glyph, s):
    """Draws glyph in the current source colour into the square 0, 0, s, s."""
    ctx.set_line_width(1.6)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    if glyph == "window":
        x, y, w, h = s * 0.06, s * 0.14, s * 0.88, s * 0.72
        rounded(ctx, x, y, w, h, 2.5)
        ctx.stroke()
        ctx.move_to(x, y + s * 0.24)
        ctx.line_to(x + w, y + s * 0.24)
        ctx.stroke()
    elif glyph == "region":
        a, lo, hi = s * 0.3, s * 0.08, s * 0.92
        _corner(ctx, [(lo, lo + a), (lo, lo), (lo + a, lo)])
        _corner(ctx, [(hi - a, lo), (hi, lo), (hi, lo + a)])
        _corner(ctx, [(hi, hi - a), (hi, hi), (hi - a, hi)])
        _corner(ctx, [(lo + a, hi), (lo, hi), (lo, hi - a)])
    elif glyph == "start":
        ctx.move_to(s * 0.22, s * 0.14)
        ctx.line_to(s * 0.86, s * 0.5)
        ctx.line_to(s * 0.22, s * 0.86)
        ctx.close_path()
        ctx.fill_preserve()
        ctx.stroke()
    elif glyph == "stop":
        rounded(ctx, s * 0.18, s * 0.18, s * 0.64, s * 0.64, 2)
        ctx.fill()
    elif glyph == "info":
        ctx.arc(s / 2, s / 2, s / 2 - 0.8, 0, 2 * math.pi)
        ctx.stroke()
        ctx.arc(s / 2, s * 0.27, 1.1, 0, 2 * math.pi)
        ctx.fill()
        ctx.move_to(s / 2, s * 0.45)
        ctx.line_to(s / 2, s * 0.73)
        ctx.stroke()
    elif glyph == "minimise":
        rounded(ctx, 0, s * 6 / 14, s, s * 2 / 14, s / 14)
        ctx.fill()
    elif glyph == "close":
        ctx.save()
        ctx.translate(s / 2, s / 2)
        ctx.rotate(math.pi / 4)
        arm = s * 1.1 / 10
        rounded(ctx, -s / 2, -arm, s, 2 * arm, arm)
        ctx.fill()
        rounded(ctx, -arm, -s / 2, 2 * arm, s, arm)
        ctx.fill()
        ctx.restore()
