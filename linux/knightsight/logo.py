"""A brass spyglass across a steel frame, drawn the way Logo.Render in src/KnightSight.cs draws it.

On a 256 grid with the light from the top left, without antialiasing at four times the size
and then scaled down, so the facets meet without hairlines and the edges come out soft.
"""

import math
import sys

import cairo

GRID = 256
OVERSAMPLING = 4

# From eyepiece to hood: start, end and half width of each part, rings and tubes taking turns.
PARTS = [(0, 12, 15), (12, 92, 13), (92, 104, 22), (104, 170, 19), (170, 182, 28), (182, 250, 25), (250, 264, 30)]

STEEL_LIT, STEEL_SHADE, STEEL_DARK = (184, 184, 184), (131, 131, 136), (102, 102, 107)
BRASS_LIT, BRASS, BRASS_SHADE, BRASS_DARK = (253, 216, 142), (233, 186, 87), (205, 147, 55), (145, 102, 49)

_drawn = {}


def _color(ctx, c):
    ctx.set_source_rgb(c[0] / 255, c[1] / 255, c[2] / 255)


def _axis(ctx):
    ctx.translate(36, 220)
    ctx.rotate(math.radians(-45))


def _band(ctx, color, *xy):
    _color(ctx, color)
    ctx.move_to(xy[0], xy[1])
    for i in range(2, 8, 2):
        ctx.line_to(xy[i], xy[i + 1])
    ctx.close_path()
    ctx.fill()


def _frame(ctx):
    o0, o1, s0, s1, i0, i1 = 44, 212, 58, 198, 72, 184
    _band(ctx, STEEL_LIT, o0, o0, o1, o0, s1, s0, s0, s0)
    _band(ctx, STEEL_LIT, o0, o0, s0, s0, s0, s1, o0, o1)
    _band(ctx, STEEL_DARK, o1, o0, o1, o1, s1, s1, s1, s0)
    _band(ctx, STEEL_DARK, o0, o1, s0, s1, s1, s1, o1, o1)
    _band(ctx, STEEL_SHADE, s0, s0, s1, s0, i1, i0, i0, i0)
    _band(ctx, STEEL_SHADE, s0, s0, i0, i0, i0, i1, s0, s1)
    _band(ctx, STEEL_LIT, s1, s0, s1, s1, i1, i1, i1, i0)
    _band(ctx, STEEL_LIT, s0, s1, i0, i1, i1, i1, s1, s1)


def _tube(ctx):
    ctx.save()
    _axis(ctx)
    for i, part in enumerate(PARTS):
        ring = i % 2 == 0
        _stripe(ctx, BRASS_SHADE if ring else BRASS, part, -1, 1)
        _stripe(ctx, BRASS if ring else BRASS_LIT, part, -1, -0.3 if ring else -0.42)
        _stripe(ctx, BRASS_DARK if ring else BRASS_SHADE, part, 0.45 if ring else 0.38, 1)
    ctx.restore()


def _stripe(ctx, color, part, start, end):
    _color(ctx, color)
    ctx.rectangle(part[0], start * part[2], part[1] - part[0], (end - start) * part[2])
    ctx.fill()


def render(size):
    large = cairo.ImageSurface(cairo.FORMAT_ARGB32, size * OVERSAMPLING, size * OVERSAMPLING)
    ctx = cairo.Context(large)
    ctx.set_antialias(cairo.ANTIALIAS_NONE)
    ctx.scale(large.get_width() / GRID, large.get_height() / GRID)
    _frame(ctx)
    # The tube lies over the frame with a gap around it. Straight edges for the narrow
    # and the wide half, so the rings leave no slivers of frame.
    ctx.save()
    _axis(ctx)
    ctx.rectangle(-7, -20, 118, 40)
    ctx.rectangle(97, -35, 174, 70)
    ctx.restore()
    ctx.set_operator(cairo.OPERATOR_CLEAR)
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    ctx.fill()
    ctx.set_operator(cairo.OPERATOR_OVER)
    _tube(ctx)

    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(out)
    ctx.scale(1 / OVERSAMPLING, 1 / OVERSAMPLING)
    ctx.set_source_surface(large)
    ctx.get_source().set_filter(cairo.FILTER_BEST)
    ctx.paint()
    return out


def draw(ctx, x, y, size, device_scale=1):
    """Paints the logo at x, y, rendered once per size and device scale."""
    edge = round(size * device_scale)
    if edge not in _drawn:
        _drawn[edge] = render(edge)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(size / edge, size / edge)
    ctx.set_source_surface(_drawn[edge])
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    ctx.restore()


if __name__ == "__main__":
    render(int(sys.argv[1])).write_to_png(sys.argv[2])
