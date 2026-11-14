"""Runs the panel in a headless GNOME Shell on Wayland, shares a text editor through the
desktop's own portal dialog and works in it through the real MCP server.

Needs a session bus, a fresh runtime folder, GNOME Shell with its portal, PipeWire and
gnome-text-editor: tests/smoke-wayland.sh sets them up.
"""

import json
import os
import subprocess
import sys
import time
import unittest

from harness import LINUX, Mcp, image_of, listening, pixbuf, pixel_of, spawn, stop_all, text_of, wait_for

import gi

for name, version in (("Atspi", "2.0"), ("Gtk", "4.0"), ("Gdk", "4.0"), ("PangoCairo", "1.0")):
    gi.require_version(name, version)

from gi.repository import Atspi, GdkPixbuf, Gio, GLib  # noqa: E402

from knightsight import panel, protocol, theme  # noqa: E402

OUT = os.environ["SMOKE_OUT"]
EDITOR = "org.gnome.TextEditor"
KNIGHTSIGHT = "io.github.junkerderprovinz.knightsight"
NOTHING = protocol.NOTHING_SHARED
LINE = "A line typed through the share."
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
Atspi.init()


def log(name):
    return open(os.path.join(OUT, name), "w")


def start(name, *args, **kw):
    with log(name + ".log") as f:
        return spawn(*args, stdout=f, stderr=subprocess.STDOUT, **kw)


def call(name, path, interface, method, args, reply):
    return bus.call_sync(name, path, interface, method, args, GLib.VariantType(reply), Gio.DBusCallFlags.NONE,
                         10000, None).unpack()


def shell(code):
    ok, value = call("org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell", "Eval", GLib.Variant("(s)", (code,)),
                     "(bs)")
    if not ok:
        raise AssertionError(f"the shell could not run {code}: {value}")
    return json.loads(value) if value else None


def shell_ready():
    try:
        return shell("globalThis.smoke !== undefined && smoke.ready()")
    except (AssertionError, GLib.Error):
        return False


def window(app):
    return next((w for w in shell("smoke.windows()") if w["app"] == app), None)


def place(app, *frame):
    """Moves a window once it is on the screen, since the shell places it as it appears."""
    wanted = list(frame)
    wait_for(lambda: shell("smoke.hideOverview()") and (window(app) or {}).get("mapped"), f"{app} to appear", 30)

    def there():
        got = shell(f"smoke.place('{app}', {', '.join(map(str, frame))})")
        return got[:len(wanted)] == wanted

    wait_for(there, f"{app} to move to {frame}", 10)


def screenshot(name, area=(0, 0, 1280, 800)):
    path = os.path.join(OUT, name)
    call("org.gnome.Shell.Screenshot", "/org/gnome/Shell/Screenshot", "org.gnome.Shell.Screenshot",
         "ScreenshotArea", GLib.Variant("(iiiibs)", (*area, False, path)), "(bs)")
    return GdkPixbuf.Pixbuf.new_from_file(path)


def tree(a, depth=0):
    """Every accessible below a, depth first, with how deep it lies."""
    yield a, depth
    try:
        n = a.get_child_count()
    except GLib.Error:
        return
    for i in range(n):
        child = a.get_child_at_index(i)
        if child is not None:
            yield from tree(child, depth + 1)


def describe(a):
    try:
        actions = a.get_action_iface()
        names = [actions.get_action_name(i) for i in range(actions.get_n_actions())] if actions else []
        r = a.get_extents(Atspi.CoordType.WINDOW)
        states = [s.value_nick for s in a.get_state_set().get_states()
                  if s.value_nick in ("checked", "selected", "sensitive")]
        return f"{a.get_role_name()} {a.get_name()!r} {names} {states} {(r.x, r.y, r.width, r.height)}"
    except GLib.Error as e:
        return f"gone ({e.message})"


def dump(root, name):
    with log(name) as f:
        for a, depth in tree(root):
            f.write("  " * depth + describe(a) + "\n")


def evidence(name):
    """Keeps what the screen, the shell and the accessibility tree show, for a look afterwards."""
    with log(name + "-windows.json") as f:
        json.dump(shell("smoke.windows()"), f, indent=1)
    dump(Atspi.get_desktop(0), name + "-accessible.txt")
    screenshot(name + ".png")


def find(root, roles, text, pressable=False):
    """The first accessible below root in one of the roles whose name holds the text."""
    for a, _ in tree(root):
        if a.get_role_name() in roles and text in (a.get_name() or ""):
            if not pressable or a.get_n_actions():
                return a
    return None


def portal():
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is not None and app.get_name() == "xdg-desktop-portal-gnome":
            return app
    return None


def press(a):
    a.get_action_iface().do_action(0)


def click(a):
    """Clicks the middle of a with the pointer, for a list row that offers no action of its own."""
    top = a
    while top.get_role_name() != "frame":
        top = top.get_parent()
    fx, fy, _, _ = next(w for w in shell("smoke.windows()") if w["title"] == top.get_name())["frame"]
    r = a.get_extents(Atspi.CoordType.WINDOW)
    shell(f"smoke.click({fx + r.x + r.width // 2}, {fy + r.y + r.height // 2})")


