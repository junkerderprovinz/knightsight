"""Runs the panel on an X server with openbox, picks a window and a region through the panel
itself, and drives the share through the real MCP server.

Needs DISPLAY, a session bus, openbox, xdotool, Tk, AT-SPI and node: tests/smoke-x11.sh sets them up.
"""

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import HERE, LINUX, Mcp, image_of, listening, pixbuf, pixel, run, spawn, stop_all, text_of, wait_for

import gi  # noqa: E402

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib  # noqa: E402

from knightsight import picture, protocol, theme, xlib  # noqa: E402

NOTHING = protocol.NOTHING_SHARED


def window(name):
    def find():
        try:
            return run("xdotool", "search", "--onlyvisible", "--name", f"^{name}$").split()[0]
        except subprocess.CalledProcessError:
            return None
    return wait_for(find, f"the window {name}")


def origin(wid):
    shell = dict(line.split("=") for line in run("xdotool", "getwindowgeometry", "--shell", wid).splitlines())
    return int(shell["X"]), int(shell["Y"])


def press(x, y):
    """A slow click, so the panel's 15 ms poll of the mouse sees the button go down and up."""
    run("xdotool", "mousemove", str(x), str(y))
    time.sleep(0.2)
    run("xdotool", "mousedown", "1")
    time.sleep(0.15)
    run("xdotool", "mouseup", "1")
    time.sleep(0.4)


