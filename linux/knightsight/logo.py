"""A brass spyglass across a split steel ring, drawn the way Logo.Render in src/KnightSight.cs draws it.

The shapes come from .github/assets/knightsight.svg through gen-logo-shapes.mjs. They are
filled without antialiasing at four times the size and then scaled down, so neighbouring
shapes meet without hairlines and the edges still come out soft.
"""

import sys

import cairo

from .logo_shapes import HEIGHT, SHAPES, WIDTH

OVERSAMPLING = 4
# The app icons keep some air around the mark, as the GNOME icon grid expects.
ICON_MARGIN = 0.06

_drawn = {}


def _fill(ctx, rgb, steps):
    """Fills one shape from the generator's M, L, C and Z steps with their absolute points."""
    ctx.set_source_rgb((rgb >> 16) / 255, (rgb >> 8 & 0xFF) / 255, (rgb & 0xFF) / 255)
    t = steps.split()
    i = 0
    while i < len(t):
        op = t[i]
        i += 1
        if op == "Z":
            ctx.close_path()
            continue
        n = 6 if op == "C" else 2
        v = [float(x) for x in t[i : i + n]]
        i += n
        if op == "M":
            ctx.move_to(*v)
        elif op == "L":
            ctx.line_to(*v)
        else:
            ctx.curve_to(*v)
    ctx.fill()


def render(size, margin=0.0):
    large = cairo.ImageSurface(cairo.FORMAT_ARGB32, size * OVERSAMPLING, size * OVERSAMPLING)
    ctx = cairo.Context(large)
    ctx.set_antialias(cairo.ANTIALIAS_NONE)
    scale = large.get_width() * (1 - 2 * margin) / max(WIDTH, HEIGHT)
    ctx.translate((large.get_width() - WIDTH * scale) / 2, (large.get_height() - HEIGHT * scale) / 2)
    ctx.scale(scale, scale)
    for rgb, steps in SHAPES:
        _fill(ctx, rgb, steps)

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
    render(int(sys.argv[1]), ICON_MARGIN).write_to_png(sys.argv[2])
