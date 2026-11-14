import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LANGUAGE"] = "en"

import gi  # noqa: E402

for name, version in (("Gtk", "4.0"), ("Gdk", "4.0"), ("Gst", "1.0"), ("GstVideo", "1.0")):
    gi.require_version(name, version)

from gi.repository import Gst, GstVideo  # noqa: E402

from knightsight import portal, stream  # noqa: E402
from knightsight.protocol import Rect, Refused  # noqa: E402


def sample(width, height, crop=None, filled=None):
    """A frame the way pipewiresrc hands it over: zero bytes where the desktop drew nothing, an
    opaque grey where it did, and the crop region it attached."""
    pixels = bytearray(width * height * 4)
    if filled:
        x, y, w, h = filled
        for row in range(y, y + h):
            start = (row * width + x) * 4
            pixels[start:start + w * 4] = bytes((128, 128, 128, 255)) * w
    buffer = Gst.Buffer.new_wrapped(bytes(pixels))
    if crop:
        meta = buffer.add_meta(GstVideo.VideoCropMeta.get_info(), None)
        c = stream.CropMeta.from_address(hash(meta))
        c.x, c.y, c.width, c.height = crop
    caps = Gst.Caps.from_string(f"video/x-raw,format=BGRx,width={width},height={height}")
    return Gst.Sample.new(buffer, caps, None, None)


class Frames:
    def __init__(self, frame):
        self.latest = frame

    def frame(self):
        return self.latest


def window_share(frame, size=(1568, 882)):
    return portal.Share("/session", 7, {"size": size}, portal.KEYBOARD | portal.POINTER, Frames(frame))


def desk():
    d = portal.Desk.__new__(portal.Desk)
    d.panel = types.SimpleNamespace(busy=lambda: None, focused=False)
    d.sent = []
    d._notify = lambda _share, method, _signature, *args: d.sent.append((method, args))
    return d


class Crop(unittest.TestCase):
    def test_the_crop_region_is_what_the_frame_shows(self):
        frame = stream.Frame(sample(1568, 882, (0, 0, 710, 534)))
        self.assertEqual((frame.width, frame.height), (1568, 882))
        self.assertEqual(frame.area, Rect(0, 0, 710, 534))

    def test_a_frame_without_crop_shows_all_of_itself(self):
        self.assertEqual(stream.Frame(sample(640, 480)).area, Rect(0, 0, 640, 480))

    def test_a_window_without_crop_shows_what_the_desktop_filled(self):
        frame = stream.Frame(sample(1568, 882, filled=(0, 0, 710, 534)), window=True)
        self.assertEqual(frame.area, Rect(0, 0, 710, 534))

    def test_a_window_keeps_dark_and_offset_content(self):
        frame = stream.Frame(sample(1280, 800, filled=(30, 12, 401, 299)), window=True)
        self.assertEqual(frame.area, Rect(30, 12, 401, 299))

    def test_the_crop_region_wins_over_what_was_filled(self):
        frame = stream.Frame(sample(1568, 882, (0, 0, 700, 500), filled=(0, 0, 710, 534)), window=True)
        self.assertEqual(frame.area, Rect(0, 0, 700, 500))

    def test_a_screen_keeps_its_black_edges(self):
        self.assertEqual(stream.Frame(sample(1280, 800, filled=(100, 100, 300, 200))).area, Rect(0, 0, 1280, 800))


class PaddedWindow(unittest.TestCase):
    """GNOME sends a window in a frame as large as the monitor, the rest of it black."""

    def setUp(self):
        self.desk = desk()
        self.share = window_share(stream.Frame(sample(1568, 882, (0, 0, 710, 534)), window=True))

    def test_look_shows_only_the_window(self):
        reply = self.desk.look(self.share)
        self.assertEqual((reply["width"], reply["height"]), (710, 534))

    def test_a_click_in_the_window_reaches_it(self):
        self.desk.click(self.share, {"x": 100, "y": 200})
        self.assertEqual(self.desk.sent[0], ("NotifyPointerMotionAbsolute", (7, 100.0, 200.0)))

    def test_a_click_in_the_padding_is_refused(self):
        with self.assertRaisesRegex(Refused, "outside the share"):
            self.desk.click(self.share, {"x": 1010, "y": 620})
        self.assertEqual(self.desk.sent, [])

    def test_points_move_with_the_crop_and_the_stream_units(self):
        share = window_share(stream.Frame(sample(1568, 882, (20, 10, 700, 500)), window=True), size=(784, 441))
        self.desk.click(share, {"x": 0, "y": 0})
        self.assertEqual(self.desk.sent[0], ("NotifyPointerMotionAbsolute", (7, 10.0, 5.0)))

    def test_without_crop_the_padding_is_refused_too(self):
        share = window_share(stream.Frame(sample(1568, 882, filled=(0, 0, 710, 534)), window=True))
        self.assertEqual(self.desk.look(share)["width"], 710)
        with self.assertRaisesRegex(Refused, "outside the share"):
            self.desk.click(share, {"x": 1010, "y": 620})
        self.assertEqual(self.desk.sent, [])


if __name__ == "__main__":
    unittest.main()