def drag(x0, y0, x1, y1):
    run("xdotool", "mousemove", str(x0), str(y0))
    time.sleep(0.2)
    run("xdotool", "mousedown", "1")
    for i in range(1, 11):
        run("xdotool", "mousemove", str(x0 + (x1 - x0) * i // 10), str(y0 + (y1 - y0) * i // 10))
        time.sleep(0.03)
    run("xdotool", "mouseup", "1")
    time.sleep(0.5)


def screen_pixel(x, y):
    d = xlib.Display()
    try:
        data, _, _ = d.image(d.root, x, y, 1, 1)
        return data[2], data[1], data[0]
    finally:
        d.close()


def screenshot(name):
    """Keeps the screen in the folder SMOKE_OUT names, for a look after a failed run."""
    folder = os.environ.get("SMOKE_OUT")
    if not folder:
        return
    d = xlib.Display()
    try:
        data, stride, _ = d.image(d.root, 0, 0, 1280, 800)
    finally:
        d.close()
    picture.surface(data, stride, 1280, 800, False).write_to_png(os.path.join(folder, name))


def top(d, w):
    """The child of the root that holds w, the window manager's frame around it."""
    while True:
        parent = d.tree(w)[0]
        if parent in (0, d.root):
            return w
        w = parent


def cursor_stacking(target, other):
    """Whether the assistant's arrow shows right above the target, with only KnightSight's
    own marks between them, and below the other window."""
    d = xlib.Display()
    try:
        order = d.tree(d.root)[1]
        cursor = next((w for w in order if d.prop(w, "WM_NAME") == b"KnightSight cursor"), None)
        if cursor is None or d.attributes(cursor).map_state != xlib.IsViewable:
            return False
        low, high = order.index(top(d, int(target))), order.index(cursor)
        between = order[low + 1:high]
        return low < high < order.index(top(d, int(other))) and all(d.attributes(w).override_redirect for w in between)
    finally:
        d.close()


def dump_tree(name):
    """Keeps every application's accessibility tree beside the screenshots."""
    folder = os.environ.get("SMOKE_OUT")
    if not folder:
        return
    Atspi.init()

    def lines(a, depth):
        try:
            r = a.get_extents(Atspi.CoordType.WINDOW)
            states = sorted(s.value_nick for s in a.get_state_set().get_states())
            yield f"{'  ' * depth}{a.get_role().value_nick} {a.get_name()!r} {states} {(r.x, r.y, r.width, r.height)}"
        except GLib.Error as e:
            yield f"{'  ' * depth}{a.get_role_name()} ({e.message})"
        for i in range(a.get_child_count()):
            child = a.get_child_at_index(i)
            if child is not None:
                yield from lines(child, depth + 1)

    with open(os.path.join(folder, name), "w") as f:
        f.write("\n".join(lines(Atspi.get_desktop(0), 0)) + "\n")


class SmokeX11(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = tempfile.NamedTemporaryFile("r", suffix=".log", delete=False)
        spawn("openbox")
        time.sleep(1)
        spawn(sys.executable, os.path.join(HERE, "target.py"), cls.log.name, "Target", "#ff0000", "+600+100")
        window("Target")
        env = dict(os.environ, LANGUAGE="en", GDK_BACKEND="x11", GSK_RENDERER="cairo", NO_AT_BRIDGE="1",
                   GTK_A11Y="none", PYTHONPATH=LINUX, PYTHONFAULTHANDLER="1")
        cls.panel = spawn(sys.executable, "-m", "knightsight", env=env)
        try:
            wait_for(lambda: listening() or cls.panel.poll() is not None, "the port", 60)
        except AssertionError:
            # PYTHONFAULTHANDLER makes the stuck panel print where each thread is.
            cls.panel.send_signal(signal.SIGABRT)
            cls.panel.wait()
            raise
        if cls.panel.poll() is not None:
            raise AssertionError(f"the panel exited with {cls.panel.returncode}")
        cls.panel_id = window("KnightSight")
        time.sleep(1)
        cls.mcp = Mcp()

    @classmethod
    def tearDownClass(cls):
        stop_all()
        cls.log.close()
        os.unlink(cls.log.name)

    def events(self):
        self.log.seek(0)
        return self.log.read().splitlines()

    def wait_event(self, line):
        wait_for(lambda: line in self.events(), repr(line), 20)

    def panel_point(self, x, y):
        px, py = origin(self.panel_id)
        return px + x, py + y

    def choose_window(self, title):
        """Clicks Choose window and then the window, again if a slow runner missed it, until
        the grey frame shows up beside the window."""
        tx, ty = origin(window(title))

        def framed():
            return all(abs(c - n) <= 6 for c, n in zip(screen_pixel(tx - 2, ty + 150), theme.NEUTRAL))

        for _ in range(3):
            press(*self.panel_point(379, 176))
            press(tx + 200, ty + 150)
            try:
                return wait_for(framed, "the grey frame", 5)
            except AssertionError:
                pass
        screenshot(f"{title}-not-chosen.png")
        geometry = run("xdotool", "getwindowgeometry", window(title))
        raise AssertionError(f"{title} could not be chosen, beside it is {screen_pixel(tx - 2, ty + 150)}, {geometry}")

    def start_sharing(self):
        for _ in range(3):
            press(*self.panel_point(571, 234))
            try:
                return wait_for(lambda: NOTHING not in text_of(self.mcp.tool("look")), "the share to start", 5)
            except AssertionError:
                pass
        raise AssertionError("sharing did not start")

    def test_a_control_from_look_is_clicked_by_its_ref(self):
        env = dict(os.environ, GDK_BACKEND="x11", GSK_RENDERER="cairo")
        spawn(sys.executable, os.path.join(HERE, "controls.py"), self.log.name, "Controls", env=env)
        # Openbox puts the panel below the Target, so the top left corner stays free.
        run("xdotool", "windowmove", window("Controls"), "20", "20")
        time.sleep(1)
        self.choose_window("Controls")
        self.start_sharing()

        seen = [""]

        def button():
            seen[0] = text_of(self.mcp.tool("look"))
            found = re.search(r'^(e\d+) button "Press me" at ', seen[0], re.M)
            return found and found.group(1)

        try:
            ref = wait_for(button, "the button among the controls of a look", 15)
        finally:
            print("The look listed:", *re.findall(r"^e\d+ .*$", seen[0], re.M), sep="\n  ", flush=True)
            dump_tree("accessible.txt")
        self.assertIn("Clicked", text_of(self.mcp.tool("click", ref=ref)))
        self.wait_event("Controls pressed")
        self.assertIn("no element e999", text_of(self.mcp.tool("click", ref="e999")))

        run("xdotool", "key", "ctrl+alt+shift+x")
        wait_for(lambda: NOTHING in text_of(self.mcp.tool("look")), "the hotkey to end the share", 5)

    def test_screen_share(self):
        press(*self.panel_point(621, 176))
        time.sleep(2)
        screenshot("screen-picker.png")
        press(640, 300)
        self.start_sharing()
        shot = self.mcp.tool("look")
        self.assertIn("Screen 1 (1280 x 800), 1280 x 800", text_of(shot))
        picture = pixbuf(image_of(shot))
        self.assertEqual((picture.get_width(), picture.get_height()), (1280, 800))

        run("xdotool", "windowactivate", "--sync", self.panel_id)
        x, y = self.panel_point(100, 100)
        self.assertIn("lies on KnightSight itself", text_of(self.mcp.tool("click", x=x, y=y)))

        run("xdotool", "key", "ctrl+alt+shift+x")
        wait_for(lambda: NOTHING in text_of(self.mcp.tool("look")), "the hotkey to end the share", 5)

    def test_window_share(self):
        self.assertIn(NOTHING, text_of(self.mcp.tool("look")))

        self.choose_window("Target")
        self.assertIn(NOTHING, text_of(self.mcp.tool("look")), "a chosen window is not shared yet")
        self.start_sharing()

        shot = self.mcp.tool("look")
        self.assertNotIn("isError", shot, text_of(shot))
        self.assertIn("Target, 400 x 300", text_of(shot))
        self.assertEqual(pixel(image_of(shot), 200, 150), (255, 0, 0))

        tx, ty = origin(window("Target"))
        r, g, b = screen_pixel(tx - 2, ty + 150)
        self.assertTrue(r > 200 and g > 100 and b < 120, f"the frame left of the share is {(r, g, b)}")

        spawn(sys.executable, os.path.join(HERE, "target.py"), self.log.name, "Other", "#0000ff", "+650+150")
        other = window("Other")
        time.sleep(1)
        covered = self.mcp.tool("look")
        self.assertEqual(pixel(image_of(covered), 200, 150), (255, 0, 0), "a covered window is still seen")

        run("xdotool", "windowactivate", "--sync", other)
        run("xdotool", "mousemove", "5", "5")
        clicked = self.mcp.tool("click", x=50, y=60)
        self.assertIn("Clicked", text_of(clicked))
        self.wait_event("Target button 1 50 60")
        self.assertEqual(run("xdotool", "getmouselocation", "--shell").splitlines()[:2], ["X=5", "Y=5"])
        self.assertEqual(run("xdotool", "getactivewindow", "getwindowname"), "Other")
        try:
            wait_for(lambda: cursor_stacking(window("Target"), other), "the arrow right above the Target", 3)
        finally:
            screenshot("cursor.png")

        self.mcp.tool("type", text="Hi")
        self.wait_event("Target key H")
        self.wait_event("Target key i")
        self.mcp.tool("key", keys="ctrl+l")
        self.wait_event("Target key l ctrl")
        self.mcp.tool("scroll", x=100, y=100, amount=2)
        self.wait_event("Target button 5 100 100")
        self.assertEqual(run("xdotool", "getactivewindow", "getwindowname"), "Other")
        self.assertFalse([e for e in self.events() if e.startswith("Other")], "nothing reached the other window")

        run("xdotool", "windowminimize", "--sync", window("Target"))
        back = self.mcp.tool("look")
        self.assertNotIn("isError", back, text_of(back))
        self.assertEqual(pixel(image_of(back), 200, 150), (255, 0, 0), "a minimized window comes back to be seen")
        self.assertEqual(run("xdotool", "getactivewindow", "getwindowname"), "Other")

        self.assertIn("outside the share", text_of(self.mcp.tool("click", x=400, y=10)))
        self.assertIn("whole system", text_of(self.mcp.tool("key", keys="super+a")))
        steps = self.mcp.tool("steps", steps=[{"action": "click", "x": 10, "y": 10}, {"action": "key", "keys": "win"}])
        self.assertIn("Step 2 (key)", text_of(steps))
        self.wait_event("Target button 1 10 10")

        run("xdotool", "key", "ctrl+alt+shift+x")
        wait_for(lambda: NOTHING in text_of(self.mcp.tool("look")), "the hotkey to end the share", 5)

        press(*self.panel_point(500, 176))
        time.sleep(2)
        drag(100, 100, 300, 250)
        self.start_sharing()
        region = self.mcp.tool("look")
        self.assertIn("Region 200 x 150, 200 x 150", text_of(region))


if __name__ == "__main__":
    unittest.main(verbosity=2)
