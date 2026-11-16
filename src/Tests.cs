// Built and run by build.ps1 -Test, together with the rest of src. Every static method of
// Tests without parameters is one test.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using System.Windows.Automation;
using System.Windows.Forms;

namespace KnightSight
{
    static class Tests
    {
        static int Main()
        {
            Theme.Load();
            int passed = 0, failed = 0;
            foreach (var test in typeof(Tests).GetMethods(BindingFlags.NonPublic | BindingFlags.Static))
            {
                if (test.ReturnType != typeof(void) || test.GetParameters().Length > 0) continue;
                try
                {
                    test.Invoke(null, null);
                    passed++;
                }
                catch (TargetInvocationException e)
                {
                    failed++;
                    Console.WriteLine("FAIL " + test.Name + ": " + e.InnerException.Message);
                }
            }
            Console.WriteLine(passed + " passed, " + failed + " failed");
            return failed == 0 ? 0 : 1;
        }

        static void Same(object expected, object actual)
        {
            if (!Equals(expected, actual)) throw new Exception("expected " + expected + ", got " + actual);
        }

        static void True(bool condition, string what)
        {
            if (!condition) throw new Exception(what);
        }

        static Board BoardWith(params RectangleF[] marks)
        {
            var board = new Board();
            board.Toggle(true);
            foreach (var mark in marks) board.Add(new[] { mark }, NoteKind.Wish, "note at " + mark.Location, "Tester");
            return board;
        }

        static Dictionary<string, object> RoundOf(Board board, Size shot, float density)
        {
            using (var bmp = new Bitmap(shot.Width, shot.Height))
                return board.Seal(bmp, density, "Test window", new DateTime(2026, 11, 15, 13, 3, 12, DateTimeKind.Utc)).Fields;
        }

        static Dictionary<string, object> Field(Dictionary<string, object> round, int note)
        {
            return (Dictionary<string, object>)((IList)round["notes"])[note];
        }

        static Dictionary<string, object> Mark(Dictionary<string, object> note, int mark)
        {
            return (Dictionary<string, object>)((IList)note["marks"])[mark];
        }

        static Size PngSize(object base64)
        {
            using (var ms = new MemoryStream(Convert.FromBase64String((string)base64)))
            using (var image = Image.FromStream(ms))
                return image.Size;
        }

        static void NoteKeepsItsSpotWhenTheWindowMoves()
        {
            var spot = Spot.ToShare(new Point(150, 260), new Rectangle(100, 200, 800, 600), 1);
            Same(new PointF(50, 60), spot);
            var mark = new RectangleF(spot, new SizeF(30, 20));
            Same(new Rectangle(350, 460, 30, 20), Spot.ToScreen(mark, new Rectangle(300, 400, 800, 600), 1));
        }

        static void NoteKeepsItsOffsetWhenTheWindowIsResized()
        {
            var mark = new RectangleF(50, 60, 30, 20);
            Same(new Rectangle(150, 260, 30, 20), Spot.ToScreen(mark, new Rectangle(100, 200, 400, 300), 1));
            Same(new Rectangle(150, 260, 30, 20), Spot.ToScreen(mark, new Rectangle(100, 200, 1600, 900), 1));
        }

        static void NoteGrowsWithTheWindowOnADenserScreen()
        {
            var spot = Spot.ToShare(new Point(250, 260), new Rectangle(100, 200, 800, 600), 1.5f);
            Same(new PointF(100, 40), spot);
            var mark = new RectangleF(spot, new SizeF(20, 10));
            Same(new Rectangle(1200, 280, 40, 20), Spot.ToScreen(mark, new Rectangle(1000, 200, 1600, 1200), 2));
        }

        static void NoteOutsideTheShrunkShareIsNotShown()
        {
            True(Spot.Shows(new RectangleF(10, 10, 5, 5), new Rectangle(0, 0, 100, 100), 1), "a mark inside shows");
            True(!Spot.Shows(new RectangleF(150, 10, 5, 5), new Rectangle(0, 0, 100, 100), 1), "a mark right of the share is hidden");
            True(Spot.Shows(new RectangleF(90, 90, 40, 40), new Rectangle(0, 0, 100, 100), 1), "a mark reaching out of the share still shows");
        }

