import base64
import io

import cairo

from . import protocol


def surface(data, stride, width, height, alpha):
    """Wraps pixels in cairo's native layout, BGRA in memory on the machines this runs on."""
    fmt = cairo.FORMAT_ARGB32 if alpha else cairo.FORMAT_RGB24
    return cairo.ImageSurface.create_for_data(data, fmt, width, height, stride)


def cut(source, x, y, width, height):
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    ctx = cairo.Context(out)
    ctx.set_source_surface(source, -x, -y)
    ctx.paint()
    return out


def scaled(source, crop=None):
    """The picture, or the crop x, y, w, h of it, scaled down to the protocol's size limit."""
    x, y, w, h = crop or (0, 0, source.get_width(), source.get_height())
    pw, ph = protocol.picture_size(w, h)
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, pw, ph)
    ctx = cairo.Context(out)
    ctx.scale(pw / w, ph / h)
    ctx.set_source_surface(source, -x, -y)
    ctx.get_source().set_filter(cairo.FILTER_BEST)
    ctx.paint()
    return out


def fitted(source, width, height):
    """The picture shrunk or grown to fit inside width x height, keeping its shape."""
    w, h = source.get_width(), source.get_height()
    s = min(width / w, height / h)
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, max(1, round(w * s)), max(1, round(h * s)))
    ctx = cairo.Context(out)
    ctx.scale(s, s)
    ctx.set_source_surface(source, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    return out


def png(surface):
    out = io.BytesIO()
    surface.write_to_png(out)
    return base64.b64encode(out.getvalue()).decode("ascii")


def encode(source):
    """The reply fields for look."""
    out = scaled(source)
    return {"image": png(out), "width": out.get_width(), "height": out.get_height()}
