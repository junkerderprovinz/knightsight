import base64
import io

import cairo

from . import protocol


def surface(data, stride, width, height, alpha):
    """Wraps pixels in cairo's native layout, BGRA in memory on the machines this runs on."""
    fmt = cairo.FORMAT_ARGB32 if alpha else cairo.FORMAT_RGB24
    return cairo.ImageSurface.create_for_data(data, fmt, width, height, stride)


def encode(source, crop=None):
    """The reply fields for look: the picture scaled to the protocol's size limit, as PNG."""
    x, y, w, h = crop or (0, 0, source.get_width(), source.get_height())
    pw, ph = protocol.picture_size(w, h)
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, pw, ph)
    ctx = cairo.Context(out)
    ctx.scale(pw / w, ph / h)
    ctx.set_source_surface(source, -x, -y)
    ctx.get_source().set_filter(cairo.FILTER_BEST)
    ctx.paint()
    png = io.BytesIO()
    out.write_to_png(png)
    return {"image": base64.b64encode(png.getvalue()).decode("ascii"), "width": pw, "height": ph}
