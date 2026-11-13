"""The few pieces of Xlib, XTest, Composite, Shape and the screen saver extension the X11 desk uses."""

import ctypes
from ctypes import (POINTER, Structure, Union, byref, c_char_p, c_int, c_long, c_short, c_ubyte, c_uint,
                    c_ulong, c_void_p)

XID = c_ulong
Bool = c_int

ZPixmap = 2
TrueColor = 4
InputOutput = 1
PropModeReplace = 0
IconicState = 3
ClientMessage = 33
KeyPress = 2
Button1Mask = 1 << 8
ControlMask, ShiftMask, LockMask, Mod1Mask, Mod2Mask = 1 << 2, 1 << 0, 1 << 1, 1 << 3, 1 << 4
GrabModeAsync = 1
SubstructureNotifyMask = 1 << 19
SubstructureRedirectMask = 1 << 20
CWBackPixel, CWBorderPixel, CWOverrideRedirect, CWColormap = 1 << 1, 1 << 3, 1 << 9, 1 << 13
CWSibling, CWStackMode = 1 << 5, 1 << 6
Above = 0
ShapeBounding, ShapeInput = 0, 2
ShapeSet = 0
CompositeRedirectAutomatic = 0


class XImage(Structure):
    _fields_ = [
        ("width", c_int), ("height", c_int), ("xoffset", c_int), ("format", c_int), ("data", c_void_p),
        ("byte_order", c_int), ("bitmap_unit", c_int), ("bitmap_bit_order", c_int), ("bitmap_pad", c_int),
        ("depth", c_int), ("bytes_per_line", c_int), ("bits_per_pixel", c_int),
        ("red_mask", c_ulong), ("green_mask", c_ulong), ("blue_mask", c_ulong), ("obdata", c_void_p),
        ("funcs", c_void_p * 6),
    ]