        static void CropAddsAMarginAndStaysInsideTheShot()
        {
            Same(new Rectangle(76, 76, 98, 68), Spot.Crop(new RectangleF(100, 100, 50, 20), new Size(800, 600), 1));
            Same(new Rectangle(0, 0, 54, 44), Spot.Crop(new RectangleF(0, 0, 30, 20), new Size(800, 600), 1));
            Same(new Rectangle(752, 556, 48, 44), Spot.Crop(new RectangleF(776, 580, 30, 30), new Size(800, 600), 1));
        }

        static void CropOfAPinIsABoxAroundIt()
        {
            Same(new Rectangle(280, 180, 240, 240), Spot.Crop(new RectangleF(400, 300, 0, 0), new Size(800, 600), 1));
            Same(new Rectangle(0, 0, 130, 130), Spot.Crop(new RectangleF(10, 10, 0, 0), new Size(800, 600), 1));
        }

        static void CropCountsTheMarginInShareUnits()
        {
            Same(new Rectangle(152, 152, 196, 136), Spot.Crop(new RectangleF(100, 100, 50, 20), new Size(1600, 1200), 2));
        }

        static void PinboardOpensOnlyWhileSharing()
        {
            var board = new Board();
            True(!board.Toggle(false), "stays closed while nothing is shared");
            True(board.Toggle(true), "opens while sharing");
            True(!board.Toggle(true), "a second toggle closes it");
        }

        static void ClosingThePinboardKeepsTheNotes()
        {
            var board = BoardWith(new RectangleF(1, 2, 3, 4));
            board.Toggle(true);
            True(!board.Open, "closed");
            Same(1, board.Notes.Count);
            board.Toggle(true);
            Same(1, board.Notes.Count);
        }

        static void ChoosingAnotherShareDropsTheUnsentNotes()
        {
            var board = BoardWith(new RectangleF(1, 2, 3, 4));
            board.Forget();
            Same(0, board.Notes.Count);
            True(!board.Open, "closed");
        }

        static void NumbersCountOnAcrossRounds()
        {
            var board = BoardWith(new RectangleF(1, 1, 5, 5), new RectangleF(2, 2, 5, 5));
            using (var bmp = new Bitmap(100, 100)) board.Send(board.Seal(bmp, 1, "t", DateTime.UtcNow));
            Same(0, board.Notes.Count);
            True(!board.Open, "sending closes the pinboard");
            board.Toggle(true);
            Same(3, board.Add(new[] { new RectangleF(3, 3, 0, 0) }, NoteKind.Bug, "third", "").Number);
        }

        static void NothingSentYetAnswersRoundZero()
        {
            var answer = new Board().Answer(false);
            Same(1, answer.Count);
            Same(0, answer["round"]);
        }

        static void SentRoundIsHandedOutOnceAsUnread()
        {
            var board = BoardWith(new RectangleF(10, 10, 20, 20));
            using (var bmp = new Bitmap(100, 100)) board.Send(board.Seal(bmp, 1, "t", DateTime.UtcNow));
            True(board.Answer(true).ContainsKey("notes"), "the first unread answer brings the notes");
            var again = board.Answer(true);
            Same(1, again.Count);
            Same(1, again["round"]);
            True(board.Answer(false).ContainsKey("notes"), "asking without unread brings the round again");
        }

        static void RoundCountsAsFetchedOnceHandedOut()
        {
            var board = BoardWith(new RectangleF(10, 10, 20, 20));
            using (var bmp = new Bitmap(100, 100)) board.Send(board.Seal(bmp, 1, "t", DateTime.UtcNow));
            True(!board.Fetched, "not fetched before the first answer");
            board.Answer(true);
            True(board.Fetched, "fetched after it");
        }

