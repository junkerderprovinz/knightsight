import os
import sys

APP_ID = "io.github.junkerderprovinz.knightsight"

MISSING = """KnightSight needs Python's GObject bindings with GTK 4 and GStreamer. Install them with
  Debian, Ubuntu:  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-gstreamer-1.0 gstreamer1.0-pipewire
  Fedora:          sudo dnf install python3-gobject gtk4 gstreamer1-plugins-base pipewire-gstreamer
  Arch:            sudo pacman -S python-gobject python-cairo gtk4 gst-plugins-base gst-plugin-pipewire
or install the Flatpak, which brings all of it along."""


def main():
    from . import xlib
    # Two threads talk to the X server, each on its own connection, which Xlib allows only
    # when told before anything else uses it, GTK included.
    if os.environ.get("DISPLAY") and xlib.x11:
        xlib.XInitThreads()
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        gi.require_version("PangoCairo", "1.0")
        gi.require_version("Gst", "1.0")
        from gi.repository import GObject, Gtk
    except (ImportError, ValueError):
        print(MISSING, file=sys.stderr)
        return 1

    from . import panel, portal, server

    portal.register(APP_ID)
    app = Gtk.Application(application_id=APP_ID)

    def make_desk(window):
        display = window.get_display()
        if GObject.type_name(display.__gtype__) == "GdkX11Display" and xlib.available():
            from . import x11
            return x11.Desk(window)
        return portal.Desk(window)

    def activate(app):
        if app.get_windows():
            app.get_windows()[0].present()
            return
        window = panel.Panel(app, make_desk)
        server.serve(window)
        window.present()

    app.connect("activate", activate)
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