class XWindowAttributes(Structure):
    _fields_ = [
        ("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int), ("border_width", c_int), ("depth", c_int),
        ("visual", c_void_p), ("root", XID), ("class_", c_int), ("bit_gravity", c_int), ("win_gravity", c_int),
        ("backing_store", c_int), ("backing_planes", c_ulong), ("backing_pixel", c_ulong), ("save_under", Bool),
        ("colormap", XID), ("map_installed", Bool), ("map_state", c_int), ("all_event_masks", c_long),
        ("your_event_mask", c_long), ("do_not_propagate_mask", c_long), ("override_redirect", Bool),
        ("screen", c_void_p),
    ]


class XSetWindowAttributes(Structure):
    _fields_ = [
        ("background_pixmap", XID), ("background_pixel", c_ulong), ("border_pixmap", XID), ("border_pixel", c_ulong),
        ("bit_gravity", c_int), ("win_gravity", c_int), ("backing_store", c_int), ("backing_planes", c_ulong),
        ("backing_pixel", c_ulong), ("save_under", Bool), ("event_mask", c_long), ("do_not_propagate_mask", c_long),
        ("override_redirect", Bool), ("colormap", XID), ("cursor", XID),
    ]


class XVisualInfo(Structure):
    _fields_ = [
        ("visual", c_void_p), ("visualid", c_ulong), ("screen", c_int), ("depth", c_int), ("class_", c_int),
        ("red_mask", c_ulong), ("green_mask", c_ulong), ("blue_mask", c_ulong), ("colormap_size", c_int),
        ("bits_per_rgb", c_int),
    ]


class XWindowChanges(Structure):
    _fields_ = [("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int), ("border_width", c_int),
                ("sibling", XID), ("stack_mode", c_int)]


class XErrorEvent(Structure):
    _fields_ = [("type", c_int), ("display", c_void_p), ("resourceid", XID), ("serial", c_ulong),
                ("error_code", c_ubyte), ("request_code", c_ubyte), ("minor_code", c_ubyte)]


class XClientMessageEvent(Structure):
    _fields_ = [("type", c_int), ("serial", c_ulong), ("send_event", Bool), ("display", c_void_p), ("window", XID),
                ("message_type", XID), ("format", c_int), ("l", c_long * 5)]


class XKeyEvent(Structure):
    _fields_ = [("type", c_int), ("serial", c_ulong), ("send_event", Bool), ("display", c_void_p), ("window", XID),
                ("root", XID), ("subwindow", XID), ("time", c_ulong), ("x", c_int), ("y", c_int), ("x_root", c_int),
                ("y_root", c_int), ("state", c_uint), ("keycode", c_uint), ("same_screen", Bool)]


class XEvent(Union):
    _fields_ = [("type", c_int), ("xclient", XClientMessageEvent), ("xkey", XKeyEvent), ("pad", c_long * 24)]


class XScreenSaverInfo(Structure):
    _fields_ = [("window", XID), ("state", c_int), ("kind", c_int), ("til_or_since", c_ulong), ("idle", c_ulong),
                ("event_mask", c_ulong)]


class XRectangle(Structure):
    _fields_ = [("x", c_short), ("y", c_short), ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]


ERROR_HANDLER = ctypes.CFUNCTYPE(c_int, c_void_p, POINTER(XErrorEvent))


def _bind(lib, name, restype, *argtypes):
    f = getattr(lib, name)
    f.restype = restype
    f.argtypes = argtypes
    return f


def _open(soname):
    try:
        return ctypes.CDLL(soname)
    except OSError:
        return None


x11 = _open("libX11.so.6")
xtst = _open("libXtst.so.6")
xcomposite = _open("libXcomposite.so.1")
xext = _open("libXext.so.6")
# The idle time comes from here. Without it a click goes ahead without waiting for a pause.
xss = _open("libXss.so.1")

D = c_void_p
W = XID

if x11:
    XInitThreads = _bind(x11, "XInitThreads", c_int)
    XOpenDisplay = _bind(x11, "XOpenDisplay", D, c_char_p)
    XCloseDisplay = _bind(x11, "XCloseDisplay", c_int, D)
    XDefaultRootWindow = _bind(x11, "XDefaultRootWindow", W, D)
    XDefaultScreen = _bind(x11, "XDefaultScreen", c_int, D)
    XDefaultVisual = _bind(x11, "XDefaultVisual", c_void_p, D, c_int)
    XDefaultDepth = _bind(x11, "XDefaultDepth", c_int, D, c_int)
    XConnectionNumber = _bind(x11, "XConnectionNumber", c_int, D)
    XInternAtom = _bind(x11, "XInternAtom", XID, D, c_char_p, Bool)
    XGetWindowProperty = _bind(x11, "XGetWindowProperty", c_int, D, W, XID, c_long, c_long, Bool, XID,
                               POINTER(XID), POINTER(c_int), POINTER(c_ulong), POINTER(c_ulong),
                               POINTER(POINTER(c_ubyte)))
    XChangeProperty = _bind(x11, "XChangeProperty", c_int, D, W, XID, XID, c_int, c_int, c_void_p, c_int)
    XFree = _bind(x11, "XFree", c_int, c_void_p)
    XQueryTree = _bind(x11, "XQueryTree", c_int, D, W, POINTER(W), POINTER(W), POINTER(POINTER(W)), POINTER(c_uint))
    XQueryPointer = _bind(x11, "XQueryPointer", Bool, D, W, POINTER(W), POINTER(W), POINTER(c_int), POINTER(c_int),
                          POINTER(c_int), POINTER(c_int), POINTER(c_uint))
    XTranslateCoordinates = _bind(x11, "XTranslateCoordinates", Bool, D, W, W, c_int, c_int, POINTER(c_int),
                                  POINTER(c_int), POINTER(W))
    XGetWindowAttributes = _bind(x11, "XGetWindowAttributes", c_int, D, W, POINTER(XWindowAttributes))
    XGetImage = _bind(x11, "XGetImage", POINTER(XImage), D, XID, c_int, c_int, c_uint, c_uint, c_ulong, c_int)
    XDestroyImage = _bind(x11, "XDestroyImage", c_int, POINTER(XImage))
    XCreateImage = _bind(x11, "XCreateImage", POINTER(XImage), D, c_void_p, c_uint, c_int, c_int, c_void_p, c_uint,
                         c_uint, c_int, c_int)
    XPutImage = _bind(x11, "XPutImage", c_int, D, XID, c_void_p, POINTER(XImage), c_int, c_int, c_int, c_int, c_uint,
                      c_uint)
    XCreateGC = _bind(x11, "XCreateGC", c_void_p, D, XID, c_ulong, c_void_p)
    XFreeGC = _bind(x11, "XFreeGC", c_int, D, c_void_p)
    XSync = _bind(x11, "XSync", c_int, D, Bool)
    XFlush = _bind(x11, "XFlush", c_int, D)
    XSetErrorHandler = _bind(x11, "XSetErrorHandler", c_void_p, ERROR_HANDLER)
    XCreateWindow = _bind(x11, "XCreateWindow", W, D, W, c_int, c_int, c_uint, c_uint, c_uint, c_int, c_uint,
                          c_void_p, c_ulong, POINTER(XSetWindowAttributes))
    XCreateColormap = _bind(x11, "XCreateColormap", XID, D, W, c_void_p, c_int)
    XMatchVisualInfo = _bind(x11, "XMatchVisualInfo", c_int, D, c_int, c_int, c_int, POINTER(XVisualInfo))
    XDestroyWindow = _bind(x11, "XDestroyWindow", c_int, D, W)
    XMapRaised = _bind(x11, "XMapRaised", c_int, D, W)
    XUnmapWindow = _bind(x11, "XUnmapWindow", c_int, D, W)
    XMoveResizeWindow = _bind(x11, "XMoveResizeWindow", c_int, D, W, c_int, c_int, c_uint, c_uint)
    XSetWindowBackground = _bind(x11, "XSetWindowBackground", c_int, D, W, c_ulong)
    XClearWindow = _bind(x11, "XClearWindow", c_int, D, W)
    XConfigureWindow = _bind(x11, "XConfigureWindow", c_int, D, W, c_uint, POINTER(XWindowChanges))
    XRaiseWindow = _bind(x11, "XRaiseWindow", c_int, D, W)
    XCreateBitmapFromData = _bind(x11, "XCreateBitmapFromData", XID, D, XID, c_char_p, c_uint, c_uint)
    XFreePixmap = _bind(x11, "XFreePixmap", c_int, D, XID)
    XSendEvent = _bind(x11, "XSendEvent", c_int, D, W, Bool, c_long, POINTER(XEvent))
    XKeysymToKeycode = _bind(x11, "XKeysymToKeycode", c_ubyte, D, c_ulong)
    XkbKeycodeToKeysym = _bind(x11, "XkbKeycodeToKeysym", c_ulong, D, c_ubyte, c_int, c_int)
    XStringToKeysym = _bind(x11, "XStringToKeysym", c_ulong, c_char_p)
    XDisplayKeycodes = _bind(x11, "XDisplayKeycodes", c_int, D, POINTER(c_int), POINTER(c_int))
    XGetKeyboardMapping = _bind(x11, "XGetKeyboardMapping", POINTER(c_ulong), D, c_ubyte, c_int, POINTER(c_int))
    XChangeKeyboardMapping = _bind(x11, "XChangeKeyboardMapping", c_int, D, c_int, c_int, POINTER(c_ulong), c_int)
    XGrabKey = _bind(x11, "XGrabKey", c_int, D, c_int, c_uint, W, Bool, c_int, c_int)
    XPending = _bind(x11, "XPending", c_int, D)
    XNextEvent = _bind(x11, "XNextEvent", c_int, D, POINTER(XEvent))
    XGetSelectionOwner = _bind(x11, "XGetSelectionOwner", W, D, XID)

if xtst:
    XTestFakeMotionEvent = _bind(xtst, "XTestFakeMotionEvent", c_int, D, c_int, c_int, c_int, c_ulong)
    XTestFakeButtonEvent = _bind(xtst, "XTestFakeButtonEvent", c_int, D, c_uint, Bool, c_ulong)
    XTestFakeKeyEvent = _bind(xtst, "XTestFakeKeyEvent", c_int, D, c_uint, Bool, c_ulong)

if xcomposite:
    XCompositeRedirectWindow = _bind(xcomposite, "XCompositeRedirectWindow", None, D, W, c_int)
    XCompositeUnredirectWindow = _bind(xcomposite, "XCompositeUnredirectWindow", None, D, W, c_int)
    XCompositeNameWindowPixmap = _bind(xcomposite, "XCompositeNameWindowPixmap", XID, D, W)

if xext:
    XShapeCombineRectangles = _bind(xext, "XShapeCombineRectangles", None, D, W, c_int, c_int, c_int,
                                    POINTER(XRectangle), c_int, c_int, c_int)
    XShapeCombineMask = _bind(xext, "XShapeCombineMask", None, D, W, c_int, c_int, c_int, XID, c_int)

if xss:
    XScreenSaverAllocInfo = _bind(xss, "XScreenSaverAllocInfo", POINTER(XScreenSaverInfo))
    XScreenSaverQueryInfo = _bind(xss, "XScreenSaverQueryInfo", c_int, D, XID, POINTER(XScreenSaverInfo))

# Errors arrive asynchronously, so they are kept per connection and read after an XSync.
_errors = {}


@ERROR_HANDLER
def _on_error(display, event):
    _errors[display] = event.contents.error_code
    return 0


def available():
    return bool(x11 and xtst and xcomposite and xext)


class Display:
    """One connection to the X server. Xlib wants each used by one thread at a time."""

    def __init__(self):
        self.d = XOpenDisplay(None)
        if not self.d:
            raise OSError("cannot open the X display")
        XSetErrorHandler(_on_error)
        self.root = XDefaultRootWindow(self.d)
        self.screen = XDefaultScreen(self.d)
        self._atoms = {}

    def atom(self, name):
        if name not in self._atoms:
            self._atoms[name] = XInternAtom(self.d, name.encode(), False)
        return self._atoms[name]

    def failed(self):
        """Syncs and tells whether a request since the last call raised an error."""
        XSync(self.d, False)
        return _errors.pop(self.d, None) is not None

    def prop(self, window, name, kind=0):
        """A property as bytes (format 8) or a list of numbers (formats 16 and 32), None when absent."""
        actual, fmt, n, after = XID(), c_int(), c_ulong(), c_ulong()
        data = POINTER(c_ubyte)()
        status = XGetWindowProperty(self.d, window, self.atom(name), 0, 1 << 16, False, kind, byref(actual),
                                    byref(fmt), byref(n), byref(after), byref(data))
        if status != 0 or not data:
            self.failed()
            return None
        try:
            if fmt.value == 8:
                return ctypes.string_at(data, n.value)
            item = c_ulong if fmt.value == 32 else ctypes.c_ushort
            return list(ctypes.cast(data, POINTER(item))[:n.value])
        finally:
            XFree(data)

    def set_prop(self, window, name, kind, values):
        array = (c_ulong * len(values))(*values)
        XChangeProperty(self.d, window, self.atom(name), self.atom(kind), 32, PropModeReplace, array, len(values))

    def tree(self, window):
        """The parent and the children of window, bottom of the stack first."""
        root, parent, children, n = W(), W(), POINTER(W)(), c_uint()
        if not XQueryTree(self.d, window, byref(root), byref(parent), byref(children), byref(n)):
            self.failed()
            return 0, []
        try:
            return parent.value, list(children[:n.value])
        finally:
            if children:
                XFree(children)

    def pointer(self):
        root, child, rx, ry, wx, wy, mask = W(), W(), c_int(), c_int(), c_int(), c_int(), c_uint()
        XQueryPointer(self.d, self.root, byref(root), byref(child), byref(rx), byref(ry), byref(wx), byref(wy),
                      byref(mask))
        return rx.value, ry.value, child.value, mask.value

    def translate(self, src, dst, x, y):
        dx, dy, child = c_int(), c_int(), W()
        XTranslateCoordinates(self.d, src, dst, x, y, byref(dx), byref(dy), byref(child))
        return dx.value, dy.value, child.value

    def attributes(self, window):
        a = XWindowAttributes()
        if not XGetWindowAttributes(self.d, window, byref(a)) or self.failed():
            return None
        return a

    def image(self, drawable, x, y, width, height):
        """The pixels as bytes in cairo's native layout with their stride, or None."""
        img = XGetImage(self.d, drawable, x, y, width, height, (1 << 64) - 1, ZPixmap)
        if not img or self.failed():
            return None
        try:
            i = img.contents
            if i.bits_per_pixel != 32:
                raise OSError("only 32 bit pixels are read")
            return bytearray(ctypes.string_at(i.data, i.bytes_per_line * i.height)), i.bytes_per_line, i.depth
        finally:
            XDestroyImage(img)

    def send_root(self, window, message, *values):
        ev = XEvent()
        ev.xclient.type = ClientMessage
        ev.xclient.window = window
        ev.xclient.message_type = self.atom(message)
        ev.xclient.format = 32
        for i, v in enumerate(values):
            ev.xclient.l[i] = v
        XSendEvent(self.d, self.root, False, SubstructureRedirectMask | SubstructureNotifyMask, byref(ev))
        XFlush(self.d)

    def idle_ms(self):
        if not xss:
            return None
        info = XScreenSaverAllocInfo()
        try:
            XScreenSaverQueryInfo(self.d, self.root, info)
            return info.contents.idle
        finally:
            XFree(info)

    def close(self):
        XCloseDisplay(self.d)
