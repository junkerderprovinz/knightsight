import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LANGUAGE"] = "en"

from knightsight import notes  # noqa: E402
from knightsight.notes import Board, Fit, Mark, Note, Rounds  # noqa: E402
from knightsight.protocol import Rect  # noqa: E402


def pin(number, x, y, kind="wish"):
    return Note(number, kind, "text", "Junker", [Mark(x, y)])


def box(number, x, y, w, h, kind="bug"):
    return Note(number, kind, "text", "Junker", [Mark(x, y, w, h)])


def spots(number, *marks, kind="bug"):
    return Note(number, kind, "text", "Junker", list(marks))


class Numbers(unittest.TestCase):
    def test_numbers_count_on_across_rounds(self):
        board = Board()
        board.add("bug", "a", "", [Mark(1, 2, 3, 4)])
        second = board.add("wish", "b", "", [Mark(5, 6)])
        board.clear()
        self.assertEqual(board.add("question", "c", "", [Mark(0, 0)]).number, 3)
        self.assertEqual(second.number, 2)
        self.assertTrue(second.marks[0].pin)

    def test_a_deleted_number_is_not_given_again(self):
        board = Board()
        first = board.add("bug", "a", "", [Mark(1, 2, 3, 4)])
        board.remove(first)
        self.assertEqual(board.add("bug", "b", "", [Mark(1, 2, 3, 4)]).number, 2)
        self.assertEqual([n.number for n in board.notes], [2])


class Labels(unittest.TestCase):
    def test_a_single_mark_wears_the_number(self):
        self.assertEqual(pin(3, 0, 0).label(0), "3")

    def test_several_marks_add_a_letter_in_the_order_they_were_made(self):
        note = spots(12, Mark(0, 0), Mark(5, 5, 10, 10), Mark(9, 9))
        self.assertEqual([note.label(i) for i in range(3)], ["12a", "12b", "12c"])

    def test_the_list_counts_the_spots_of_a_note_with_several(self):
        self.assertEqual(notes.kind_line(box(1, 0, 0, 5, 5)), "Bug")
        self.assertEqual(notes.kind_line(spots(1, Mark(0, 0), Mark(9, 9))), "Bug, 2 spots")


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
        self.assertEqual(notes.mark(fit, (100, 100), (103, 104), 800, 600), Mark(100, 100))

    def test_a_drag_makes_a_box_whichever_way_it_goes(self):
        fit = Fit.inside(1600, 1200, 800, 600)
        self.assertEqual(notes.mark(fit, (300, 200), (100, 150), 1600, 1200), Mark(200, 300, 400, 100))

    def test_a_click_beside_the_picture_marks_nothing(self):
        fit = Fit.inside(800, 200, 800, 600)
        self.assertIsNone(notes.mark(fit, (400, 100), (401, 101), 800, 200))
        self.assertEqual(notes.mark(fit, (400, 300), (401, 301), 800, 200), Mark(400, 100))

    def test_a_drag_along_the_band_beside_the_picture_marks_nothing(self):
        fit = Fit.inside(800, 200, 800, 600)
        self.assertIsNone(notes.mark(fit, (100, 50), (500, 120), 800, 200))
        self.assertEqual(notes.mark(fit, (100, 50), (500, 250), 800, 200), Mark(100, 0, 400, 50))

    def test_hits_find_the_newest_mark_under_the_pointer(self):
        fit = Fit(1)
        under, over = box(1, 100, 100, 200, 100), box(2, 150, 150, 50, 50)
        found = [under, over, pin(3, 600, 400)]
        self.assertEqual(notes.hit(found, fit, 160, 160), (over, over.marks[0]))
        self.assertEqual(notes.hit(found, fit, 110, 110), (under, under.marks[0]))
        self.assertIs(notes.hit(found, fit, 608, 405)[0], found[2])
        self.assertIsNone(notes.hit(found, fit, 500, 500))

    def test_a_hit_names_the_mark_of_a_note_with_several(self):
        note = spots(1, Mark(100, 100, 50, 50), Mark(400, 400), Mark(120, 120, 10, 10))
        self.assertIs(notes.hit([note], Fit(1), 402, 401)[1], note.marks[1])
        self.assertIs(notes.hit([note], Fit(1), 125, 125)[1], note.marks[2])

    def test_a_box_badge_is_hit_outside_the_box(self):
        self.assertIsNotNone(notes.hit([box(1, 100, 100, 50, 50)], Fit(1), 92, 92))


