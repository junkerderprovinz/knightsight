"""The frames of one portal screen cast, read from PipeWire through GStreamer."""

import ctypes
import threading

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from . import picture  # noqa: E402
from .protocol import Rect  # noqa: E402

Gst.init(None)


class CropMeta(ctypes.Structure):
    """GstVideoCropMeta in memory. PyGObject hands out only its GstMeta head, without the region."""
    _fields_ = [("flags", ctypes.c_uint), ("info", ctypes.c_void_p),
                ("x", ctypes.c_uint), ("y", ctypes.c_uint), ("width", ctypes.c_uint), ("height", ctypes.c_uint)]


def _crop(buffer):
    # The meta type exists once GStreamer's video library has registered it, which
    # pipewiresrc does before it attaches the first crop region.
    info = Gst.Meta.get_info("GstVideoCropMeta")
    meta = info and buffer.get_meta(info.api)
    if meta is None:
        return None
    c = CropMeta.from_address(hash(meta))
    return Rect(c.x, c.y, c.width, c.height)


def _filled(data, stride, width, height):
    """The smallest rectangle around every pixel that holds more than zero bytes, or None.
    Around a window GNOME leaves the frame zeroed, while the window and even the faintest
    part of its shadow carry an alpha byte."""
    top = bottom = None
    left, right = width, 0
    for y in range(height):
        row = data[y * stride:y * stride + width * 4]
        end = len(row.rstrip(b"\0"))
        if not end:
            continue
        if top is None:
            top = y
        bottom = y
        left = min(left, (width * 4 - len(row.lstrip(b"\0"))) // 4)
        right = max(right, (end + 3) // 4)
    if top is None:
        return None
    return Rect(left, top, right - left, bottom + 1 - top)


class Frame:
    """One frame and the part of it the desktop filled. GNOME sends a window in a frame as
    large as the monitor, with the window in the corner and black around it, and says where
    in a crop region. PipeWire passes that region on to GStreamer from 1.6 on, so for a
    window without one the zeroed padding is left out instead."""

    def __init__(self, sample, window=False):
        s = sample.get_caps().get_structure(0)
        self.width, self.height = s.get_value("width"), s.get_value("height")
        buffer = sample.get_buffer()
        _, mapped = buffer.map(Gst.MapFlags.READ)
        try:
            self.data = bytearray(mapped.data)
        finally:
            buffer.unmap(mapped)
        self.stride = len(self.data) // self.height
        self.area = (_crop(buffer) or window and _filled(self.data, self.stride, self.width, self.height)
                     or Rect(0, 0, self.width, self.height))

    def surface(self):
        return picture.surface(self.data, self.stride, self.width, self.height, False)


class Frames:
    def __init__(self, fd, node, window):
        self.window = window
        # keepalive-time repeats the last frame, since a window that does not change sends none.
        self.pipeline = Gst.parse_launch(
            f"pipewiresrc fd={fd} path={node} always-copy=true keepalive-time=1000 do-timestamp=true"
            " ! videoconvert ! video/x-raw,format=BGRx ! appsink name=sink emit-signals=true max-buffers=1 drop=true"
            " sync=false")
        self.lock = threading.Lock()
        self.latest = None
        self.pipeline.get_by_name("sink").connect("new-sample", self._sample)
        self.pipeline.set_state(Gst.State.PLAYING)

    def _sample(self, sink):
        sample = sink.emit("pull-sample")
        with self.lock:
            self.latest = sample
        return Gst.FlowReturn.OK

    def frame(self):
        """The newest frame, or None before the first one arrives."""
        with self.lock:
            sample = self.latest
        return None if sample is None else Frame(sample, self.window)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
