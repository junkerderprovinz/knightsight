import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from knightsight import elements  # noqa: E402


class Roles(unittest.TestCase):
    def test_controls_map_onto_the_roles_a_look_reports(self):
        for nick, role in (("button", "button"), ("push-button", "button"), ("toggle-button", "button"),
                           ("link", "link"), ("entry", "edit"), ("password-text", "edit"), ("check-box", "checkbox"),
                           ("switch", "checkbox"), ("radio-button", "radio"), ("combo-box", "combobox"),
                           ("check-menu-item", "menuitem"), ("page-tab", "tab"), ("list-item", "listitem"),
                           ("tree-item", "treeitem"), ("slider", "slider"), ("label", "text")):
            self.assertEqual(elements.kind(nick, set()), role, nick)

    def test_a_text_that_can_be_edited_is_a_field(self):
        self.assertEqual(elements.kind("text", {"editable", "showing"}), "edit")
        self.assertEqual(elements.kind("text", {"showing"}), "text")

    def test_containers_and_windows_are_left_out(self):
        for nick in ("panel", "filler", "frame", "document-web", "scroll-pane", "image", "tool-bar", "menu-bar"):
            self.assertIsNone(elements.kind(nick, {"showing"}), nick)

    def test_a_nameless_control_is_listed_only_while_it_can_be_used(self):
        self.assertTrue(elements.worth_listing("edit", "", {"showing", "sensitive", "editable"}, None))
        self.assertTrue(elements.worth_listing("button", "", {"enabled"}, None))
        self.assertFalse(elements.worth_listing("button", "", {"showing"}, None))
        self.assertTrue(elements.worth_listing("button", "Save", {"showing"}, None))

    def test_a_text_is_listed_when_it_says_something_new(self):
        self.assertTrue(elements.worth_listing("text", "notes.txt", set(), None))
        self.assertFalse(elements.worth_listing("text", "", {"enabled"}, None))
        self.assertFalse(elements.worth_listing("text", "Bread", set(), "Bread"))

    def test_names_come_on_one_line_and_cut_short(self):
        self.assertEqual(elements.clean("  Save\n as\t copy  "), "Save as copy")
        self.assertEqual(elements.clean(None), "")
        self.assertEqual(len(elements.clean("x" * 200)), elements.NAME_LIMIT)


class Places(unittest.TestCase):
    def test_a_control_is_moved_into_the_share_and_scaled_to_the_picture(self):
        self.assertEqual(elements.placed((10, 20, 30, 40), (5, 6), (800, 600), 1),
                         {"x": 15, "y": 26, "width": 30, "height": 40})
        self.assertEqual(elements.placed((100, 100, 50, 20), (0, 0), (3136, 1000), 0.5),
                         {"x": 50, "y": 50, "width": 25, "height": 10})

    def test_a_control_reaching_out_of_the_share_is_clipped_to_it(self):
        self.assertEqual(elements.placed((-20, 580, 100, 50), (0, 0), (800, 600), 1),
                         {"x": 0, "y": 580, "width": 80, "height": 20})

    def test_controls_outside_the_share_or_without_size_are_left_out(self):
        self.assertIsNone(elements.placed((900, 10, 20, 20), (0, 0), (800, 600), 1))
        self.assertIsNone(elements.placed((10, 10, 20, 20), (-40, 0), (800, 600), 1))
        self.assertIsNone(elements.placed((10, 10, 0, 20), (0, 0), (800, 600), 1))

    def test_controls_are_numbered_top_to_bottom_then_left_to_right(self):
        found = [{"role": "button", "name": n, "x": x, "y": y, "width": 10, "height": 10}
                 for n, x, y in (("C", 5, 40), ("B", 90, 10), ("A", 20, 10))]
        self.assertEqual([(e["ref"], e["name"]) for e in elements.listed(found)], [("e1", "A"), ("e2", "B"), ("e3", "C")])
        self.assertEqual(list(elements.listed(found)[0]), ["ref", "role", "name", "x", "y", "width", "height"])

    def test_a_look_lists_at_most_the_limit(self):
        found = [{"role": "text", "name": str(i), "x": 0, "y": i, "width": 1, "height": 1} for i in range(400)]
        out = elements.listed(found)
        self.assertEqual(len(out), elements.LIMIT)
        self.assertEqual(out[-1]["ref"], f"e{elements.LIMIT}")


class Frames(unittest.TestCase):
    def test_the_frame_of_the_window_size_is_picked(self):
        frames = [("Editor", (0, 0, 800, 600), "a"), ("Find", (0, 0, 300, 220), "b")]
        self.assertEqual(elements.pick_frame(frames, None, 800, 600)[2], "a")

    def test_a_shadow_around_the_frame_still_fits(self):
        self.assertTrue(elements.fits((0, 0, 640, 480), 702, 542))
        self.assertTrue(elements.fits((0, 0, 640, 480), 640, 480))
        self.assertFalse(elements.fits((0, 0, 600, 250), 702, 542))
        self.assertFalse(elements.fits((0, 0, 640, 480), 1280, 800))

    def test_the_title_decides_between_frames_of_one_size(self):
        frames = [("One", (0, 0, 400, 300), "a"), ("Two", (0, 0, 400, 300), "b")]
        self.assertEqual(elements.pick_frame(frames, "Two", 400, 300)[2], "b")
        self.assertIsNone(elements.pick_frame(frames, None, 400, 300))

    def test_the_only_frame_of_a_process_is_its_window(self):
        frames = [("Odd", (0, 0, 10, 10), "a")]
        self.assertEqual(elements.pick_frame(frames, "Controls", 400, 300)[2], "a")
        self.assertIsNone(elements.pick_frame(frames, None, 400, 300))

    def test_a_cast_with_or_without_the_shadow_lines_up_with_the_frame(self):
        self.assertEqual(elements.cast_offset((0, 0, 640, 480), 702, 542), (31, 31))
        self.assertEqual(elements.cast_offset((0, 0, 640, 480), 640, 480), (0, 0))


class Missing(unittest.TestCase):
    def test_without_atspi_a_look_lists_nothing(self):
        kept = elements.Atspi
        elements.Atspi = None
        try:
            self.assertIsNone(elements.controls((400, 300), (400, 300), 1234, "Controls", (0, 0)))
        finally:
            elements.Atspi = kept


if __name__ == "__main__":
    unittest.main()
