"""The desk on Wayland, through the XDG desktop portals.

ScreenCast lets the person pick a window or a screen in the desktop's own dialog and sends
its frames over PipeWire. RemoteDesktop, started in the same session, carries clicks and keys.
The desktop places no frame of ours on the screen, so the panel shows the share state itself.
"""

import itertools
import os
import time

from gi.repository import Gdk, Gio, GLib

from . import elements, picture, protocol, say
from .picker import RegionPicker
from .pinboard import Pinboard
from .protocol import Rect, Refused
from .stream import Frames

BUS = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
SCREEN_CAST = "org.freedesktop.portal.ScreenCast"
REMOTE_DESKTOP = "org.freedesktop.portal.RemoteDesktop"
SHORTCUTS = "org.freedesktop.portal.GlobalShortcuts"
MONITOR, WINDOW = 1, 2
KEYBOARD, POINTER = 1, 2
CURSOR_HIDDEN = 1
BTN_LEFT, BTN_RIGHT = 0x110, 0x111
MODIFIER_KEYS = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L"}
CANCELLED = 1
# How long the pointer gets to reach a spot before KnightSight asks whether it lies on its own windows.
SETTLE_S = 0.1


def register(app_id):
    """Tells the portal who a program outside a Flatpak is. It has to come before any other portal call."""
    if os.path.exists("/.flatpak-info"):
        return
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    try:
        bus.call_sync(BUS, PATH, "org.freedesktop.host.portal.Registry", "Register",
                      GLib.Variant("(sa{sv})", (app_id, {})), None, Gio.DBusCallFlags.NONE, 1000, None)
    except GLib.Error:
        pass


def _u(v):
    return GLib.Variant("u", v)


class Requests:
    """Portal calls answer through a Request object's Response signal, which this waits for."""

    def __init__(self, bus):
        self.bus = bus
        self.sender = bus.get_unique_name()[1:].replace(".", "_")
        self.counter = itertools.count(1)

    def token(self):
        return f"knightsight{os.getpid()}_{next(self.counter)}"

    def call(self, interface, method, signature, args, options, done):
        token = self.token()
        options = dict(options, handle_token=GLib.Variant("s", token))
        path = f"{PATH}/request/{self.sender}/{token}"
        subscription = None

        def answered(_bus, _sender, _path, _iface, _name, params):
            self.bus.signal_unsubscribe(subscription)
            code, results = params.unpack()
            done(code, results)

        subscription = self.bus.signal_subscribe(BUS, "org.freedesktop.portal.Request", "Response", path, None,
                                                 Gio.DBusSignalFlags.NO_MATCH_RULE, answered)
        self.bus.call(BUS, PATH, interface, method, GLib.Variant(signature, (*args, options)), None,
                      Gio.DBusCallFlags.NONE, -1, None, lambda bus, result: self._sent(result, subscription, done))

    def _sent(self, result, subscription, done):
        try:
            self.bus.call_finish(result)
        except GLib.Error as e:
            self.bus.signal_unsubscribe(subscription)
            done(2, {"error": e.message})

    def run(self, steps, failed):
        """Drives a generator that yields portal calls and gets each one's results back."""
        def advance(results=None):
            try:
                request = steps.send(results)
            except StopIteration:
                return
            self.call(*request, lambda code, res: advance(res) if code == 0 else failed(code, res))
        advance()


class Share:
    def __init__(self, session, node, props, devices, frames):
        self.session = session
        self.node = node
        self.props = props
        self.devices = devices
        self.frames = frames
        self.region = None
        self.screen = False
        self.title = say.CHOSEN_WINDOW
        # Keys go wherever the keyboard focus is, so they wait for a click into the share.
        self.clicked = False