        static void RoundDescribesEachNoteInPictureCoordinates()
        {
            var board = BoardWith();
            board.Add(new[] { new RectangleF(100, 50, 40, 30) }, NoteKind.Bug, "Cut off", "Junker");
            board.Add(new[] { new RectangleF(300, 200, 0, 0) }, NoteKind.Question, "Why?", "Junker");
            var round = RoundOf(board, new Size(800, 600), 1);
            Same(1, round["round"]);
            Same("2026-11-15T13:03:12Z", round["sent"]);
            Same("Test window", round["title"]);
            Same(800, round["width"]);
            Same(600, round["height"]);
            var bug = Field(round, 0);
            Same(1, bug["number"]);
            Same("bug", bug["kind"]);
            Same("Cut off", bug["text"]);
            Same("Junker", bug["author"]);
            True(!bug.ContainsKey("x"), "the place belongs to the marks");
            var box = Mark(bug, 0);
            Same("1", box["label"]);
            Same(100, box["x"]);
            Same(50, box["y"]);
            Same(40, box["width"]);
            Same(30, box["height"]);
            True(!box.ContainsKey("pin"), "a box is no pin");
            var question = Field(round, 1);
            Same("question", question["kind"]);
            var pin = Mark(question, 0);
            Same("2", pin["label"]);
            Same(true, pin["pin"]);
            Same(300, pin["x"]);
            True(!pin.ContainsKey("width"), "a pin has no size");
        }

        static void RoundOfALargeShareScalesLikeLook()
        {
            var board = BoardWith(new RectangleF(1000, 500, 200, 100));
            var round = RoundOf(board, new Size(3136, 2000), 1);
            Same(1568, round["width"]);
            Same(1000, round["height"]);
            Same(new Size(1568, 1000), PngSize(round["image"]));
            var note = Mark(Field(round, 0), 0);
            Same(500, note["x"]);
            Same(250, note["y"]);
            Same(100, note["width"]);
            Same(new Size(248, 148), PngSize(note["image"]));
        }

        static void RoundOfAWindowOnADenseScreenCountsInItsPixels()
        {
            var board = BoardWith(new RectangleF(100, 50, 40, 30));
            var note = Mark(Field(RoundOf(board, new Size(1200, 900), 1.5f), 0), 0);
            Same(150, note["x"]);
            Same(75, note["y"]);
            Same(60, note["width"]);
        }

        static void RoundSurvivesTheJsonSerializer()
        {
            var board = BoardWith(new RectangleF(10, 10, 20, 20));
            var json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue }.Serialize(RoundOf(board, new Size(100, 100), 1));
            True(json.Contains("\"kind\":\"wish\""), json.Substring(0, Math.Min(200, json.Length)));
        }

        static void SavedPageShowsTheNotesEscaped()
        {
            var board = BoardWith();
            board.Add(new[] { new RectangleF(10, 10, 20, 20) }, NoteKind.Bug, "<b>Too</b> & wide", "Junker");
            string page;
            using (var bmp = new Bitmap(100, 100)) page = Board.Page(board.Seal(bmp, 1, "A <window>", DateTime.UtcNow));
            True(page.Contains("&lt;b&gt;Too&lt;/b&gt; &amp; wide"), "the note text is escaped");
            True(page.Contains("A &lt;window&gt;"), "the title is escaped");
            True(page.Contains("data:image/png;base64,"), "the pictures are inside the page");
            True(!page.Contains("<b>Too"), "no raw markup from the note");
        }

        static void SingleMarkIsLabelledWithItsNumber()
        {
            Same("3", Note.Label(3, 0, 1));
        }

        static void SeveralMarksAreLabelledWithLetters()
        {
            Same("3a", Note.Label(3, 0, 2));
            Same("3b", Note.Label(3, 1, 2));
            Same("12z", Note.Label(12, 25, 26));
        }

        static void NoteTakesUpToTwentySixMarks()
        {
            var marks = new List<RectangleF>();
            for (int i = 0; i < 25; i++) True(Note.AddMark(marks, new RectangleF(i, i, 0, 0)), "mark " + (i + 1) + " fits");
            True(Note.AddMark(marks, new RectangleF(50, 50, 10, 10)), "the twenty-sixth fits");
            True(!Note.AddMark(marks, new RectangleF(60, 60, 0, 0)), "a twenty-seventh does not");
            Same(26, marks.Count);
        }

