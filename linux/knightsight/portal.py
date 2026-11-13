"""The desk on Wayland, through the XDG desktop portals.

ScreenCast lets the person pick a window or a screen in the desktop's own dialog and sends
its frames over PipeWire. RemoteDesktop, started in the same session, carries clicks and keys.
The desktop places no frame of ours on the screen, so the panel shows the share state itself.
"""

import itertools
import os
import time

from gi.repository import Gdk, Gio, GLib

from . import picture, protocol, say
from .picker import RegionPicker
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
        self.shortcuts = None

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
            done(Share(session, node, props, r.get("devices", 0) if remote else 0, self._frames(session, node)))

        self.requests.run(steps(), failed)

    def _frames(self, session, node):
        result, fds = self.bus.call_with_unix_fd_list_sync(
            BUS, PATH, SCREEN_CAST, "OpenPipeWireRemote", GLib.Variant("(oa{sv})", (session, {})),
            GLib.VariantType("(h)"), Gio.DBusCallFlags.NONE, -1, None, None)
        return Frames(fds.get(result.unpack()[0]), node)

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

    def pick_region(self, monitor, done):
        """The desktop shares a whole screen, and the region is cut from its frames."""
        def opened(share):
            started = time.monotonic()

            def first_frame():
                shot = share.frames.surface()
                if shot is None:
                    if time.monotonic() - started < 5:
                        return True
                    self._drop(share)
                    done(None, say.NO_PORTAL)
                    return False
                RegionPicker(shot, self._monitor(share) or monitor, picked).present()
                return False

            def picked(r):
                if r is None:
                    self._drop(share)
                    done(None, None)
                    return
                share.region = Rect(*r)
                share.title = f"{say.REGION} {r[2]} x {r[3]}"
                self._adopt(share)
                done(share, None)

            GLib.timeout_add(50, first_frame)

        self._open(MONITOR, opened, self._failed(done))

    @staticmethod
    def _monitor(share):
        """The monitor the desktop says it shares, when it gives the position."""
        position, size = share.props.get("position"), share.props.get("size")
        if not position or not size:
            return None
        monitors = Gdk.Display.get_default().get_monitors()
        for i in range(monitors.get_n_items()):
            g = monitors.get_item(i).get_geometry()
            if (g.x, g.y, g.width, g.height) == (*position, *size):
                return monitors.get_item(i)
        return None

    def bind_hotkey(self, stop):
        """Asks the desktop for Ctrl+Alt+Shift+X once, the first time something is shared."""
        if self.shortcuts or self._property(SHORTCUTS, "version") is None:
            return
        self.shortcuts = "asking"

        def steps():
            r = yield SHORTCUTS, "CreateSession", "(a{sv})", (), {"session_handle_token": GLib.Variant("s", self.requests.token())}
            session = r["session_handle"]
            shortcut = {"description": GLib.Variant("s", say.STOP_SHARE),
                        "preferred_trigger": GLib.Variant("s", "CTRL+ALT+SHIFT+x")}
            self.shortcuts = session
            self.bus.signal_subscribe(BUS, SHORTCUTS, "Activated", PATH, session, Gio.DBusSignalFlags.NONE,
                                      lambda *_: stop())
            yield SHORTCUTS, "BindShortcuts", "(oa(sa{sv})s)", (session, [("stop", shortcut)], ""), {}

        self.requests.run(steps(), lambda *_: None)

    def hotkey_pressed(self):
        return False

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

    def look(self, share):
        shot = share.frames.surface()
        if shot is None:
            raise Refused("The desktop has not sent a picture of the share yet.")
        r = share.region
        reply = picture.encode(shot, (r.x, r.y, r.width, r.height) if r else None)
        reply["title"] = share.title
        return reply

    def _frame_area(self, share):
        if share.region:
            return share.region
        size = share.frames.size()
        if size is None:
            raise Refused("The desktop has not sent a picture of the share yet.")
        return Rect(0, 0, *size)

    def _notify(self, share, method, signature, *args):
        self.bus.call_sync(BUS, PATH, REMOTE_DESKTOP, method, GLib.Variant(signature, (share.session, {}, *args)),
                           None, Gio.DBusCallFlags.NONE, -1, None)

    def _move(self, share, x, y):
        """The stream counts in the desktop's own units, which may differ from the frame's pixels."""
        if not share.devices & POINTER:
            raise Refused("This desktop lets KnightSight look, but not click or type.")
        fw, fh = share.frames.size()
        sw, sh = share.props.get("size") or (fw, fh)
        self._notify(share, "NotifyPointerMotionAbsolute", "(oa{sv}udd)", share.node, x * sw / fw, y * sh / fh)

    def click(self, share, args):
        x, y = protocol.to_area(self._frame_area(share), args)
        right, twice = protocol.flag(args, "right"), protocol.flag(args, "double")
        self._move(share, x, y)
        self.panel.busy()
        button = BTN_RIGHT if right else BTN_LEFT
        for _ in range(2 if twice else 1):
            self._notify(share, "NotifyPointerButton", "(oa{sv}iu)", button, 1)
            time.sleep(0.03)
            self._notify(share, "NotifyPointerButton", "(oa{sv}iu)", button, 0)
            time.sleep(0.03)
        share.clicked = True
        return "Clicked. The desktop moved the pointer there."

    def scroll(self, share, args):
        x, y = protocol.to_area(self._frame_area(share), args)
        notches = round(protocol.number(args, "amount"))
        self._move(share, x, y)
        self.panel.busy()
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
        time.sleep(0.005)

    def type(self, share, text):
        self._keys_allowed(share)
        self.panel.busy()
        for key, is_char in protocol.text_keys(text):
            self._stroke(share, [], Gdk.unicode_to_keyval(ord(key)) if is_char else Gdk.keyval_from_name(key))
        return "Typed."

    def key(self, share, keys):
        combo = protocol.parse_combo(keys)
        self._keys_allowed(share)
        self.panel.busy()
        keysym = Gdk.unicode_to_keyval(ord(combo.key)) if combo.is_char else Gdk.keyval_from_name(combo.key)
        self._stroke(share, combo.held, keysym)
        return "Pressed."
