// Built into KnightSight.exe by build.ps1. The panel owns the share; the pipe
// \\.\pipe\knightsight and the loopback port 47613 let mcp/knightsight-mcp.mjs look at it and
// act inside it, the port for a session on another machine that reaches it through SSH.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace KnightSight
{
    static class Native
    {
        [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
        [DllImport("user32.dll")] public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint mods, uint vk);
        [DllImport("user32.dll")] public static extern bool UnregisterHotKey(IntPtr hWnd, int id);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint attach, uint to, bool on);
        [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
        [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
        [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr hWnd, uint flags);
        [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
        [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder s, int max);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder s, int max);
        [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
        [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
        [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
        [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vk);
        [DllImport("user32.dll")] public static extern short VkKeyScan(char c);
        [DllImport("user32.dll")] public static extern uint SendInput(uint count, INPUT[] inputs, int size);
        [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr icon);
        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
        [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr hWnd, ref POINT p);
        [DllImport("user32.dll")] public static extern bool PhysicalToLogicalPointForPerMonitorDPI(IntPtr hWnd, ref POINT p);
        [DllImport("user32.dll")] public static extern IntPtr GetWindowDpiAwarenessContext(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll")] public static extern IntPtr ChildWindowFromPointEx(IntPtr hWnd, POINT p, uint flags);
        [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint thread, ref GUITHREADINFO info);
        [DllImport("user32.dll")] public static extern bool GetKeyboardState(byte[] state);
        [DllImport("user32.dll")] public static extern bool SetKeyboardState(byte[] state);
        [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
        [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hWnd, uint cmd);
        [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr hWnd, int index);
        [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int x, int y, int w, int h, uint flags);
        [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc proc, IntPtr param);
        [DllImport("user32.dll")] public static extern bool GetLastInputInfo(ref LASTINPUTINFO info);
        [DllImport("dwmapi.dll")] public static extern int DwmExtendFrameIntoClientArea(IntPtr hWnd, ref MARGINS margins);
        [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr hWnd, int attr, out RECT r, int size);
        [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr hWnd, int attr, out int value, int size);
        [DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr hWnd, int attr, ref int value, int size);
        [DllImport("user32.dll")] public static extern bool UpdateLayeredWindow(IntPtr hWnd, IntPtr dst, ref POINT at, ref SIZE size, IntPtr src, ref POINT from, int key, ref BLENDFUNCTION blend, int flags);
        [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr hWnd, IntPtr dc);
        [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleDC(IntPtr dc);
        [DllImport("gdi32.dll")] public static extern bool DeleteDC(IntPtr dc);
        [DllImport("gdi32.dll")] public static extern IntPtr SelectObject(IntPtr dc, IntPtr obj);
        [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr obj);

        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr param);

        [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
        [StructLayout(LayoutKind.Sequential)] public struct SIZE { public int Width, Height; }
        [StructLayout(LayoutKind.Sequential, Pack = 1)] public struct BLENDFUNCTION { public byte Op, Flags, Alpha, Format; }
        [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
        [StructLayout(LayoutKind.Sequential)] public struct MARGINS { public int Left, Right, Top, Bottom; }
        [StructLayout(LayoutKind.Sequential)] public struct GUITHREADINFO { public int cbSize, flags; public IntPtr active, focus, capture, menuOwner, moveSize, caret; public RECT caretRect; }
        [StructLayout(LayoutKind.Sequential)] public struct LASTINPUTINFO { public int cbSize; public uint dwTime; }
        [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }
        [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr dwExtraInfo; }
        [StructLayout(LayoutKind.Explicit)] public struct INPUTUNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
        [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public INPUTUNION u; }
    }

    class Refused : Exception
    {
        public Refused(string message) : base(message) { }
    }

    // What the person reads, in English or, on a German Windows, in German. Replies to the
    // MCP server stay English, since an assistant reads them.
    static class Say
    {
        static readonly bool german = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "de";

        static string Pick(string english, string deutsch) { return german ? deutsch : english; }

        public static readonly string Untitled = Pick("Untitled window", "Fenster ohne Titel");
        public static readonly string PickWindow = Pick("Choose window", "Fenster wählen");
        public static readonly string PickRegion = Pick("Choose region", "Bereich wählen");
        public static readonly string StartShare = Pick("Start sharing", "Freigabe starten");
        public static readonly string StopShare = Pick("Stop sharing", "Freigabe beenden");
        public static readonly string Close = Pick("Close", "Schließen");
        public static readonly string Minimise = Pick("Minimize", "Minimieren");
        public static readonly string NothingChosen = Pick("Nothing chosen yet", "Noch nichts gewählt");
        public static readonly string ClickTarget = Pick("Now click the window you want to share.", "Klick jetzt das Fenster an, das du freigeben willst.");
        public static readonly string ChooseTarget = Pick("Choose a window or a region.", "Wähl ein Fenster oder einen Bereich.");
        public static readonly string Doing = Pick("Now: ", "Gerade: ");
        public static readonly string Shared = Pick("Shared. Carry on as usual.", "Freigegeben. Du kannst normal weiterarbeiten.");
        public static readonly string WindowChosen = Pick("Window chosen, not shared yet.", "Fenster gewählt, noch nicht freigegeben.");
        public static readonly string RegionChosen = Pick("Region chosen, not shared yet.", "Bereich gewählt, noch nicht freigegeben.");
        public static readonly string Region = Pick("Region", "Bereich");
        public static readonly string Looking = Pick("Taking a screenshot", "Mache Screenshot");
        public static readonly string RightClicking = Pick("Right-clicking", "Rechtsklick");
        public static readonly string DoubleClicking = Pick("Double-clicking", "Doppelklick");
        public static readonly string Clicking = Pick("Clicking", "Klicke");
        public static readonly string Scrolling = Pick("Scrolling", "Scrolle");
        public static readonly string Typing = Pick("Typing", "Tippe");
        public static readonly string Pressing = Pick("Pressing ", "Drücke ");
        public static readonly string PressingKey = Pick("Pressing a key", "Drücke Taste");

        public static readonly Dictionary<string, string> KeyNames = german
            ? new Dictionary<string, string> { { "ctrl", "Strg" }, { "control", "Strg" }, { "strg", "Strg" }, { "shift", "Umschalt" }, { "escape", "Esc" }, { "pageup", "Bild auf" }, { "pagedown", "Bild ab" }, { "backspace", "Rücktaste" }, { "delete", "Entf" }, { "del", "Entf" } }
            : new Dictionary<string, string> { { "control", "Ctrl" }, { "strg", "Ctrl" }, { "escape", "Esc" }, { "pageup", "Page Up" }, { "pagedown", "Page Down" } };

        public static readonly string Help = Pick(
            "Grey frame: chosen, not shared yet.\n" +
            "Yellow frame: shared. Looking, clicking and typing happen\nonly inside it, and only when asked.\n" +
            "A pulsing frame means something is being done in there. Its top\nright corner says what, such as \"Typing\" or \"Taking a screenshot\".\n\n" +
            "Carry on working as usual. Mouse and keyboard stay\nwith you, even while the window is covered.\n" +
            "A minimized window is out of reach. Store apps come to the front\nfor a moment once mouse and keyboard rest for about a second.\n\n" +
            "Ctrl+Alt+Shift+X ends the share at once,\nand so does closing this window.",
            "Grauer Rahmen: gewählt, aber noch nicht freigegeben.\n" +
            "Gelber Rahmen: freigegeben. Angeschaut, geklickt und getippt\nwird nur darin, und erst auf Anfrage.\n" +
            "Pulsiert der Rahmen, wird gerade darin gearbeitet. Was genau,\nsteht oben rechts am Rahmen, etwa „Tippe“ oder „Mache Screenshot“.\n\n" +
            "Du kannst nebenbei normal weiterarbeiten. Maus und Tastatur\nbleiben bei dir, auch wenn das Fenster zugedeckt ist.\n" +
            "Minimiert ist es nicht erreichbar. Store-Apps kommen kurz nach vorn,\nsobald du gut eine Sekunde lang nichts eingibst.\n\n" +
            "Strg+Alt+Umschalt+X beendet die Freigabe sofort,\nSchließen beendet sie auch.");
    }

    // Window is zero when a region is shared. Focus is the window that took the
    // last click inside a region; keys only go there.
    class Share
    {
        public IntPtr Window;
        public Rectangle Region;
        public string Title;
        public volatile IntPtr Focus;

        public Rectangle Area { get { return Window == IntPtr.Zero ? Region : Win.Bounds(Window); } }
    }

    static class Win
    {
        public static IntPtr Root(IntPtr h) { return h == IntPtr.Zero ? h : Native.GetAncestor(h, 2); }

        public static IntPtr RootAt(int x, int y)
        {
            var p = new Native.POINT { X = x, Y = y };
            return Root(Native.WindowFromPoint(p));
        }

        // The DWM bounds leave out the invisible resize border that GetWindowRect counts.
        public static Rectangle Bounds(IntPtr h)
        {
            Native.RECT r;
            if (Native.DwmGetWindowAttribute(h, 9, out r, Marshal.SizeOf(typeof(Native.RECT))) != 0)
                Native.GetWindowRect(h, out r);
            return Rectangle.FromLTRB(r.Left, r.Top, r.Right, r.Bottom);
        }

        public static string Title(IntPtr h)
        {
            var s = new StringBuilder(256);
            Native.GetWindowText(h, s, s.Capacity);
            return s.Length > 0 ? s.ToString() : Say.Untitled;
        }

        public static string Class(IntPtr h)
        {
            var s = new StringBuilder(256);
            Native.GetClassName(h, s, s.Capacity);
            return s.ToString();
        }

        public const uint KeepPlace = 0x1 | 0x2 | 0x10;
        static readonly uint ownPid = (uint)Process.GetCurrentProcess().Id;

        public static bool IsOwn(IntPtr h)
        {
            uint pid;
            Native.GetWindowThreadProcessId(h, out pid);
            return pid == ownPid;
        }

        public static bool IsTopmost(IntPtr h) { return (Native.GetWindowLong(h, -20) & 0x8) != 0; }

        public static bool IsCloaked(IntPtr h)
        {
            int cloaked;
            return Native.DwmGetWindowAttribute(h, 14, out cloaked, sizeof(int)) == 0 && cloaked != 0;
        }

        public static IntPtr Above(IntPtr h) { return Native.GetWindow(h, 3); }

        public static bool IsOwnedBy(IntPtr h, IntPtr owner)
        {
            for (var o = Native.GetWindow(h, 4); o != IntPtr.Zero; o = Native.GetWindow(o, 4))
                if (o == owner) return true;
            return false;
        }

        // The menus and dialogs a window owns, topmost first. They are windows of their own,
        // so neither a picture of the owner nor a click on it reaches them.
        public static List<IntPtr> Popups(IntPtr root)
        {
            var found = new List<IntPtr>();
            Native.EnumWindows((h, p) =>
            {
                if (Native.IsWindowVisible(h) && !IsCloaked(h) && IsOwnedBy(h, root)) found.Add(h);
                return true;
            }, IntPtr.Zero);
            return found;
        }

        // A menu opens topmost, which would put it over whatever the person works in. Placed
        // right under the next window above the share it stays open and still takes clicks.
        public static void SinkPopups(IntPtr root)
        {
            var front = Native.GetForegroundWindow();
            if (front == root || IsOwnedBy(front, root)) return;
            var above = Above(root);
            while (above != IntPtr.Zero && (IsOwn(above) || IsOwnedBy(above, root))) above = Above(above);
            if (above == IntPtr.Zero || IsTopmost(above)) return;
            foreach (var popup in Popups(root))
                if (IsTopmost(popup)) Native.SetWindowPos(popup, above, 0, 0, 0, 0, KeepPlace);
        }

        public static bool IsFullyCovered(IntPtr root)
        {
            using (var bmp = new Bitmap(1, 1))
            using (var g = Graphics.FromImage(bmp))
            using (var open = new Region(Bounds(root)))
            {
                for (var w = Above(root); w != IntPtr.Zero; w = Above(w))
                    if (Native.IsWindowVisible(w) && !IsOwnedBy(w, root) && !IsCloaked(w) && (Native.GetWindowLong(w, -20) & 0x80) == 0)
                        open.Exclude(Bounds(w));
                return open.IsEmpty(g);
            }
        }

        public static bool IsChromium(IntPtr h) { return Class(h).StartsWith("Chrome_WidgetWin"); }

        public static bool IsBrowser(IntPtr h) { return IsChromium(h) || Class(h) == "MozillaWindowClass"; }

        // Store apps take input through a composition layer that ignores posted messages.
        public static bool NeedsForeground(IntPtr h)
        {
            var c = Class(h);
            return c == "ApplicationFrameWindow" || c == "Windows.UI.Core.CoreWindow";
        }

        public static IntPtr PopupAt(IntPtr root, Point at)
        {
            foreach (var popup in Popups(root))
                if (Bounds(popup).Contains(at)) return popup;
            return root;
        }

        public static IntPtr Deepest(IntPtr root, Point at)
        {
            var current = root;
            while (true)
            {
                // Skips invisible and transparent children.
                var child = Native.ChildWindowFromPointEx(current, ToClient(current, at), 0x1 | 0x4);
                if (child == IntPtr.Zero || child == current) return current;
                current = child;
            }
        }

        // In the units the window itself counts in, which differ from the screen's when it is not DPI aware.
        public static Native.POINT ToClient(IntPtr h, Point at)
        {
            var p = new Native.POINT { X = at.X, Y = at.Y };
            var before = Native.SetThreadDpiAwarenessContext(Native.GetWindowDpiAwarenessContext(h));
            Native.PhysicalToLogicalPointForPerMonitorDPI(h, ref p);
            Native.ScreenToClient(h, ref p);
            Native.SetThreadDpiAwarenessContext(before);
            return p;
        }

        // Each thread keeps its own focus, whether or not it is in front.
        public static IntPtr KeyTarget(IntPtr root)
        {
            uint pid;
            var info = new Native.GUITHREADINFO { cbSize = Marshal.SizeOf(typeof(Native.GUITHREADINFO)) };
            Native.GetGUIThreadInfo(Native.GetWindowThreadProcessId(root, out pid), ref info);
            return info.focus != IntPtr.Zero ? info.focus : root;
        }

        public static uint IdleMilliseconds()
        {
            var info = new Native.LASTINPUTINFO { cbSize = Marshal.SizeOf(typeof(Native.LASTINPUTINFO)) };
            Native.GetLastInputInfo(ref info);
            return unchecked((uint)Environment.TickCount - info.dwTime);
        }

        // A background process may only move the foreground while attached to the
        // input of the thread that has it.
        public static bool Activate(IntPtr h)
        {
            if (Native.GetForegroundWindow() == h) return true;
            uint pid;
            uint front = Native.GetWindowThreadProcessId(Native.GetForegroundWindow(), out pid);
            uint me = Native.GetCurrentThreadId();
            Native.AttachThreadInput(me, front, true);
            Native.SetForegroundWindow(h);
            Native.BringWindowToTop(h);
            Native.AttachThreadInput(me, front, false);
            Thread.Sleep(150);
            return Native.GetForegroundWindow() == h;
        }
    }

    static class Input
    {
        const uint KeyUp = 0x2, Unicode = 0x4, Extended = 0x1;

        static readonly Dictionary<string, ushort> Named = new Dictionary<string, ushort>
        {
            { "enter", 0x0D }, { "tab", 0x09 }, { "esc", 0x1B }, { "escape", 0x1B }, { "space", 0x20 },
            { "backspace", 0x08 }, { "delete", 0x2E }, { "del", 0x2E }, { "insert", 0x2D },
            { "home", 0x24 }, { "end", 0x23 }, { "pageup", 0x21 }, { "pagedown", 0x22 },
            { "up", 0x26 }, { "down", 0x28 }, { "left", 0x25 }, { "right", 0x27 },
        };
        static readonly HashSet<ushort> ExtendedKeys = new HashSet<ushort> { 0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27 };
        static readonly Dictionary<string, ushort> Modifiers = new Dictionary<string, ushort>
        {
            { "ctrl", 0x11 }, { "control", 0x11 }, { "strg", 0x11 }, { "alt", 0x12 }, { "shift", 0x10 },
        };

        static Native.INPUT Key(ushort vk, ushort scan, uint flags)
        {
            var i = new Native.INPUT { type = 1 };
            i.u.ki.wVk = vk;
            i.u.ki.wScan = scan;
            i.u.ki.dwFlags = flags | (ExtendedKeys.Contains(vk) ? Extended : 0);
            return i;
        }

        static Native.INPUT Mouse(uint flags, int data)
        {
            var i = new Native.INPUT { type = 0 };
            i.u.mi.dwFlags = flags;
            i.u.mi.mouseData = unchecked((uint)data);
            return i;
        }

        static void Send(List<Native.INPUT> inputs)
        {
            Native.SendInput((uint)inputs.Count, inputs.ToArray(), Marshal.SizeOf(typeof(Native.INPUT)));
        }

        public static void Click(int x, int y, bool right, bool twice)
        {
            Native.SetCursorPos(x, y);
            var inputs = new List<Native.INPUT>();
            for (int n = twice ? 2 : 1; n > 0; n--)
            {
                inputs.Add(Mouse(right ? 0x8u : 0x2u, 0));
                inputs.Add(Mouse(right ? 0x10u : 0x4u, 0));
            }
            Send(inputs);
        }

        public static void Scroll(int x, int y, int notches)
        {
            Native.SetCursorPos(x, y);
            Send(new List<Native.INPUT> { Mouse(0x800, -notches * 120) });
        }

        public static void Type(string text)
        {
            var inputs = new List<Native.INPUT>();
            foreach (char c in text)
            {
                if (c == '\r') continue;
                if (c == '\n' || c == '\t')
                {
                    ushort vk = c == '\n' ? (ushort)0x0D : (ushort)0x09;
                    inputs.Add(Key(vk, 0, 0));
                    inputs.Add(Key(vk, 0, KeyUp));
                    continue;
                }
                inputs.Add(Key(0, c, Unicode));
                inputs.Add(Key(0, c, Unicode | KeyUp));
            }
            Send(inputs);
        }

        // Reads ctrl+l, shift+tab or a single key into the modifiers and the key.
        static List<ushort> ParseCombo(string combo, out ushort key)
        {
            var held = new List<ushort>();
            key = 0;
            foreach (var raw in combo.ToLowerInvariant().Split('+'))
            {
                var part = raw.Trim();
                ushort vk;
                if (part == "win" || part == "windows" || part == "meta")
                    throw new Refused("The Windows key acts on the whole system and is refused.");
                if (Modifiers.TryGetValue(part, out vk)) { held.Add(vk); continue; }
                if (key != 0) throw new Refused("Only one key besides Ctrl, Alt and Shift: " + combo);
                if (Named.TryGetValue(part, out vk)) key = vk;
                else if (part.Length > 1 && part[0] == 'f' && ushort.TryParse(part.Substring(1), out vk) && vk >= 1 && vk <= 24) key = (ushort)(0x6F + vk);
                else if (part.Length == 1)
                {
                    short scan = Native.VkKeyScan(part[0]);
                    if (scan == -1) throw new Refused("This keyboard has no such key: " + part);
                    key = (ushort)(scan & 0xFF);
                    if ((scan & 0x100) != 0 && !held.Contains(0x10)) held.Add(0x10);
                }
                else throw new Refused("Unknown key: " + part);
            }
            if (key == 0) throw new Refused("The key itself is missing: " + combo);
            return held;
        }

        public static void Press(string combo)
        {
            ushort key;
            var held = ParseCombo(combo, out key);
            var inputs = new List<Native.INPUT>();
            foreach (var m in held) inputs.Add(Key(m, 0, 0));
            inputs.Add(Key(key, 0, 0));
            inputs.Add(Key(key, 0, KeyUp));
            for (int i = held.Count - 1; i >= 0; i--) inputs.Add(Key(held[i], 0, KeyUp));
            Send(inputs);
        }

        static void Post(IntPtr target, uint message, long wParam, long lParam)
        {
            if (Native.PostMessage(target, message, new IntPtr(wParam), new IntPtr(lParam))) return;
            if (Marshal.GetLastWin32Error() == 5) throw new Refused("The window runs as administrator and takes no input from here.");
            throw new Refused("The window takes no input right now.");
        }

        static long Packed(int x, int y) { return ((long)(ushort)y << 16) | (ushort)x; }

        public static void PostClick(IntPtr target, Point at, bool right, bool twice)
        {
            var client = Win.ToClient(target, at);
            long spot = Packed(client.X, client.Y), held = right ? 0x2 : 0x1;
            uint down = right ? 0x204u : 0x201u, up = right ? 0x205u : 0x202u, again = right ? 0x206u : 0x203u;
            Post(target, 0x200, 0, spot);
            Post(target, down, held, spot);
            Thread.Sleep(30);
            Post(target, up, 0, spot);
            if (!twice) return;
            Thread.Sleep(30);
            Post(target, again, held, spot);
            Post(target, up, 0, spot);
        }

        public static void PostWheel(IntPtr target, Point at, int notches)
        {
            long distance = (ushort)(short)(-notches * 120);
            Post(target, 0x20A, distance << 16, Packed(at.X, at.Y));
        }

        public static void PostText(IntPtr target, string text)
        {
            foreach (char c in text)
            {
                if (c == '\r') continue;
                if (c == '\n') PostKey(target, 0x0D, false);
                else if (c == '\t') PostKey(target, 0x09, false);
                else Post(target, 0x102, c, 1);
                Thread.Sleep(2);
            }
        }

        // The application's message loop turns the key into its character by itself.
        public static void PostKey(IntPtr target, ushort vk, bool alt)
        {
            long info = 1L | ((long)Native.MapVirtualKey(vk, 0) << 16);
            if (ExtendedKeys.Contains(vk)) info |= 1L << 24;
            if (alt) info |= 1L << 29;
            Post(target, alt ? 0x104u : 0x100u, vk, info);
            Thread.Sleep(15);
            Post(target, alt ? 0x105u : 0x101u, vk, info | 0xC0000000L);
        }

        // An application reads the modifiers from its own thread's key state. This sets that
        // state alone, so the person's keyboard stays out of it.
        public static void PostCombo(IntPtr root, IntPtr target, string combo)
        {
            ushort key;
            var held = ParseCombo(combo, out key);
            if (held.Count == 0) { PostKey(target, key, false); return; }

            uint pid, me = Native.GetCurrentThreadId(), them = Native.GetWindowThreadProcessId(root, out pid);
            if (!Native.AttachThreadInput(me, them, true)) throw new Refused("The window takes no input right now.");
            var state = new byte[256];
            Native.GetKeyboardState(state);
            var before = (byte[])state.Clone();
            try
            {
                foreach (var m in held)
                {
                    state[m] = 0x80;
                    state[m == 0x11 ? 0xA2 : m == 0x12 ? 0xA4 : 0xA0] = 0x80;
                }
                Native.SetKeyboardState(state);
                PostKey(target, key, held.Contains(0x12));
                // The application reads the state once it gets to the message, a little after the post.
                Thread.Sleep(100);
            }
            finally
            {
                Native.SetKeyboardState(before);
                Native.AttachThreadInput(me, them, false);
            }
        }
    }

    class Edge : Form
    {
        public Edge()
        {
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            Opacity = 0.9;
        }

        protected override bool ShowWithoutActivation { get { return true; } }

        // Tool window, click-through, never activated.
        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.ExStyle |= 0x80 | 0x20 | 0x08000000;
                return p;
            }
        }
    }

    // Four thin windows around the share, so nothing covers what is shared.
    class Frame
    {
        readonly Edge[] edges = { new Edge(), new Edge(), new Edge(), new Edge() };

        public void Show(Rectangle r, Color color, int width)
        {
            var o = Rectangle.Inflate(r, width, width);
            var sides = new[]
            {
                new Rectangle(o.Left, o.Top, o.Width, width),
                new Rectangle(o.Left, o.Bottom - width, o.Width, width),
                new Rectangle(o.Left, r.Top, width, r.Height),
                new Rectangle(o.Right - width, r.Top, width, r.Height),
            };
            for (int i = 0; i < 4; i++)
            {
                if (edges[i].BackColor != color) edges[i].BackColor = color;
                if (edges[i].Bounds != sides[i]) edges[i].Bounds = sides[i];
                if (!edges[i].Visible) edges[i].Show();
            }
        }

        public void Hide()
        {
            foreach (var e in edges) if (e.Visible) e.Hide();
        }

        public IEnumerable<Form> Windows { get { return edges; } }
    }

    // The label at the top right of the share that says what is being done in it. A
    // layered window, so the pill keeps its soft edges and shadow over any background.
    class Badge : Form
    {
        readonly Font font;
        readonly float k;

        public Badge(float k)
        {
            this.k = k;
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            font = new Font(Theme.SemiBold, 13 * k, GraphicsUnit.Pixel);
        }

        protected override bool ShowWithoutActivation { get { return true; } }

        // Layered tool window, click-through, never activated.
        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.ExStyle |= 0x80000 | 0x80 | 0x20 | 0x08000000;
                return p;
            }
        }

        float Shadow { get { return 8 * k; } }

        // Off a bitmap, not the window, so the pipe thread can measure too.
        public Size Measure(string text)
        {
            using (var bmp = new Bitmap(1, 1))
            using (var g = Graphics.FromImage(bmp))
            {
                var w = g.MeasureString(text, font).Width;
                return new Size((int)Math.Ceiling(w + 40 * k + 2 * Shadow), (int)Math.Ceiling(30 * k + 2 * Shadow));
            }
        }

        // Pulse runs from 0 to 1 and back; it lights the dot while something is being done.
        public void Draw(string text, Point at, float alpha, float pulse)
        {
            var size = Measure(text);
            using (var bmp = new Bitmap(size.Width, size.Height, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(bmp))
                {
                    Theme.Prepare(g);
                    float m = Shadow;
                    var pill = new RectangleF(m, m, size.Width - 2 * m, size.Height - 2 * m);
                    for (int i = 4; i >= 1; i--)
                        using (var path = Theme.Rounded(new RectangleF(pill.X - i * 1.5f * k, pill.Y - i * 1.5f * k + 2 * k, pill.Width + i * 3 * k, pill.Height + i * 3 * k), pill.Height / 2 + i * 1.5f * k))
                        using (var brush = new SolidBrush(Color.FromArgb(14, 0, 0, 0)))
                            g.FillPath(brush, path);
                    using (var path = Theme.Rounded(pill, pill.Height / 2))
                    using (var brush = new SolidBrush(Theme.Surface))
                        g.FillPath(brush, path);
                    float d = 8 * k, cx = pill.X + 14 * k, cy = pill.Y + pill.Height / 2;
                    using (var halo = new SolidBrush(Color.FromArgb((int)(90 * pulse), Theme.Warning)))
                        g.FillEllipse(halo, cx - d * 0.9f, cy - d * 0.9f, d * 1.8f, d * 1.8f);
                    using (var dot = new SolidBrush(Motion.Mix(Theme.Accent, Theme.Warning, pulse)))
                        g.FillEllipse(dot, cx - d / 2, cy - d / 2, d, d);
                    using (var ink = new SolidBrush(Theme.Text))
                    using (var format = new StringFormat { LineAlignment = StringAlignment.Center })
                        g.DrawString(text, font, ink, new RectangleF(pill.X + 26 * k, pill.Y, pill.Width, pill.Height), format);
                }
                if (!Visible) Show();
                Push(bmp, at, (byte)(255 * alpha));
            }
        }

        void Push(Bitmap bmp, Point at, byte alpha)
        {
            IntPtr screen = Native.GetDC(IntPtr.Zero), mem = Native.CreateCompatibleDC(screen);
            IntPtr hbmp = bmp.GetHbitmap(Color.FromArgb(0)), old = Native.SelectObject(mem, hbmp);
            try
            {
                var size = new Native.SIZE { Width = bmp.Width, Height = bmp.Height };
                var dst = new Native.POINT { X = at.X, Y = at.Y };
                var src = new Native.POINT();
                var blend = new Native.BLENDFUNCTION { Op = 0, Flags = 0, Alpha = alpha, Format = 1 };
                Native.UpdateLayeredWindow(Handle, screen, ref dst, ref size, mem, ref src, 0, ref blend, 2);
            }
            finally
            {
                Native.SelectObject(mem, old);
                Native.DeleteObject(hbmp);
                Native.DeleteDC(mem);
                Native.ReleaseDC(IntPtr.Zero, screen);
            }
        }
    }

    class RegionPicker : Form
    {
        Point start;
        Rectangle selection;
        bool dragging;
        public Rectangle Result { get; private set; }

        public RegionPicker()
        {
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            TopMost = true;
            StartPosition = FormStartPosition.Manual;
            Bounds = SystemInformation.VirtualScreen;
            BackColor = Color.Black;
            TransparencyKey = Color.Magenta;
            Opacity = 0.4;
            Cursor = Cursors.Cross;
            DoubleBuffered = true;
            KeyPreview = true;
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape) Close();
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) { Close(); return; }
            start = e.Location;
            dragging = true;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            if (!dragging) return;
            selection = Rectangle.FromLTRB(Math.Min(start.X, e.X), Math.Min(start.Y, e.Y), Math.Max(start.X, e.X), Math.Max(start.Y, e.Y));
            Invalidate();
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            if (!dragging) return;
            dragging = false;
            if (selection.Width >= 20 && selection.Height >= 20)
                Result = new Rectangle(selection.X + Left, selection.Y + Top, selection.Width, selection.Height);
            Close();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            if (selection.Width == 0) return;
            e.Graphics.FillRectangle(Brushes.Magenta, selection);
            using (var pen = new Pen(Color.White, 2)) e.Graphics.DrawRectangle(pen, selection);
        }
    }

    class Hotkeys : NativeWindow
    {
        readonly Action<int> pressed;

        public Hotkeys(Action<int> pressed)
        {
            this.pressed = pressed;
            CreateHandle(new CreateParams());
        }

        // Ctrl+Alt+Shift, without key repeat.
        public bool Register(int id, Keys key) { return Native.RegisterHotKey(Handle, id, 0x1 | 0x2 | 0x4 | 0x4000, (uint)key); }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == 0x0312) pressed(m.WParam.ToInt32());
            base.WndProc(ref m);
        }
    }

    // A brass spyglass across a steel frame: someone looking at what is shared. Drawn on a
    // 256 grid with the light from the top left, without smoothing at four times the size and
    // then scaled down, so the facets meet without hairlines and the clip's edges come out soft.
    public static class Logo
    {
        const float Grid = 256;
        const int Oversampling = 4;

        // From eyepiece to hood: start, end and half width of each part, rings and tubes taking turns.
        static readonly float[][] Parts =
        {
            new float[] { 0, 12, 15 }, new float[] { 12, 92, 13 }, new float[] { 92, 104, 22 }, new float[] { 104, 170, 19 },
            new float[] { 170, 182, 28 }, new float[] { 182, 250, 25 }, new float[] { 250, 264, 30 },
        };
        static readonly Color SteelLit = Color.FromArgb(184, 184, 184), SteelShade = Color.FromArgb(131, 131, 136),
            SteelDark = Color.FromArgb(102, 102, 107);
        static readonly Color BrassLit = Color.FromArgb(253, 216, 142), Brass = Color.FromArgb(233, 186, 87),
            BrassShade = Color.FromArgb(205, 147, 55), BrassDark = Color.FromArgb(145, 102, 49);
        static readonly Dictionary<int, Bitmap> drawn = new Dictionary<int, Bitmap>();

        public static Bitmap Render(int size)
        {
            using (var large = new Bitmap(size * Oversampling, size * Oversampling))
            {
                using (var g = Graphics.FromImage(large))
                {
                    g.ScaleTransform(large.Width / Grid, large.Height / Grid);
                    using (var tube = TubeArea())
                    using (var clear = new Region(tube))
                        g.ExcludeClip(clear);
                    DrawFrame(g);
                    g.ResetClip();
                    DrawTube(g);
                }
                var bmp = new Bitmap(size, size);
                using (var g = Graphics.FromImage(bmp))
                {
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    g.DrawImage(large, new Rectangle(0, 0, size, size));
                }
                return bmp;
            }
        }

        public static void Draw(Graphics g, float x, float y, float size)
        {
            int edge = (int)Math.Round(size);
            Bitmap bmp;
            if (!drawn.TryGetValue(edge, out bmp)) drawn[edge] = bmp = Render(edge);
            g.DrawImage(bmp, x, y, size, size);
        }

        static Matrix TubeAxis()
        {
            var m = new Matrix();
            m.Translate(36, 220);
            m.Rotate(-45);
            return m;
        }

        static GraphicsPath TubeArea()
        {
            // Straight edges for the narrow and the wide half, so the rings leave no slivers of frame.
            var path = new GraphicsPath(FillMode.Winding);
            path.AddRectangle(RectangleF.FromLTRB(-7, -20, 111, 20));
            path.AddRectangle(RectangleF.FromLTRB(97, -35, 271, 35));
            using (var axis = TubeAxis()) path.Transform(axis);
            return path;
        }

        static void DrawFrame(Graphics g)
        {
            const float outer0 = 44, outer1 = 212, step0 = 58, step1 = 198, inner0 = 72, inner1 = 184;
            Band(g, SteelLit, outer0, outer0, outer1, outer0, step1, step0, step0, step0);
            Band(g, SteelLit, outer0, outer0, step0, step0, step0, step1, outer0, outer1);
            Band(g, SteelDark, outer1, outer0, outer1, outer1, step1, step1, step1, step0);
            Band(g, SteelDark, outer0, outer1, step0, step1, step1, step1, outer1, outer1);
            Band(g, SteelShade, step0, step0, step1, step0, inner1, inner0, inner0, inner0);
            Band(g, SteelShade, step0, step0, inner0, inner0, inner0, inner1, step0, step1);
            Band(g, SteelLit, step1, step0, step1, step1, inner1, inner1, inner1, inner0);
            Band(g, SteelLit, step0, step1, inner0, inner1, inner1, inner1, step1, step1);
        }

        static void Band(Graphics g, Color color, float x0, float y0, float x1, float y1, float x2, float y2, float x3, float y3)
        {
            using (var brush = new SolidBrush(color))
                g.FillPolygon(brush, new[] { new PointF(x0, y0), new PointF(x1, y1), new PointF(x2, y2), new PointF(x3, y3) });
        }

        static void DrawTube(Graphics g)
        {
            var state = g.Save();
            using (var axis = TubeAxis()) g.MultiplyTransform(axis);
            for (int i = 0; i < Parts.Length; i++)
            {
                var p = Parts[i];
                bool ring = i % 2 == 0;
                Stripe(g, ring ? BrassShade : Brass, p, -1, 1);
                Stripe(g, ring ? Brass : BrassLit, p, -1, ring ? -0.3f : -0.42f);
                Stripe(g, ring ? BrassDark : BrassShade, p, ring ? 0.45f : 0.38f, 1);
            }
            g.Restore(state);
        }

        // A band along one part, its edges given as fractions of the half width.
        static void Stripe(Graphics g, Color color, float[] part, float from, float to)
        {
            using (var brush = new SolidBrush(color))
                g.FillRectangle(brush, RectangleF.FromLTRB(part[0], from * part[2], part[1], to * part[2]));
        }

        public static Icon MakeIcon(int size)
        {
            using (var bmp = Render(size))
            {
                var handle = bmp.GetHicon();
                var icon = (Icon)System.Drawing.Icon.FromHandle(handle).Clone();
                Native.DestroyIcon(handle);
                return icon;
            }
        }
    }

    // The GlimStone palette for the two themes, and Noto Sans, which the build embeds.
    static class Theme
    {
        public static readonly Color Accent = Color.FromArgb(252, 196, 25);
        public static readonly Color AccentHover = Color.FromArgb(253, 214, 94);
        public static readonly Color AccentInk = Color.FromArgb(22, 22, 22);
        public static readonly Color Warning = Color.FromArgb(255, 131, 43);
        public static readonly Color Neutral = Color.FromArgb(141, 141, 141);

        public static bool Dark;
        public static Color Ground, Surface, Surface2, Surface3, Hover, Text, Secondary, Muted;
        public static FontFamily Regular, SemiBold;
        static readonly System.Drawing.Text.PrivateFontCollection fonts = new System.Drawing.Text.PrivateFontCollection();

        public static void Load()
        {
            var v = Microsoft.Win32.Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1);
            Dark = v is int && (int)v == 0;
            Ground = Dark ? Color.FromArgb(22, 22, 22) : Color.FromArgb(244, 244, 244);
            Surface = Dark ? Color.FromArgb(38, 38, 38) : Color.White;
            Surface2 = Dark ? Color.FromArgb(57, 57, 57) : Color.FromArgb(232, 232, 232);
            Surface3 = Dark ? Color.FromArgb(82, 82, 82) : Color.FromArgb(209, 209, 209);
            Hover = Dark ? Color.FromArgb(53, 53, 53) : Color.FromArgb(224, 224, 224);
            Text = Dark ? Color.FromArgb(244, 244, 244) : Color.FromArgb(22, 22, 22);
            Secondary = Dark ? Color.FromArgb(198, 198, 198) : Color.FromArgb(82, 82, 82);
            Muted = Dark ? Color.FromArgb(141, 141, 141) : Color.FromArgb(111, 111, 111);

            foreach (var name in new[] { "NotoSans-Regular.ttf", "NotoSans-SemiBold.ttf" })
            {
                using (var stream = typeof(Theme).Assembly.GetManifestResourceStream(name))
                {
                    var data = new byte[stream.Length];
                    stream.Read(data, 0, data.Length);
                    // The collection reads the font from this memory for as long as it lives.
                    var mem = Marshal.AllocCoTaskMem(data.Length);
                    Marshal.Copy(data, 0, mem, data.Length);
                    fonts.AddMemoryFont(mem, data.Length);
                }
            }
            foreach (var f in fonts.Families)
            {
                if (f.Name.Contains("SemiBold")) SemiBold = f;
                else Regular = f;
            }
        }

        public static GraphicsPath Rounded(RectangleF r, float radius)
        {
            var p = new GraphicsPath();
            float d = Math.Min(radius * 2, Math.Min(r.Width, r.Height));
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        public static void Prepare(Graphics g)
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
        }
    }

    // The motion engine's lively numbers. With client-area animation off in Windows
    // every duration is zero, so a change lands at once instead of being skipped.
    static class Motion
    {
        [DllImport("user32.dll")] static extern bool SystemParametersInfo(uint action, uint param, ref int value, uint ini);

        static readonly bool on = Allowed();
        public static float Control { get { return on ? 150 : 0; } }
        public static float Content { get { return on ? 220 : 0; } }
        public const float PressScale = 0.96f;

        static bool Allowed()
        {
            int value = 1;
            SystemParametersInfo(0x1042, 0, ref value, 0);
            return value != 0;
        }

        public static float Step(float from, float to, float elapsed, float duration)
        {
            if (duration <= 0) return to;
            float d = elapsed / duration;
            return from < to ? Math.Min(to, from + d) : Math.Max(to, from - d);
        }

        public static float Ease(float t) { return 1 - (1 - t) * (1 - t) * (1 - t); }

        public static Color Mix(Color a, Color b, float t)
        {
            return Color.FromArgb(
                (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
        }
    }

    enum Glyph { None, Window, Region, Start, Stop, Info, Minimise, Close }

    // Line icons drawn in the button's ink, so they follow hover, theme and disabled state.
    static class Glyphs
    {
        public static void Draw(Graphics g, Glyph glyph, RectangleF b, Color ink, float k)
        {
            using (var pen = new Pen(ink, 1.6f * k) { LineJoin = LineJoin.Round, StartCap = LineCap.Round, EndCap = LineCap.Round })
            using (var brush = new SolidBrush(ink))
            {
                float s = b.Width;
                switch (glyph)
                {
                    case Glyph.Window:
                        var frame = new RectangleF(b.X + s * 0.06f, b.Y + s * 0.14f, s * 0.88f, s * 0.72f);
                        using (var path = Theme.Rounded(frame, 2.5f * k)) g.DrawPath(pen, path);
                        g.DrawLine(pen, frame.X, frame.Y + s * 0.24f, frame.Right, frame.Y + s * 0.24f);
                        break;
                    case Glyph.Region:
                        float a = s * 0.3f, l = b.X + s * 0.08f, t = b.Y + s * 0.08f, r = b.Right - s * 0.08f, bt = b.Bottom - s * 0.08f;
                        g.DrawLines(pen, new[] { new PointF(l, t + a), new PointF(l, t), new PointF(l + a, t) });
                        g.DrawLines(pen, new[] { new PointF(r - a, t), new PointF(r, t), new PointF(r, t + a) });
                        g.DrawLines(pen, new[] { new PointF(r, bt - a), new PointF(r, bt), new PointF(r - a, bt) });
                        g.DrawLines(pen, new[] { new PointF(l + a, bt), new PointF(l, bt), new PointF(l, bt - a) });
                        break;
                    case Glyph.Start:
                        using (var path = new GraphicsPath())
                        {
                            path.AddPolygon(new[] { new PointF(b.X + s * 0.22f, b.Y + s * 0.14f), new PointF(b.X + s * 0.86f, b.Y + s * 0.5f), new PointF(b.X + s * 0.22f, b.Y + s * 0.86f) });
                            g.FillPath(brush, path);
                            g.DrawPath(pen, path);
                        }
                        break;
                    case Glyph.Stop:
                        using (var path = Theme.Rounded(RectangleF.Inflate(b, -s * 0.18f, -s * 0.18f), 2 * k)) g.FillPath(brush, path);
                        break;
                    case Glyph.Info:
                        g.DrawEllipse(pen, RectangleF.Inflate(b, -0.8f * k, -0.8f * k));
                        float cx = b.X + s / 2, d = 2.2f * k;
                        g.FillEllipse(brush, cx - d / 2, b.Y + s * 0.27f - d / 2, d, d);
                        g.DrawLine(pen, cx, b.Y + s * 0.45f, cx, b.Y + s * 0.73f);
                        break;
                    case Glyph.Minimise:
                        using (var path = Theme.Rounded(new RectangleF(b.X, b.Y + s * 6 / 14, s, s * 2 / 14), s / 14))
                            g.FillPath(brush, path);
                        break;
                    case Glyph.Close:
                        var state = g.Save();
                        g.TranslateTransform(b.X + s / 2, b.Y + s / 2);
                        g.RotateTransform(45);
                        float arm = s * 1.1f / 10;
                        using (var path = Theme.Rounded(new RectangleF(-s / 2, -arm, s, 2 * arm), arm)) g.FillPath(brush, path);
                        using (var path = Theme.Rounded(new RectangleF(-arm, -s / 2, 2 * arm, s), arm)) g.FillPath(brush, path);
                        g.Restore(state);
                        break;
                }
            }
        }
    }

    // A rounded button: neutral on the card, the one filled accent button of the view, or a
    // blank control on the ground whose square lights up under the pointer.
    // Hover fades in and a press sinks it a little, both as transitions over Motion.Control.
    class SoftButton : Control
    {
        public bool Primary, Blank;
        public float Square;
        public Color Under;
        public float Radius;
        public Glyph Icon;
        public float K = 1;
        bool hover, down;
        float lit, sink;
        DateTime last;
        readonly System.Windows.Forms.Timer clock = new System.Windows.Forms.Timer { Interval = 15 };

        public SoftButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            Cursor = Cursors.Hand;
            clock.Tick += (o, e) => Advance();
        }

        protected override void OnMouseEnter(EventArgs e) { hover = true; Run(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; Run(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = e.Button == MouseButtons.Left; Run(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { down = false; Run(); base.OnMouseUp(e); }
        protected override void OnEnabledChanged(EventArgs e) { Cursor = Enabled ? Cursors.Hand : Cursors.Default; Run(); base.OnEnabledChanged(e); }
        protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }
        protected override void OnGotFocus(EventArgs e) { Invalidate(); base.OnGotFocus(e); }
        protected override void OnLostFocus(EventArgs e) { Invalidate(); base.OnLostFocus(e); }

        protected override void OnKeyUp(KeyEventArgs e)
        {
            if (Enabled && (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space)) OnClick(EventArgs.Empty);
            base.OnKeyUp(e);
        }

        void Run()
        {
            if (clock.Enabled) return;
            last = DateTime.UtcNow;
            clock.Start();
            Advance();
        }

        void Advance()
        {
            var now = DateTime.UtcNow;
            float elapsed = (float)(now - last).TotalMilliseconds;
            last = now;
            float litTo = hover && Enabled ? 1 : 0, sinkTo = down && Enabled ? 1 : 0;
            lit = Motion.Step(lit, litTo, elapsed, Motion.Control);
            sink = Motion.Step(sink, sinkTo, elapsed, Motion.Control);
            if (lit == litTo && sink == sinkTo) clock.Stop();
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            Theme.Prepare(g);
            g.Clear(Under);
            Color fill, ink;
            float t = Motion.Ease(lit);
            if (Blank) { fill = Motion.Mix(Under, Theme.Hover, t); ink = Motion.Mix(Theme.Secondary, Theme.Text, t); }
            else if (!Enabled) { fill = Theme.Surface2; ink = Theme.Muted; }
            else if (Primary) { fill = Motion.Mix(Theme.Accent, Theme.AccentHover, t); ink = Theme.AccentInk; }
            else { fill = Motion.Mix(Theme.Surface2, Theme.Surface3, t); ink = Theme.Text; }
            float scale = 1 - (1 - Motion.PressScale) * Motion.Ease(sink);
            float w = (Blank ? Square : Width - 1) * scale, h = (Blank ? Square : Height - 1) * scale;
            var r = new RectangleF((Width - 1 - w) / 2, (Height - 1 - h) / 2, w, h);
            using (var path = Theme.Rounded(r, Radius * scale))
            {
                using (var brush = new SolidBrush(fill)) g.FillPath(brush, path);
                if (Focused && ShowFocusCues)
                    using (var ring = new Pen(Theme.Accent, 2 * K)) g.DrawPath(ring, path);
            }

            float icon = Icon == Glyph.None ? 0 : 16 * K * scale, gap = Text.Length > 0 && icon > 0 ? 8 * K : 0;
            float textWidth = Text.Length > 0 ? g.MeasureString(Text, Font).Width : 0;
            float x = r.X + (r.Width - icon - gap - textWidth) / 2;
            if (icon > 0) Glyphs.Draw(g, Icon, new RectangleF(x, r.Y + (r.Height - icon) / 2, icon, icon), ink, K * scale);
            if (Text.Length == 0) return;
            using (var brush = new SolidBrush(ink))
            using (var format = new StringFormat { LineAlignment = StringAlignment.Center, FormatFlags = StringFormatFlags.NoWrap })
                g.DrawString(Text, Font, brush, new RectangleF(x + icon + gap, r.Y, textWidth + 2, r.Height), format);
        }
    }

    public class Panel : Form
    {
        const int MaxEdge = 1568, Port = 47613;
        const float PanelWidth = 580, PanelHeight = 212, BarHeight = 40, Gutter = 16;
        // A request less than this long ago counts as work in progress: frame and badge stay lit
        // through the pauses between the steps of one task.
        static readonly long WorkSpan = TimeSpan.FromSeconds(5).Ticks;
        const float PulsePeriod = 1400;
        static readonly HashSet<string> ShellClasses = new HashSet<string> { "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW" };

        readonly Frame frame = new Frame();
        readonly Badge badge;
        readonly Hotkeys hotkeys;
        readonly System.Windows.Forms.Timer tick = new System.Windows.Forms.Timer { Interval = 15 };
        readonly SoftButton pickWindow = new SoftButton { Icon = Glyph.Window }, pickRegion = new SoftButton { Icon = Glyph.Region },
            toggle = new SoftButton { Primary = true, Icon = Glyph.Start }, info = new SoftButton { Icon = Glyph.Info },
            minimise = new SoftButton { Blank = true, Icon = Glyph.Minimise }, close = new SoftButton { Blank = true, Icon = Glyph.Close };
        readonly ToolTip tip = new ToolTip { OwnerDraw = true, AutoPopDelay = 20000, InitialDelay = 200 };
        readonly Font titleFont, bodyFont, tipFont;
        readonly float k;
        readonly object gate = new object();
        string headline = "", subline = "", oldHeadline = "", oldSubline = "";
        float swap = 1, pulse, badgeAlpha;
        Color frameColor = Theme.Neutral, dotColor = Theme.Neutral;
        DateTime last = DateTime.UtcNow;
        volatile Share chosen;
        volatile bool active, badgeHeld;
        volatile string doing = "";
        long busyUntil, lastRequest;
        bool picking, buttonWasDown, working;

        RectangleF Card { get { return new RectangleF(S(Gutter), S(BarHeight), S(PanelWidth - 2 * Gutter), S(PanelHeight - BarHeight - Gutter)); } }

        public static void Run()
        {
            bool first;
            using (var mutex = new Mutex(true, @"Local\KnightSightPanel", out first))
            {
                if (!first) return;
                if (!Native.SetProcessDpiAwarenessContext(new IntPtr(-4))) Native.SetProcessDPIAware();
                Application.EnableVisualStyles();
                Theme.Load();
                Application.Run(new Panel());
            }
        }

        Panel()
        {
            using (var g = Graphics.FromHwnd(IntPtr.Zero)) k = g.DpiX / 96f;
            titleFont = new Font(Theme.SemiBold, S(16), GraphicsUnit.Pixel);
            bodyFont = new Font(Theme.Regular, S(13), GraphicsUnit.Pixel);
            tipFont = new Font(Theme.Regular, S(13), GraphicsUnit.Pixel);
            var buttonFont = new Font(Theme.SemiBold, S(14), GraphicsUnit.Pixel);

            Text = "KnightSight";
            Icon = Logo.MakeIcon((int)S(32));
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Theme.Ground;
            DoubleBuffered = true;
            Size = new Size((int)S(PanelWidth), (int)S(PanelHeight));
            badge = new Badge(k);

            var card = Card;
            float buttonsY = card.Bottom - S(20) - S(40);
            Place(pickWindow, Say.PickWindow, buttonFont, card.X + S(20), buttonsY + S(2), S(148), S(36));
            Place(pickRegion, Say.PickRegion, buttonFont, card.X + S(176), buttonsY + S(2), S(148), S(36));
            Place(toggle, Say.StartShare, buttonFont, card.Right - S(20) - S(176), buttonsY, S(176), S(40));
            Place(info, "", buttonFont, card.Right - S(20) - S(28), card.Y + S(18), S(28), S(28));
            info.Radius = S(14);
            info.Cursor = Cursors.Help;
            PlaceOnBar(close, Say.Close, PanelWidth - 44);
            PlaceOnBar(minimise, Say.Minimise, PanelWidth - 88);
            tip.SetToolTip(info, Say.Help);
            tip.Popup += (o, e) =>
            {
                using (var g = CreateGraphics())
                {
                    var size = g.MeasureString(tip.GetToolTip(e.AssociatedControl), tipFont);
                    e.ToolTipSize = new Size((int)(size.Width + S(24)), (int)(size.Height + S(16)));
                }
            };
            tip.Draw += (o, e) =>
            {
                Theme.Prepare(e.Graphics);
                using (var brush = new SolidBrush(Theme.Dark ? Theme.Surface2 : Color.FromArgb(38, 38, 38)))
                    e.Graphics.FillRectangle(brush, e.Bounds);
                using (var brush = new SolidBrush(Color.FromArgb(244, 244, 244)))
                    e.Graphics.DrawString(e.ToolTipText, tipFont, brush, S(12), S(8));
            };

            pickWindow.Click += (o, e) => StartPick();
            pickRegion.Click += (o, e) => PickRegion();
            toggle.Click += (o, e) => { if (active) Stop(); else Start(); };
            minimise.Click += (o, e) => WindowState = FormWindowState.Minimized;
            close.Click += (o, e) => Close();
            Controls.AddRange(new Control[] { pickWindow, pickRegion, toggle, info, minimise, close });

            hotkeys = new Hotkeys(id => Stop());
            hotkeys.Register(1, Keys.X);

            tick.Tick += OnTick;
            tick.Start();
            new Thread(ServePipe) { IsBackground = true }.Start();
            new Thread(ServePort) { IsBackground = true }.Start();
            ShowState();
        }

        float S(float v) { return v * k; }

        void Place(SoftButton b, string text, Font font, float x, float y, float w, float h)
        {
            b.Text = text;
            b.Font = font;
            b.Under = Theme.Surface;
            b.Radius = S(6);
            b.K = k;
            b.Bounds = Rectangle.Round(new RectangleF(x, y, w, h));
        }

        void PlaceOnBar(SoftButton b, string name, float x)
        {
            b.Under = Theme.Ground;
            b.Radius = S(6);
            b.K = k;
            b.Square = S(28);
            b.Bounds = Rectangle.Round(new RectangleF(S(x), 0, S(44), S(BarHeight)));
            tip.SetToolTip(b, name);
        }

        // The caption style stays so Windows keeps the shadow, the corners, snapping and the
        // minimise animation. The whole window counts as client area, and the bar takes the
        // part of the caption.
        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.Style |= 0x00C00000 | 0x00080000 | 0x00020000;
                return p;
            }
        }

        protected override void WndProc(ref Message m)
        {
            const int NcCalcSize = 0x83, NcHitTest = 0x84, HitClient = 1, HitCaption = 2;
            if (m.Msg == NcCalcSize && m.WParam != IntPtr.Zero)
            {
                m.Result = IntPtr.Zero;
                return;
            }
            if (m.Msg == NcHitTest)
            {
                int y = PointToClient(new Point((short)(m.LParam.ToInt64() & 0xFFFF), (short)((m.LParam.ToInt64() >> 16) & 0xFFFF))).Y;
                m.Result = new IntPtr(y < S(BarHeight) ? HitCaption : HitClient);
                return;
            }
            base.WndProc(ref m);
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            int on = Theme.Dark ? 1 : 0, rounded = 2, noBorder = unchecked((int)0xFFFFFFFE);
            Native.DwmSetWindowAttribute(Handle, 20, ref on, sizeof(int));
            Native.DwmSetWindowAttribute(Handle, 33, ref rounded, sizeof(int));
            Native.DwmSetWindowAttribute(Handle, 34, ref noBorder, sizeof(int));
            // A window with no frame of its own gets its shadow back from one row of DWM frame.
            var row = new Native.MARGINS { Bottom = 1 };
            Native.DwmExtendFrameIntoClientArea(Handle, ref row);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            Theme.Prepare(g);
            var card = Card;
            using (var path = Theme.Rounded(card, S(10)))
            using (var brush = new SolidBrush(Theme.Surface))
                g.FillPath(brush, path);

            float logo = S(52);
            Logo.Draw(g, card.X + S(20), card.Y + S(18), logo);
            float textX = card.X + S(20) + logo + S(16);
            var area = new RectangleF(textX, card.Y + S(20), info.Left - S(12) - textX, S(48));
            // The state dot: grey until shared, accent while shared, pulsing while work goes on.
            float d = S(8), dy = area.Y + S(26) + S(10);
            if (working && Motion.Control > 0)
                using (var halo = new SolidBrush(Color.FromArgb((int)(80 * pulse), Theme.Warning)))
                    g.FillEllipse(halo, area.X + d / 2 - d, dy - d, d * 2, d * 2);
            using (var brush = new SolidBrush(dotColor))
                g.FillEllipse(brush, area.X, dy - d / 2, d, d);
            // A new text slides up into place while the old one fades out above it.
            float t = Motion.Ease(swap), shift = S(6);
            if (t < 1) Texts(g, area, oldHeadline, oldSubline, 1 - t, -shift * t);
            Texts(g, area, headline, subline, t, shift * (1 - t));
        }

        void Texts(Graphics g, RectangleF area, string head, string sub, float alpha, float dy)
        {
            int a = (int)(255 * alpha);
            float indent = S(16);
            using (var format = new StringFormat { Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap })
            using (var title = new SolidBrush(Color.FromArgb(a, Theme.Text)))
            using (var body = new SolidBrush(Color.FromArgb(a, Theme.Secondary)))
            {
                g.DrawString(head, titleFont, title, new RectangleF(area.X, area.Y + dy, area.Width, S(24)), format);
                g.DrawString(sub, bodyFont, body, new RectangleF(area.X + indent, area.Y + S(26) + dy, area.Width - indent, S(20)), format);
            }
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            active = false;
            tick.Stop();
            frame.Hide();
            badge.Hide();
            hotkeys.DestroyHandle();
            base.OnFormClosed(e);
        }

        void ShowState()
        {
            var c = chosen;
            string head = c == null ? Say.NothingChosen : c.Window != IntPtr.Zero ? Win.Title(c.Window) : c.Title, sub;
            if (picking) sub = Say.ClickTarget;
            else if (c == null) sub = Say.ChooseTarget;
            else if (active && working) sub = Say.Doing + doing;
            else if (active) sub = Say.Shared;
            else sub = c.Window != IntPtr.Zero ? Say.WindowChosen : Say.RegionChosen;
            if (head != headline || sub != subline)
            {
                oldHeadline = headline;
                oldSubline = subline;
                headline = head;
                subline = sub;
                swap = 0;
            }
            pickWindow.Enabled = pickRegion.Enabled = !active;
            toggle.Enabled = c != null;
            toggle.Text = active ? Say.StopShare : Say.StartShare;
            toggle.Icon = active ? Glyph.Stop : Glyph.Start;
            Invalidate();
        }

        void StartPick()
        {
            picking = true;
            buttonWasDown = (Native.GetAsyncKeyState(0x01) & 0x8000) != 0;
            ShowState();
        }

        void PollPick()
        {
            bool down = (Native.GetAsyncKeyState(0x01) & 0x8000) != 0;
            if (buttonWasDown && !down)
            {
                Native.POINT p;
                Native.GetCursorPos(out p);
                var h = Win.RootAt(p.X, p.Y);
                if (h != IntPtr.Zero && !Win.IsOwn(h) && !ShellClasses.Contains(Win.Class(h)))
                {
                    picking = false;
                    chosen = new Share { Window = h, Title = Win.Title(h) };
                    ShowState();
                }
            }
            buttonWasDown = down;
        }

        void PickRegion()
        {
            picking = false;
            Hide();
            var picker = new RegionPicker();
            picker.FormClosed += (o, e) =>
            {
                var r = picker.Result;
                if (!r.IsEmpty) chosen = new Share { Region = r, Title = Say.Region + " " + r.Width + " x " + r.Height };
                Show();
                Activate();
                ShowState();
            };
            picker.Show();
            picker.Activate();
        }

        void Start()
        {
            if (chosen == null) return;
            active = true;
            ShowState();
        }

        void Stop()
        {
            active = false;
            ShowState();
        }

        void OnTick(object sender, EventArgs e)
        {
            var now = DateTime.UtcNow;
            float elapsed = (float)(now - last).TotalMilliseconds;
            last = now;
            if (swap < 1)
            {
                swap = Motion.Step(swap, 1, elapsed, Motion.Content);
                Invalidate();
            }
            if (picking) PollPick();

            bool nowWorking = active && now.Ticks - Interlocked.Read(ref lastRequest) < WorkSpan;
            bool moving = Motion.Control > 0;
            pulse = moving ? 0.5f - 0.5f * (float)Math.Cos(2 * Math.PI * (now.Ticks / 10000 % (long)PulsePeriod) / PulsePeriod) : 1;
            string shown = subline;
            if (nowWorking != working) { working = nowWorking; ShowState(); }
            else if (working && Say.Doing + doing != shown) ShowState();
            var dotTarget = !active ? Theme.Neutral : working ? Motion.Mix(Theme.Accent, Theme.Warning, pulse) : Theme.Accent;
            if (dotTarget != dotColor) { dotColor = dotTarget; Invalidate(); }

            var c = chosen;
            if (c == null) { frame.Hide(); HideBadge(); return; }
            if (c.Window != IntPtr.Zero)
            {
                if (!Native.IsWindow(c.Window))
                {
                    chosen = null;
                    active = false;
                    frame.Hide();
                    HideBadge();
                    ShowState();
                    return;
                }
                if (Native.IsIconic(c.Window) || Win.IsCloaked(c.Window)) { frame.Hide(); HideBadge(); return; }
            }

            int width = (int)Math.Round(S(3));
            Color target;
            if (!active) target = Theme.Neutral;
            else if (now.Ticks < Interlocked.Read(ref busyUntil)) target = Theme.Warning;
            else if (working) { target = Motion.Mix(Theme.Accent, Theme.Warning, pulse); width += (int)Math.Round(S(2) * pulse); }
            else target = Theme.Accent;
            float step = !moving || working ? 1 : Math.Min(1, elapsed / Motion.Control);
            frameColor = Motion.Mix(frameColor, target, step);
            var area = c.Area;
            frame.Show(area, frameColor, width);
            Stack(c);

            badgeAlpha = Motion.Step(badgeAlpha, working ? 1 : 0, elapsed, Motion.Content);
            if (badgeAlpha <= 0 || badgeHeld) { HideBadge(); return; }
            var text = doing;
            badge.Draw(text, BadgeSpot(area, badge.Measure(text)), Motion.Ease(badgeAlpha), pulse);
        }

        void HideBadge()
        {
            if (badge.Visible) badge.Hide();
        }

        // Frame and badge sit right above a shared window: high enough to show, and no higher,
        // so a window the person has laid over the share stays clear of them.
        void Stack(Share s)
        {
            var marks = new List<Form>(frame.Windows) { badge };
            bool top = s.Window == IntPtr.Zero || Win.IsTopmost(s.Window);
            foreach (var mark in marks) if (mark.TopMost != top) mark.TopMost = top;
            if (top) return;
            if (active) Win.SinkPopups(s.Window);

            var handles = new List<IntPtr>();
            foreach (var mark in marks) if (mark.Visible) handles.Add(mark.Handle);
            int seen = 0;
            var w = Win.Above(s.Window);
            while (w != IntPtr.Zero && (handles.Contains(w) || Win.IsOwnedBy(w, s.Window)))
            {
                if (handles.Contains(w)) seen++;
                w = Win.Above(w);
            }
            if (seen == handles.Count) return;
            foreach (var h in handles)
            {
                if (w != IntPtr.Zero && !Win.IsTopmost(w))
                {
                    Native.SetWindowPos(h, w, 0, 0, 0, 0, Win.KeepPlace);
                    continue;
                }
                // The share leads the normal windows. Windows ignores HWND_TOP from a program in
                // the background, but dropping back from topmost lands on top of them too.
                Native.SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, Win.KeepPlace);
                Native.SetWindowPos(h, new IntPtr(-2), 0, 0, 0, 0, Win.KeepPlace);
            }
        }

        // Above the top right corner of the frame, or inside it when the share reaches the top of its screen.
        Point BadgeSpot(Rectangle area, Size size)
        {
            int shadow = (int)S(8), gap = (int)S(6), outer = (int)S(5);
            int x = area.Right + outer - size.Width + shadow;
            int y = area.Top - outer - gap - size.Height + shadow;
            if (y < Screen.FromRectangle(area).Bounds.Top)
            {
                x = area.Right - (int)S(10) - size.Width + shadow;
                y = area.Top + (int)S(10) - shadow;
            }
            return new Point(x, y);
        }

        bool BadgeInside(Rectangle area)
        {
            var size = badge.Measure(doing);
            var spot = BadgeSpot(area, size);
            return spot.Y + size.Height > area.Top && spot.Y < area.Bottom;
        }

        void ServePipe()
        {
            while (true)
            {
                try
                {
                    using (var pipe = new NamedPipeServerStream("knightsight", PipeDirection.InOut, 1))
                    {
                        pipe.WaitForConnection();
                        Talk(pipe);
                    }
                }
                catch (IOException) { }
            }
        }

        // Loopback only: the port is reached through an SSH tunnel, never from the network.
        void ServePort()
        {
            TcpListener listener;
            try
            {
                listener = new TcpListener(IPAddress.Loopback, Port);
                listener.Start();
            }
            catch (SocketException) { return; }
            while (true)
            {
                var client = listener.AcceptTcpClient();
                new Thread(() =>
                {
                    using (client)
                    {
                        try { Talk(client.GetStream()); }
                        catch (IOException) { }
                    }
                }) { IsBackground = true }.Start();
            }
        }

        void Talk(Stream stream)
        {
            var utf8 = new UTF8Encoding(false);
            var reader = new StreamReader(stream, utf8);
            var writer = new StreamWriter(stream, utf8) { AutoFlush = true };
            string line;
            while ((line = reader.ReadLine()) != null) writer.WriteLine(Answer(line));
        }

        static string Describe(string cmd, Dictionary<string, object> args)
        {
            switch (cmd)
            {
                case "look": return Say.Looking;
                case "click": return Flag(args, "right") ? Say.RightClicking : Flag(args, "double") ? Say.DoubleClicking : Say.Clicking;
                case "scroll": return Say.Scrolling;
                case "type": return Say.Typing;
                case "key":
                    object v;
                    return args.TryGetValue("keys", out v) && v is string ? Say.Pressing + KeyName((string)v) : Say.PressingKey;
                default: return cmd;
            }
        }

        static string KeyName(string combo)
        {
            var parts = combo.Split('+');
            for (int i = 0; i < parts.Length; i++)
            {
                var p = parts[i].Trim().ToLowerInvariant();
                string name;
                parts[i] = Say.KeyNames.TryGetValue(p, out name) ? name : p.Length == 0 ? p : char.ToUpperInvariant(p[0]) + p.Substring(1);
            }
            return string.Join("+", parts);
        }

        // One request at a time, whether it comes through the pipe or the port.
        string Answer(string line)
        {
            lock (gate) return Reply(line);
        }

        string Reply(string line)
        {
            var json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
            var reply = new Dictionary<string, object>();
            try
            {
                var args = json.Deserialize<Dictionary<string, object>>(line);
                var s = chosen;
                if (s == null || !active) throw new Refused("Nothing is shared right now. Choose a window or a region in the KnightSight window and start sharing.");
                if (s.Window != IntPtr.Zero && Native.IsIconic(s.Window)) throw new Refused("The shared window is minimized.");
                var cmd = Str(args, "cmd");
                doing = Describe(cmd, args);
                Interlocked.Exchange(ref lastRequest, DateTime.UtcNow.Ticks);
                switch (cmd)
                {
                    case "look": Look(s, reply); break;
                    case "click": reply["message"] = ClickAt(s, args); break;
                    case "scroll": reply["message"] = ScrollAt(s, args); break;
                    case "type": reply["message"] = TypeIn(s, Str(args, "text")); break;
                    case "key": reply["message"] = PressIn(s, Str(args, "keys")); break;
                    default: throw new Refused("Unknown command: " + cmd);
                }
                reply["ok"] = true;
            }
            catch (Refused e) { reply.Clear(); reply["ok"] = false; reply["error"] = e.Message; }
            catch (Exception e) { reply.Clear(); reply["ok"] = false; reply["error"] = e.GetType().Name + ": " + e.Message; }
            return json.Serialize(reply);
        }

        static string Str(Dictionary<string, object> args, string key)
        {
            object v;
            if (!args.TryGetValue(key, out v) || !(v is string)) throw new Refused("Missing " + key + ".");
            return (string)v;
        }

        static double Number(Dictionary<string, object> args, string key)
        {
            object v;
            if (!args.TryGetValue(key, out v) || v == null) throw new Refused("Missing " + key + ".");
            return Convert.ToDouble(v);
        }

        static bool Flag(Dictionary<string, object> args, string key)
        {
            object v;
            return args.TryGetValue(key, out v) && v is bool && (bool)v;
        }

        static double Scale(Size size)
        {
            return Math.Min(1.0, (double)MaxEdge / Math.Max(size.Width, size.Height));
        }

        void Busy()
        {
            Interlocked.Exchange(ref busyUntil, DateTime.UtcNow.AddMilliseconds(800).Ticks);
        }

        void Look(Share s, Dictionary<string, object> reply)
        {
            using (var shot = s.Window != IntPtr.Zero ? CaptureWindow(s.Window) : CaptureRegionClear(s.Region))
            {
                double scale = Scale(shot.Size);
                int w = Math.Max(1, (int)Math.Round(shot.Width * scale)), h = Math.Max(1, (int)Math.Round(shot.Height * scale));
                using (var small = new Bitmap(w, h))
                {
                    using (var g = Graphics.FromImage(small))
                    {
                        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        g.DrawImage(shot, 0, 0, w, h);
                    }
                    using (var ms = new MemoryStream())
                    {
                        small.Save(ms, ImageFormat.Png);
                        reply["image"] = Convert.ToBase64String(ms.ToArray());
                    }
                }
                reply["width"] = w;
                reply["height"] = h;
                reply["title"] = s.Window != IntPtr.Zero ? Win.Title(s.Window) : s.Title;
                if (s.Window != IntPtr.Zero && Win.IsChromium(s.Window) && Win.IsFullyCovered(s.Window))
                    reply["note"] = "The window is fully covered. Chromium programs stop drawing then, so the picture may be out of date.";
            }
        }

        // PrintWindow draws the window itself, so whatever lies on top of it stays private.
        static Bitmap CaptureWindow(IntPtr h)
        {
            var visible = Win.Bounds(h);
            Rectangle full;
            using (var whole = Print(h, out full))
            {
                if (whole == null) throw new Refused("The shared window has no size right now.");
                var crop = new Rectangle(visible.X - full.X, visible.Y - full.Y, visible.Width, visible.Height);
                crop.Intersect(new Rectangle(Point.Empty, full.Size));
                var shot = whole.Clone(crop, PixelFormat.Format32bppArgb);
                var popups = Win.Popups(h);
                popups.Reverse();
                using (var g = Graphics.FromImage(shot))
                    foreach (var popup in popups)
                    {
                        Rectangle at;
                        using (var picture = Print(popup, out at))
                            if (picture != null) g.DrawImage(picture, at.X - visible.X, at.Y - visible.Y);
                    }
                return shot;
            }
        }

        static Bitmap Print(IntPtr h, out Rectangle bounds)
        {
            Native.RECT r;
            Native.GetWindowRect(h, out r);
            bounds = Rectangle.FromLTRB(r.Left, r.Top, r.Right, r.Bottom);
            if (bounds.Width <= 0 || bounds.Height <= 0) return null;
            var bmp = new Bitmap(bounds.Width, bounds.Height, PixelFormat.Format32bppArgb);
            using (var g = Graphics.FromImage(bmp))
            {
                var hdc = g.GetHdc();
                try { Native.PrintWindow(h, hdc, 2); }
                finally { g.ReleaseHdc(hdc); }
            }
            return bmp;
        }

        // A region is copied off the screen, so a badge sitting inside it steps away for the shot.
        Bitmap CaptureRegionClear(Rectangle r)
        {
            if (!BadgeInside(r)) return CaptureRegion(r);
            badgeHeld = true;
            try
            {
                Invoke((MethodInvoker)HideBadge);
                Thread.Sleep(40);
                return CaptureRegion(r);
            }
            finally { badgeHeld = false; }
        }

        static Bitmap CaptureRegion(Rectangle r)
        {
            var bmp = new Bitmap(r.Width, r.Height, PixelFormat.Format32bppArgb);
            using (var g = Graphics.FromImage(bmp)) g.CopyFromScreen(r.Location, Point.Empty, r.Size);
            return bmp;
        }

        // Picture coordinates back to the screen, refused outside the share.
        static Point ToScreen(Share s, Dictionary<string, object> args)
        {
            var area = s.Area;
            double scale = Scale(area.Size);
            int x = area.X + (int)Math.Round(Number(args, "x") / scale);
            int y = area.Y + (int)Math.Round(Number(args, "y") / scale);
            if (!area.Contains(x, y)) throw new Refused("The point lies outside the share.");
            return new Point(x, y);
        }

        // The window a click at this point belongs to. In a region that is whatever shows there.
        static IntPtr RootFor(Share s, Point p)
        {
            if (s.Window != IntPtr.Zero) return s.Window;
            var root = Win.RootAt(p.X, p.Y);
            if (root == IntPtr.Zero || Win.IsOwn(root)) throw new Refused("No window that takes input lies at this point.");
            return root;
        }

        // For windows that only listen to real input: waits for a pause in the person's own
        // input, takes the front for a moment and gives it back with the pointer where it was.
        void Foreground(IntPtr root, Action act)
        {
            var giveUp = DateTime.UtcNow.AddSeconds(8);
            while (Win.IdleMilliseconds() < 1200)
            {
                if (DateTime.UtcNow > giveUp) throw new Refused("This window needs the foreground for a moment, but the mouse or keyboard is in use.");
                Thread.Sleep(100);
            }
            Native.POINT cursor;
            Native.GetCursorPos(out cursor);
            var front = Native.GetForegroundWindow();
            if (!Win.Activate(root)) throw new Refused("The shared window cannot be brought to the front.");
            try
            {
                act();
                Thread.Sleep(150);
            }
            finally
            {
                Native.SetCursorPos(cursor.X, cursor.Y);
                Win.Activate(front);
            }
        }

        string ClickAt(Share s, Dictionary<string, object> args)
        {
            var p = ToScreen(s, args);
            bool right = Flag(args, "right"), twice = Flag(args, "double");
            var root = RootFor(s, p);
            if (s.Window == IntPtr.Zero) s.Focus = root;
            Busy();
            if (Win.NeedsForeground(root))
            {
                Foreground(root, () => Input.Click(p.X, p.Y, right, twice));
                return "Clicked, briefly in the foreground.";
            }
            if (right && Win.IsChromium(root)) throw new Refused("Chromium programs take no right-click in the background. Their menus would stop responding.");
            Input.PostClick(Win.Deepest(Win.PopupAt(root, p), p), p, right, twice);
            return "Clicked.";
        }

        string ScrollAt(Share s, Dictionary<string, object> args)
        {
            var p = ToScreen(s, args);
            int notches = (int)Math.Round(Number(args, "amount"));
            var root = RootFor(s, p);
            Busy();
            if (Win.NeedsForeground(root))
            {
                Foreground(root, () => Input.Scroll(p.X, p.Y, notches));
                return "Scrolled, briefly in the foreground.";
            }
            // A browser drops the wheel when another window shows at that spot.
            var showing = Win.RootAt(p.X, p.Y);
            if (Win.IsBrowser(root) && showing != root && !Win.IsOwnedBy(showing, root))
            {
                var target = Win.KeyTarget(root);
                for (int i = 3 * Math.Abs(notches); i > 0; i--) Input.PostKey(target, notches > 0 ? (ushort)0x28 : (ushort)0x26, false);
                return "Scrolled with the arrow keys, since the spot is covered. They act where the last click went.";
            }
            Input.PostWheel(Win.Deepest(Win.PopupAt(root, p), p), p, notches);
            return "Scrolled.";
        }

        // In a region keys go to the window last clicked there, wherever it has moved since.
        static IntPtr KeyRoot(Share s)
        {
            if (s.Window != IntPtr.Zero) return s.Window;
            if (s.Focus == IntPtr.Zero || !Native.IsWindow(s.Focus))
                throw new Refused("Keys go to the window last clicked inside the region, and nothing has been clicked there yet.");
            return s.Focus;
        }

        string TypeIn(Share s, string text)
        {
            var root = KeyRoot(s);
            Busy();
            if (Win.NeedsForeground(root))
            {
                Foreground(root, () => Input.Type(text));
                return "Typed, briefly in the foreground.";
            }
            Input.PostText(Win.KeyTarget(root), text);
            return "Typed.";
        }

        string PressIn(Share s, string keys)
        {
            var root = KeyRoot(s);
            Busy();
            // Chromium only runs key combinations in a window that really is active.
            if (Win.NeedsForeground(root) || (Win.IsChromium(root) && keys.Contains("+")))
            {
                Foreground(root, () => Input.Press(keys));
                return "Pressed, briefly in the foreground.";
            }
            Input.PostCombo(root, Win.KeyTarget(root), keys);
            return "Pressed.";
        }
    }

    static class Program
    {
        [STAThread]
        static void Main() { Panel.Run(); }
    }
}