        static void LastMarkOfANoteStays()
        {
            var marks = new List<RectangleF> { new RectangleF(1, 1, 0, 0) };
            True(!Note.RemoveMark(marks, 0), "the only mark stays");
            Same(1, marks.Count);
            marks.Add(new RectangleF(5, 5, 10, 10));
            True(Note.RemoveMark(marks, 0), "one of two goes");
            Same(new RectangleF(5, 5, 10, 10), marks[0]);
        }

        static void RoundGivesEachMarkItsOwnLabelAndCrop()
        {
            var board = BoardWith();
            board.Add(new[] { new RectangleF(100, 50, 40, 30), new RectangleF(300, 200, 0, 0) }, NoteKind.Bug, "Two spots", "Junker");
            var note = Field(RoundOf(board, new Size(800, 600), 1), 0);
            Same(2, ((IList)note["marks"]).Count);
            var box = Mark(note, 0);
            Same("1a", box["label"]);
            Same(40, box["width"]);
            Same(new Size(88, 78), PngSize(box["image"]));
            var pin = Mark(note, 1);
            Same("1b", pin["label"]);
            Same(true, pin["pin"]);
            Same(new Size(240, 240), PngSize(pin["image"]));
        }

        static void SavedPageShowsEveryCropWithItsLabel()
        {
            var board = BoardWith();
            board.Add(new[] { new RectangleF(10, 10, 20, 20), new RectangleF(60, 60, 0, 0) }, NoteKind.Wish, "Both", "");
            string page;
            using (var bmp = new Bitmap(100, 100)) page = Board.Page(board.Seal(bmp, 1, "t", DateTime.UtcNow));
            True(page.Contains(">1a<") && page.Contains(">1b<"), "both labels are on the page");
            Same(3, page.Split(new[] { "data:image/png;base64," }, StringSplitOptions.None).Length - 1);
        }

        static Element Found(string role, string name, int x, int y, int width, int height)
        {
            return new Element { Role = role, Name = name, Box = new Rectangle(x, y, width, height) };
        }

        static string RefusalOf(Action act)
        {
            try { act(); }
            catch (Refused e) { return e.Message; }
            throw new Exception("was not refused");
        }

        static void ControlTypesMapOntoTheClosedSetOfRoles()
        {
            Same("button", ControlTree.Role(ControlType.Button));
            Same("button", ControlTree.Role(ControlType.SplitButton));
            Same("link", ControlTree.Role(ControlType.Hyperlink));
            Same("edit", ControlTree.Role(ControlType.Edit));
            Same("checkbox", ControlTree.Role(ControlType.CheckBox));
            Same("radio", ControlTree.Role(ControlType.RadioButton));
            Same("combobox", ControlTree.Role(ControlType.ComboBox));
            Same("menuitem", ControlTree.Role(ControlType.MenuItem));
            Same("tab", ControlTree.Role(ControlType.TabItem));
            Same("listitem", ControlTree.Role(ControlType.ListItem));
            Same("treeitem", ControlTree.Role(ControlType.TreeItem));
            Same("slider", ControlTree.Role(ControlType.Slider));
            Same("text", ControlTree.Role(ControlType.Text));
        }

        static void ContainersAndPicturesHaveNoRole()
        {
            foreach (var type in new[] { ControlType.Pane, ControlType.Group, ControlType.Document, ControlType.Window, ControlType.Image, null })
                Same(null, ControlTree.Role(type));
        }

