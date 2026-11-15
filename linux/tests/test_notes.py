import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LANGUAGE"] = "en"

from knightsight import notes  # noqa: E402
from knightsight.notes import Board, Fit, Note, Rounds  # noqa: E402


def pin(number, x, y, kind="wish"):
    return Note(number, kind, "text", "Junker", x, y)


def box(number, x, y, w, h, kind="bug"):
    return Note(number, kind, "text", "Junker", x, y, w, h)


class Numbers(unittest.TestCase):
    def test_numbers_count_on_across_rounds(self):
        board = Board()
        board.add("bug", "a", "", (1, 2, 3, 4))
        second = board.add("wish", "b", "", (5, 6, 0, 0))
        board.clear()
        self.assertEqual(board.add("question", "c", "", (0, 0, 0, 0)).number, 3)
        self.assertEqual(second.number, 2)
        self.assertTrue(second.pin)

    def test_a_deleted_number_is_not_given_again(self):
        board = Board()
        first = board.add("bug", "a", "", (1, 2, 3, 4))
        board.remove(first)
        self.assertEqual(board.add("bug", "b", "", (1, 2, 3, 4)).number, 2)
        self.assertEqual([n.number for n in board.notes], [2])


class Toggling(unittest.TestCase):
    def test_a_second_toggle_right_after_the_first_is_ignored(self):
        now = [10.0]
        gate = notes.Gate(0.4, lambda: now[0])
        self.assertTrue(gate.open())
        now[0] = 10.3
        self.assertFalse(gate.open())
        now[0] = 10.5
        self.assertTrue(gate.open())


class Placing(unittest.TestCase):
    def test_a_picture_fits_centred_into_a_wider_view(self):
        fit = Fit.inside(800, 600, 1000, 600)
        self.assertEqual((fit.k, fit.x, fit.y), (1, 100, 0))
        self.assertEqual(fit.to_share(150, 30, 800, 600), (50, 30))
        self.assertEqual(fit.to_view(50, 30), (150, 30))

    def test_a_large_share_maps_back_from_a_smaller_view(self):
        fit = Fit.inside(2000, 1000, 1000, 500)
        self.assertEqual(fit.to_share(500, 250, 2000, 1000), (1000, 500))

    def test_points_beside_the_picture_land_on_its_edge(self):
        fit = Fit.inside(800, 600, 1000, 600)
        self.assertEqual(fit.to_share(20, -5, 800, 600), (0, 0))
        self.assertEqual(fit.to_share(990, 700, 800, 600), (800, 600))

    def test_a_short_move_sets_a_pin(self):
        fit = Fit.inside(800, 600, 800, 600)
        self.assertEqual(notes.mark(fit, (100, 100), (103, 104), 800, 600), (100, 100, 0, 0))

    def test_a_drag_makes_a_box_whichever_way_it_goes(self):
        fit = Fit.inside(1600, 1200, 800, 600)
        self.assertEqual(notes.mark(fit, (300, 200), (100, 150), 1600, 1200), (200, 300, 400, 100))

    def test_a_click_beside_the_picture_marks_nothing(self):
        fit = Fit.inside(800, 200, 800, 600)
        self.assertIsNone(notes.mark(fit, (400, 100), (401, 101), 800, 200))
        self.assertEqual(notes.mark(fit, (400, 300), (401, 301), 800, 200), (400, 100, 0, 0))

    def test_a_drag_along_the_band_beside_the_picture_marks_nothing(self):
        fit = Fit.inside(800, 200, 800, 600)
        self.assertIsNone(notes.mark(fit, (100, 50), (500, 120), 800, 200))
        self.assertEqual(notes.mark(fit, (100, 50), (500, 250), 800, 200), (100, 0, 400, 50))

    def test_hits_find_the_newest_mark_under_the_pointer(self):
        fit = Fit(1)
        under, over = box(1, 100, 100, 200, 100), box(2, 150, 150, 50, 50)
        found = [under, over, pin(3, 600, 400)]
        self.assertIs(notes.hit(found, fit, 160, 160), over)
        self.assertIs(notes.hit(found, fit, 110, 110), under)
        self.assertIs(notes.hit(found, fit, 608, 405), found[2])
        self.assertIsNone(notes.hit(found, fit, 500, 500))

    def test_a_box_badge_is_hit_outside_the_box(self):
        self.assertIsNotNone(notes.hit([box(1, 100, 100, 50, 50)], Fit(1), 92, 92))