class Desk:
    overlay = False
    help = say.HELP_WAYLAND
    pick_hint = say.PICK_IN_DIALOG

    def __init__(self, panel):
        self.panel = panel
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.requests = Requests(self.bus)
        self.current = None
        self.closed_watch = None
        # The session holding the shortcuts and the watch on them, while a share runs.
        self.shortcuts = None
        self.asking = False
        self.sharing = False

    def _property(self, interface, name):
        try:
            result = self.bus.call_sync(BUS, PATH, "org.freedesktop.DBus.Properties", "Get",
                                        GLib.Variant("(ss)", (interface, name)), GLib.VariantType("(v)"),
                                        Gio.DBusCallFlags.NONE, 1000, None)
        except GLib.Error:
            return None
        return result.unpack()[0]

    def _open(self, kind, done, failed):
        """One session for picture and input, so the desktop asks once for both."""
        remote = self._property(REMOTE_DESKTOP, "AvailableDeviceTypes")
        cursors = self._property(SCREEN_CAST, "AvailableCursorModes") or 0
        if self._property(SCREEN_CAST, "version") is None:
            failed(2, {})
            return
        host = REMOTE_DESKTOP if remote else SCREEN_CAST

        def steps():
            r = yield host, "CreateSession", "(a{sv})", (), {"session_handle_token": GLib.Variant("s", self.requests.token())}
            session = r["session_handle"]
            sources = {"types": _u(kind), "multiple": GLib.Variant("b", False)}
            if cursors & CURSOR_HIDDEN:
                sources["cursor_mode"] = _u(CURSOR_HIDDEN)
            yield SCREEN_CAST, "SelectSources", "(oa{sv})", (session,), sources
            if remote:
                yield REMOTE_DESKTOP, "SelectDevices", "(oa{sv})", (session,), {"types": _u(KEYBOARD | POINTER)}
            r = yield host, "Start", "(osa{sv})", (session, ""), {}
            streams = r.get("streams") or []
            if not streams:
                self._close(session)
                failed(2, {})
                return
            node, props = streams[0]
            done(Share(session, node, props, r.get("devices", 0) if remote else 0, self._frames(session, node, kind)))

        self.requests.run(steps(), failed)

    def _frames(self, session, node, kind):
        result, fds = self.bus.call_with_unix_fd_list_sync(
            BUS, PATH, SCREEN_CAST, "OpenPipeWireRemote", GLib.Variant("(oa{sv})", (session, {})),
            GLib.VariantType("(h)"), Gio.DBusCallFlags.NONE, -1, None, None)
        return Frames(fds.get(result.unpack()[0]), node, kind == WINDOW)

    def _close(self, session):
        self.bus.call(BUS, session, "org.freedesktop.portal.Session", "Close", None, None,
                      Gio.DBusCallFlags.NONE, -1, None, None)

    def _adopt(self, share):
        self.release()
        self.current = share

        def closed(*_):
            if self.current is share:
                self.release()
                self.panel.forget()

        self.closed_watch = self.bus.signal_subscribe(BUS, "org.freedesktop.portal.Session", "Closed", share.session,
                                                      None, Gio.DBusSignalFlags.NONE, closed)

    def release(self):
        share, self.current = self.current, None
        if share is None:
            return
        self.bus.signal_unsubscribe(self.closed_watch)
        self._drop(share)

    def _drop(self, share):
        share.frames.stop()
        self._close(share.session)

    def close(self):
        self.release()

    def _failed(self, done):
        def failed(code, results):
            done(None, None if code == CANCELLED else say.NO_PORTAL)
        return failed

    def pick_window(self, done):
        def opened(share):
            self._adopt(share)
            done(share, None)
        self._open(WINDOW, opened, self._failed(done))

    def stop_pick(self):
        pass

    def _screen(self, then, done):
        """Has the desktop share a whole screen and hands then the share with its first frame."""
        def opened(share):
            started = time.monotonic()

            def first_frame():
                frame = share.frames.frame()
                if frame is not None:
                    then(share, frame)
                elif time.monotonic() - started < 5:
                    return True
                else:
                    self._drop(share)
                    done(None, say.NO_PORTAL)
                return False

            GLib.timeout_add(50, first_frame)

        self._open(MONITOR, opened, self._failed(done))

    def pick_region(self, monitor, done):
        """The region is cut from the frames of a whole screen."""
        def framed(share, frame):
            def picked(r):
                if r is None:
                    self._drop(share)
                    done(None, None)
                    return
                share.region = Rect(*r)
                share.title = f"{say.REGION} {r[2]} x {r[3]}"
                self._adopt(share)
                done(share, None)

            number = self._monitor(share)
            shared = monitor if number is None else Gdk.Display.get_default().get_monitors().get_item(number)
            RegionPicker(frame.surface(), shared, picked).present()

        self._screen(framed, done)

    def pick_screen(self, done):
        """The desktop's dialog chooses the screen, which is then a region as large as its frames."""
        def framed(share, frame):
            share.region = Rect(0, 0, frame.width, frame.height)
            width, height = share.props.get("size") or (frame.width, frame.height)
            number = self._monitor(share)
            share.title = say.screen(None if number is None else number + 1, width, height)
            share.screen = True
            self._adopt(share)
            done(share, None)

        self._screen(framed, done)

    @staticmethod
    def _monitor(share):
        """Where the monitor the desktop says it shares stands in the system's order, when the
        desktop gives its position."""
        position, size = share.props.get("position"), share.props.get("size")
        if not position or not size:
            return None
        monitors = Gdk.Display.get_default().get_monitors()
        for i in range(monitors.get_n_items()):
            g = monitors.get_item(i).get_geometry()
            if (g.x, g.y, g.width, g.height) == (*position, *size):
                return i
        return None

    def bind_hotkey(self, pressed):
        """Asks the desktop for Ctrl+Alt+Shift+X and Ctrl+Shift+A while something is shared.
        pressed gets the name of the one pressed. Other programs use Ctrl+Shift+A too, and the
        portal frees a shortcut only with its session, so the session ends with the share."""
        self.sharing = True
        if self.shortcuts or self.asking or self._property(SHORTCUTS, "version") is None:
            return
        self.asking = True

        def shortcut(description, trigger):
            return {"description": GLib.Variant("s", description), "preferred_trigger": GLib.Variant("s", trigger)}

        def steps():
            r = yield SHORTCUTS, "CreateSession", "(a{sv})", (), {"session_handle_token": GLib.Variant("s", self.requests.token())}
            session = r["session_handle"]
            self.asking = False
            if not self.sharing:
                self._close(session)
                return
            watch = self.bus.signal_subscribe(
                BUS, SHORTCUTS, "Activated", PATH, session, Gio.DBusSignalFlags.NONE,
                lambda _bus, _sender, _path, _iface, _name, params: pressed(params.unpack()[1]))
            self.shortcuts = (session, watch)
            shortcuts = [("stop", shortcut(say.STOP_SHARE, "CTRL+ALT+SHIFT+X")),
                         ("pinboard", shortcut(say.PINBOARD, "CTRL+SHIFT+A"))]
            yield SHORTCUTS, "BindShortcuts", "(oa(sa{sv})s)", (session, shortcuts, ""), {}

        def failed(*_):
            self.asking = False

        self.requests.run(steps(), failed)

    def unbind_hotkey(self):
        self.sharing = False
        if self.shortcuts:
            session, watch = self.shortcuts
            self.shortcuts = None
            self.bus.signal_unsubscribe(watch)
            self._close(session)

    def pinboard(self, shot, closed):
        return Pinboard(self.panel, shot, closed)

    def hotkey_pressed(self):
        return None

    def title(self, share):
        return share.title

    def area(self, share):
        return share.region

    def gone(self, share):
        return False

    def hidden(self, share):
        return False

    def minimized(self, share):
        return False

    def unminimize(self, share):
        return False

    def show(self, share, area, color, width, badge):
        pass

    def hide(self):
        pass

    @staticmethod
    def _frame(share):
        frame = share.frames.frame()
        if frame is None:
            raise Refused("The desktop has not sent a picture of the share yet.")
        return frame

    def still(self, share):
        """The share in full resolution, cut from the newest frame."""
        frame = self._frame(share)
        r = share.region or frame.area
        return picture.cut(frame.surface(), r.x, r.y, r.width, r.height)

    def preview(self, share):
        """The frames keep coming while a share is chosen, so the finder shows the newest one."""
        return self.still(share)

    def look(self, share):
        shot = self.still(share)
        reply = picture.encode(shot)
        reply["title"] = share.title
        # The portal tells nothing about where a region's screen lies, so only a window is read.
        if share.region is None:
            size = (shot.get_width(), shot.get_height())
            found = elements.controls(size, size)
            if found is not None:
                reply["elements"] = found
        return reply

    def _point(self, share, args, clicked=None):
        """Maps a point in the picture to the stream, which counts in the desktop's own units
        and may differ from the frame's pixels. clicked gets the share's area and the point, both
        in frame pixels."""
        frame = self._frame(share)
        area = share.region or frame.area
        x, y = protocol.to_area(area, args)
        if clicked:
            clicked(area, x, y)
        sw, sh = share.props.get("size") or (frame.width, frame.height)
        return x * sw / frame.width, y * sh / frame.height

    def _notify(self, share, method, signature, *args):
        self.bus.call_sync(BUS, PATH, REMOTE_DESKTOP, method, GLib.Variant(signature, (share.session, {}, *args)),
                           None, Gio.DBusCallFlags.NONE, -1, None)

    def _move(self, share, x, y):
        if not share.devices & POINTER:
            raise Refused("This desktop lets KnightSight look, but not click or type.")
        with protocol.delivering():
            self._notify(share, "NotifyPointerMotionAbsolute", "(oa{sv}udd)", share.node, x, y)
        # Wayland tells only the window under the pointer where it is, so KnightSight's own
        # windows say whether the pointer came to rest on them.
        time.sleep(SETTLE_S)
        if self.panel.under_pointer:
            raise Refused(protocol.ON_US)

    def click(self, share, args):
        x, y = self._point(share, args, self.panel.clicked)
        right, twice = protocol.flag(args, "right"), protocol.flag(args, "double")
        self._move(share, x, y)
        self.panel.busy()
        button = BTN_RIGHT if right else BTN_LEFT
        with protocol.delivering():
            for _ in range(2 if twice else 1):
                self._notify(share, "NotifyPointerButton", "(oa{sv}iu)", button, 1)
                time.sleep(0.03)
                self._notify(share, "NotifyPointerButton", "(oa{sv}iu)", button, 0)
                time.sleep(0.03)
        share.clicked = True
        return "Clicked. The desktop moved the pointer there."

    def scroll(self, share, args):
        x, y = self._point(share, args)
        notches = round(protocol.number(args, "amount"))
        self._move(share, x, y)
        self.panel.busy()
        with protocol.delivering():
            self._notify(share, "NotifyPointerAxisDiscrete", "(oa{sv}ui)", 0, notches)
        return "Scrolled. The desktop moved the pointer there."

    def _keys_allowed(self, share):
        if not share.devices & KEYBOARD:
            raise Refused("This desktop lets KnightSight look, but not type.")
        if not share.clicked:
            raise Refused("Keys go to the window last clicked inside the share, and nothing has been clicked there yet.")
        if self.panel.focused:
            raise Refused("The KnightSight window has the keyboard focus, so the keys would land there.")

    def _press(self, share, keysym, down):
        self._notify(share, "NotifyKeyboardKeysym", "(oa{sv}iu)", keysym, 1 if down else 0)

    def _stroke(self, share, held, keysym):
        mods = [Gdk.keyval_from_name(MODIFIER_KEYS[m]) for m in held]
        for m in mods:
            self._press(share, m, True)
        self._press(share, keysym, True)
        self._press(share, keysym, False)
        for m in reversed(mods):
            self._press(share, m, False)
        # GNOME can apply the release of a modifier after the keys that follow it, which
        # then arrive as Ctrl+Return or Ctrl+Shift+A.
        time.sleep(0.1 if mods else 0.005)

    def type(self, share, text):
        self._keys_allowed(share)
        self.panel.busy()
        with protocol.delivering():
            for key, is_char in protocol.text_keys(text):
                self._stroke(share, [], Gdk.unicode_to_keyval(ord(key)) if is_char else Gdk.keyval_from_name(key))
        return "Typed."

    def key(self, share, keys):
        combo = protocol.parse_combo(keys)
        self._keys_allowed(share)
        self.panel.busy()
        keysym = Gdk.unicode_to_keyval(ord(combo.key)) if combo.is_char else Gdk.keyval_from_name(combo.key)
        with protocol.delivering():
            self._stroke(share, combo.held, keysym)
        return "Pressed."