        static void HiddenEmptyAndDisabledNamelessControlsAreLeftOut()
        {
            var box = new Rectangle(10, 10, 50, 20);
            True(ControlTree.Pick(ControlType.Button, "Save", box, true, true, false) == null, "offscreen");
            True(ControlTree.Pick(ControlType.Button, "Save", new Rectangle(10, 10, 0, 20), false, true, false) == null, "zero width");
            True(ControlTree.Pick(ControlType.Button, "", box, false, false, false) == null, "disabled without a name");
            True(ControlTree.Pick(ControlType.Text, " ", box, false, true, false) == null, "text without a name");
            True(ControlTree.Pick(ControlType.Pane, "Main", box, false, true, false) == null, "a pane");
            Same("Save", ControlTree.Pick(ControlType.Button, "Save", box, false, false, false).Name);
            Same("", ControlTree.Pick(ControlType.Button, null, box, false, true, false).Name);
        }

        static void NamesAreTrimmedToOneShortLine()
        {
            var box = new Rectangle(0, 0, 5, 5);
            Same("Save as file", ControlTree.Pick(ControlType.Button, "  Save as\r\n  file ", box, false, true, false).Name);
            Same(80, ControlTree.Pick(ControlType.Text, new string('x', 200), box, false, true, false).Name.Length);
        }

        static void PasswordFieldShowsOnlyItsRole()
        {
            var field = ControlTree.Pick(ControlType.Edit, "hunter2", new Rectangle(0, 0, 100, 20), false, true, true);
            Same("edit", field.Role);
            Same("", field.Name);
        }

        static void ControlsComeInReadingOrderInPictureCoordinates()
        {
            var found = new List<Element>
            {
                Found("button", "OK", 500, 700, 100, 40),
                Found("edit", "Search", 120, 220, 400, 30),
                Found("text", "Status", 50, 760, 200, 20),
                Found("link", "Away", 1000, 220, 50, 20),
                Found("checkbox", "Wrap", 110, 220, 10, 10),
            };
            var listed = ControlTree.Arrange(found, new Rectangle(100, 200, 800, 600), 0.5);
            Same(4, listed.Count);
            Same("e1 Wrap {X=5,Y=10,Width=5,Height=5}", listed[0].Ref + " " + listed[0].Name + " " + listed[0].Box);
            Same("e2 Search {X=10,Y=10,Width=200,Height=15}", listed[1].Ref + " " + listed[1].Name + " " + listed[1].Box);
            Same("e3 OK {X=200,Y=250,Width=50,Height=20}", listed[2].Ref + " " + listed[2].Name + " " + listed[2].Box);
            Same("e4 Status {X=0,Y=280,Width=75,Height=10}", listed[3].Ref + " " + listed[3].Name + " " + listed[3].Box);
        }

        static void LookListsAtMostAHundredAndFiftyControls()
        {
            var found = new List<Element>();
            for (int i = 0; i < 200; i++) found.Add(Found("listitem", "Row " + i, 0, i * 10, 100, 10));
            var listed = ControlTree.Arrange(found, new Rectangle(0, 0, 100, 2000), 1);
            Same(150, listed.Count);
            Same("e150", listed[149].Ref);
            Same("Row 149", listed[149].Name);
        }

        static void ControlsSurviveTheJsonSerializer()
        {
            var listed = ControlTree.Arrange(new List<Element> { Found("button", "Add", 430, 40, 60, 30) }, new Rectangle(0, 0, 600, 400), 1);
            var json = new JavaScriptSerializer().Serialize(listed.ConvertAll(e => e.Fields()));
            Same("[{\"ref\":\"e1\",\"role\":\"button\",\"name\":\"Add\",\"x\":430,\"y\":40,\"width\":60,\"height\":30}]", json);
        }

        static void RefStandsForTheCentreOfItsControl()
        {
            var last = ControlTree.Arrange(new List<Element> { Found("button", "Add", 430, 40, 60, 31) }, new Rectangle(0, 0, 600, 400), 1);
            var args = new Dictionary<string, object> { { "cmd", "click" }, { "ref", "e1" } };
            Panel.Aim(args, last, "Click");
            Same(460.0, args["x"]);
            Same(55.5, args["y"]);
        }

        static void UnknownRefIsRefused()
        {
            var last = ControlTree.Arrange(new List<Element> { Found("button", "Add", 0, 0, 10, 10) }, new Rectangle(0, 0, 600, 400), 1);
            var args = new Dictionary<string, object> { { "ref", "e12" } };
            Same("There is no element e12 from the last look. Take a new look.", RefusalOf(() => Panel.Aim(args, last, "Click")));
            True(!args.ContainsKey("x"), "no point was made up");
        }

