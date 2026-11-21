import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LANGUAGE"] = "en"

from knightsight import notes, protocol, say  # noqa: E402
from knightsight.protocol import Rect, Refused  # noqa: E402


class Desk:
    def __init__(self):
        self.done = []
        self.is_minimized = False
        self.comes_back = False
        self.controls = None
        self.fails = None
        self.ours = []

    def minimized(self, share):
        return self.is_minimized

    def unminimize(self, share):
        self.is_minimized = not self.comes_back
        return self.comes_back

    def look(self, share):
        reply = {"image": "", "width": share.width, "height": share.height, "title": "Test"}
        if self.controls is not None:
            reply["elements"] = self.controls
        return reply

    def click(self, share, args):
        point = protocol.to_area(share, args)
        protocol.clear_of(*point, self.ours)
        if self.fails:
            with protocol.delivering():
                raise self.fails
        self.done.append(("click", point))
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
        self.rounds = notes.Rounds()
        self.elements = None

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

    def test_minimized_window_that_stays_down_is_refused(self):
        panel = Panel()
        panel.desk.is_minimized = True
        self.assertEqual(ask(panel, cmd="look")["error"], "The shared window is minimized and did not come back.")

    def test_minimized_window_is_brought_back_and_looked_at(self):
        panel = Panel()
        panel.desk.is_minimized = True
        panel.desk.comes_back = True
        self.assertEqual(ask(panel, cmd="look")["title"], "Test")
        self.assertFalse(panel.desk.is_minimized)

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


ADD = {"ref": "e2", "role": "button", "name": "Add", "x": 430, "y": 40, "width": 60, "height": 30}


class Refs(unittest.TestCase):
    def test_a_ref_from_the_last_look_is_clicked_in_its_middle(self):
        panel = Panel()
        panel.desk.controls = [ADD]
        self.assertEqual(ask(panel, cmd="look")["elements"], [ADD])
        self.assertEqual(ask(panel, cmd="click", ref="e2"), {"ok": True, "message": "Clicked."})
        self.assertEqual(ask(panel, cmd="scroll", ref="e2", amount=1), {"ok": True, "message": "Scrolled."})
        self.assertEqual(panel.desk.done[0], ("click", (560, 105)))
        self.assertEqual(panel.desk.done[1][1], (560, 105))

    def test_a_ref_before_any_look_is_refused(self):
        panel = Panel()
        self.assertEqual(ask(panel, cmd="click", ref="e2")["error"],
                         "There is no element e2 from the last look. Take a new look.")
        self.assertEqual(panel.desk.done, [])

    def test_a_ref_the_last_look_did_not_list_is_refused(self):
        panel = Panel()
        panel.desk.controls = [ADD]
        ask(panel, cmd="look")
        self.assertEqual(ask(panel, cmd="click", ref="e12")["error"],
                         "There is no element e12 from the last look. Take a new look.")

    def test_a_look_without_controls_forgets_the_refs_before_it(self):
        panel = Panel()
        panel.desk.controls = [ADD]
        ask(panel, cmd="look")
        panel.desk.controls = None
        self.assertNotIn("elements", ask(panel, cmd="look"))
        self.assertFalse(ask(panel, cmd="click", ref="e2")["ok"])

    def test_neither_a_point_nor_a_ref_is_refused(self):
        panel = Panel()
        self.assertEqual(ask(panel, cmd="click")["error"], "Click needs x and y or a ref from look.")
        self.assertEqual(ask(panel, cmd="scroll", amount=2)["error"], "Scroll needs x and y or a ref from look.")


class Delivery(unittest.TestCase):
    def test_a_refusal_before_any_input_says_nothing_about_delivery(self):
        reply = ask(Panel(), cmd="click", x=5000, y=1)
        self.assertEqual(reply, {"ok": False, "error": "The point lies outside the share."})

    def test_a_failure_while_input_goes_out_may_have_delivered(self):
        panel = Panel()
        panel.desk.fails = OSError("the input layer broke")
        self.assertEqual(ask(panel, cmd="click", x=1, y=1),
                         {"ok": False, "error": "OSError: the input layer broke", "delivered": "maybe"})
        panel.desk.fails = Refused("The window closed while the input went to it.")
        self.assertEqual(ask(panel, cmd="click", x=1, y=1)["delivered"], "maybe")