class Crops(unittest.TestCase):
    def test_a_box_gets_a_margin(self):
        self.assertEqual(notes.crop_box(box(1, 100, 80, 160, 40), 1000, 800), (76, 56, 208, 88))

    def test_the_margin_stops_at_the_share(self):
        self.assertEqual(notes.crop_box(box(1, 10, 5, 100, 50), 120, 60), (0, 0, 120, 60))

    def test_a_pin_gets_a_square_around_it(self):
        self.assertEqual(notes.crop_box(pin(1, 400, 300), 1000, 800), (280, 180, 240, 240))
        self.assertEqual(notes.crop_box(pin(1, 50, 790), 1000, 800), (0, 670, 170, 130))

    def test_a_spot_off_a_shrunk_share_has_no_crop(self):
        self.assertIsNone(notes.crop_box(box(1, 900, 700, 40, 40), 600, 400))


class Sending(unittest.TestCase):
    def test_places_are_scaled_into_the_picture(self):
        crops = []
        fields = notes.assemble("Editor", 3136, 1000, [box(3, 200, 100, 400, 60), pin(4, 1001, 500, "question")],
                                "FRAME", lambda note, b: crops.append((note.number, b)) or f"CROP{note.number}",
                                "2026-11-15T13:03:12Z")
        self.assertEqual(fields["width"], 1568)
        self.assertEqual(fields["height"], 500)
        self.assertEqual(fields["image"], "FRAME")
        self.assertEqual(fields["notes"], [
            {"number": 3, "kind": "bug", "text": "text", "author": "Junker", "x": 100, "y": 50,
             "width": 200, "height": 30, "image": "CROP3"},
            {"number": 4, "kind": "question", "text": "text", "author": "Junker", "x": 500, "y": 250,
             "pin": True, "image": "CROP4"},
        ])
        self.assertEqual(crops, [(3, (176, 76, 448, 108)), (4, (881, 380, 240, 240))])

    def test_a_note_off_the_share_comes_without_a_crop(self):
        fields = notes.assemble("Editor", 400, 300, [box(1, 500, 500, 10, 10)], "", lambda *_: "CROP", "")
        self.assertNotIn("image", fields["notes"][0])

    def test_nothing_sent_answers_round_zero(self):
        self.assertEqual(Rounds().answer(False), {"ok": True, "round": 0})
        self.assertEqual(Rounds().answer(True), {"ok": True, "round": 0})

    def test_only_the_latest_round_is_kept(self):
        rounds = Rounds()
        rounds.send({"title": "first"})
        rounds.send({"title": "second"})
        self.assertEqual(rounds.answer(False), {"ok": True, "round": 2, "title": "second"})

    def test_a_round_counts_as_read_once_handed_out(self):
        rounds = Rounds()
        rounds.send({"title": "first"})
        self.assertFalse(rounds.read)
        self.assertEqual(rounds.answer(True)["title"], "first")
        self.assertTrue(rounds.read)
        self.assertEqual(rounds.answer(True), {"ok": True, "round": 1})
        rounds.send({"title": "second"})
        self.assertEqual(rounds.answer(True)["title"], "second")


class Author(unittest.TestCase):
    def test_the_name_is_remembered(self):
        with tempfile.TemporaryDirectory() as folder:
            config = os.path.join(folder, "knightsight")
            self.assertEqual(notes.load_author(config), "")
            notes.save_author(config, "Junker")
            self.assertEqual(notes.load_author(config), "Junker")

    def test_a_broken_file_gives_no_name(self):
        with tempfile.TemporaryDirectory() as folder:
            for content in ("{not json", "[1, 2]", '{"author": 3}'):
                with open(os.path.join(folder, "pinboard.json"), "w") as f:
                    f.write(content)
                self.assertEqual(notes.load_author(folder), "")


class Page(unittest.TestCase):
    def fields(self):
        return notes.assemble("<Editor>", 800, 600, [box(1, 10, 10, 50, 50), pin(2, 300, 300, "question")],
                              "FRAME", lambda note, b: f"CROP{note.number}", "2026-11-15T13:03:12Z")

    def test_the_page_holds_its_pictures(self):
        page = notes.page(self.fields(), 3)
        for data in ("FRAME", "CROP1", "CROP2"):
            self.assertIn(f"data:image/png;base64,{data}", page)
        self.assertIn("Round 3", page)
        self.assertIn("2026-11-15 13:03:12 UTC", page)
        self.assertIn("from Junker", page)
        self.assertIn("#1d99f3", page)

    def test_text_from_the_person_is_escaped(self):
        fields = self.fields()
        fields["notes"][0]["text"] = "<script>alert(1)</script>"
        page = notes.page(fields, 1)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Pinboard notes on &lt;Editor&gt;", page)


if __name__ == "__main__":
    unittest.main()
