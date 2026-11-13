import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LANGUAGE"] = "en"

from knightsight import protocol  # noqa: E402
from knightsight.protocol import Rect, Refused  # noqa: E402


class Desk:
    def __init__(self):
        self.done = []
        self.is_minimized = False

    def minimized(self, share):
        return self.is_minimized

    def look(self, share):
        return {"image": "", "width": share.width, "height": share.height, "title": "Test"}

    def click(self, share, args):
        self.done.append(("click", protocol.to_area(share, args)))
        return "Clicked."

    def scroll(self, share, args):
        self.done.append(("scroll", protocol.to_area(share, args), protocol.number(args, "amount")))
        return "Scrolled."

    def type(self, share, text):
        self.done.append(("type", text))
        return "Typed."

    def key(self, share, keys):
        self.done.append(("key", protocol.parse_combo(keys)))
        return "Pressed."


class Panel:
    def __init__(self, shared=True, area=Rect(100, 50, 800, 600)):
        self.desk = Desk()
        self.shared = area if shared else None
        self.doing = None

    def share(self):
        return self.shared

    def working(self, doing):
        self.doing = doing


def ask(panel, **request):
    return json.loads(protocol.reply(json.dumps(request).encode(), panel))


class Replies(unittest.TestCase):
    def test_nothing_shared_is_refused_before_anything_else(self):
        panel = Panel(shared=False)
        for request in ({"cmd": "look"}, {"cmd": "click", "x": 1, "y": 1}, {"cmd": "nonsense"}, {}):
            self.assertEqual(ask(panel, **request), {"ok": False, "error": protocol.NOTHING_SHARED})
        self.assertIsNone(panel.doing)

    def test_minimized_window_is_refused(self):
        panel = Panel()
        panel.desk.is_minimized = True
        self.assertEqual(ask(panel, cmd="look")["error"], "The shared window is minimized.")

    def test_look_returns_the_picture_fields(self):
        reply = ask(Panel(), cmd="look")
        self.assertEqual(reply, {"ok": True, "image": "", "width": 800, "height": 600, "title": "Test"})

    def test_actions_return_their_message(self):
        panel = Panel()
        self.assertEqual(ask(panel, cmd="click", x=10, y=20), {"ok": True, "message": "Clicked."})
        self.assertEqual(ask(panel, cmd="type", text="hi"), {"ok": True, "message": "Typed."})
        self.assertEqual(ask(panel, cmd="key", keys="ctrl+l"), {"ok": True, "message": "Pressed."})
        self.assertEqual(ask(panel, cmd="scroll", x=1, y=1, amount=3), {"ok": True, "message": "Scrolled."})
        self.assertEqual(panel.desk.done[0], ("click", (110, 70)))

    def test_unknown_command_is_refused(self):
        self.assertEqual(ask(Panel(), cmd="steps")["error"], "Unknown command: steps")

    def test_missing_fields_are_named(self):
        panel = Panel()
        self.assertEqual(ask(panel, x=1)["error"], "Missing cmd.")
        self.assertEqual(ask(panel, cmd="type")["error"], "Missing text.")
        self.assertEqual(ask(panel, cmd="key")["error"], "Missing keys.")
        self.assertEqual(ask(panel, cmd="click", x=1)["error"], "Missing y.")
        self.assertEqual(ask(panel, cmd="scroll", x=1, y=1)["error"], "Missing amount.")

    def test_broken_json_gets_an_error_reply(self):
        reply = json.loads(protocol.reply(b"{not json", Panel()))
        self.assertFalse(reply["ok"])
        self.assertTrue(reply["error"].startswith("JSONDecodeError: "))

    def test_working_names_what_is_done(self):
        panel = Panel()
        ask(panel, cmd="click", x=1, y=1, right=True)
        self.assertEqual(panel.doing, "Right-clicking")
        ask(panel, cmd="key", keys="ctrl+pageup")
        self.assertEqual(panel.doing, "Pressing Ctrl+Page Up")