class Gestures(unittest.TestCase):
    SIZE = (800, 600)

    def press(self, shown, editing, start, end, shift=False):
        return notes.gesture(shown, editing, Fit(1), start, end, *self.SIZE, shift)

    def test_a_drag_on_the_share_starts_a_new_note(self):
        self.assertEqual(self.press([], None, (10, 10), (60, 40)), ("new", Mark(10, 10, 50, 30)))

    def test_a_click_on_a_mark_opens_its_note(self):
        other = pin(1, 100, 100)
        self.assertEqual(self.press([other], None, (101, 100), (101, 100)), ("edit", other))

    def test_a_click_on_the_open_notes_own_mark_keeps_it_open(self):
        open_note = pin(1, 100, 100)
        self.assertIsNone(self.press([open_note], open_note, (100, 100), (100, 100)))

    def test_shift_and_a_drag_add_a_box_to_the_open_note(self):
        open_note = pin(1, 100, 100)
        self.assertEqual(self.press([open_note], open_note, (300, 300), (340, 320), True),
                         ("add", Mark(300, 300, 40, 20)))

    def test_shift_and_a_click_add_a_pin_even_on_another_notes_mark(self):
        open_note, other = pin(1, 100, 100), pin(2, 500, 500)
        self.assertEqual(self.press([other, open_note], open_note, (500, 500), (500, 500), True),
                         ("add", Mark(500, 500)))

    def test_shift_and_a_click_on_an_own_mark_remove_it(self):
        open_note = spots(1, Mark(100, 100), Mark(300, 300, 40, 40))
        self.assertEqual(self.press([open_note], open_note, (320, 320), (320, 320), True),
                         ("drop", open_note.marks[1]))

    def test_the_last_mark_of_a_note_stays(self):
        open_note = pin(1, 100, 100)
        self.assertIsNone(self.press([open_note], open_note, (100, 100), (100, 100), True))

    def test_a_note_takes_twenty_six_marks_at_most(self):
        open_note = spots(1, *[Mark(10 * i, 10) for i in range(notes.MAX_MARKS)])
        self.assertIsNone(self.press([open_note], open_note, (500, 500), (500, 500), True))

    def test_shift_without_an_open_note_works_as_without(self):
        self.assertEqual(self.press([], None, (10, 10), (11, 10), True), ("new", Mark(10, 10)))


class Beside(unittest.TestCase):
    SCREEN = (1920, 1080)

    def test_the_notes_go_right_of_the_share_where_there_is_room(self):
        self.assertEqual(notes.beside(Rect(100, 200, 800, 600), (372, 600), self.SCREEN, 16), (916, 200))

    def test_they_go_left_when_the_share_reaches_the_right_edge(self):
        self.assertEqual(notes.beside(Rect(1000, 200, 900, 600), (372, 600), self.SCREEN, 16), (612, 200))

    def test_they_lie_over_a_share_that_fills_the_screen(self):
        self.assertEqual(notes.beside(Rect(0, 0, 1920, 1080), (372, 600), self.SCREEN, 16), (1532, 0))

    def test_a_window_over_part_of_a_region_overlaps_it(self):
        self.assertTrue(notes.overlaps(Rect(700, 100, 372, 600), Rect(100, 50, 800, 600)))

    def test_a_window_beside_or_touching_a_region_does_not(self):
        self.assertFalse(notes.overlaps(Rect(916, 50, 372, 600), Rect(100, 50, 800, 600)))
        self.assertFalse(notes.overlaps(Rect(900, 50, 372, 600), Rect(100, 50, 800, 600)))
        self.assertFalse(notes.overlaps(Rect(100, 650, 372, 600), Rect(100, 50, 800, 600)))

    def test_they_stay_on_the_screen_beside_a_low_share(self):
        self.assertEqual(notes.beside(Rect(100, 900, 400, 100), (372, 600), self.SCREEN, 16), (516, 480))


