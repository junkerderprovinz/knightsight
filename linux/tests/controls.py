"""A GTK window with a button, which unlike Tk shows up in the accessibility tree, and writes
down each press of it."""

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

log_path, title = sys.argv[1:3]
log = open(log_path, "a", buffering=1)
Gtk.init()
window = Gtk.Window(title=title, default_width=400, default_height=300)
# Off the middle, where choosing the window clicks.
button = Gtk.Button(label="Press me", halign=Gtk.Align.START, valign=Gtk.Align.START, margin_start=24, margin_top=24)
button.connect("clicked", lambda _b: log.write(f"{title} pressed\n"))
window.set_child(button)
loop = GLib.MainLoop()
window.connect("close-request", lambda _w: loop.quit() or False)
window.present()
loop.run()