class Points(unittest.TestCase):
    def test_small_share_maps_one_to_one(self):
        self.assertEqual(protocol.to_area(Rect(100, 50, 800, 600), {"x": 0, "y": 0}), (100, 50))
        self.assertEqual(protocol.to_area(Rect(100, 50, 800, 600), {"x": 799, "y": 599}), (899, 649))

    def test_large_share_scales_back_from_the_picture(self):
        area = Rect(0, 0, 3136, 1000)
        self.assertEqual(protocol.picture_size(3136, 1000), (1568, 500))
        self.assertEqual(protocol.to_area(area, {"x": 1000, "y": 250}), (2000, 500))

    def test_points_outside_are_refused(self):
        area = Rect(100, 50, 800, 600)
        for x, y in ((800, 0), (0, 600), (-1, 0), (0, -1), (5000, 5000)):
            with self.assertRaisesRegex(Refused, "outside the share"):
                protocol.to_area(area, {"x": x, "y": y})

    def test_numbers_may_arrive_as_text(self):
        self.assertEqual(protocol.to_area(Rect(0, 0, 10, 10), {"x": "3", "y": 4.4}), (3, 4))

    def test_text_that_is_no_number_is_refused(self):
        with self.assertRaisesRegex(Refused, "x is not a number"):
            protocol.to_area(Rect(0, 0, 10, 10), {"x": "left", "y": 1})


class Keys(unittest.TestCase):
    def test_single_keys(self):
        self.assertEqual(protocol.parse_combo("enter"), protocol.Combo([], "Return", False))
        self.assertEqual(protocol.parse_combo("Esc"), protocol.Combo([], "Escape", False))
        self.assertEqual(protocol.parse_combo("a"), protocol.Combo([], "a", True))
        self.assertEqual(protocol.parse_combo("F12"), protocol.Combo([], "F12", False))
        self.assertEqual(protocol.parse_combo("pagedown"), protocol.Combo([], "Page_Down", False))

    def test_combinations_keep_their_order(self):
        self.assertEqual(protocol.parse_combo("ctrl+shift+t"), protocol.Combo(["ctrl", "shift"], "t", True))
        self.assertEqual(protocol.parse_combo("Strg + Alt + Del"), protocol.Combo(["ctrl", "alt"], "Delete", False))
        self.assertEqual(protocol.parse_combo("control+ctrl+l"), protocol.Combo(["ctrl"], "l", True))

    def test_system_key_is_refused(self):
        for combo in ("win", "super+l", "meta+tab", "ctrl+windows+d"):
            with self.assertRaisesRegex(Refused, "whole system"):
                protocol.parse_combo(combo)

    def test_two_keys_are_refused(self):
        with self.assertRaisesRegex(Refused, "Only one key besides"):
            protocol.parse_combo("a+b")

    def test_unknown_and_missing_keys_are_refused(self):
        for combo, message in (("hyper", "Unknown key: hyper"), ("f25", "Unknown key: f25"), ("f0", "Unknown key: f0"),
                               ("ctrl+", "Unknown key: "), ("ctrl+shift", "The key itself is missing: ctrl+shift")):
            with self.assertRaises(Refused) as caught:
                protocol.parse_combo(combo)
            self.assertEqual(str(caught.exception), message)

    def test_text_turns_line_breaks_into_keys(self):
        self.assertEqual(protocol.text_keys("a\r\nb\tc"),
                         [("a", True), ("Return", False), ("b", True), ("Tab", False), ("c", True)])

    def test_key_names_read_like_the_keyboard(self):
        self.assertEqual(protocol.key_name("ctrl+shift+t"), "Ctrl+Shift+T")
        self.assertEqual(protocol.key_name("escape"), "Esc")
        self.assertEqual(protocol.key_name("control+pagedown"), "Ctrl+Page Down")


if __name__ == "__main__":
    unittest.main()
