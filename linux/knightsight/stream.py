"""The frames of one portal screen cast, read from PipeWire through GStreamer."""

import threading

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from . import picture  # noqa: E402

Gst.init(None)


class Frames:
    def __init__(self, fd, node):
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

    def size(self):
        with self.lock:
            sample = self.latest
        if sample is None:
            return None
        s = sample.get_caps().get_structure(0)
        return s.get_value("width"), s.get_value("height")

    def surface(self):
        """The newest frame as a cairo surface, or None before the first one arrives."""
        with self.lock:
            sample = self.latest
        if sample is None:
            return None
        s = sample.get_caps().get_structure(0)
        width, height = s.get_value("width"), s.get_value("height")
        buffer = sample.get_buffer()
        ok, mapped = buffer.map(Gst.MapFlags.READ)
        if not ok:
            return None
        try:
            data = bytearray(mapped.data)
        finally:
            buffer.unmap(mapped)
        return picture.surface(data, len(data) // height, width, height, False)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
