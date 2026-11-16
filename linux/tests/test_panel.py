import contextlib
import io
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gi  # noqa: E402

for name, version in (("Gtk", "4.0"), ("Gdk", "4.0"), ("PangoCairo", "1.0")):
    gi.require_version(name, version)

from knightsight import panel, theme  # noqa: E402


class Ticks(unittest.TestCase):
    def test_a_failing_frame_keeps_the_timer_and_is_reported_once(self):
        def broken():
            raise AttributeError("'Desk' object has no attribute 'hide'")

        fake = types.SimpleNamespace(advance=broken, last_error=None)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertTrue(panel.Panel.tick(fake))
            self.assertTrue(panel.Panel.tick(fake))
        self.assertEqual(err.getvalue().count("Traceback"), 1)
        self.assertIn("AttributeError: 'Desk' object has no attribute 'hide'", err.getvalue())


class Colours(unittest.TestCase):
    def test_a_colour_moved_a_little_each_frame_reaches_its_target(self):
        color = theme.ACCENT
        for _ in range(100):
            color = theme.mix(color, theme.NEUTRAL, 16 / theme.CONTROL_MS)
        self.assertEqual(color, theme.NEUTRAL)
        self.assertEqual(theme.mix((0, 0, 0), (255, 128, 1), 0), (0, 0, 0))
        self.assertEqual(theme.mix((0, 0, 0), (255, 128, 1), 1), (255, 128, 1))


if __name__ == "__main__":
    unittest.main()