class Crops(unittest.TestCase):
    def test_a_box_gets_a_margin(self):
        self.assertEqual(notes.crop_box(Mark(100, 80, 160, 40), 1000, 800), (76, 56, 208, 88))

    def test_the_margin_stops_at_the_share(self):
        self.assertEqual(notes.crop_box(Mark(10, 5, 100, 50), 120, 60), (0, 0, 120, 60))

    def test_a_pin_gets_a_square_around_it(self):
        self.assertEqual(notes.crop_box(Mark(400, 300), 1000, 800), (280, 180, 240, 240))
        self.assertEqual(notes.crop_box(Mark(50, 790), 1000, 800), (0, 670, 170, 130))

    def test_a_spot_off_a_shrunk_share_has_no_crop(self):
        self.assertIsNone(notes.crop_box(Mark(900, 700, 40, 40), 600, 400))


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
            {"number": 3, "kind": "bug", "text": "text", "author": "Junker",
             "marks": [{"label": "3", "x": 100, "y": 50, "width": 200, "height": 30, "image": "CROP3"}]},
            {"number": 4, "kind": "question", "text": "text", "author": "Junker",
             "marks": [{"label": "4", "x": 500, "y": 250, "pin": True, "image": "CROP4"}]},
        ])
        self.assertEqual(crops, [(3, (176, 76, 448, 108)), (4, (881, 380, 240, 240))])

    def test_every_mark_of_a_note_gets_its_label_and_crop(self):
        crops = []
        note = spots(3, Mark(120, 80, 160, 40), Mark(400, 300))
        fields = notes.assemble("Editor", 1000, 800, [note], "FRAME",
                                lambda n, b: crops.append(b) or f"CROP{len(crops)}", "")
        self.assertEqual(fields["notes"], [
            {"number": 3, "kind": "bug", "text": "text", "author": "Junker", "marks": [
                {"label": "3a", "x": 120, "y": 80, "width": 160, "height": 40, "image": "CROP1"},
                {"label": "3b", "x": 400, "y": 300, "pin": True, "image": "CROP2"}]},
        ])
        self.assertEqual(crops, [(96, 56, 208, 88), (280, 180, 240, 240)])

    def test_a_mark_off_the_share_comes_without_a_crop(self):
        note = spots(1, Mark(10, 10, 20, 20), Mark(500, 500, 10, 10))
        fields = notes.assemble("Editor", 400, 300, [note], "", lambda *_: "CROP", "")
        self.assertEqual(fields["notes"][0]["marks"][0]["image"], "CROP")
        self.assertNotIn("image", fields["notes"][0]["marks"][1])

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
        shown = [box(1, 10, 10, 50, 50), spots(2, Mark(300, 300), Mark(500, 100, 40, 40), kind="question")]
        return notes.assemble("<Editor>", 800, 600, shown, "FRAME", lambda note, b: f"CROP{note.number}x{b[0]}",
                              "2026-11-15T13:03:12Z")

    def test_the_page_holds_its_pictures(self):
        page = notes.page(self.fields(), 3)
        for data in ("FRAME", "CROP1x0", "CROP2x180", "CROP2x476"):
            self.assertIn(f"data:image/png;base64,{data}", page)
        self.assertIn("Round 3", page)
        self.assertIn("2026-11-15 13:03:12 UTC", page)
        self.assertIn("from Junker", page)
        self.assertIn("#1d99f3", page)

    def test_every_crop_is_labelled(self):
        page = notes.page(self.fields(), 1)
        for label in (">2a<", ">2b<"):
            self.assertIn(label, page)

    def test_text_from_the_person_is_escaped(self):
        fields = self.fields()
        fields["notes"][0]["text"] = "<script>alert(1)</script>"
        page = notes.page(fields, 1)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Pinboard notes on &lt;Editor&gt;", page)


if __name__ == "__main__":
    unittest.main()
