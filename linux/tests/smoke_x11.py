"""Runs the panel on an X server with openbox, picks a window and a region through the panel
itself, and drives the share through the real MCP server.

Needs DISPLAY, a session bus, openbox, xdotool, Tk and node: tests/smoke-x11.sh sets them up.
"""

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LINUX = os.path.dirname(HERE)
REPO = os.path.dirname(LINUX)
sys.path.insert(0, LINUX)

import gi  # noqa: E402

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

from knightsight import protocol, xlib  # noqa: E402

NOTHING = protocol.NOTHING_SHARED
started = []


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def spawn(*args, **kw):
    p = subprocess.Popen(args, **kw)
    started.append(p)
    return p


def wait_for(check, what, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("timed out waiting for " + what)


def window(name):
    def find():
        try:
            return run("xdotool", "search", "--name", f"^{name}$").split()[0]
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


def pixel(png, x, y):
    loader = GdkPixbuf.PixbufLoader()
    loader.write(base64.b64decode(png))
    loader.close()
    pb = loader.get_pixbuf()
    data = pb.get_pixels()
    i = y * pb.get_rowstride() + x * pb.get_n_channels()
    return tuple(data[i:i + 3])


def screen_pixel(x, y):
    d = xlib.Display()
    try:
        data, _, _ = d.image(d.root, x, y, 1, 1)
        return data[2], data[1], data[0]
    finally:
        d.close()


def listening():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", protocol.PORT)) == 0


class Mcp:
    def __init__(self):
        self.p = spawn("node", os.path.join(REPO, "mcp", "knightsight-mcp.mjs"), stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE, text=True)
        self.n = 0
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})

    def call(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())["result"]

    def tool(self, name, **args):
        return self.call("tools/call", {"name": name, "arguments": args})


def text_of(result):
    return "\n".join(c["text"] for c in result["content"] if c["type"] == "text")


def image_of(result):
    return next(c["data"] for c in result["content"] if c["type"] == "image")


class SmokeX11(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = tempfile.NamedTemporaryFile("r", suffix=".log", delete=False)
        spawn("openbox")
        time.sleep(1)
        spawn(sys.executable, os.path.join(HERE, "target.py"), cls.log.name, "Target", "#ff0000", "+600+100")
        window("Target")
        env = dict(os.environ, LANGUAGE="en", GDK_BACKEND="x11", GSK_RENDERER="cairo", NO_AT_BRIDGE="1",
                   PYTHONPATH=LINUX)
        cls.panel = spawn(sys.executable, "-m", "knightsight", env=env)
        wait_for(listening, "the port")
        cls.panel_id = window("KnightSight")
        cls.mcp = Mcp()

    @classmethod
    def tearDownClass(cls):
        for p in reversed(started):
            p.kill()
            p.wait()
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
        press(*self.panel_point(110, 156))
        tx, ty = origin(window(title))
        press(tx + 200, ty + 150)

    def start_sharing(self):
        press(*self.panel_point(456, 156))

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

        self.mcp.tool("type", text="Hi")
        self.wait_event("Target key H")
        self.wait_event("Target key i")
        self.mcp.tool("key", keys="ctrl+l")
        self.wait_event("Target key l ctrl")
        self.mcp.tool("scroll", x=100, y=100, amount=2)
        self.wait_event("Target button 5 100 100")
        self.assertEqual(run("xdotool", "getactivewindow", "getwindowname"), "Other")
        self.assertFalse([e for e in self.events() if e.startswith("Other")], "nothing reached the other window")

        self.assertIn("outside the share", text_of(self.mcp.tool("click", x=400, y=10)))
        self.assertIn("whole system", text_of(self.mcp.tool("key", keys="super+a")))
        steps = self.mcp.tool("steps", steps=[{"action": "click", "x": 10, "y": 10}, {"action": "key", "keys": "win"}])
        self.assertIn("Step 2 (key)", text_of(steps))
        self.wait_event("Target button 1 10 10")

        run("xdotool", "key", "ctrl+alt+shift+x")
        wait_for(lambda: NOTHING in text_of(self.mcp.tool("look")), "the hotkey to end the share", 5)

        press(*self.panel_point(266, 156))
        time.sleep(0.5)
        drag(100, 100, 300, 250)
        self.start_sharing()
        region = self.mcp.tool("look")
        self.assertIn("Region 200 x 150, 200 x 150", text_of(region))


if __name__ == "__main__":
    unittest.main(verbosity=2)
