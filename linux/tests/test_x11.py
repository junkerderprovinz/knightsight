import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gi  # noqa: E402

for name, version in (("Gtk", "4.0"), ("Gdk", "4.0"), ("PangoCairo", "1.0")):
    gi.require_version(name, version)

from knightsight import x11  # noqa: E402

STAT = "4242 (Web Content (1)) S 1 4242 4242 0 -1 4194560 2405 0 0 0 9 3 0 0 20 0 1 0 {} 9150464 893"


class FakeX:
    def __init__(self, pid=4242):
        self.pid = pid
        self.open = True

    def prop(self, window, name, kind=0):
        return [self.pid] if name == "_NET_WM_PID" and self.pid else None

    def attributes(self, window):
        return types.SimpleNamespace() if self.open else None


class Identity(unittest.TestCase):
    def setUp(self):
        self.proc = tempfile.TemporaryDirectory()
        os.mkdir(os.path.join(self.proc.name, "4242"))
        self.start(51133)
        patch = mock.patch.object(x11, "PROC", self.proc.name)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.proc.cleanup)

    def start(self, ticks):
        with open(os.path.join(self.proc.name, "4242", "stat"), "w") as f:
            f.write(STAT.format(ticks))

    def test_the_start_time_is_read_past_a_name_with_brackets_and_spaces(self):
        self.assertEqual(x11.stat_start(STAT.format(51133)), 51133)

    def test_the_chosen_window_belongs_to_the_process_it_had(self):
        x = FakeX()
        wins = x11.Windows(x)
        share = x11.Share("Target", window=7, owner=wins.owner(7))
        self.assertEqual(share.owner, (4242, 51133))
        self.assertTrue(wins.belongs(share))

    def test_a_new_process_under_the_same_pid_ends_the_share(self):
        wins = x11.Windows(FakeX())
        share = x11.Share("Target", window=7, owner=wins.owner(7))
        self.start(60000)
        self.assertFalse(wins.belongs(share))

    def test_a_closed_or_ownerless_window_ends_the_share(self):
        x = FakeX()
        wins = x11.Windows(x)
        share = x11.Share("Target", window=7, owner=wins.owner(7))
        x.pid = 0
        self.assertFalse(wins.belongs(share))
        x.pid, x.open = 4242, False
        self.assertFalse(wins.belongs(share))

    def test_a_process_that_ended_has_no_start_time(self):
        self.assertIsNone(x11.started(999999))


class Arrow(unittest.TestCase):
    def test_the_glide_leaves_its_start_quickly_and_slows_into_the_spot(self):
        self.assertEqual(x11.glided((0, 0), (100, 50), 0), (0, 0))
        self.assertEqual(x11.glided((0, 0), (100, 50), 1), (100, 50))
        self.assertEqual(x11.glided((0, 0), (100, 50), 3), (100, 50))
        self.assertGreater(x11.glided((0, 0), (100, 50), 0.5)[0], 75)

    def test_a_ring_grows_from_6_to_22_px_while_it_fades_out(self):
        self.assertEqual(x11.rings([10.0], 10.0), [(6, 1)])
        radius, opacity = x11.rings([10.0], 10.2)[0]
        self.assertTrue(6 < radius < 22 and 0 < opacity < 1, (radius, opacity))
        self.assertEqual(x11.rings([10.0], 10.5), [])

    def test_a_double_click_ripples_twice(self):
        self.assertEqual(len(x11.rings([10.0, 10.0 + x11.SECOND_RING_S], 10.2)), 2)

    def test_the_arrow_fades_in_at_its_first_spot_and_glides_to_the_next(self):
        cursor = x11.Cursor(types.SimpleNamespace(x=None))
        self.assertEqual(cursor.aim(10, 10, 5), 0)
        self.assertEqual(cursor.tip, (10, 10))
        cursor.alpha = 1
        self.assertEqual(cursor.aim(200, 80, 5), x11.GLIDE_S)
        self.assertEqual(cursor.glide[1], (200, 80))

    def test_reduced_motion_jumps_without_a_delay_or_a_ripple(self):
        cursor = x11.Cursor(types.SimpleNamespace(x=None))
        cursor.aim(10, 10, 5)
        cursor.alpha, cursor.moving = 1, False
        self.assertEqual(cursor.aim(200, 80, 5), 0)
        self.assertEqual(cursor.tip, (200, 80))
        cursor.ripple(2)
        self.assertEqual(cursor.starts, [])


if __name__ == "__main__":
    unittest.main()