class SmokeWayland(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(stop_all)
        start("pipewire", "pipewire")
        start("wireplumber", "wireplumber")
        start("gnome-shell", "gnome-shell", "--headless", "--wayland", "--virtual-monitor", "1280x800")
        wait_for(shell_ready, "the shell and its helper", 90)

        cls.notes = os.path.join(OUT, "notes.txt")
        with open(cls.notes, "w") as f:
            f.write("Shopping list\n\nBread\nCheese\nApples\n")
        start("editor", "gnome-text-editor", "--standalone", "--ignore-session", cls.notes)
        wait_for(lambda: window(EDITOR), "the text editor", 60)
        place(EDITOR, 10, 60, 640, 480)

        env = dict(os.environ, PYTHONPATH=LINUX, PYTHONFAULTHANDLER="1")
        cls.panel = start("panel", sys.executable, "-m", "knightsight", env=env)
        wait_for(lambda: listening() or cls.panel.poll() is not None, "the port", 60)
        if cls.panel.poll() is not None:
            raise AssertionError(f"the panel exited with {cls.panel.returncode}")
        wait_for(lambda: window(KNIGHTSIGHT), "the KnightSight window", 30)
        place(KNIGHTSIGHT, 690, 60)
        time.sleep(1)
        cls.mcp = Mcp()

    def panel_click(self, x, y):
        wait_for(lambda: shell("smoke.hideOverview()"), "the overview to close", 10)
        fx, fy, _, _ = window(KNIGHTSIGHT)["frame"]
        shell(f"smoke.click({fx + x}, {fy + y})")
        time.sleep(0.3)

    def card_edge(self, name):
        """The colour of the card's frame, which on Wayland stands in for one around the window."""
        fx, fy, fw, fh = window(KNIGHTSIGHT)["frame"]
        shot = screenshot(name, (fx, fy, fw, fh))
        return pixel_of(shot, panel.CARD[0] + 1, panel.BAR + panel.CARD[3] // 2)

    def share_in_dialog(self):
        """Picks the editor in the desktop's dialog and confirms it."""
        app = wait_for(portal, "the portal", 30)
        title = os.path.basename(self.notes)
        entry = wait_for(lambda: find(app, ("list item",), title), "the editor in the dialog", 30)
        dump(app, "dialog.txt")
        click(entry)
        # GTK names the roles differently from one version to the next.
        remote = find(app, ("check box", "switch"), "Allow Remote Interaction", pressable=True)
        if not remote.get_state_set().contains(Atspi.StateType.CHECKED):
            press(remote)
        time.sleep(0.5)
        dump(app, "dialog-chosen.txt")
        screenshot("dialog-chosen.png")
        press(find(app, ("push button", "button"), "Share", pressable=True))
        wait_for(lambda: app.get_child_count() == 0, "the dialog to close", 20)

    def tearDown(self):
        evidence("end")

    def test_window_share(self):
        self.assertIn(NOTHING, text_of(self.mcp.tool("look")))

        self.panel_click(110, 156)
        self.share_in_dialog()
        time.sleep(1)
        self.assertEqual(self.card_edge("panel-chosen.png"), theme.NEUTRAL)

        self.panel_click(456, 156)
        wait_for(lambda: NOTHING not in text_of(self.mcp.tool("look")), "the share to start", 10)
        time.sleep(1)
        # Lit in the accent colour, or on its way to the warning colour while requests come in.
        r, g, b = self.card_edge("panel-shared.png")
        self.assertTrue(r > 240 and 120 < g < 210 and b < 60, f"the card's frame is {(r, g, b)} while sharing")
        screenshot("screen-shared.png")

        # The picture holds the window and at most its shadow, never the black around them.
        shot = self.mcp.tool("look")
        picture = pixbuf(image_of(shot))
        picture.savev(os.path.join(OUT, "look.png"), "png", [], [])
        width, height = picture.get_width(), picture.get_height()
        editor = window(EDITOR)
        self.assertIn(f"Chosen window, {width} x {height}", text_of(shot))
        self.assertTrue(editor["frame"][2] <= width <= editor["buffer"][2], f"the picture is {width} wide, {editor}")
        self.assertTrue(editor["frame"][3] <= height <= editor["buffer"][3], f"the picture is {height} high, {editor}")

        self.assertIn("Clicked", text_of(self.mcp.tool("click", x=width // 2, y=height // 2)))
        wait_for(lambda: window(EDITOR)["focus"], "the editor to get the focus", 5)
        for step in (self.mcp.tool("key", keys="ctrl+end"), self.mcp.tool("type", text="\n" + LINE),
                     self.mcp.tool("key", keys="ctrl+s")):
            self.assertNotIn("isError", step, text_of(step))

        def saved():
            with open(self.notes) as f:
                return LINE in f.read()

        wait_for(saved, "the editor to save the typed line", 10)
        self.assertIn("outside the share", text_of(self.mcp.tool("click", x=width + 40, y=height // 2)))
        screenshot("screen-end.png")
        with open(os.path.join(OUT, "panel.log")) as f:
            self.assertNotIn("Traceback", f.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