        static void RefBeforeAnyLookIsRefused()
        {
            var args = new Dictionary<string, object> { { "ref", "e1" } };
            Same("There is no element e1 from the last look. Take a new look.", RefusalOf(() => Panel.Aim(args, null, "Scroll")));
        }

        static void PointWithoutRefPassesAsItIs()
        {
            var args = new Dictionary<string, object> { { "x", 12 }, { "y", 34 } };
            Panel.Aim(args, null, "Click");
            Same(12, args["x"]);
            Same(34, args["y"]);
        }

        static void ClickOrScrollWithoutPointOrRefIsRefused()
        {
            var click = new Dictionary<string, object>();
            var scroll = new Dictionary<string, object> { { "x", 5 }, { "amount", 3 } };
            Same("Click needs x and y or a ref from look.", RefusalOf(() => Panel.Aim(click, null, "Click")));
            Same("Scroll needs x and y or a ref from look.", RefusalOf(() => Panel.Aim(scroll, null, "Scroll")));
        }

        static void ShareKnowsItsWindowByProcessAndStart()
        {
            var share = new Share { Pid = 42, Started = 131000000000000000 };
            True(share.Owns(42, 131000000000000000), "same process, same start");
            True(!share.Owns(42, 131000000000000001), "a new process under the old id");
            True(!share.Owns(43, 131000000000000000), "another process");
        }

        static void ChosenWindowRemembersItsProcess()
        {
            using (var form = new Form())
            {
                var share = Share.Of(form.Handle);
                using (var me = Process.GetCurrentProcess())
                {
                    Same((uint)me.Id, share.Pid);
                    Same(me.StartTime.ToFileTimeUtc(), share.Started);
                }
                True(!share.Gone, "the window is still there");
                form.Dispose();
                True(share.Gone, "the window has closed");
            }
        }

        static void ScreenTitleNamesItsNumberAndSize()
        {
            bool german = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "de";
            Same(german ? "Bildschirm 2 (2560 x 1440)" : "Screen 2 (2560 x 1440)", Say.ScreenTitle(2, new Size(2560, 1440)));
        }

        static void ScreenUnderThePointerIsTheOneChosen()
        {
            var screens = new[] { new Rectangle(0, 0, 1920, 1080), new Rectangle(-2560, -200, 2560, 1440) };
            Same(0, ScreenPicker.Under(screens, new Point(1919, 1079)));
            Same(1, ScreenPicker.Under(screens, new Point(-1, 0)));
            Same(-1, ScreenPicker.Under(screens, new Point(1920, 500)));
        }

        static void PointOnThePanelIsRefused()
        {
            var own = new[] { new Rectangle(660, 418, 600, 244), new Rectangle(1300, 100, 320, 480) };
            Same("That point lies on KnightSight itself.", RefusalOf(() => Panel.Clear(new Point(660, 418), own)));
            Same("That point lies on KnightSight itself.", RefusalOf(() => Panel.Clear(new Point(1400, 300), own)));
        }

        static void PointBesideThePanelPasses()
        {
            var own = new[] { new Rectangle(660, 418, 600, 244) };
            Panel.Clear(new Point(1260, 500), own);
            Panel.Clear(new Point(700, 417), own);
            Panel.Clear(new Point(700, 500), new Rectangle[0]);
        }

        static void InputThatWentOutCountsAsSent()
        {
            using (var form = new Form())
            {
                Input.Sent = false;
                Input.PostText(form.Handle, "a");
                True(Input.Sent, "a posted character counts");
            }
        }

        static void InputThatNeverLeftCountsAsUnsent()
        {
            var form = new Form();
            var gone = form.Handle;
            form.Dispose();
            Input.Sent = false;
            RefusalOf(() => Input.PostText(gone, "a"));
            True(!Input.Sent, "nothing was posted");
        }
    }
}
