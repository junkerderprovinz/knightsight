"""The panel's palette for the two themes, warm blacks and whites around the accent, following
the desktop's light or dark style."""

from gi.repository import Gio, GLib, Gtk

from . import notes

ACCENT = (252, 196, 25)
ACCENT_HOVER = (253, 214, 94)
ACCENT_INK = (22, 22, 22)
WARNING = (255, 131, 43)
NEUTRAL = (141, 136, 128)

CONTROL_MS = 150
CONTENT_MS = 220
PRESS_SCALE = 0.96


class Palette:
    def __init__(self, dark):
        self.dark = dark
        self.ground = (15, 14, 12) if dark else (245, 243, 239)
        self.surface = (28, 26, 23) if dark else (255, 255, 255)
        self.surface2 = (52, 48, 43) if dark else (233, 230, 224)
        self.surface3 = (78, 73, 66) if dark else (210, 205, 197)
        self.hover = (46, 43, 38) if dark else (225, 221, 214)
        self.text = (240, 236, 228) if dark else (24, 22, 19)
        self.secondary = (190, 184, 173) if dark else (86, 81, 73)
        self.muted = (140, 134, 124) if dark else (115, 109, 100)
        self.tip = self.surface2 if dark else (28, 26, 23)


def web(c):
    return "#%02x%02x%02x" % c


def rgb(c):
    return c[0] / 255, c[1] / 255, c[2] / 255


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease(t):
    return 1 - (1 - t) ** 3


def step(value, target, elapsed, duration):
    if duration <= 0:
        return target
    d = elapsed / duration
    return min(target, value + d) if value < target else max(target, value - d)


def animations():
    """With animations off in the desktop every duration is zero, so a change lands at once."""
    return Gtk.Settings.get_default().props.gtk_enable_animations


def css(p):
    # The chosen kind of a note is filled in its colour, with the same dark ink on all three.
    kinds = "\n".join(f".soft.{kind} {{ background: {web(c)}; color: {web(ACCENT_INK)}; }}"
                      for kind, c in notes.KIND_COLOURS.items())
    return f"""
window.knightsight, window.knightsight .bar {{ background: {web(p.ground)}; }}
window.knightsight {{ font-family: "Noto Sans", sans-serif; }}
.soft {{
  min-height: 0; min-width: 0; padding: 0; border: none; box-shadow: none; outline: none;
  border-radius: 6px; font-weight: 600; font-size: 14px;
  background: {web(p.surface2)}; color: {web(p.text)};
  transition: background {CONTROL_MS}ms ease-out, color {CONTROL_MS}ms ease-out, transform {CONTROL_MS}ms ease-out;
}}
.soft:hover {{ background: {web(p.surface3)}; }}
.soft:active {{ transform: scale({PRESS_SCALE}); }}
.soft:disabled {{ background: {web(p.surface2)}; color: {web(p.muted)}; }}
.soft:focus-visible {{ box-shadow: inset 0 0 0 2px {web(ACCENT)}; }}
.soft.primary {{ background: {web(ACCENT)}; color: {web(ACCENT_INK)}; }}
.soft.primary:hover {{ background: {web(ACCENT_HOVER)}; }}
.soft.primary:disabled {{ background: {web(p.surface2)}; color: {web(p.muted)}; }}
.soft.outline {{ background: {web(p.surface2)}; color: {web(p.text)}; box-shadow: inset 0 0 0 1.5px {web(ACCENT)}; }}
.soft.outline:hover {{ background: {web(p.surface3)}; }}
.soft.large {{ border-radius: 10px; font-size: 15px; }}
.soft.round {{ border-radius: 14px; }}
.soft.blank {{ background: none; color: {web(p.secondary)}; }}
.soft.blank > .square {{ border-radius: 6px; transition: background {CONTROL_MS}ms ease-out; }}
.soft.blank:hover {{ color: {web(p.text)}; }}
.soft.blank:hover > .square {{ background: {web(p.hover)}; }}
.soft.lit {{ background: {web(ACCENT)}; color: {web(ACCENT_INK)}; }}
.soft.lit:hover {{ background: {web(ACCENT_HOVER)}; }}
{kinds}
window.pinboard {{ color: {web(p.text)}; }}
.pinboard .card {{ background: {web(p.surface)}; border-radius: 10px; padding: 16px; }}
.pinboard .heading {{ font-weight: 600; font-size: 16px; }}
.pinboard .count {{ color: {web(p.muted)}; font-weight: 600; font-size: 14px; }}
.pinboard .muted {{ color: {web(p.muted)}; font-size: 12px; }}
.pinboard list {{ background: none; }}
.pinboard row {{ border-radius: 6px; padding: 6px 8px; transition: background {CONTROL_MS}ms ease-out; }}
.pinboard row:hover {{ background: {web(p.hover)}; }}
.pinboard .field {{ background: {web(p.surface2)}; border-radius: 6px; padding: 8px 10px; }}
.pinboard .field:focus-within {{ box-shadow: inset 0 0 0 2px {web(ACCENT)}; }}
.pinboard textview, .pinboard textview text {{ background: none; color: {web(p.text)}; font-size: 14px; }}
.pinboard .placeholder {{ color: {web(p.muted)}; font-size: 14px; }}
.pinboard entry {{
  min-height: 34px; padding: 0 10px; border: none; outline: none; box-shadow: none; border-radius: 6px;
  background: {web(p.surface2)}; color: {web(p.text)}; font-size: 14px;
}}
.pinboard entry:focus-within {{ box-shadow: inset 0 0 0 2px {web(ACCENT)}; }}
tooltip.background {{ background: {web(p.tip)}; color: #f4f4f4; border-radius: 6px; }}
tooltip > box {{ padding: 8px 12px; }}
tooltip label {{ font-size: 13px; }}
"""


_PORTAL = ("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings")


def _from_portal(bus):
    try:
        result = bus.call_sync(*_PORTAL, "ReadOne", GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
                               GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 1000, None)
    except GLib.Error:
        return None
    return result.unpack()[0] == 1


def _from_gtk():
    settings = Gtk.Settings.get_default()
    return settings.props.gtk_application_prefer_dark_theme or settings.props.gtk_theme_name.lower().endswith("-dark")


def watch(changed):
    """Calls changed with the current palette now and again whenever the desktop switches."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    dark = _from_portal(bus)
    changed(Palette(_from_gtk() if dark is None else dark))

    def on_signal(_bus, _sender, _path, _iface, _name, params):
        namespace, key, value = params.unpack()
        if namespace == "org.freedesktop.appearance" and key == "color-scheme":
            changed(Palette(value == 1))

    bus.signal_subscribe(_PORTAL[0], _PORTAL[2], "SettingChanged", _PORTAL[1], None, Gio.DBusSignalFlags.NONE, on_signal)