PANEL = Rect(300, 400, 720, 304)


class OwnWindows(unittest.TestCase):
    def test_a_point_on_the_panel_is_refused(self):
        with self.assertRaises(Refused) as caught:
            protocol.clear_of(310, 410, [None, PANEL])
        self.assertEqual(str(caught.exception), "That point lies on KnightSight itself.")

    def test_a_point_beside_the_panel_or_on_a_hidden_window_passes(self):
        protocol.clear_of(299, 410, [PANEL])
        protocol.clear_of(310, 704, [PANEL])
        protocol.clear_of(310, 410, [None])

    def test_a_click_on_the_panel_says_nothing_reached_the_window(self):
        panel = Panel(area=Rect(0, 0, 1280, 800))
        panel.desk.ours = [PANEL]
        self.assertEqual(ask(panel, cmd="click", x=310, y=410), {"ok": False, "error": protocol.ON_US})
        self.assertEqual(panel.desk.done, [])


class Screens(unittest.TestCase):
    def test_a_screen_is_titled_by_its_number_and_size(self):
        self.assertEqual(say.screen(1, 2560, 1440), "Screen 1 (2560 x 1440)")
        self.assertEqual(say.screen(None, 1280, 800), "Screen (1280 x 800)")

    def test_a_german_desktop_titles_it_in_german(self):
        with mock.patch.object(say, "GERMAN", True):
            self.assertEqual(say.screen(2, 1920, 1080), "Bildschirm 2 (1920 x 1080)")


class Notes(unittest.TestCase):
    def test_notes_are_answered_while_nothing_is_shared(self):
        panel = Panel(shared=False)
        self.assertEqual(ask(panel, cmd="notes"), {"ok": True, "round": 0})
        panel.rounds.send({"title": "Test", "notes": []})
        self.assertEqual(ask(panel, cmd="notes")["round"], 1)

    def test_asking_for_notes_is_no_work(self):
        panel = Panel()
        panel.rounds.send({"title": "Test", "notes": []})
        ask(panel, cmd="notes")
        ask(panel, cmd="notes", unread=True)
        self.assertIsNone(panel.doing)

    def test_unread_hands_a_round_out_once(self):
        panel = Panel()
        panel.rounds.send({"title": "Test", "notes": []})
        self.assertEqual(ask(panel, cmd="notes", unread=True), {"ok": True, "round": 1, "title": "Test", "notes": []})
        self.assertEqual(ask(panel, cmd="notes", unread=True), {"ok": True, "round": 1})
        self.assertEqual(ask(panel, cmd="notes")["title"], "Test")

    def test_a_confirmed_round_is_not_handed_out_again(self):
        panel = Panel()
        panel.rounds.send({"title": "Test", "notes": []})
        self.assertEqual(ask(panel, cmd="notes", unread=True, confirm=True)["title"], "Test")
        self.assertEqual(ask(panel, cmd="notes", unread=True, confirm=True)["title"], "Test")
        self.assertEqual(ask(panel, cmd="notes", read=1), {"ok": True})
        self.assertEqual(ask(panel, cmd="notes", unread=True, confirm=True), {"ok": True, "round": 1})

    def test_a_note_arrives_with_its_marks(self):
        panel = Panel(shared=False)
        note = notes.Note(3, "bug", "Too tight", "Junker", [notes.Mark(120, 80, 160, 40), notes.Mark(400, 300)])
        panel.rounds.send(notes.assemble("Editor", 1000, 800, [note], "FRAME", lambda *_: "CROP", "2026-11-15T13:03:12Z"))
        reply = ask(panel, cmd="notes")
        self.assertEqual(reply["notes"], [{
            "number": 3, "kind": "bug", "text": "Too tight", "author": "Junker", "marks": [
                {"label": "3a", "x": 120, "y": 80, "width": 160, "height": 40, "image": "CROP"},
                {"label": "3b", "x": 400, "y": 300, "pin": True, "image": "CROP"}]}])
        self.assertEqual({k: reply[k] for k in ("round", "sent", "title", "width", "height", "image")},
                         {"round": 1, "sent": "2026-11-15T13:03:12Z", "title": "Editor", "width": 1000,
                          "height": 800, "image": "FRAME"})


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
