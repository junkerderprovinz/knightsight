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
using System.Windows.Automation;
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
        [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int cmd);
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
        [DllImport("gdi32.dll")] public static extern IntPtr AddFontMemResourceEx(IntPtr font, uint length, IntPtr reserved, ref uint count);
        [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool SetWindowDisplayAffinity(IntPtr hWnd, uint affinity);
        [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
        [DllImport("kernel32.dll")] public static extern bool GetProcessTimes(IntPtr process, out long created, out long exited, out long kernel, out long user);
        [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr handle);

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
        public static readonly string PickWindow = Pick("Window", "Fenster");
        public static readonly string PickRegion = Pick("Region", "Bereich");
        public static readonly string PickWindowTip = Pick("Choose the window to share", "Fenster zum Freigeben wählen");
        public static readonly string PickRegionTip = Pick("Choose a region of the screen", "Bereich des Bildschirms wählen");
        public static readonly string PickScreen = Pick("Screen", "Bildschirm");
        public static readonly string PickScreenTip = Pick("Share a whole screen", "Einen ganzen Bildschirm freigeben");
        public static readonly string ClickScreen = Pick("Click to share this screen", "Klick, um diesen Bildschirm freizugeben");
        public static readonly string NoTarget = Pick("No target", "Kein Ziel");
        public static readonly string StartShare = Pick("Start sharing", "Freigabe starten");
        public static readonly string StopShare = Pick("Stop sharing", "Freigabe beenden");
        public static readonly string Close = Pick("Close", "Schließen");
        public static readonly string Minimise = Pick("Minimize", "Minimieren");
        public static readonly string NothingChosen = Pick("Nothing chosen yet", "Noch nichts gewählt");
        public static readonly string ClickTarget = Pick("Now click the window you want to share.", "Klick jetzt das Fenster an, das du freigeben willst.");
        public static readonly string ChooseTarget = Pick("Choose what to share.", "Wähl, was du freigeben willst.");
        public static readonly string Doing = Pick("Now: ", "Gerade: ");
        public static readonly string Shared = Pick("Shared. Carry on as usual.", "Freigegeben. Du kannst normal weiterarbeiten.");
        public static readonly string WindowChosen = Pick("Window chosen, not shared yet.", "Fenster gewählt, noch nicht freigegeben.");
        public static readonly string RegionChosen = Pick("Region chosen, not shared yet.", "Bereich gewählt, noch nicht freigegeben.");
        public static readonly string ScreenChosen = Pick("Screen chosen, not shared yet.", "Bildschirm gewählt, noch nicht freigegeben.");
        public static readonly string Region = Pick("Region", "Bereich");
        public static readonly string Looking = Pick("Taking a screenshot", "Mache Screenshot");
        public static readonly string RightClicking = Pick("Right-clicking", "Rechtsklick");
        public static readonly string DoubleClicking = Pick("Double-clicking", "Doppelklick");
        public static readonly string Clicking = Pick("Clicking", "Klicke");
        public static readonly string Scrolling = Pick("Scrolling", "Scrolle");
        public static readonly string Typing = Pick("Typing", "Tippe");
        public static readonly string Pressing = Pick("Pressing ", "Drücke ");
        public static readonly string PressingKey = Pick("Pressing a key", "Drücke Taste");

        public static readonly string Pinboard = Pick("Pinboard", "Pinnwand");
        public static readonly string PinboardTip = Pick("Pinboard (Ctrl+Shift+A)", "Pinnwand (Strg+Umschalt+A)");
        public static readonly string PinboardOn = Pick("Pinboard on. Drag a box or click to set a pin.", "Pinnwand an. Markier eine Stelle oder setz eine Nadel.");
        public static readonly string Fetched = Pick("Your assistant has fetched your notes.", "Dein Assistent hat deine Notizen abgeholt.");
        public static readonly string[] Kinds = { Pick("Bug", "Fehler"), Pick("Wish", "Wunsch"), Pick("Question", "Frage") };
        public static readonly string NewNote = Pick("New note", "Neue Notiz");
        public static readonly string NotePlaceholder = Pick("What should your assistant know about this spot?", "Was soll dein Assistent zu dieser Stelle wissen?");
        public static readonly string AuthorPlaceholder = Pick("Your name", "Dein Name");
        public static readonly string MoreSpots = Pick("Hold Shift to add more spots to this note.", "Mit Umschalt markierst du weitere Stellen dazu.");
        public static readonly string Save = Pick("Save", "Speichern");
        public static readonly string Delete = Pick("Delete", "Löschen");
        public static readonly string EmptyBoard = Pick("Drag a box around a spot or click to set a pin.", "Zieh ein Rechteck um eine Stelle oder klick für eine Nadel.");
        public static readonly string GoThere = Pick("Go there", "Hingehen");
        public static readonly string SaveFile = Pick("Save as file", "Als Datei speichern");
        public static readonly string Done = Pick("Done", "Fertig");
        public static readonly string ClosePinboard = Pick("Close pinboard", "Pinnwand schließen");
        public static readonly string FileKind = Pick("Pinboard notes", "Pinnwand-Notizen");
        public static readonly string FileName = Pick("knightsight-notes.html", "knightsight-notizen.html");
        public static readonly string Language = Pick("en", "de");

        public static string Spots(int count) { return count + Pick(" spots", " Stellen"); }
        public static string ScreenTitle(int number, Size size) { return Pick("Screen ", "Bildschirm ") + number + " (" + size.Width + " x " + size.Height + ")"; }
        public static string NoteTitle(int number) { return Pick("Note ", "Notiz ") + number; }
        public static string Round(int number) { return Pick("Round ", "Runde ") + number; }
        public static string From(string author) { return Pick("from ", "von ") + author; }
        public static string NotesOn(string title) { return Pick("Pinboard notes on ", "Pinnwand-Notizen zu ") + title; }

        public static string Sent(int count)
        {
            return count == 1
                ? Pick("Sent 1 note. Your assistant can fetch it now.", "1 Notiz gesendet. Dein Assistent kann sie abholen.")
                : Pick("Sent " + count + " notes. Your assistant can fetch them now.", count + " Notizen gesendet. Dein Assistent kann sie abholen.");
        }

        public static readonly Dictionary<string, string> KeyNames = german
            ? new Dictionary<string, string> { { "ctrl", "Strg" }, { "control", "Strg" }, { "strg", "Strg" }, { "shift", "Umschalt" }, { "escape", "Esc" }, { "pageup", "Bild auf" }, { "pagedown", "Bild ab" }, { "backspace", "Rücktaste" }, { "delete", "Entf" }, { "del", "Entf" } }
            : new Dictionary<string, string> { { "control", "Ctrl" }, { "strg", "Ctrl" }, { "escape", "Esc" }, { "pageup", "Page Up" }, { "pagedown", "Page Down" } };

        public static readonly string Help = Pick(
            "Grey frame: chosen, not shared yet.\n" +
            "Yellow frame: shared. Looking, clicking and typing happen\nonly inside it, and only when asked.\n" +
            "A pulsing frame means something is being done in there. Its top\nright corner says what, such as \"Typing\" or \"Taking a screenshot\".\n\n" +
            "Carry on working as usual. Mouse and keyboard stay\nwith you, even while the window is covered.\n" +
            "A minimized window comes back behind your other windows\nas soon as your assistant asks for it. Store apps come to the front\nfor a moment once mouse and keyboard rest for about a second.\n\n" +
            "Ctrl+Shift+A opens the pinboard while you share.\nMark spots, write a note to them and click Done,\nthen your assistant can fetch them.\n\n" +
            "Ctrl+Alt+Shift+X ends the share at once,\nand so does closing this window.",
            "Grauer Rahmen: gewählt, aber noch nicht freigegeben.\n" +
            "Gelber Rahmen: freigegeben. Angeschaut, geklickt und getippt\nwird nur darin, und erst auf Anfrage.\n" +
            "Pulsiert der Rahmen, wird gerade darin gearbeitet. Was genau,\nsteht oben rechts am Rahmen, etwa „Tippe“ oder „Mache Screenshot“.\n\n" +
            "Du kannst nebenbei normal weiterarbeiten. Maus und Tastatur\nbleiben bei dir, auch wenn das Fenster zugedeckt ist.\n" +
            "Ein minimiertes Fenster kommt hinter deinen anderen Fenstern zurück,\nsobald dein Assistent danach fragt. Store-Apps kommen kurz nach vorn,\nsobald du gut eine Sekunde lang nichts eingibst.\n\n" +
            "Strg+Umschalt+A öffnet beim Freigeben die Pinnwand.\nMarkier Stellen, schreib eine Notiz dazu und\nklick auf Fertig. Dann kann dein Assistent sie abholen.\n\n" +
            "Strg+Alt+Umschalt+X beendet die Freigabe sofort,\nSchließen beendet sie auch.");
    }

    // Window is zero when a region is shared. Focus is the window that took the
    // last click inside a region; keys only go there.
    class Share
    {
        public IntPtr Window;
        public Rectangle Region;
        public bool Screen;
        public string Title;
        public volatile IntPtr Focus;
        // Windows hands the handle of a closed window and the id of an ended process on to
        // newcomers, so a shared window is known by its process and that process's start too.
        public uint Pid;
        public long Started;
        // The controls of the last look, which a ref in click or scroll points into.
        public volatile List<Element> Elements;
        // The last click from the share's top left corner, where the assistant's pointer waits while it types.
        public Point? Clicked;

        public Rectangle Area { get { return Window == IntPtr.Zero ? Region : Win.Bounds(Window); } }

        public static Share Of(IntPtr window)
        {
            var s = new Share { Window = window, Title = Win.Title(window) };
            Win.Owner(window, out s.Pid, out s.Started);
            return s;
        }

        public bool Owns(uint pid, long started) { return pid == Pid && started == Started; }

        public bool Gone
        {
            get
            {
                uint pid;
                long started;
                Win.Owner(Window, out pid, out started);
                return !Native.IsWindow(Window) || !Owns(pid, started);
            }
        }
    }

    // A control from a look. Box is in screen pixels as the walk finds it and in the
    // picture's pixels once Arrange has placed it.
    class Element
    {
        public string Ref, Role, Name;
        public Rectangle Box;

        public Dictionary<string, object> Fields()
        {
            return new Dictionary<string, object>
            {
                { "ref", Ref }, { "role", Role }, { "name", Name },
                { "x", Box.X }, { "y", Box.Y }, { "width", Box.Width }, { "height", Box.Height },
            };
        }
    }

    // Reads the controls of a window through UI Automation. The walk runs on a thread of its
    // own, so a program that answers slowly holds up a look for the budget at most.
    static class ControlTree
    {
        const int Most = 150, LongestName = 80;
        static readonly TimeSpan Budget = TimeSpan.FromMilliseconds(1500);

        static readonly Dictionary<ControlType, string> Roles = new Dictionary<ControlType, string>
        {
            { ControlType.Button, "button" }, { ControlType.SplitButton, "button" }, { ControlType.Hyperlink, "link" },
            { ControlType.Edit, "edit" }, { ControlType.CheckBox, "checkbox" }, { ControlType.RadioButton, "radio" },
            { ControlType.ComboBox, "combobox" }, { ControlType.MenuItem, "menuitem" }, { ControlType.TabItem, "tab" },
            { ControlType.ListItem, "listitem" }, { ControlType.DataItem, "listitem" }, { ControlType.TreeItem, "treeitem" },
            { ControlType.Slider, "slider" }, { ControlType.Text, "text" },
        };

        // A provider may report a control type of its own that UI Automation has no name for.
        public static string Role(ControlType type)
        {
            string role;
            return type != null && Roles.TryGetValue(type, out role) ? role : null;
        }

        // Null for what a look leaves out. Only the name is read, never the value, and a
        // password field gives away nothing but its role.
        public static Element Pick(ControlType type, string name, Rectangle box, bool offscreen, bool enabled, bool password)
        {
            var role = Role(type);
            if (role == null || offscreen || box.Width <= 0 || box.Height <= 0) return null;
            name = password ? "" : string.Join(" ", (name ?? "").Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
            if (name.Length > LongestName) name = name.Substring(0, LongestName);
            if (name.Length == 0 && (!enabled || role == "text")) return null;
            return new Element { Role = role, Name = name, Box = box };
        }

        // Clips to the share, scales into the picture and numbers the controls in reading order.
        public static List<Element> Arrange(List<Element> found, Rectangle area, double scale)
        {
            var placed = new List<KeyValuePair<int, Element>>();
            foreach (var e in found)
            {
                var r = Rectangle.Intersect(e.Box, area);
                if (r.Width <= 0 || r.Height <= 0) continue;
                var box = Rectangle.FromLTRB(
                    (int)Math.Round((r.Left - area.X) * scale), (int)Math.Round((r.Top - area.Y) * scale),
                    (int)Math.Round((r.Right - area.X) * scale), (int)Math.Round((r.Bottom - area.Y) * scale));
                if (box.Width <= 0 || box.Height <= 0) continue;
                placed.Add(new KeyValuePair<int, Element>(placed.Count, new Element { Role = e.Role, Name = e.Name, Box = box }));
            }
            // The index keeps controls on the same spot in the order the walk met them.
            placed.Sort((a, b) =>
            {
                var p = a.Value.Box;
                var q = b.Value.Box;
                return p.Y != q.Y ? p.Y.CompareTo(q.Y) : p.X != q.X ? p.X.CompareTo(q.X) : a.Key.CompareTo(b.Key);
            });
            var listed = new List<Element>();
            for (int i = 0; i < placed.Count && i < Most; i++)
            {
                placed[i].Value.Ref = "e" + (i + 1);
                listed.Add(placed[i].Value);
            }
            return listed;
        }

        // Null when the walk broke, which leaves the look without controls but with its picture.
        public static List<Element> Read(List<IntPtr> windows, Rectangle area, double scale)
        {
            var found = new List<Element>();
            bool broke = false;
            var clock = Stopwatch.StartNew();
            // Whatever goes wrong inside another program's accessibility support costs the controls alone.
            var walker = new Thread(() =>
            {
                try { Walk(windows, found, clock); }
                catch (Exception) { lock (found) broke = true; }
            }) { IsBackground = true };
            walker.Start();
            walker.Join(Budget + TimeSpan.FromMilliseconds(200));
            lock (found) return broke ? null : Arrange(new List<Element>(found), area, scale);
        }

        // Breadth first, so a walk cut short by the budget has covered the whole window
        // at the outer levels rather than one corner of it in depth.
        static void Walk(List<IntPtr> windows, List<Element> found, Stopwatch clock)
        {
            var cache = new CacheRequest();
            cache.Add(AutomationElement.NameProperty);
            cache.Add(AutomationElement.ControlTypeProperty);
            cache.Add(AutomationElement.BoundingRectangleProperty);
            cache.Add(AutomationElement.IsOffscreenProperty);
            cache.Add(AutomationElement.IsEnabledProperty);
            cache.Add(AutomationElement.IsPasswordProperty);
            var tree = TreeWalker.ControlViewWalker;
            var pending = new Queue<AutomationElement>();
            foreach (var h in windows)
            {
                try { pending.Enqueue(AutomationElement.FromHandle(h)); }
                catch (ElementNotAvailableException) { }
            }
            while (pending.Count > 0 && clock.Elapsed < Budget)
            {
                AutomationElement child;
                try { child = tree.GetFirstChild(pending.Dequeue(), cache); }
                catch (ElementNotAvailableException) { continue; }
                while (child != null && clock.Elapsed < Budget)
                {
                    var c = child.Cached;
                    var r = c.BoundingRectangle;
                    var e = r.IsEmpty ? null : Pick(c.ControlType, c.Name,
                        Rectangle.FromLTRB((int)Math.Floor(r.Left), (int)Math.Floor(r.Top), (int)Math.Ceiling(r.Right), (int)Math.Ceiling(r.Bottom)),
                        c.IsOffscreen, c.IsEnabled, c.IsPassword);
                    if (e != null) lock (found) found.Add(e);
                    pending.Enqueue(child);
                    try { child = tree.GetNextSibling(child, cache); }
                    catch (ElementNotAvailableException) { child = null; }
                }
            }
        }
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

        // Limited query rights, which a process running as administrator grants as well.
        public static void Owner(IntPtr h, out uint pid, out long started)
        {
            Native.GetWindowThreadProcessId(h, out pid);
            started = 0;
            var process = Native.OpenProcess(0x1000, false, pid);
            if (process == IntPtr.Zero) return;
            long exited, kernel, user;
            if (!Native.GetProcessTimes(process, out started, out exited, out kernel, out user)) started = 0;
            Native.CloseHandle(process);
        }

        public static bool IsTopmost(IntPtr h) { return (Native.GetWindowLong(h, -20) & 0x8) != 0; }

        public static bool IsCloaked(IntPtr h)
        {
            int cloaked;
            return Native.DwmGetWindowAttribute(h, 14, out cloaked, sizeof(int)) == 0 && cloaked != 0;
        }

        public static IntPtr Above(IntPtr h) { return Native.GetWindow(h, 3); }

        // A minimized window draws nothing and takes no input. It comes back without focus at
        // the bottom of the stack, behind whatever the person is working in, and gets a moment
        // to paint before the first picture.
        public static bool Unminimise(IntPtr h)
        {
            Native.SetWindowPos(h, (IntPtr)1, 0, 0, 0, 0, KeepPlace);
            Native.ShowWindowAsync(h, 4);
            for (int i = 0; i < 40 && Native.IsIconic(h); i++) Thread.Sleep(25);
            Native.SetWindowPos(h, (IntPtr)1, 0, 0, 0, 0, KeepPlace);
            if (Native.IsIconic(h)) return false;
            Thread.Sleep(300);
            return true;
        }

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

        // Whether any input went out since the panel last cleared it, so a refusal that comes
        // after can say some of it may have arrived.
        public static bool Sent;

        static void Send(List<Native.INPUT> inputs)
        {
            if (Native.SendInput((uint)inputs.Count, inputs.ToArray(), Marshal.SizeOf(typeof(Native.INPUT))) > 0) Sent = true;
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
            if (Native.PostMessage(target, message, new IntPtr(wParam), new IntPtr(lParam))) { Sent = true; return; }
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
                Layered.Push(Handle, bmp, at, (byte)(255 * alpha));
            }
        }
    }

    // A layered window takes its whole picture at once, with soft edges over any background.
    static class Layered
    {
        public static void Push(IntPtr window, Bitmap bmp, Point at, byte alpha)
        {
            IntPtr screen = Native.GetDC(IntPtr.Zero), mem = Native.CreateCompatibleDC(screen);
            IntPtr hbmp = bmp.GetHbitmap(Color.FromArgb(0)), old = Native.SelectObject(mem, hbmp);
            try
            {
                var size = new Native.SIZE { Width = bmp.Width, Height = bmp.Height };
                var dst = new Native.POINT { X = at.X, Y = at.Y };
                var src = new Native.POINT();
                var blend = new Native.BLENDFUNCTION { Op = 0, Flags = 0, Alpha = alpha, Format = 1 };
                Native.UpdateLayeredWindow(window, screen, ref dst, ref size, mem, ref src, 0, ref blend, 2);
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

    // The assistant's arrow, which shows where it acts while the person's own pointer stays put.
    // It sits right above the window it points into, so whatever covers that window covers the
    // arrow too, and it stays out of every picture taken of the screen.
    class Pointer : Form
    {
        const float Reach = 26, Linger = 4000, RingSpan = 400, RingGap = 150;
        static readonly Color Ink = Color.FromArgb(22, 22, 22);
        static readonly PointF[] Shape =
        {
            new PointF(0, 0), new PointF(0, 17.5f), new PointF(4.2f, 13.6f), new PointF(7.2f, 20),
            new PointF(9.9f, 18.8f), new PointF(7, 12.6f), new PointF(12.4f, 12.6f),
        };
        readonly float k;
        IntPtr target;
        // From the share's top left corner, so the arrow moves along with a shared window.
        PointF from, to;
        DateTime appeared, moved, arrived;
        int rings;
        Point placed;
        float placedAlpha;

        public Pointer(float k)
        {
            this.k = k;
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
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

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            Native.SetWindowDisplayAffinity(Handle, 0x11);
        }

        // Starts the way to the spot and says how long the action should wait for the arrow.
        public int Aim(IntPtr over, Point spot, int clicks)
        {
            var now = DateTime.UtcNow;
            bool fresh = target == IntPtr.Zero || Remaining(now) <= 0;
            if (fresh) appeared = now;
            from = fresh ? spot : Where(now);
            to = spot;
            target = over;
            moved = now;
            arrived = now.AddMilliseconds(Motion.Content);
            rings = Motion.Content > 0 ? clicks : 0;
            return (int)Motion.Content;
        }

        public void Keep()
        {
            if (target != IntPtr.Zero && Remaining(DateTime.UtcNow) > 0) arrived = DateTime.UtcNow;
        }

        public void Vanish()
        {
            target = IntPtr.Zero;
            if (!Visible) return;
            // Blank first, so the next showing starts from nothing instead of this picture.
            using (var blank = new Bitmap(1, 1, PixelFormat.Format32bppArgb)) Layered.Push(Handle, blank, placed, 0);
            Hide();
        }

        PointF Where(DateTime now)
        {
            float t = Motion.Content > 0 ? Math.Min(1, (float)(now - moved).TotalMilliseconds / Motion.Content) : 1, e = Motion.Ease(t);
            return new PointF(from.X + (to.X - from.X) * e, from.Y + (to.Y - from.Y) * e);
        }

        // Milliseconds until the arrow has faded out after the assistant's last action.
        double Remaining(DateTime now) { return (arrived - now).TotalMilliseconds + Linger + Motion.Content; }

        // Fades in where it first appears and out once the assistant has rested for a while.
        float Alpha(DateTime now)
        {
            float span = Motion.Content;
            double since = (now - appeared).TotalMilliseconds, left = Remaining(now);
            if (span <= 0) return left > 0 ? 1 : 0;
            return (float)Math.Max(0, Math.Min(1, Math.Min(since, left) / span));
        }

        bool Moving(DateTime now)
        {
            return (now - moved).TotalMilliseconds < Motion.Content || rings > 0 && (now - arrived).TotalMilliseconds < RingSpan + RingGap * (rings - 1);
        }

        public void Follow(Rectangle area, ICollection<IntPtr> marks)
        {
            if (target == IntPtr.Zero) return;
            var now = DateTime.UtcNow;
            if (Remaining(now) <= 0 || !Native.IsWindow(target)) { Vanish(); return; }
            float alpha = Alpha(now);
            var spot = Where(now);
            var at = new Point(area.X + (int)Math.Round(spot.X), area.Y + (int)Math.Round(spot.Y));
            if (!Visible) Show();
            StackOver(marks);
            if (at == placed && alpha == placedAlpha && !Moving(now)) return;
            Draw(at, alpha, now);
        }

        // Right above the target, the menus it owns and the frame and badge of the share, and no higher.
        void StackOver(ICollection<IntPtr> marks)
        {
            bool settled = false;
            var w = Win.Above(target);
            for (; w != IntPtr.Zero && (w == Handle || marks.Contains(w) || Win.IsOwnedBy(w, target)); w = Win.Above(w))
                settled = w == Handle;
            if (settled) return;
            Native.SetWindowPos(Handle, w != IntPtr.Zero && !Win.IsTopmost(w) ? w : IntPtr.Zero, 0, 0, 0, 0, Win.KeepPlace);
        }

        void Draw(Point at, float alpha, DateTime now)
        {
            int size = (int)Math.Ceiling(2 * Reach * k);
            float c = size / 2f;
            using (var bmp = new Bitmap(size, size, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(bmp))
                {
                    Theme.Prepare(g);
                    for (int i = 0; i < rings; i++)
                    {
                        float u = ((float)(now - arrived).TotalMilliseconds - i * RingGap) / RingSpan;
                        if (u < 0 || u >= 1) continue;
                        float r = (6 + 16 * Motion.Ease(u)) * k;
                        using (var pen = new Pen(Color.FromArgb((int)(255 * (1 - u)), Theme.Accent), 2 * k))
                            g.DrawEllipse(pen, c - r, c - r, 2 * r, 2 * r);
                    }
                    using (var arrow = new GraphicsPath())
                    {
                        arrow.AddPolygon(Array.ConvertAll(Shape, p => new PointF(c + p.X * k, c + p.Y * k)));
                        using (var shadow = (GraphicsPath)arrow.Clone())
                        using (var offset = new Matrix())
                        {
                            offset.Translate(k, 2 * k);
                            shadow.Transform(offset);
                            for (int i = 3; i >= 1; i--)
                                using (var soft = new Pen(Color.FromArgb(16, 0, 0, 0), 2 * i * k) { LineJoin = LineJoin.Round })
                                    g.DrawPath(soft, shadow);
                        }
                        using (var fill = new SolidBrush(Theme.Accent)) g.FillPath(fill, arrow);
                        using (var edge = new Pen(Ink, 1.5f * k) { LineJoin = LineJoin.Round }) g.DrawPath(edge, arrow);
                    }
                }
                placed = at;
                placedAlpha = alpha;
                Layered.Push(Handle, bmp, new Point(at.X - (int)c, at.Y - (int)c), (byte)(255 * alpha));
            }
        }
    }

    // A dimmed layer over every monitor that closes with what was picked, or with nothing on Escape.
    class Picker : Form
    {
        public Rectangle Result { get; protected set; }

        public Picker()
        {
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            TopMost = true;
            StartPosition = FormStartPosition.Manual;
            Bounds = SystemInformation.VirtualScreen;
            KeyPreview = true;
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape) Close();
        }
    }

    class RegionPicker : Picker
    {
        Point start;
        Rectangle selection;
        bool dragging;

        public RegionPicker()
        {
            BackColor = Color.Black;
            TransparencyKey = Color.Magenta;
            Opacity = 0.4;
            Cursor = Cursors.Cross;
            DoubleBuffered = true;
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

    // Every monitor dimmed with a hint in its middle and the one under the pointer outlined. A
    // layered window, so the hint stays solid while the screens behind it are dimmed.
    class ScreenPicker : Picker
    {
        readonly float k;
        readonly Rectangle all = SystemInformation.VirtualScreen;
        readonly Rectangle[] screens = Array.ConvertAll(Screen.AllScreens, s => s.Bounds);
        readonly Font font;
        int hover = -1;
        public int Number { get; private set; }

        public ScreenPicker(float k)
        {
            this.k = k;
            font = new Font(Theme.SemiBold, 15 * k, GraphicsUnit.Pixel);
            Cursor = Cursors.Hand;
        }

        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.ExStyle |= 0x80000;
                return p;
            }
        }

        public static int Under(Rectangle[] screens, Point p)
        {
            for (int i = 0; i < screens.Length; i++)
                if (screens[i].Contains(p)) return i;
            return -1;
        }

        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            hover = Under(screens, Cursor.Position);
            Draw();
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            int at = Under(screens, new Point(all.X + e.X, all.Y + e.Y));
            if (at == hover) return;
            hover = at;
            Draw();
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            int at = Under(screens, new Point(all.X + e.X, all.Y + e.Y));
            if (e.Button == MouseButtons.Left && at >= 0)
            {
                Result = screens[at];
                Number = at + 1;
            }
            Close();
        }

        void Draw()
        {
            using (var bmp = new Bitmap(all.Width, all.Height, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(bmp))
                {
                    Theme.Prepare(g);
                    g.Clear(Color.FromArgb(102, 0, 0, 0));
                    g.TranslateTransform(-all.X, -all.Y);
                    for (int i = 0; i < screens.Length; i++) Hint(g, screens[i], i == hover);
                }
                Layered.Push(Handle, bmp, all.Location, 255);
            }
        }

        void Hint(Graphics g, Rectangle screen, bool lit)
        {
            float edge = 4 * k, icon = 18 * k, gap = 8 * k;
            if (lit)
                using (var pen = new Pen(Theme.Accent, edge))
                    g.DrawRectangle(pen, screen.X + edge / 2, screen.Y + edge / 2, screen.Width - edge, screen.Height - edge);
            var text = g.MeasureString(Say.ClickScreen, font);
            float w = icon + gap + text.Width + 40 * k, h = 44 * k;
            var pill = new RectangleF(screen.X + (screen.Width - w) / 2, screen.Y + (screen.Height - h) / 2, w, h);
            using (var path = Theme.Rounded(pill, h / 2))
            {
                using (var brush = new SolidBrush(Theme.Surface)) g.FillPath(brush, path);
                if (lit)
                    using (var pen = new Pen(Theme.Accent, 2 * k)) g.DrawPath(pen, path);
            }
            float x = pill.X + 20 * k;
            Glyphs.Draw(g, Glyph.Screen, new RectangleF(x, pill.Y + (h - icon) / 2, icon, icon), Theme.Text, k);
            using (var ink = new SolidBrush(Theme.Text))
            using (var format = new StringFormat { LineAlignment = StringAlignment.Center, FormatFlags = StringFormatFlags.NoWrap })
                g.DrawString(Say.ClickScreen, font, ink, new RectangleF(x + icon + gap, pill.Y, text.Width + 2, h), format);
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

        public const uint Alt = 0x1, Control = 0x2, Shift = 0x4;

        // Without key repeat.
        public bool Register(int id, uint mods, Keys key) { return Native.RegisterHotKey(Handle, id, mods | 0x4000, (uint)key); }

        public void Release(int id) { Native.UnregisterHotKey(Handle, id); }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == 0x0312) pressed(m.WParam.ToInt32());
            base.WndProc(ref m);
        }
    }

    // A brass spyglass across a split steel ring: someone looking at what is shared. The shapes
    // come from .github/assets/knightsight.svg through gen-logo-shapes.mjs. They are filled
    // without smoothing at four times the size and then scaled down, so neighbouring shapes meet
    // without hairlines and the edges still come out soft.
    public static partial class Logo
    {
        const int Oversampling = 4;
        static readonly Dictionary<int, Bitmap> drawn = new Dictionary<int, Bitmap>();

        sealed class Shape
        {
            public readonly Color Fill;
            public readonly string Path;
            public Shape(int rgb, string path) { Fill = Color.FromArgb(255, Color.FromArgb(rgb)); Path = path; }
        }

        sealed class Drawing
        {
            public readonly float Width, Height;
            public readonly Shape[] Shapes;
            public Drawing(float width, float height, Shape[] shapes) { Width = width; Height = height; Shapes = shapes; }
        }

        public static Bitmap Render(int size)
        {
            using (var large = new Bitmap(size * Oversampling, size * Oversampling))
            {
                using (var g = Graphics.FromImage(large))
                {
                    float scale = large.Width / Math.Max(Bare.Width, Bare.Height);
                    g.TranslateTransform((large.Width - Bare.Width * scale) / 2, (large.Height - Bare.Height * scale) / 2);
                    g.ScaleTransform(scale, scale);
                    foreach (var shape in Bare.Shapes)
                        using (var path = Outline(shape.Path))
                        using (var brush = new SolidBrush(shape.Fill))
                            g.FillPath(brush, path);
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

        // The steps the generator writes: M, L, C and Z, each followed by its absolute points.
        static GraphicsPath Outline(string steps)
        {
            var path = new GraphicsPath(FillMode.Winding);
            var t = steps.Split(' ');
            var at = PointF.Empty;
            for (int i = 0; i < t.Length; )
            {
                switch (t[i++])
                {
                    case "M":
                        path.StartFigure();
                        at = Next(t, ref i);
                        break;
                    case "L":
                    {
                        var p = Next(t, ref i);
                        path.AddLine(at, p);
                        at = p;
                        break;
                    }
                    case "C":
                    {
                        PointF c1 = Next(t, ref i), c2 = Next(t, ref i), p = Next(t, ref i);
                        path.AddBezier(at, c1, c2, p);
                        at = p;
                        break;
                    }
                    case "Z":
                        path.CloseFigure();
                        break;
                }
            }
            return path;
        }

        static PointF Next(string[] t, ref int i)
        {
            var p = new PointF(float.Parse(t[i], CultureInfo.InvariantCulture), float.Parse(t[i + 1], CultureInfo.InvariantCulture));
            i += 2;
            return p;
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
        public static readonly Color Neutral = Color.FromArgb(141, 136, 128);

        public static bool Dark;
        public static Color Ground, Surface, Surface2, Surface3, Hover, Text, Secondary, Muted;
        public static FontFamily Regular, SemiBold;
        static readonly System.Drawing.Text.PrivateFontCollection fonts = new System.Drawing.Text.PrivateFontCollection();

        public static void Load()
        {
            var v = Microsoft.Win32.Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1);
            Dark = v is int && (int)v == 0;
            Ground = Dark ? Color.FromArgb(15, 14, 12) : Color.FromArgb(245, 243, 239);
            Surface = Dark ? Color.FromArgb(28, 26, 23) : Color.White;
            Surface2 = Dark ? Color.FromArgb(52, 48, 43) : Color.FromArgb(233, 230, 224);
            Surface3 = Dark ? Color.FromArgb(78, 73, 66) : Color.FromArgb(210, 205, 197);
            Hover = Dark ? Color.FromArgb(46, 43, 38) : Color.FromArgb(225, 221, 214);
            Text = Dark ? Color.FromArgb(240, 236, 228) : Color.FromArgb(24, 22, 19);
            Secondary = Dark ? Color.FromArgb(190, 184, 173) : Color.FromArgb(86, 81, 73);
            Muted = Dark ? Color.FromArgb(140, 134, 124) : Color.FromArgb(115, 109, 100);

            foreach (var name in new[] { "NotoSans-Regular.ttf", "NotoSans-SemiBold.ttf" })
            {
                using (var stream = typeof(Theme).Assembly.GetManifestResourceStream(name))
                {
                    var data = new byte[stream.Length];
                    stream.Read(data, 0, data.Length);
                    // The collection reads the font from this memory for as long as it lives. GDI
                    // gets it too, for the text boxes, which draw with GDI.
                    var mem = Marshal.AllocCoTaskMem(data.Length);
                    Marshal.Copy(data, 0, mem, data.Length);
                    fonts.AddMemoryFont(mem, data.Length);
                    uint count = 0;
                    Native.AddFontMemResourceEx(mem, (uint)data.Length, IntPtr.Zero, ref count);
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

    enum Glyph { None, Window, Region, Screen, Start, Stop, Info, Minimise, Close, Pin }

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
                    case Glyph.Screen:
                        var monitor = new RectangleF(b.X + s * 0.06f, b.Y + s * 0.1f, s * 0.88f, s * 0.6f);
                        using (var path = Theme.Rounded(monitor, 2.5f * k)) g.DrawPath(pen, path);
                        float mid = b.X + s / 2, foot = b.Y + s * 0.9f;
                        g.DrawLine(pen, mid, monitor.Bottom, mid, foot);
                        g.DrawLine(pen, mid - s * 0.2f, foot, mid + s * 0.2f, foot);
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
                    case Glyph.Pin:
                        using (var path = new GraphicsPath())
                        {
                            path.AddPolygon(new[]
                            {
                                new PointF(b.X + s * 0.34f, b.Y + s * 0.1f), new PointF(b.X + s * 0.66f, b.Y + s * 0.1f),
                                new PointF(b.X + s * 0.62f, b.Y + s * 0.4f), new PointF(b.X + s * 0.78f, b.Y + s * 0.56f),
                                new PointF(b.X + s * 0.22f, b.Y + s * 0.56f), new PointF(b.X + s * 0.38f, b.Y + s * 0.4f),
                            });
                            g.DrawPath(pen, path);
                        }
                        g.DrawLine(pen, b.X + s / 2, b.Y + s * 0.56f, b.X + s / 2, b.Y + s * 0.92f);
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
    // blank control on the ground whose square lights up under the pointer. Fill, when set,
    // paints it in a colour of its own, such as the kind of a note.
    // Hover fades in and a press sinks it a little, both as transitions over Motion.Control.
    class SoftButton : Control
    {
        public bool Primary, Blank, Outline;
        public Color Fill = Color.Empty;
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
            else if (!Fill.IsEmpty) { fill = Motion.Mix(Fill, Color.White, 0.2f * t); ink = Theme.AccentInk; }
            else if (Outline) { fill = Motion.Mix(Theme.Surface2, Theme.Surface3, t); ink = Theme.Text; }
            else if (Primary) { fill = Motion.Mix(Theme.Accent, Theme.AccentHover, t); ink = Theme.AccentInk; }
            else { fill = Motion.Mix(Theme.Surface2, Theme.Surface3, t); ink = Theme.Text; }
            float scale = 1 - (1 - Motion.PressScale) * Motion.Ease(sink);
            float w = (Blank ? Square : Width - 1) * scale, h = (Blank ? Square : Height - 1) * scale;
            var r = new RectangleF((Width - 1 - w) / 2, (Height - 1 - h) / 2, w, h);
            using (var path = Theme.Rounded(r, Radius * scale))
            {
                using (var brush = new SolidBrush(fill)) g.FillPath(brush, path);
                if (Outline && Enabled)
                    using (var edge = new Pen(Theme.Accent, 1.5f * K)) g.DrawPath(edge, path);
                if (Focused && ShowFocusCues)
                    using (var ring = new Pen(Theme.Accent, 2 * K)) g.DrawPath(ring, path);
            }

            float icon = Icon == Glyph.None ? 0 : 16 * K * scale, gap = Text.Length > 0 && icon > 0 ? 8 * K : 0;
            // Typographic, so the padding GDI+ adds around text does not push it off centre.
            using (var format = new StringFormat(StringFormat.GenericTypographic) { LineAlignment = StringAlignment.Center, FormatFlags = StringFormatFlags.NoWrap })
            {
                float textWidth = Text.Length > 0 ? g.MeasureString(Text, Font, PointF.Empty, format).Width : 0;
                float x = r.X + (r.Width - icon - gap - textWidth) / 2;
                if (icon > 0) Glyphs.Draw(g, Icon, new RectangleF(x, r.Y + (r.Height - icon) / 2, icon, icon), ink, K * scale);
                if (Text.Length == 0) return;
                using (var brush = new SolidBrush(ink))
                    g.DrawString(Text, Font, brush, new RectangleF(x + icon + gap, r.Y, textWidth + 2, r.Height), format);
            }
        }
    }

    enum NoteKind { Bug, Wish, Question }

    // A note has one or more marks, in the order they were made. A pin is a mark without a size.
    // Marks count in the share's own units from its top left corner, see Spot.
    class Note
    {
        public const int MostMarks = 26;
        public int Number;
        public NoteKind Kind;
        public string Text, Author;
        public List<RectangleF> Marks = new List<RectangleF>();

        public static readonly string[] Keys = { "bug", "wish", "question" };

        public string Label(int mark) { return Label(Number, mark, Marks.Count); }

        // The marks of one note tell apart by a letter, 3a and 3b.
        public static string Label(int number, int mark, int count)
        {
            var n = number.ToString(CultureInfo.InvariantCulture);
            return count == 1 ? n : n + (char)('a' + mark);
        }

        public static bool AddMark(List<RectangleF> marks, RectangleF mark)
        {
            if (marks.Count >= MostMarks) return false;
            marks.Add(mark);
            return true;
        }

        public static bool RemoveMark(List<RectangleF> marks, int mark)
        {
            if (marks.Count < 2) return false;
            marks.RemoveAt(mark);
            return true;
        }
    }

    // A window's notes count in its pixels at 96 DPI, so they stay on their spot when the window
    // moves and grow along when it moves to a denser screen. A region has a density of one.
    static class Spot
    {
        const float Margin = 24, PinBox = 240;

        public static PointF ToShare(Point screen, Rectangle area, float density)
        {
            return new PointF((screen.X - area.X) / density, (screen.Y - area.Y) / density);
        }

        public static Rectangle ToScreen(RectangleF mark, Rectangle area, float density)
        {
            return Rectangle.Round(new RectangleF(area.X + mark.X * density, area.Y + mark.Y * density, mark.Width * density, mark.Height * density));
        }

        // A window that shrank can leave a note outside of it, which then waits there unseen.
        public static bool Shows(RectangleF mark, Rectangle area, float density)
        {
            var r = ToScreen(mark, area, density);
            return mark.Width == 0 && mark.Height == 0 ? area.Contains(r.Location) : r.IntersectsWith(area);
        }

        // The part of a picture of the share that shows a mark, with some of its surroundings.
        public static Rectangle Crop(RectangleF mark, Size shot, float density)
        {
            var px = new RectangleF(mark.X * density, mark.Y * density, mark.Width * density, mark.Height * density);
            var box = mark.Width == 0 && mark.Height == 0
                ? new RectangleF(px.X - PinBox * density / 2, px.Y - PinBox * density / 2, PinBox * density, PinBox * density)
                : RectangleF.Inflate(px, Margin * density, Margin * density);
            var r = Rectangle.Round(box);
            r.Intersect(new Rectangle(Point.Empty, shot));
            return r;
        }
    }

    // How the notes look, on the pinboard and in the pictures that go to the assistant alike.
    static class Pins
    {
        static readonly Color[] Colors = { Color.FromArgb(250, 77, 86), Theme.Accent, Color.FromArgb(29, 153, 243) };

        public static Color Of(NoteKind kind) { return Colors[(int)kind]; }

        // A rectangle of no size on the screen is a pin.
        public static void Draw(Graphics g, NoteKind kind, string label, Rectangle r, float k, bool lit)
        {
            var color = Of(kind);
            if (r.Width == 0 && r.Height == 0)
            {
                Badge(g, label, r.Location, 24 * k, color, Color.White, k, true);
                return;
            }
            using (var fill = new SolidBrush(Color.FromArgb(36, color))) g.FillRectangle(fill, r);
            using (var pen = new Pen(color, (lit ? 3 : 2) * k)) g.DrawRectangle(pen, r);
            Badge(g, label, r.Location, 22 * k, color, Color.White, k, false);
        }

        public static void Draft(Graphics g, Rectangle r, float k)
        {
            using (var fill = new SolidBrush(Color.FromArgb(26, Theme.Accent))) g.FillRectangle(fill, r);
            using (var pen = new Pen(Theme.Accent, 2 * k) { DashStyle = DashStyle.Dash }) g.DrawRectangle(pen, r);
        }

        // Where a click picks a mark: its badge or its box.
        public static bool Hits(Rectangle r, Point p, float k)
        {
            bool pin = r.Width == 0 && r.Height == 0;
            float reach = (pin ? 14 : 13) * k, dx = p.X - r.X, dy = p.Y - r.Y;
            if (dx * dx + dy * dy <= reach * reach) return true;
            return !pin && Rectangle.Inflate(r, (int)(3 * k), (int)(3 * k)).Contains(p);
        }

        // A label wider than the disc, such as 12b, gets a pill of the same height.
        public static void Badge(Graphics g, string label, PointF at, float d, Color color, Color ring, float k, bool shadow)
        {
            using (var font = new Font(Theme.SemiBold, (label.Length < 3 ? 12 : 11) * k, GraphicsUnit.Pixel))
            using (var ink = new SolidBrush(Theme.AccentInk))
            using (var format = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
            {
                float w = Math.Max(d, g.MeasureString(label, font).Width + 2 * k), edge = 2 * k;
                var body = new RectangleF(at.X - w / 2, at.Y - d / 2, w, d);
                if (shadow)
                    for (int i = 3; i >= 1; i--)
                    {
                        var soft = RectangleF.Inflate(body, i * k, i * k);
                        soft.Offset(0, 2 * k);
                        using (var path = Theme.Rounded(soft, soft.Height / 2))
                        using (var brush = new SolidBrush(Color.FromArgb(18, 0, 0, 0)))
                            g.FillPath(brush, path);
                    }
                using (var path = Theme.Rounded(RectangleF.Inflate(body, edge, edge), d / 2 + edge))
                using (var brush = new SolidBrush(ring))
                    g.FillPath(brush, path);
                using (var path = Theme.Rounded(body, d / 2))
                using (var brush = new SolidBrush(color))
                    g.FillPath(brush, path);
                g.DrawString(label, font, ink, new RectangleF(body.X - d, body.Y, body.Width + 2 * d, d + k), format);
            }
        }
    }

    // What Done hands to the assistant, in the fields of the reply to "notes".
    class Round
    {
        public int Number;
        public Dictionary<string, object> Fields;
    }

    // The notes on the pinboard and the round sent last. The notes belong to the panel's
    // thread, the round is read from the request threads too, so it goes through the lock.
    class Board
    {
        public readonly List<Note> Notes = new List<Note>();
        public bool Open { get; private set; }
        int next = 1, rounds;
        Round sent;
        bool read;

        public bool Fetched { get { lock (this) return sent != null && read; } }

        public int Next { get { return next; } }

        public bool Toggle(bool shared)
        {
            Open = shared && !Open;
            return Open;
        }

        public void Close() { Open = false; }

        public void Forget()
        {
            Notes.Clear();
            Open = false;
        }

        public Note Add(IList<RectangleF> marks, NoteKind kind, string text, string author)
        {
            var note = new Note { Number = next++, Kind = kind, Text = text, Author = author, Marks = new List<RectangleF>(marks) };
            Notes.Add(note);
            return note;
        }

        // The shot is the share at its full size, so a mark at density 1.5 sits at one and a
        // half times its place in it.
        public Round Seal(Bitmap shot, float density, string title, DateTime when)
        {
            double scale = Panel.Scale(shot.Size);
            int w = Math.Max(1, (int)Math.Round(shot.Width * scale)), h = Math.Max(1, (int)Math.Round(shot.Height * scale));
            var notes = new List<object>();
            using (var frame = new Bitmap(w, h))
            {
                using (var g = Graphics.FromImage(frame))
                {
                    Theme.Prepare(g);
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.DrawImage(shot, 0, 0, w, h);
                    float k = Math.Max(1, (float)scale * density);
                    foreach (var note in Notes)
                        for (int i = 0; i < note.Marks.Count; i++)
                            Pins.Draw(g, note.Kind, note.Label(i), InPicture(note.Marks[i], density, scale), k, false);
                }
                foreach (var note in Notes) notes.Add(Describe(note, shot, density, scale));
                var fields = new Dictionary<string, object>
                {
                    { "round", rounds + 1 },
                    { "sent", when.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture) },
                    { "title", title }, { "width", w }, { "height", h }, { "image", Png(frame) }, { "notes", notes },
                };
                return new Round { Number = rounds + 1, Fields = fields };
            }
        }

        static Rectangle InPicture(RectangleF mark, float density, double scale)
        {
            double f = density * scale;
            return new Rectangle((int)Math.Round(mark.X * f), (int)Math.Round(mark.Y * f), (int)Math.Round(mark.Width * f), (int)Math.Round(mark.Height * f));
        }

        static Dictionary<string, object> Describe(Note note, Bitmap shot, float density, double scale)
        {
            var marks = new List<object>();
            for (int i = 0; i < note.Marks.Count; i++) marks.Add(Place(note, i, shot, density, scale));
            return new Dictionary<string, object>
            {
                { "number", note.Number }, { "kind", Note.Keys[(int)note.Kind] }, { "text", note.Text }, { "author", note.Author },
                { "marks", marks },
            };
        }

        static Dictionary<string, object> Place(Note note, int index, Bitmap shot, float density, double scale)
        {
            var mark = note.Marks[index];
            var at = InPicture(mark, density, scale);
            var d = new Dictionary<string, object> { { "label", note.Label(index) }, { "x", at.X }, { "y", at.Y } };
            if (mark.Width == 0 && mark.Height == 0) d["pin"] = true;
            else { d["width"] = at.Width; d["height"] = at.Height; }

            var crop = Spot.Crop(mark, shot.Size, density);
            double fit = Panel.Scale(crop.Size);
            int cw = Math.Max(1, (int)Math.Round(crop.Width * fit)), ch = Math.Max(1, (int)Math.Round(crop.Height * fit));
            using (var piece = new Bitmap(cw, ch))
            {
                using (var g = Graphics.FromImage(piece))
                {
                    Theme.Prepare(g);
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.DrawImage(shot, new Rectangle(0, 0, cw, ch), crop, GraphicsUnit.Pixel);
                    var local = InPicture(mark, density, fit);
                    local.Offset(-(int)Math.Round(crop.X * fit), -(int)Math.Round(crop.Y * fit));
                    Pins.Draw(g, note.Kind, note.Label(index), local, Math.Max(1, (float)fit * density), false);
                }
                d["image"] = Png(piece);
            }
            return d;
        }

        public static string Png(Bitmap bmp)
        {
            using (var ms = new MemoryStream())
            {
                bmp.Save(ms, ImageFormat.Png);
                return Convert.ToBase64String(ms.ToArray());
            }
        }

        public void Send(Round round)
        {
            lock (this)
            {
                sent = round;
                read = false;
                rounds = round.Number;
            }
            Notes.Clear();
            Open = false;
        }

        // With unread set, a round already handed out answers with its number alone, which is
        // what the MCP server waits on.
        public Dictionary<string, object> Answer(bool unread)
        {
            lock (this)
            {
                if (sent == null) return new Dictionary<string, object> { { "round", 0 } };
                if (unread && read) return new Dictionary<string, object> { { "round", sent.Number } };
                read = true;
                return sent.Fields;
            }
        }

        // One file with the pictures inside, for when there is no assistant to fetch the notes.
        public static string Page(Round round)
        {
            var f = round.Fields;
            Func<object, string> e = v => WebUtility.HtmlEncode(Convert.ToString(v, CultureInfo.CurrentCulture));
            var sent = DateTime.Parse((string)f["sent"], CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal).ToLocalTime();
            var page = new StringBuilder();
            page.Append("<!doctype html>\n<html lang=\"").Append(Say.Language).Append("\">\n<meta charset=\"utf-8\">\n<title>")
                .Append(e(Say.NotesOn((string)f["title"]))).Append("</title>\n<style>\n")
                .Append("body { font: 15px/1.5 \"Noto Sans\", system-ui, sans-serif; max-width: 960px; margin: 32px auto; padding: 0 16px; background: #f4f4f4; color: #161616; }\n")
                .Append("article { background: #fff; border-radius: 10px; padding: 16px 20px; margin: 16px 0; }\n")
                .Append("img { max-width: 100%; border-radius: 6px; }\n")
                .Append("figure { margin: 12px 0; } figcaption { color: #6f6f6f; font-size: 13px; font-weight: 600; }\n")
                .Append(".meta { color: #6f6f6f; font-size: 13px; }\n")
                .Append(".kind { display: inline-block; padding: 1px 8px; border-radius: 5px; color: #161616; font-size: 13px; font-weight: 600; margin-right: 8px; }\n")
                .Append("@media (prefers-color-scheme: dark) { body { background: #161616; color: #f4f4f4; } article { background: #262626; } .meta { color: #8d8d8d; } }\n")
                .Append("</style>\n<h1>").Append(e(Say.NotesOn((string)f["title"]))).Append("</h1>\n<p class=\"meta\">")
                .Append(e(Say.Round(round.Number) + ", " + sent.ToString("g", CultureInfo.CurrentCulture))).Append("</p>\n")
                .Append("<img src=\"data:image/png;base64,").Append(f["image"]).Append("\" alt=\"\">\n");
            foreach (Dictionary<string, object> note in (IEnumerable<object>)f["notes"])
            {
                int kind = Array.IndexOf(Note.Keys, (string)note["kind"]);
                var color = Pins.Of((NoteKind)kind);
                page.Append("<article>\n<h2><span class=\"kind\" style=\"background: #").Append((color.ToArgb() & 0xFFFFFF).ToString("X6"))
                    .Append("\">").Append(e(Say.Kinds[kind])).Append("</span>").Append(e(Say.NoteTitle((int)note["number"]))).Append("</h2>\n<p>")
                    .Append(e(note["text"]).Replace("\n", "<br>")).Append("</p>\n");
                if (((string)note["author"]).Length > 0) page.Append("<p class=\"meta\">").Append(e(Say.From((string)note["author"]))).Append("</p>\n");
                var marks = (IList<object>)note["marks"];
                foreach (Dictionary<string, object> mark in marks)
                {
                    var picture = "<img src=\"data:image/png;base64," + mark["image"] + "\" alt=\"\">";
                    if (marks.Count == 1) page.Append(picture).Append("\n");
                    else page.Append("<figure>").Append(picture).Append("<figcaption>").Append(e(mark["label"])).Append("</figcaption></figure>\n");
                }
                page.Append("</article>\n");
            }
            return page.ToString();
        }
    }

    // A window of our own look that Windows still gives its shadow, rounded corners and snapping:
    // the caption style stays, the whole window counts as client area, and the strip at the top
    // that is Grip pixels high takes the part of the caption.
    public class Card : Form
    {
        protected int Grip;
        // DWM's colour for the hairline around the window, or none.
        protected int Border = unchecked((int)0xFFFFFFFE);

        // A card that comes and goes with the pinboard skips the fade, which would otherwise
        // still show in a picture taken right after it hides.
        protected bool Instant;

        protected static int ColorRef(Color c) { return c.R | c.G << 8 | c.B << 16; }

        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.Style |= 0x00C00000 | 0x00080000;
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
                m.Result = new IntPtr(y < Grip ? HitCaption : HitClient);
                return;
            }
            base.WndProc(ref m);
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            int on = Theme.Dark ? 1 : 0, rounded = 2;
            Native.DwmSetWindowAttribute(Handle, 20, ref on, sizeof(int));
            Native.DwmSetWindowAttribute(Handle, 33, ref rounded, sizeof(int));
            Native.DwmSetWindowAttribute(Handle, 34, ref Border, sizeof(int));
            int still = Instant ? 1 : 0;
            Native.DwmSetWindowAttribute(Handle, 3, ref still, sizeof(int));
            // A window with no frame of its own gets its shadow back from one row of DWM frame.
            var row = new Native.MARGINS { Bottom = 1 };
            Native.DwmExtendFrameIntoClientArea(Handle, ref row);
        }
    }

    // A text box on the ground colour that shows its hint while it is empty.
    class Field : TextBox
    {
        public string Hint = "";

        public Field(float k, bool lines)
        {
            BorderStyle = BorderStyle.None;
            Multiline = lines;
            AcceptsReturn = lines;
            BackColor = Theme.Ground;
            ForeColor = Theme.Text;
            Font = new Font(Theme.Regular, 14 * k, GraphicsUnit.Pixel);
        }

        protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }

        protected override void WndProc(ref Message m)
        {
            base.WndProc(ref m);
            if (m.Msg != 0xF || TextLength > 0) return;
            using (var g = CreateGraphics())
                TextRenderer.DrawText(g, Hint, Font, ClientRectangle, Theme.Muted, BackColor,
                    TextFormatFlags.WordBreak | TextFormatFlags.NoPadding | TextFormatFlags.TextBoxControl);
        }
    }

    // The card beside a mark where its note is written.
    class NoteEditor : Card
    {
        readonly float k;
        readonly SoftButton[] kinds = new SoftButton[3];
        readonly SoftButton save = new SoftButton { Primary = true }, delete = new SoftButton(), close = new SoftButton { Blank = true, Icon = Glyph.Close };
        readonly Field text, author;
        readonly Font titleFont, hintFont;
        readonly Rectangle textField, authorField;
        string title = "", before = "";
        public Note Note { get; private set; }
        public NoteKind Kind { get; private set; }
        public Action Saved, Deleted, Dismissed, KindChanged, Typed;

        public NoteEditor(float k)
        {
            this.k = k;
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            BackColor = Theme.Surface;
            DoubleBuffered = true;
            Border = ColorRef(Theme.Surface3);
            Instant = true;
            titleFont = new Font(Theme.SemiBold, 15 * k, GraphicsUnit.Pixel);
            hintFont = new Font(Theme.Regular, 13 * k, GraphicsUnit.Pixel);
            var buttonFont = new Font(Theme.SemiBold, 14 * k, GraphicsUnit.Pixel);
            int w = S(340), pad = S(16);
            Size = new Size(w, S(336));
            Grip = S(44);

            close.Under = Theme.Surface;
            close.Radius = S(6);
            close.K = k;
            close.Square = S(28);
            close.Bounds = new Rectangle(w - S(8) - S(36), S(6), S(36), S(36));
            close.Click += (o, e) => Dismissed();

            int kindWidth = (w - 2 * pad - 2 * S(8)) / 3;
            for (int i = 0; i < 3; i++)
            {
                var kind = (NoteKind)i;
                kinds[i] = Button(new SoftButton(), Say.Kinds[i], buttonFont, new Rectangle(pad + i * (kindWidth + S(8)), S(52), kindWidth, S(32)));
                kinds[i].Click += (o, e) => Choose(kind);
            }

            textField = new Rectangle(pad, S(96), w - 2 * pad, S(100));
            text = new Field(k, true) { Hint = Say.NotePlaceholder, Bounds = Rectangle.Inflate(textField, -S(10), -S(8)) };
            text.TextChanged += (o, e) =>
            {
                save.Enabled = text.Text.Trim().Length > 0;
                if (Typed != null) Typed();
            };
            authorField = new Rectangle(pad, S(208), w - 2 * pad, S(36));
            author = new Field(k, false) { Hint = Say.AuthorPlaceholder };
            author.Bounds = new Rectangle(authorField.X + S(10), authorField.Y + (authorField.Height - author.PreferredHeight) / 2, authorField.Width - S(20), author.PreferredHeight);

            Button(delete, Say.Delete, buttonFont, new Rectangle(pad, S(284), S(104), S(36))).Click += (o, e) => Deleted();
            Button(save, Say.Save, buttonFont, new Rectangle(w - pad - S(120), S(284), S(120), S(36))).Click += (o, e) => Saved();
            Controls.AddRange(new Control[] { close, kinds[0], kinds[1], kinds[2], text, author, delete, save });
        }

        int S(float v) { return (int)Math.Round(v * k); }

        SoftButton Button(SoftButton b, string label, Font font, Rectangle bounds)
        {
            b.Text = label;
            b.Font = font;
            b.Under = Theme.Surface;
            b.Radius = S(6);
            b.K = k;
            b.Bounds = bounds;
            return b;
        }

        protected override bool ShowWithoutActivation { get { return true; } }

        public string NoteText { get { return text.Text.Trim(); } }
        public string Author { get { return author.Text.Trim(); } }

        // Unsaved text, which a stray click on the overlay should not throw away.
        public bool Dirty { get { return text.Text != before; } }

        public bool CanSave { get { return save.Enabled; } }

        public void Open(Note note, string name)
        {
            Note = note;
            title = note == null ? Say.NewNote : Say.NoteTitle(note.Number);
            before = note == null ? "" : note.Text;
            text.Text = before;
            author.Text = note == null ? name : note.Author;
            delete.Visible = note != null;
            save.Enabled = before.Length > 0;
            Choose(note == null ? NoteKind.Wish : note.Kind);
            Invalidate();
        }

        public void Begin(bool select)
        {
            Activate();
            text.Focus();
            if (select) text.SelectAll();
            else text.Select(text.TextLength, 0);
        }

        void Choose(NoteKind kind)
        {
            Kind = kind;
            for (int i = 0; i < 3; i++)
            {
                kinds[i].Fill = i == (int)kind ? Pins.Of((NoteKind)i) : Color.Empty;
                kinds[i].Invalidate();
            }
            if (KindChanged != null) KindChanged();
        }

        protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
        {
            if (keyData == (Keys.Control | Keys.Enter))
            {
                if (save.Enabled) Saved();
                return true;
            }
            if (keyData == Keys.Escape)
            {
                Dismissed();
                return true;
            }
            // A multi-line text box of WinForms ignores Ctrl+A by itself.
            if (keyData == (Keys.Control | Keys.A) && ActiveControl is TextBox)
            {
                ((TextBox)ActiveControl).SelectAll();
                return true;
            }
            return base.ProcessCmdKey(ref msg, keyData);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            Theme.Prepare(g);
            using (var ink = new SolidBrush(Theme.Text))
            using (var format = new StringFormat { LineAlignment = StringAlignment.Center, Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap })
                g.DrawString(title, titleFont, ink, new RectangleF(S(16), S(6), close.Left - S(24), S(36)), format);
            using (var ground = new SolidBrush(Theme.Ground))
                foreach (var field in new[] { textField, authorField })
                    using (var path = Theme.Rounded(field, S(6))) g.FillPath(ground, path);
            using (var muted = new SolidBrush(Theme.Muted))
                g.DrawString(Say.MoreSpots, hintFont, muted, new RectangleF(S(16), authorField.Bottom + S(8), authorField.Width, S(20)));
        }
    }

    // The rows of the note list. A click on one goes to its note.
    class NoteRows : Control
    {
        public const float RowHeight = 48;
        readonly float k;
        readonly Font kindFont, textFont, hintFont;
        List<Note> notes = new List<Note>();
        int hover = -1, top;
        public Action<Note> Picked;

        public NoteRows(float k)
        {
            this.k = k;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            kindFont = new Font(Theme.SemiBold, 12 * k, GraphicsUnit.Pixel);
            textFont = new Font(Theme.Regular, 14 * k, GraphicsUnit.Pixel);
            hintFont = new Font(Theme.Regular, 13 * k, GraphicsUnit.Pixel);
        }

        float Row { get { return RowHeight * k; } }

        public void Fill(List<Note> shown)
        {
            notes = shown;
            top = Math.Max(0, Math.Min(top, notes.Count - (int)(Height / Row)));
            Invalidate();
        }

        int At(Point p)
        {
            int i = top + (int)(p.Y / Row);
            return p.Y >= 0 && i < notes.Count ? i : -1;
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            int at = At(e.Location);
            Cursor = at >= 0 ? Cursors.Hand : Cursors.Default;
            if (at != hover) { hover = at; Invalidate(); }
            base.OnMouseMove(e);
        }

        protected override void OnMouseLeave(EventArgs e) { hover = -1; Invalidate(); base.OnMouseLeave(e); }

        protected override void OnMouseClick(MouseEventArgs e)
        {
            int at = At(e.Location);
            if (e.Button == MouseButtons.Left && at >= 0) Picked(notes[at]);
            base.OnMouseClick(e);
        }

        protected override void OnMouseWheel(MouseEventArgs e)
        {
            int most = Math.Max(0, notes.Count - (int)(Height / Row));
            top = Math.Max(0, Math.Min(most, top - Math.Sign(e.Delta)));
            hover = At(e.Location);
            Invalidate();
            base.OnMouseWheel(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            Theme.Prepare(g);
            g.Clear(Theme.Surface);
            if (notes.Count == 0)
            {
                using (var ink = new SolidBrush(Theme.Secondary))
                    g.DrawString(Say.EmptyBoard, hintFont, ink, new RectangleF(16 * k, 4 * k, Width - 32 * k, Height - 8 * k));
                return;
            }
            using (var oneLine = new StringFormat { Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap })
            using (var right = new StringFormat { Alignment = StringAlignment.Far, LineAlignment = StringAlignment.Center })
            using (var muted = new SolidBrush(Theme.Muted))
            using (var secondary = new SolidBrush(Theme.Secondary))
            using (var ink = new SolidBrush(Theme.Text))
            using (var lit = new SolidBrush(Theme.Hover))
                for (int i = top; i < notes.Count && (i - top) * Row < Height; i++)
                {
                    var note = notes[i];
                    float y = (i - top) * Row;
                    float end = Width - 16 * k;
                    if (i == hover)
                    {
                        using (var path = Theme.Rounded(new RectangleF(8 * k, y + 2 * k, Width - 16 * k, Row - 4 * k), 6 * k)) g.FillPath(lit, path);
                        float go = g.MeasureString(Say.GoThere, kindFont).Width;
                        g.DrawString(Say.GoThere, kindFont, secondary, new RectangleF(end - go - 4 * k, y, go + 4 * k, Row), right);
                        end -= go + 12 * k;
                    }
                    Pins.Badge(g, note.Number.ToString(CultureInfo.InvariantCulture), new PointF(30 * k, y + Row / 2), 22 * k, Pins.Of(note.Kind), i == hover ? Theme.Hover : Theme.Surface, k, false);
                    float x = 52 * k;
                    var kind = Say.Kinds[(int)note.Kind] + (note.Marks.Count > 1 ? ", " + Say.Spots(note.Marks.Count) : "");
                    g.DrawString(kind, kindFont, muted, new RectangleF(x, y + 5 * k, end - x, 18 * k), oneLine);
                    g.DrawString(note.Text.Replace("\r", "").Replace('\n', ' '), textFont, ink, new RectangleF(x, y + 22 * k, end - x, 22 * k), oneLine);
                }
        }
    }

    // The list of all notes on the pinboard, with Save as file and Done.
    class NoteList : Card
    {
        const int MaxRows = 6;
        readonly float k;
        readonly NoteRows rows;
        readonly SoftButton saveFile = new SoftButton(), done = new SoftButton { Primary = true }, close = new SoftButton { Blank = true, Icon = Glyph.Close };
        readonly Font titleFont, countFont;
        int count;
        public Action Done, SaveFile, Dismissed;
        public Action<Note> Picked { set { rows.Picked = value; } }

        public NoteList(float k)
        {
            this.k = k;
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            BackColor = Theme.Surface;
            DoubleBuffered = true;
            Border = ColorRef(Theme.Surface3);
            Instant = true;
            titleFont = new Font(Theme.SemiBold, 15 * k, GraphicsUnit.Pixel);
            countFont = new Font(Theme.Regular, 14 * k, GraphicsUnit.Pixel);
            var buttonFont = new Font(Theme.SemiBold, 14 * k, GraphicsUnit.Pixel);
            int w = S(320);
            Grip = S(44);
            rows = new NoteRows(k) { Bounds = new Rectangle(0, S(48), w, S(56)) };

            close.Under = Theme.Surface;
            close.Radius = S(6);
            close.K = k;
            close.Square = S(28);
            close.Bounds = new Rectangle(w - S(8) - S(36), S(6), S(36), S(36));
            close.Click += (o, e) => Dismissed();
            new ToolTip().SetToolTip(close, Say.ClosePinboard);
            foreach (var b in new[] { saveFile, done })
            {
                b.Font = buttonFont;
                b.Under = Theme.Surface;
                b.Radius = S(6);
                b.K = k;
            }
            saveFile.Text = Say.SaveFile;
            done.Text = Say.Done;
            saveFile.Click += (o, e) => SaveFile();
            done.Click += (o, e) => Done();
            Controls.AddRange(new Control[] { close, rows, saveFile, done });
            Fill(new List<Note>());
            Allow(false);
        }

        int S(float v) { return (int)Math.Round(v * k); }

        protected override bool ShowWithoutActivation { get { return true; } }

        public void Fill(List<Note> notes)
        {
            count = notes.Count;
            int w = S(320);
            int listHeight = count == 0 ? S(56) : S(NoteRows.RowHeight) * Math.Min(count, MaxRows);
            rows.Height = listHeight;
            int y = rows.Bottom + S(12);
            int doneWidth = S(104);
            done.Bounds = new Rectangle(w - S(16) - doneWidth, y, doneWidth, S(36));
            saveFile.Bounds = new Rectangle(S(16), y, done.Left - S(8) - S(16), S(36));
            Size = new Size(w, y + S(36) + S(16));
            rows.Fill(notes);
            Invalidate();
        }

        // A note still open in the editor counts too, since Done takes it along.
        public void Allow(bool send)
        {
            if (saveFile.Enabled == send) return;
            saveFile.Enabled = done.Enabled = send;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            Theme.Prepare(g);
            var head = new RectangleF(S(16), S(6), close.Left - S(24), S(36));
            using (var ink = new SolidBrush(Theme.Text))
            using (var muted = new SolidBrush(Theme.Muted))
            using (var format = new StringFormat { LineAlignment = StringAlignment.Center, FormatFlags = StringFormatFlags.NoWrap })
            {
                g.DrawString(Say.Pinboard, titleFont, ink, head, format);
                if (count == 0) return;
                float x = head.X + g.MeasureString(Say.Pinboard, titleFont).Width + S(2);
                g.DrawString(count.ToString(CultureInfo.CurrentCulture), countFont, muted, new RectangleF(x, head.Y + S(1), head.Right - x, head.Height), format);
            }
        }
    }

    // The see-through layer over the share while the pinboard is open. It takes the clicks that
    // would otherwise reach the shared window.
    class Overlay : Form
    {
        public Overlay()
        {
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            Cursor = Cursors.Cross;
        }

        protected override bool ShowWithoutActivation { get { return true; } }

        // Layered tool window.
        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.ExStyle |= 0x80000 | 0x80;
                return p;
            }
        }

        public void Push(Bitmap bmp, Point at)
        {
            if (!Visible) Show();
            Layered.Push(Handle, bmp, at, 255);
        }
    }

    // The pinboard over one share: the overlay that takes the marks, the card for a note and the
    // list of them all. The panel calls Follow on every tick while it is open.
    class Pinboard
    {
        const float DragStart = 6, Gap = 12;
        const string Settings = @"HKEY_CURRENT_USER\Software\KnightSight";
        static readonly TimeSpan FlashSpan = TimeSpan.FromMilliseconds(900);

        readonly Board board;
        readonly float k;
        readonly Overlay overlay = new Overlay();
        readonly NoteEditor editor;
        readonly NoteList list;
        Rectangle area, editorAnchor;
        float density = 1;
        Bitmap picture;
        bool dirty = true, editing, listMoved, placing;
        Point listOffset;
        Point? down;
        Rectangle draft;
        // The marks of the note in the editor, which Shift adds to and takes from before it is saved.
        List<RectangleF> marks = new List<RectangleF>();
        bool marksChanged, adding;
        Note hover, flash;
        DateTime flashStart;
        public Action Finish, SaveFile, Closed;

        public Pinboard(Board board, float k)
        {
            this.board = board;
            this.k = k;
            editor = new NoteEditor(k) { Owner = overlay };
            list = new NoteList(k) { Owner = overlay };
            editor.Saved = Save;
            editor.Deleted = Delete;
            editor.Dismissed = CloseNote;
            editor.KindChanged = () => { if (editing) Render(); };
            editor.Typed = () => list.Allow(board.Notes.Count > 0 || (editing && editor.CanSave));
            list.Done = () => { KeepOpenNote(); Finish(); };
            list.SaveFile = () => { KeepOpenNote(); SaveFile(); };
            list.Dismissed = () => Closed();
            list.Picked = GoTo;
            list.LocationChanged += (o, e) =>
            {
                if (placing || !list.Visible) return;
                listMoved = true;
                listOffset = new Point(list.Left - area.X, list.Top - area.Y);
            };
            overlay.MouseDown += (o, e) => Pressed(e);
            overlay.MouseMove += (o, e) => Moved(e);
            overlay.MouseUp += (o, e) => Released(e);
            overlay.KeyDown += (o, e) =>
            {
                if (e.KeyCode != Keys.Escape) return;
                if (editing) CloseNote();
                else Closed();
            };
        }

        public IWin32Window Window { get { return list; } }

        // Bottom first, as the panel stacks them above the share.
        public IEnumerable<Form> Windows { get { return new Form[] { overlay, list, editor }; } }

        public IEnumerable<Form> Cards { get { return new Form[] { list, editor }; } }

        static string Author
        {
            get { return Microsoft.Win32.Registry.GetValue(Settings, "Author", "") as string ?? ""; }
            set { Microsoft.Win32.Registry.SetValue(Settings, "Author", value); }
        }

        Rectangle OnScreen(RectangleF mark) { return Spot.ToScreen(mark, area, density); }

        IList<RectangleF> MarksOf(Note note) { return editing && editor.Note == note ? marks : note.Marks; }

        int MarkAt(IList<RectangleF> those, Point screen)
        {
            for (int m = those.Count - 1; m >= 0; m--)
                if (Spot.Shows(those[m], area, density) && Pins.Hits(OnScreen(those[m]), screen, k)) return m;
            return -1;
        }

        Note NoteAt(Point screen)
        {
            for (int i = board.Notes.Count - 1; i >= 0; i--)
                if (MarkAt(MarksOf(board.Notes[i]), screen) >= 0) return board.Notes[i];
            return null;
        }

        public void Follow(Rectangle bounds, float scale)
        {
            if (bounds.Width <= 0 || bounds.Height <= 0) { Conceal(); return; }
            bool moved = bounds != area;
            if (bounds.Size != area.Size || scale != density) dirty = true;
            area = bounds;
            density = scale;
            if (flash != null)
            {
                dirty = true;
                if (DateTime.UtcNow - flashStart > FlashSpan) flash = null;
            }
            if (dirty) Render();
            else if (moved || !overlay.Visible) overlay.Push(picture, area.Location);
            PlaceList();
            if (editing) PlaceEditor();
        }

        // Out of sight for a moment, for a picture taken off the screen. The next Follow brings it back.
        public void Conceal()
        {
            foreach (var w in Windows) if (w.Visible) w.Hide();
            area = Rectangle.Empty;
        }

        public void Hide()
        {
            Conceal();
            editing = false;
            down = null;
            draft = Rectangle.Empty;
            hover = flash = null;
        }

        void Render()
        {
            dirty = false;
            if (picture == null || picture.Size != area.Size)
            {
                if (picture != null) picture.Dispose();
                picture = new Bitmap(area.Width, area.Height, PixelFormat.Format32bppArgb);
            }
            using (var g = Graphics.FromImage(picture))
            {
                Theme.Prepare(g);
                g.Clear(Color.FromArgb(20, 0, 0, 0));
                g.TranslateTransform(-area.X, -area.Y);
                foreach (var note in board.Notes)
                    if (!editing || editor.Note != note) DrawMarks(g, note.Kind, note.Number, note.Marks, note == hover || note == flash, note == flash);
                if (editing) DrawMarks(g, editor.Kind, editor.Note != null ? editor.Note.Number : board.Next, marks, true, editor.Note != null && editor.Note == flash);
                if (!draft.IsEmpty) Pins.Draft(g, draft, k);
            }
            overlay.Push(picture, area.Location);
        }

        void DrawMarks(Graphics g, NoteKind kind, int number, IList<RectangleF> those, bool lit, bool flashing)
        {
            for (int i = 0; i < those.Count; i++)
            {
                if (!Spot.Shows(those[i], area, density)) continue;
                var r = OnScreen(those[i]);
                if (flashing) Halo(g, kind, r);
                Pins.Draw(g, kind, Note.Label(number, i, those.Count), r, k, lit);
            }
        }

        // A ring that widens and fades around a mark Go there points at.
        void Halo(Graphics g, NoteKind kind, Rectangle r)
        {
            bool pin = r.Width == 0 && r.Height == 0;
            float t = Math.Min(1, (float)((DateTime.UtcNow - flashStart).TotalMilliseconds / FlashSpan.TotalMilliseconds));
            float grow = (pin ? 16 : 6) * k + 14 * k * Motion.Ease(t);
            using (var pen = new Pen(Color.FromArgb((int)(200 * (1 - t)), Pins.Of(kind)), 3 * k))
            {
                if (pin) g.DrawEllipse(pen, r.X - grow, r.Y - grow, 2 * grow, 2 * grow);
                else g.DrawRectangle(pen, r.X - grow, r.Y - grow, r.Width + 2 * grow, r.Height + 2 * grow);
            }
        }

        void PlaceList()
        {
            if (!list.Visible)
            {
                list.Fill(board.Notes);
                list.Allow(board.Notes.Count > 0);
                list.Show();
            }
            var size = list.Size;
            var work = Screen.FromRectangle(area).WorkingArea;
            int gap = (int)(Gap * k);
            Point at;
            if (listMoved) at = new Point(area.X + listOffset.X, area.Y + listOffset.Y);
            else if (area.Right + gap + size.Width <= work.Right) at = new Point(area.Right + gap, area.Top);
            else if (area.Left - gap - size.Width >= work.Left) at = new Point(area.Left - gap - size.Width, area.Top);
            else at = new Point(area.Right - gap - size.Width, area.Top + gap);
            at.Y = Math.Max(work.Top, Math.Min(at.Y, work.Bottom - size.Height));
            if (list.Location == at) return;
            placing = true;
            list.Location = at;
            placing = false;
        }

        // Right of the mark where the screen has room, else left of it, else below it. Once
        // placed it stays where the person drags it until the mark moves.
        void PlaceEditor()
        {
            var r = OnScreen(marks[0]);
            if (!editor.Visible) editor.Show();
            if (r == editorAnchor) return;
            editorAnchor = r;
            var size = editor.Size;
            var work = Screen.FromRectangle(area).WorkingArea;
            int gap = (int)(Gap * k), reach = r.Width == 0 ? (int)(16 * k) : 0;
            var at = new Point(r.Right + reach + gap, r.Top - (int)(10 * k));
            if (at.X + size.Width > work.Right) at.X = r.Left - reach - gap - size.Width;
            if (at.X < work.Left)
            {
                at.X = r.Left;
                at.Y = r.Bottom + reach + gap;
            }
            at.X = Math.Max(work.Left, Math.Min(at.X, work.Right - size.Width));
            at.Y = Math.Max(work.Top, Math.Min(at.Y, work.Bottom - size.Height));
            editor.Location = at;
        }

        void Pressed(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) return;
            var p = new Point(area.X + e.X, area.Y + e.Y);
            adding = editing && (Control.ModifierKeys & Keys.Shift) != 0;
            if (adding)
            {
                int own = MarkAt(marks, p);
                if (own < 0)
                {
                    down = p;
                    return;
                }
                if (Note.RemoveMark(marks, own)) marksChanged = true;
                else System.Media.SystemSounds.Beep.Play();
                editorAnchor = Rectangle.Empty;
                Render();
                editor.Begin(false);
                return;
            }
            if (editing && (editor.Dirty || marksChanged))
            {
                editor.Begin(false);
                return;
            }
            var hit = NoteAt(p);
            if (hit != null) Open(hit);
            else down = p;
        }

        void Moved(MouseEventArgs e)
        {
            var p = new Point(area.X + e.X, area.Y + e.Y);
            if (down.HasValue)
            {
                var d = down.Value;
                if (draft.IsEmpty && Math.Abs(p.X - d.X) < DragStart * k && Math.Abs(p.Y - d.Y) < DragStart * k) return;
                p.X = Math.Max(area.Left, Math.Min(p.X, area.Right - 1));
                p.Y = Math.Max(area.Top, Math.Min(p.Y, area.Bottom - 1));
                draft = Rectangle.FromLTRB(Math.Min(d.X, p.X), Math.Min(d.Y, p.Y), Math.Max(d.X, p.X), Math.Max(d.Y, p.Y));
                Render();
                return;
            }
            var over = NoteAt(p);
            overlay.Cursor = over != null ? Cursors.Hand : Cursors.Cross;
            if (over == hover) return;
            hover = over;
            Render();
        }

        void Released(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left || !down.HasValue) return;
            var start = Spot.ToShare(down.Value, area, density);
            var mark = draft.IsEmpty
                ? new RectangleF(start, SizeF.Empty)
                : new RectangleF(Spot.ToShare(draft.Location, area, density), new SizeF(draft.Width / density, draft.Height / density));
            down = null;
            draft = Rectangle.Empty;
            if (adding)
            {
                if (Note.AddMark(marks, mark)) marksChanged = true;
                else System.Media.SystemSounds.Beep.Play();
                Render();
                editor.Begin(false);
                return;
            }
            marks = new List<RectangleF> { mark };
            marksChanged = false;
            editor.Open(null, Author);
            Opened();
        }

        void Open(Note note)
        {
            marks = new List<RectangleF>(note.Marks);
            marksChanged = false;
            editor.Open(note, Author);
            Opened();
        }

        void Opened()
        {
            editing = true;
            editorAnchor = Rectangle.Empty;
            PlaceEditor();
            editor.Begin(editor.Note != null);
            Render();
        }

        void GoTo(Note note)
        {
            flash = note;
            flashStart = DateTime.UtcNow;
            if (note.Marks.Exists(m => Spot.Shows(m, area, density))) Open(note);
            Render();
        }

        void Save()
        {
            Author = editor.Author;
            if (editor.Note == null) board.Add(marks, editor.Kind, editor.NoteText, editor.Author);
            else
            {
                editor.Note.Marks = new List<RectangleF>(marks);
                editor.Note.Kind = editor.Kind;
                editor.Note.Text = editor.NoteText;
                editor.Note.Author = editor.Author;
            }
            CloseNote();
        }

        void KeepOpenNote()
        {
            if (editing && editor.CanSave) Save();
        }

        void Delete()
        {
            board.Notes.Remove(editor.Note);
            CloseNote();
        }

        void CloseNote()
        {
            editing = false;
            marks = new List<RectangleF>();
            marksChanged = false;
            editor.Hide();
            list.Fill(board.Notes);
            list.Allow(board.Notes.Count > 0);
            Render();
        }
    }

    public class Panel : Card
    {
        const int MaxEdge = 1568, Port = 47613;
        const float PanelWidth = 720, PanelHeight = 304, BarHeight = 44, Gutter = 20, FinderWidth = 252;
        // A request less than this long ago counts as work in progress: frame and badge stay lit
        // through the pauses between the steps of one task.
        static readonly long WorkSpan = TimeSpan.FromSeconds(5).Ticks;
        const float PulsePeriod = 1400;
        static readonly HashSet<string> ShellClasses = new HashSet<string> { "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW" };

        readonly Frame frame = new Frame();
        readonly Badge badge;
        readonly Pointer pointer;
        readonly Hotkeys hotkeys;
        readonly System.Windows.Forms.Timer tick = new System.Windows.Forms.Timer { Interval = 15 };
        readonly SoftButton pickWindow = new SoftButton { Icon = Glyph.Window }, pickRegion = new SoftButton { Icon = Glyph.Region },
            pickScreen = new SoftButton { Icon = Glyph.Screen },
            toggle = new SoftButton { Primary = true, Icon = Glyph.Start }, info = new SoftButton { Blank = true, Icon = Glyph.Info },
            minimise = new SoftButton { Blank = true, Icon = Glyph.Minimise }, close = new SoftButton { Blank = true, Icon = Glyph.Close },
            pin = new SoftButton { Icon = Glyph.Pin };
        readonly Board board = new Board();
        readonly Pinboard pinboard;
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
        bool picking, buttonWasDown, working, fetchedShown;
        // What the panel says about the notes sent last, until the share ends.
        string sentNote;
        // The finder's picture of the share, refreshed about once a second, and where its corners
        // stand: wide and breathing until the share starts, then snapped in close.
        Bitmap preview;
        long previewDue, clickTicks;
        int previewBusy;
        float corners = 18, cornerSpeed, lit, clickX, clickY;

        RectangleF Finder { get { var c = Card; return new RectangleF(c.X + S(24), c.Y + S(24), S(FinderWidth), c.Height - S(48)); } }

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
            titleFont = new Font(Theme.SemiBold, S(18), GraphicsUnit.Pixel);
            bodyFont = new Font(Theme.Regular, S(14), GraphicsUnit.Pixel);
            tipFont = new Font(Theme.Regular, S(13), GraphicsUnit.Pixel);
            var buttonFont = new Font(Theme.SemiBold, S(14), GraphicsUnit.Pixel);

            Text = "KnightSight";
            Icon = Logo.MakeIcon((int)S(32));
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Theme.Ground;
            DoubleBuffered = true;
            Size = new Size((int)S(PanelWidth), (int)S(PanelHeight));
            Grip = (int)S(BarHeight);
            badge = new Badge(k);
            pointer = new Pointer(k);

            var card = Card;
            float side = Finder.Right + S(28), sideWidth = card.Right - S(24) - side;
            float small = (sideWidth - S(20)) / 3, shareY = card.Bottom - S(24) - S(52), rowY = shareY - S(12) - S(40);
            Place(pickWindow, Say.PickWindow, buttonFont, side, rowY, small, S(40));
            Place(pickRegion, Say.PickRegion, buttonFont, side + small + S(10), rowY, small, S(40));
            Place(pickScreen, Say.PickScreen, buttonFont, side + 2 * (small + S(10)), rowY, small, S(40));
            Place(pin, Say.Pinboard, buttonFont, side, shareY, S(132), S(52));
            Place(toggle, Say.StartShare, new Font(Theme.SemiBold, S(15), GraphicsUnit.Pixel), side + S(142), shareY, sideWidth - S(142), S(52));
            toggle.Radius = S(12);
            tip.SetToolTip(pickWindow, Say.PickWindowTip);
            tip.SetToolTip(pickRegion, Say.PickRegionTip);
            tip.SetToolTip(pickScreen, Say.PickScreenTip);
            tip.SetToolTip(pin, Say.PinboardTip);
            info.Cursor = Cursors.Help;
            PlaceOnBar(close, Say.Close, PanelWidth - 50);
            PlaceOnBar(minimise, Say.Minimise, PanelWidth - 92);
            PlaceOnBar(info, Say.Help, PanelWidth - 134);
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
            pickScreen.Click += (o, e) => PickScreen();
            toggle.Click += (o, e) => { if (active) Stop(); else Start(); };
            minimise.Click += (o, e) => WindowState = FormWindowState.Minimized;
            close.Click += (o, e) => Close();
            pin.Click += (o, e) => TogglePinboard();
            Controls.AddRange(new Control[] { pickWindow, pickRegion, pickScreen, pin, toggle, info, minimise, close });
            pinboard = new Pinboard(board, k) { Finish = FinishPinboard, SaveFile = SavePinboard, Closed = ClosePinboard };

            hotkeys = new Hotkeys(id => { if (id == 1) Stop(); else TogglePinboard(); });
            hotkeys.Register(1, Hotkeys.Control | Hotkeys.Alt | Hotkeys.Shift, Keys.X);

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
            b.Radius = S(10);
            b.K = k;
            b.Bounds = Rectangle.Round(new RectangleF(x, y, w, h));
        }

        void PlaceOnBar(SoftButton b, string name, float x)
        {
            b.Under = Theme.Ground;
            b.Radius = S(6);
            b.K = k;
            b.Square = S(28);
            b.Bounds = Rectangle.Round(new RectangleF(S(x), 0, S(42), S(BarHeight)));
            tip.SetToolTip(b, name);
        }

        // The minimise box lets Windows play its animation.
        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.Style |= 0x00020000;
                return p;
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            Theme.Prepare(g);
            var card = Card;
            using (var path = Theme.Rounded(card, S(16)))
            using (var brush = new SolidBrush(Theme.Surface))
                g.FillPath(brush, path);

            var finder = Finder;
            DrawFinder(g, finder);
            float side = finder.Right + S(28), sideWidth = card.Right - S(24) - side;
            Logo.Draw(g, side, card.Y + S(24), S(32));
            var head = new RectangleF(side + S(44), card.Y + S(28), sideWidth - S(44), S(26));
            var sub = new RectangleF(side + S(18), card.Y + S(66), sideWidth - S(18), S(20));
            // The state dot: grey until shared, accent while shared, pulsing while work goes on.
            float d = S(8), mx = side, my = sub.Y + S(10);
            if (working && Motion.Control > 0)
                using (var halo = new SolidBrush(Color.FromArgb((int)(80 * pulse), Theme.Warning)))
                    g.FillEllipse(halo, mx + d / 2 - d, my - d, d * 2, d * 2);
            using (var brush = new SolidBrush(dotColor))
                g.FillEllipse(brush, mx, my - d / 2, d, d);
            // A new text slides up into place while the old one fades out above it.
            float t = Motion.Ease(swap), shift = S(6);
            if (t < 1) Texts(g, head, sub, oldHeadline, oldSubline, 1 - t, -shift * t);
            Texts(g, head, sub, headline, subline, t, shift * (1 - t));
        }

        // The finder shows the share itself, grey while it is only chosen and in colour once it is
        // shared. A line sweeps over it while the assistant works, and a dot marks its last click.
        void DrawFinder(Graphics g, RectangleF finder)
        {
            using (var path = Theme.Rounded(finder, S(12)))
            using (var brush = new SolidBrush(Theme.Dark ? Color.FromArgb(18, 17, 16) : Theme.Surface2))
                g.FillPath(brush, path);
            var view = RectangleF.Inflate(finder, -S(18), -S(18));
            float t = Motion.Ease(lit);
            var shot = preview;
            if (chosen == null)
                using (var brush = new SolidBrush(Theme.Muted))
                using (var format = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
                    g.DrawString(Say.NoTarget, bodyFont, brush, finder, format);
            else if (shot != null)
            {
                float fit = Math.Min(view.Width / shot.Width, view.Height / shot.Height) * (0.94f + 0.06f * t);
                var at = new RectangleF(view.X + (view.Width - shot.Width * fit) / 2, view.Y + (view.Height - shot.Height * fit) / 2, shot.Width * fit, shot.Height * fit);
                float grey = 1 - t, a = 0.55f + 0.45f * t;
                var matrix = new ColorMatrix(new[] {
                    new[] { t + grey * 0.30f, grey * 0.30f, grey * 0.30f, 0, 0 },
                    new[] { grey * 0.59f, t + grey * 0.59f, grey * 0.59f, 0, 0 },
                    new[] { grey * 0.11f, grey * 0.11f, t + grey * 0.11f, 0, 0 },
                    new[] { 0f, 0, 0, a, 0 },
                    new[] { 0f, 0, 0, 0, 1 } });
                using (var clip = Theme.Rounded(at, S(5)))
                using (var attributes = new ImageAttributes())
                {
                    attributes.SetColorMatrix(matrix);
                    var saved = g.Clip;
                    g.SetClip(clip, CombineMode.Intersect);
                    g.DrawImage(shot, Rectangle.Round(at), 0, 0, shot.Width, shot.Height, GraphicsUnit.Pixel, attributes);
                    if (working && Motion.Control > 0) DrawWork(g, at);
                    g.Clip = saved;
                }
            }
            var box = RectangleF.Inflate(finder, -S(corners), -S(corners));
            float arm = S(20);
            using (var pen = new Pen(Motion.Mix(Theme.Muted, Theme.Accent, t), S(2)) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
                foreach (var c in new[] { new PointF(box.Left, box.Top), new PointF(box.Right, box.Top), new PointF(box.Left, box.Bottom), new PointF(box.Right, box.Bottom) })
                {
                    float sx = c.X == box.Left ? 1 : -1, sy = c.Y == box.Top ? 1 : -1;
                    g.DrawLines(pen, new[] { new PointF(c.X, c.Y + sy * arm), c, new PointF(c.X + sx * arm, c.Y) });
                }
        }

        void DrawWork(Graphics g, RectangleF at)
        {
            float sweep = DateTime.UtcNow.Ticks / 10000 % 1600 / 1600f, y = at.Y + at.Height * sweep;
            int alpha = (int)(230 * Math.Min(1, Math.Min(sweep, 1 - sweep) * 6));
            var line = new RectangleF(at.X, y - S(1), at.Width, S(2));
            using (var brush = new LinearGradientBrush(new RectangleF(line.X - 1, line.Y, line.Width + 2, line.Height), Color.Transparent, Color.Transparent, LinearGradientMode.Horizontal))
            {
                brush.InterpolationColors = new ColorBlend
                {
                    Colors = new[] { Color.FromArgb(0, Theme.Accent), Color.FromArgb(alpha, Theme.Accent), Color.FromArgb(0, Theme.Accent) },
                    Positions = new[] { 0f, 0.5f, 1f },
                };
                g.FillRectangle(brush, line);
            }
            float age = (DateTime.UtcNow.Ticks - Interlocked.Read(ref clickTicks)) / 10000f;
            if (age > 2500) return;
            float cx = at.X + at.Width * clickX, cy = at.Y + at.Height * clickY, d = S(8);
            using (var brush = new SolidBrush(Theme.Warning)) g.FillEllipse(brush, cx - d / 2, cy - d / 2, d, d);
            if (age < 600)
            {
                float ring = d / 2 + S(10) * age / 600;
                using (var pen = new Pen(Color.FromArgb((int)(150 * (1 - age / 600)), Theme.Warning), S(2)))
                    g.DrawEllipse(pen, cx - ring, cy - ring, ring * 2, ring * 2);
            }
        }

        // The picture is taken off the panel's thread, since printing a busy window takes a moment.
        void RefreshPreview(Share share, long now)
        {
            if (now < previewDue || Interlocked.CompareExchange(ref previewBusy, 1, 0) != 0) return;
            previewDue = now + TimeSpan.TicksPerSecond;
            var view = RectangleF.Inflate(Finder, -S(18), -S(18));
            ThreadPool.QueueUserWorkItem(_ =>
            {
                Bitmap small = null;
                try
                {
                    using (var shot = share.Window != IntPtr.Zero ? CaptureWindow(share.Window) : CaptureRegion(share.Area))
                    {
                        float fit = Math.Min(view.Width / shot.Width, view.Height / shot.Height);
                        small = new Bitmap(Math.Max(1, (int)(shot.Width * fit)), Math.Max(1, (int)(shot.Height * fit)));
                        using (var g = Graphics.FromImage(small))
                        {
                            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                            g.DrawImage(shot, 0, 0, small.Width, small.Height);
                        }
                    }
                }
                catch (Refused) { }
                catch (ArgumentException) { }
                catch (ExternalException) { }
                if (IsDisposed) { if (small != null) small.Dispose(); return; }
                BeginInvoke((MethodInvoker)(() =>
                {
                    previewBusy = 0;
                    if (small == null) return;
                    if (chosen != share) { small.Dispose(); return; }
                    var old = preview;
                    preview = small;
                    if (old != null) old.Dispose();
                    Invalidate(Rectangle.Ceiling(Finder));
                }));
            });
        }

        void Texts(Graphics g, RectangleF head, RectangleF sub, string headText, string subText, float alpha, float dy)
        {
            int a = (int)(255 * alpha);
            // Typographic, so the text starts where its rectangle does instead of a few pixels in.
            using (var format = new StringFormat(StringFormat.GenericTypographic) { Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap })
            using (var title = new SolidBrush(Color.FromArgb(a, Theme.Text)))
            using (var body = new SolidBrush(Color.FromArgb(a, Theme.Secondary)))
            {
                head.Offset(0, dy);
                sub.Offset(0, dy);
                g.DrawString(headText, titleFont, title, head, format);
                g.DrawString(subText, bodyFont, body, sub, format);
            }
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            active = false;
            tick.Stop();
            frame.Hide();
            badge.Hide();
            pointer.Vanish();
            pinboard.Hide();
            hotkeys.DestroyHandle();
            base.OnFormClosed(e);
        }

        void ShowState()
        {
            var c = chosen;
            string head = c == null ? Say.NothingChosen : c.Window != IntPtr.Zero ? Win.Title(c.Window) : c.Title, sub;
            if (picking) sub = Say.ClickTarget;
            else if (c == null) sub = Say.ChooseTarget;
            else if (active && board.Open) sub = Say.PinboardOn;
            else if (active && working) sub = Say.Doing + doing;
            else if (active && sentNote != null) sub = board.Fetched ? Say.Fetched : sentNote;
            else if (active) sub = Say.Shared;
            else sub = c.Window != IntPtr.Zero ? Say.WindowChosen : c.Screen ? Say.ScreenChosen : Say.RegionChosen;
            if (head != headline || sub != subline)
            {
                oldHeadline = headline;
                oldSubline = subline;
                headline = head;
                subline = sub;
                swap = 0;
            }
            pickWindow.Enabled = pickRegion.Enabled = pickScreen.Enabled = !active;
            toggle.Enabled = c != null;
            toggle.Text = active ? Say.StopShare : Say.StartShare;
            toggle.Icon = active ? Glyph.Stop : Glyph.Start;
            toggle.Outline = active;
            pin.Enabled = active;
            pin.Primary = board.Open;
            pin.Invalidate();
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
                    Choose(Share.Of(h));
                }
            }
            buttonWasDown = down;
        }

        void PickRegion() { Pick(new RegionPicker(), r => Say.Region + " " + r.Width + " x " + r.Height); }

        // A whole screen is shared as a region of exactly its size.
        void PickScreen()
        {
            var picker = new ScreenPicker(k);
            Pick(picker, r => Say.ScreenTitle(picker.Number, r.Size));
        }

        void Pick(Picker picker, Func<Rectangle, string> title)
        {
            picking = false;
            Hide();
            picker.FormClosed += (o, e) =>
            {
                var r = picker.Result;
                if (!r.IsEmpty) Choose(new Share { Region = r, Screen = picker is ScreenPicker, Title = title(r) });
                Show();
                Activate();
                ShowState();
            };
            picker.Show();
            picker.Activate();
        }

        // Notes belong to the share they were pinned to.
        void Choose(Share share)
        {
            chosen = share;
            pointer.Vanish();
            if (preview != null) { preview.Dispose(); preview = null; }
            previewDue = 0;
            board.Forget();
            pinboard.Hide();
            ShowState();
        }

        // Ctrl+Shift+A belongs to the pinboard only while sharing, so other programs keep it the
        // rest of the time.
        void Start()
        {
            if (chosen == null) return;
            active = true;
            chosen.Elements = null;
            chosen.Clicked = null;
            hotkeys.Register(2, Hotkeys.Control | Hotkeys.Shift, Keys.A);
            sentNote = null;
            ShowState();
        }

        void Stop()
        {
            active = false;
            hotkeys.Release(2);
            pointer.Vanish();
            sentNote = null;
            ClosePinboard();
        }

        // Ends the share the way a closed window does. The handle may already belong to another one.
        void Lose(Share s)
        {
            if (chosen != s) return;
            active = false;
            hotkeys.Release(2);
            frame.Hide();
            HideBadge();
            Choose(null);
        }

        void TogglePinboard()
        {
            var c = chosen;
            if (board.Toggle(active && c != null))
            {
                sentNote = null;
                if (c.Window != IntPtr.Zero) Win.Activate(c.Window);
            }
            else pinboard.Hide();
            ShowState();
        }

        void ClosePinboard()
        {
            board.Close();
            pinboard.Hide();
            ShowState();
        }

        static float Density(Share s)
        {
            uint dpi = s.Window == IntPtr.Zero ? 0 : Native.GetDpiForWindow(s.Window);
            return dpi == 0 ? 1 : dpi / 96f;
        }

        // The picture for the notes is taken without the pinboard on it: a window draws itself,
        // and for a region the pinboard steps aside for the copy off the screen.
        Round Seal(Share s)
        {
            Bitmap shot;
            if (s.Window != IntPtr.Zero) shot = CaptureWindow(s.Window);
            else
            {
                badgeHeld = true;
                try
                {
                    HideBadge();
                    pinboard.Conceal();
                    Thread.Sleep(60);
                    shot = CaptureRegion(s.Region);
                }
                finally { badgeHeld = false; }
            }
            using (shot) return board.Seal(shot, Density(s), s.Window != IntPtr.Zero ? Win.Title(s.Window) : s.Title, DateTime.UtcNow);
        }

        void FinishPinboard()
        {
            var c = chosen;
            if (c == null || board.Notes.Count == 0) return;
            int count = board.Notes.Count;
            Round round;
            try { round = Seal(c); }
            catch (Refused) { System.Media.SystemSounds.Beep.Play(); return; }
            board.Send(round);
            pinboard.Hide();
            sentNote = Say.Sent(count);
            fetchedShown = false;
            ShowState();
        }

        void SavePinboard()
        {
            var c = chosen;
            if (c == null || board.Notes.Count == 0) return;
            Round round;
            try { round = Seal(c); }
            catch (Refused) { System.Media.SystemSounds.Beep.Play(); return; }
            using (var dialog = new SaveFileDialog { FileName = Say.FileName, Filter = Say.FileKind + " (*.html)|*.html", DefaultExt = "html" })
                if (dialog.ShowDialog(pinboard.Window) == DialogResult.OK)
                    File.WriteAllText(dialog.FileName, Board.Page(round), new UTF8Encoding(false));
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
            if (sentNote != null && board.Fetched != fetchedShown) { fetchedShown = board.Fetched; ShowState(); }
            var dotTarget = !active ? Theme.Neutral : working ? Motion.Mix(Theme.Accent, Theme.Warning, pulse) : Theme.Accent;
            if (dotTarget != dotColor || working && moving) { dotColor = dotTarget; Invalidate(); }

            float litTo = active ? 1 : 0, cornersTo = active ? 8 : 18 + 6 * (moving ? 0.5f - 0.5f * (float)Math.Cos(2 * Math.PI * (now.Ticks / 10000 % 2400) / 2400) : 0);
            lit = Motion.Step(lit, litTo, elapsed, Motion.Content);
            if (moving)
            {
                // A spring, so the corners overshoot a little as they lock on.
                float dt = Math.Min(elapsed, 50) / 1000;
                cornerSpeed += ((cornersTo - corners) * 260 - cornerSpeed * 20) * dt;
                corners += cornerSpeed * dt;
            }
            else corners = cornersTo;
            if (moving || lit != litTo) Invalidate(Rectangle.Ceiling(Finder));

            var c = chosen;
            if (c == null) { frame.Hide(); HideBadge(); return; }
            if (c.Window != IntPtr.Zero)
            {
                if (c.Gone) { Lose(c); return; }
                if (Native.IsIconic(c.Window) || Win.IsCloaked(c.Window)) { frame.Hide(); HideBadge(); pinboard.Conceal(); pointer.Vanish(); return; }
            }

            RefreshPreview(c, now.Ticks);
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
            if (board.Open && !badgeHeld) pinboard.Follow(area, Density(c));
            pointer.Follow(area, Stack(c));

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
        // so a window the person has laid over the share stays clear of them. Hands back the
        // ones showing, which the assistant's pointer stacks above.
        List<IntPtr> Stack(Share s)
        {
            var marks = new List<Form>(frame.Windows) { badge };
            marks.AddRange(pinboard.Windows);
            bool top = s.Window == IntPtr.Zero || Win.IsTopmost(s.Window);
            foreach (var mark in marks) if (mark.TopMost != top) mark.TopMost = top;
            var handles = new List<IntPtr>();
            foreach (var mark in marks) if (mark.Visible) handles.Add(mark.Handle);
            if (top) return handles;
            if (active) Win.SinkPopups(s.Window);

            int seen = 0;
            var w = Win.Above(s.Window);
            while (w != IntPtr.Zero && (handles.Contains(w) || pointer.Visible && w == pointer.Handle || Win.IsOwnedBy(w, s.Window)))
            {
                if (handles.Contains(w)) seen++;
                w = Win.Above(w);
            }
            if (seen == handles.Count) return handles;
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
            return handles;
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
            Input.Sent = false;
            try
            {
                var args = json.Deserialize<Dictionary<string, object>>(line);
                object asked;
                // The person sent the notes on purpose, so they are there whether or not
                // anything is shared, and fetching them is no work on the share.
                if (args.TryGetValue("cmd", out asked) && "notes".Equals(asked))
                {
                    foreach (var field in board.Answer(Flag(args, "unread"))) reply[field.Key] = field.Value;
                    reply["ok"] = true;
                    return json.Serialize(reply);
                }
                var s = chosen;
                if (s == null || !active) throw new Refused("Nothing is shared right now. Choose a window or a region in the KnightSight window and start sharing.");
                if (s.Window != IntPtr.Zero && s.Gone)
                {
                    BeginInvoke((MethodInvoker)(() => Lose(s)));
                    throw new Refused("The shared window has closed, so the share has ended.");
                }
                if (s.Window != IntPtr.Zero && Native.IsIconic(s.Window) && !Win.Unminimise(s.Window))
                    throw new Refused("The shared window is minimized and did not come back.");
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
            if (reply.ContainsKey("error") && Input.Sent) reply["delivered"] = "maybe";
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

        public static double Scale(Size size)
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
            var area = s.Area;
            var windows = Readable(s);
            var found = windows == null ? null : ControlTree.Read(windows, area, Scale(area.Size));
            s.Elements = found ?? new List<Element>();
            if (found != null) reply["elements"] = found.ConvertAll(e => e.Fields());
        }

        // A region has no window of its own, so the one under its centre stands in for it.
        // Menus and dialogs are windows of their own and show in the picture, so they count too.
        static List<IntPtr> Readable(Share s)
        {
            var area = s.Area;
            var root = s.Window != IntPtr.Zero ? s.Window : Win.RootAt(area.X + area.Width / 2, area.Y + area.Height / 2);
            if (root == IntPtr.Zero || Win.IsOwn(root)) return null;
            var windows = new List<IntPtr> { root };
            windows.AddRange(Win.Popups(root));
            return windows;
        }

        // A ref stands for the centre of its control in the last look's picture.
        internal static void Aim(Dictionary<string, object> args, List<Element> last, string action)
        {
            object wanted;
            if (args.TryGetValue("ref", out wanted) && wanted != null)
            {
                var name = Convert.ToString(wanted, CultureInfo.InvariantCulture);
                var e = last == null ? null : last.Find(listed => listed.Ref == name);
                if (e == null) throw new Refused("There is no element " + name + " from the last look. Take a new look.");
                args["x"] = e.Box.X + e.Box.Width / 2.0;
                args["y"] = e.Box.Y + e.Box.Height / 2.0;
                return;
            }
            object x, y;
            if (!args.TryGetValue("x", out x) || x == null || !args.TryGetValue("y", out y) || y == null)
                throw new Refused(action + " needs x and y or a ref from look.");
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

        // A region is copied off the screen, so a badge sitting inside it and the pinboard step
        // away for the shot.
        Bitmap CaptureRegionClear(Rectangle r)
        {
            if (!BadgeInside(r) && !board.Open) return CaptureRegion(r);
            badgeHeld = true;
            try
            {
                Invoke((MethodInvoker)(() => { HideBadge(); pinboard.Conceal(); }));
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

        internal static void Clear(Point p, IEnumerable<Rectangle> own)
        {
            foreach (var r in own)
                if (r.Contains(p)) throw new Refused("That point lies on KnightSight itself.");
        }

        // In a region whatever shows at the point takes the input, which may be the panel or a
        // card of the pinboard. A shared window gets its input posted, so nothing on top of it matters.
        void KeepOff(Share s, Point p)
        {
            if (s.Window != IntPtr.Zero) return;
            var own = new List<Rectangle>();
            Invoke((MethodInvoker)(() =>
            {
                if (Visible && WindowState != FormWindowState.Minimized) own.Add(Win.Bounds(Handle));
                foreach (var card in pinboard.Cards) if (card.Visible) own.Add(Win.Bounds(card.Handle));
            }));
            Clear(p, own);
        }

        // The assistant's pointer glides to the spot first, and the action waits until it is there.
        void Present(IntPtr over, Point spot, int clicks)
        {
            int wait = 0;
            Invoke((MethodInvoker)(() => wait = pointer.Aim(over, spot, clicks)));
            Thread.Sleep(wait);
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
            // Real input would land on the pinboard's overlay.
            bool clear = board.Open;
            if (clear)
            {
                badgeHeld = true;
                Invoke((MethodInvoker)pinboard.Conceal);
            }
            try
            {
                if (!Win.Activate(root)) throw new Refused("The shared window cannot be brought to the front.");
                act();
                Thread.Sleep(150);
            }
            finally
            {
                Native.SetCursorPos(cursor.X, cursor.Y);
                Win.Activate(front);
                if (clear) badgeHeld = false;
            }
        }

        string ClickAt(Share s, Dictionary<string, object> args)
        {
            Aim(args, s.Elements, "Click");
            var p = ToScreen(s, args);
            KeepOff(s, p);
            var area = s.Area;
            var spot = new Point(p.X - area.X, p.Y - area.Y);
            clickX = spot.X / (float)area.Width;
            clickY = spot.Y / (float)area.Height;
            Interlocked.Exchange(ref clickTicks, DateTime.UtcNow.Ticks);
            bool right = Flag(args, "right"), twice = Flag(args, "double");
            var root = RootFor(s, p);
            if (s.Window == IntPtr.Zero) s.Focus = root;
            s.Clicked = spot;
            Busy();
            if (Win.NeedsForeground(root))
            {
                Present(root, spot, twice ? 2 : 1);
                Foreground(root, () => Input.Click(p.X, p.Y, right, twice));
                return "Clicked, briefly in the foreground.";
            }
            if (right && Win.IsChromium(root)) throw new Refused("Chromium programs take no right-click in the background. Their menus would stop responding.");
            Present(root, spot, twice ? 2 : 1);
            Input.PostClick(Win.Deepest(Win.PopupAt(root, p), p), p, right, twice);
            return "Clicked.";
        }

        string ScrollAt(Share s, Dictionary<string, object> args)
        {
            Aim(args, s.Elements, "Scroll");
            var p = ToScreen(s, args);
            KeepOff(s, p);
            int notches = (int)Math.Round(Number(args, "amount"));
            var root = RootFor(s, p);
            Busy();
            var area = s.Area;
            Present(root, new Point(p.X - area.X, p.Y - area.Y), 0);
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
            var area = s.Area;
            var spot = s.Clicked ?? new Point(area.Width / 2, area.Height / 2);
            KeepOff(s, new Point(area.X + spot.X, area.Y + spot.Y));
            Busy();
            Present(root, spot, 0);
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
            BeginInvoke((MethodInvoker)pointer.Keep);
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
