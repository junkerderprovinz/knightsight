# Takes the raw pictures for the README from the real KnightSight.exe: a made-up to-do app
# (quest-log.html in an app window) and the panel on a plain dark desk, copied off the screen
# as one picture per scene into captures/. The panel runs in English and follows the Windows
# app theme, so set Windows to dark first. It needs an unlocked desktop session and moves
# windows around for half a minute. Before every picture it makes sure that only its own
# windows and the app show in it, and stops when anything else lies in front.
#
# Run: powershell -STA -File .github\assets\screenshots\capture.ps1 [-Exe dist\KnightSight.exe] [-Only window,region,pinboard]
param([string]$Exe = (Join-Path $PSScriptRoot '..\..\..\dist\KnightSight.exe'), [string[]]$Only = @('window', 'region', 'pinboard'))
$ErrorActionPreference = 'Stop'

$captures = Join-Path $PSScriptRoot 'captures'
New-Item -ItemType Directory -Force $captures | Out-Null
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @'
using System;
using System.Collections;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

public static class Stage
{
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int hh, uint flags);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("gdi32.dll")] static extern bool BitBlt(IntPtr dst, int x, int y, int w, int h, IntPtr src, int sx, int sy, int rop);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int size);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }

    static Form panel;
    static Assembly app;
    // The app's window, which may show in the pictures along with this process's own.
    public static IntPtr Shown;
    const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;

    static void OnOwnThread(ThreadStart body)
    {
        var t = new Thread(body) { IsBackground = true };
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
    }

    public static void Desk(Rectangle r)
    {
        var ready = new ManualResetEvent(false);
        Form desk = null;
        OnOwnThread(delegate
        {
            desk = new Form { FormBorderStyle = FormBorderStyle.None, ShowInTaskbar = false, StartPosition = FormStartPosition.Manual, Bounds = r };
            desk.Paint += (o, e) =>
            {
                using (var b = new LinearGradientBrush(desk.ClientRectangle, Color.FromArgb(40, 41, 46), Color.FromArgb(20, 20, 23), 60f))
                    e.Graphics.FillRectangle(b, desk.ClientRectangle);
            };
            desk.Shown += (o, e) => ready.Set();
            Application.Run(desk);
        });
        ready.WaitOne();
        Raise(desk.Handle);
    }

    // The EXE's own entry point on a thread set to English, so the panel speaks English on any Windows.
    public static void Launch(string exe)
    {
        app = Assembly.LoadFile(exe);
        OnOwnThread(delegate
        {
            Thread.CurrentThread.CurrentUICulture = new CultureInfo("en-US");
            app.EntryPoint.Invoke(null, null);
        });
        for (int i = 0; i < 100 && panel == null; i++)
        {
            Thread.Sleep(100);
            foreach (Form f in Application.OpenForms) if (f.GetType().Name == "Panel" && f.Visible) panel = f;
        }
        if (panel == null) throw new Exception("The panel did not show up.");
    }

    static void Call(string method)
    {
        panel.Invoke((MethodInvoker)delegate { panel.GetType().GetMethod(method, BindingFlags.NonPublic | BindingFlags.Instance).Invoke(panel, null); });
    }

    public static void MovePanel(int x, int y)
    {
        panel.Invoke((MethodInvoker)delegate { panel.Location = new Point(x, y); });
        Raise(panel.Handle);
    }

    // What a click on a window or a dragged rectangle would choose, without the pointer
    // standing in the picture.
    static void Choose(object share)
    {
        panel.Invoke((MethodInvoker)delegate { panel.GetType().GetField("chosen", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(panel, share); });
        Call("ShowState");
    }

    public static void ChooseWindow(IntPtr h)
    {
        // Of also records the window's process, which the panel checks before every request.
        Choose(app.GetType("KnightSight.Share").GetMethod("Of").Invoke(null, new object[] { h }));
    }

    public static void ChooseRegion(Rectangle r)
    {
        var share = Activator.CreateInstance(app.GetType("KnightSight.Share"));
        var region = (string)app.GetType("KnightSight.Say").GetField("Region").GetValue(null);
        share.GetType().GetField("Region").SetValue(share, r);
        share.GetType().GetField("Title").SetValue(share, region + " " + r.Width + " x " + r.Height);
        Choose(share);
    }

    public static void Start() { Call("Start"); }
    public static void Stop() { Call("Stop"); }

    // One request through the pipe, the way the MCP server sends it.
    public static string Ask(string json)
    {
        using (var pipe = new NamedPipeClientStream(".", "knightsight", PipeDirection.InOut))
        {
            pipe.Connect(5000);
            var utf8 = new UTF8Encoding(false);
            new StreamWriter(pipe, utf8) { AutoFlush = true }.WriteLine(json);
            var reply = new StreamReader(pipe, utf8).ReadLine();
            if (!reply.Contains("\"ok\":true")) throw new Exception(reply);
            return reply;
        }
    }

    public static string Title(IntPtr h)
    {
        var s = new StringBuilder(256);
        GetWindowText(h, s, s.Capacity);
        return s.ToString();
    }

    // Puts the visible frame on the rectangle; GetWindowRect also counts the invisible resize border.
    public static void Place(IntPtr h, Rectangle to)
    {
        RECT outer, seen;
        GetWindowRect(h, out outer);
        if (DwmGetWindowAttribute(h, 9, out seen, Marshal.SizeOf(typeof(RECT))) != 0) seen = outer;
        int l = seen.L - outer.L, t = seen.T - outer.T, r = outer.R - seen.R, b = outer.B - seen.B;
        SetWindowPos(h, IntPtr.Zero, to.X - l, to.Y - t, to.Width + l + r, to.Height + t + b, 0x4 | 0x10);
        Raise(h);
    }

    // In and out of topmost lands a window on top of the others without activating it.
    static void Raise(IntPtr h)
    {
        SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, 0x1 | 0x2 | 0x10);
        SetWindowPos(h, new IntPtr(-2), 0, 0, 0, 0, 0x1 | 0x2 | 0x10);
    }

    static bool Ours(IntPtr h)
    {
        uint pid;
        GetWindowThreadProcessId(h, out pid);
        return h == Shown || pid == (uint)Process.GetCurrentProcess().Id;
    }

    // Stops before a picture that would show anything but the stage, such as a window someone
    // works in or one that keeps itself on top. WindowFromPoint passes over click-through
    // windows such as the frame, which belong to the stage anyway.
    public static void Clear(Rectangle r)
    {
        var front = GetAncestor(GetForegroundWindow(), 2);
        for (int y = r.Top + 4; y < r.Bottom; y += 24)
            for (int x = r.Left + 4; x < r.Right; x += 24)
            {
                var root = GetAncestor(WindowFromPoint(new POINT { X = x, Y = y }), 2);
                if (Ours(root)) continue;
                throw new Exception((root == front ? "The window in front, " : "Another window, ") + "\"" + Title(root) + "\", covers " + x + ", " + y + ". Nothing was captured.");
            }
    }

    // CAPTUREBLT brings in the layered windows: the frame and the label.
    public static void Shoot(Rectangle r, string path)
    {
        Clear(r);
        using (var bmp = new Bitmap(r.Width, r.Height, PixelFormat.Format32bppArgb))
        {
            using (var g = Graphics.FromImage(bmp))
            {
                IntPtr screen = GetDC(IntPtr.Zero), dc = g.GetHdc();
                BitBlt(dc, 0, 0, r.Width, r.Height, screen, r.X, r.Y, 0x00CC0020 | 0x40000000);
                g.ReleaseHdc(dc);
                ReleaseDC(IntPtr.Zero, screen);
            }
            bmp.Save(path, ImageFormat.Png);
        }
    }

    static object Get(object o, string name)
    {
        var field = o.GetType().GetField(name, Any);
        return field != null ? field.GetValue(o) : o.GetType().GetProperty(name, Any).GetValue(o, null);
    }

    static object Run(object o, string method, params object[] args) { return o.GetType().GetMethod(method, Any).Invoke(o, args); }

    static object Static(string type, string method, params object[] args)
    {
        return app.GetType("KnightSight." + type).GetMethod(method, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, args);
    }

    static int Find(IList parts, string type, string name)
    {
        for (int i = 0; i < parts.Count; i++)
            if ((type == null || (string)Get(parts[i], "Type") == type) && ((string)Get(parts[i], "Name")).StartsWith(name)) return i;
        return -1;
    }

    // The pinboard as Ctrl+Shift+A opens it, its bar in a colour of the web pinboard. Chromium
    // only builds its accessibility tree once asked, so the elements are read until the one the
    // scene marks shows up.
    public static void OpenPinboard(string colour, string element)
    {
        Call("TogglePinboard");
        Thread.Sleep(800);
        var pinboard = Get(panel, "pinboard");
        for (int i = 0; ; i++)
        {
            IList parts = null;
            panel.Invoke((MethodInvoker)delegate { parts = (IList)Get(pinboard, "parts"); });
            if (parts != null && Find(parts, "button", element) >= 0) break;
            if (i == 40) throw new Exception("The pinboard found no button " + element + ".");
            panel.Invoke((MethodInvoker)delegate { if (!(bool)Get(pinboard, "reading")) Run(pinboard, "ReadParts"); });
            Thread.Sleep(250);
        }
        panel.Invoke((MethodInvoker)delegate { Run(Get(pinboard, "Bar"), "Wear", colour); });
    }

    static object Marks(Type mark, object one)
    {
        var list = Array.CreateInstance(mark, 1);
        list.SetValue(one, 0);
        return list;
    }

    // Three notes, one per tool: a wish on the element named so, a question on a pin in the free
    // space right of an element and a bug around an area, each found by the start of its name.
    // The first note stands open in its card with the caret after its text, and the element
    // under hover lights up as under the pointer.
    // The control names stay in English, as the panel does, whatever language Windows speaks.
    public static void Notes(string element, string wish, string pinOn, string question, string areaOn, string bug, string hover)
    {
        panel.Invoke((MethodInvoker)delegate
        {
            var pinboard = Get(panel, "pinboard");
            var board = Get(panel, "board");
            var share = Get(panel, "chosen");
            var parts = (IList)Get(pinboard, "parts");
            foreach (var part in parts) part.GetType().GetField("Local").SetValue(part, "");
            var area = (Rectangle)Get(share, "Area");
            float density = (float)Static("Panel", "Density", share);
            var markType = app.GetType("KnightSight.Mark");
            var kind = app.GetType("KnightSight.NoteKind");
            Func<Rectangle, RectangleF> inShare = r => new RectangleF((r.X - area.X) / density, (r.Y - area.Y) / density, r.Width / density, r.Height / density);
            Func<int, Rectangle> box = i => Rectangle.Intersect((Rectangle)Get(parts[i], "Box"), area);
            Func<string, int> named = name =>
            {
                int i = Find(parts, null, name);
                if (i < 0) throw new Exception("No element named " + name + ".");
                return i;
            };

            int target = Find(parts, "button", element);
            var on = Activator.CreateInstance(markType, inShare(box(target)), Static("ControlTree", "Describe", parts, target));
            Run(board, "Add", Marks(markType, on), Enum.ToObject(kind, 1), wish, "");
            var spot = box(named(pinOn));
            var pin = Activator.CreateInstance(markType, inShare(new Rectangle(spot.Right + 34, spot.Y + spot.Height / 2, 0, 0)), null);
            Run(board, "Add", Marks(markType, pin), Enum.ToObject(kind, 2), question, "");
            var around = Activator.CreateInstance(markType, inShare(Rectangle.Inflate(box(named(areaOn)), 10, 8)), null);
            Run(board, "Add", Marks(markType, around), Enum.ToObject(kind, 0), bug, "");

            Run(pinboard, "Open", ((IList)Get(board, "Notes"))[0]);
            Run(Get(pinboard, "editor"), "Begin", false);
            int lit = named(hover);
            pinboard.GetType().GetField("hit", Any).SetValue(pinboard, lit);
            pinboard.GetType().GetField("part", Any).SetValue(pinboard, lit);
            Run(pinboard, "Render");
        });
    }
}
'@

# The panel's pulse follows the clock, 1.4 s a round. A quarter of the way in, the frame is
# still mostly yellow with a first touch of orange.
function Wait-Pulse {
    while ($true) {
        $ms = [DateTime]::UtcNow.Ticks / 10000 % 1400
        if ($ms -ge 230 -and $ms -lt 250) { return }
        Start-Sleep -Milliseconds 5
    }
}

function Rect($x, $y, $w, $h) { New-Object System.Drawing.Rectangle ($desk.X + $x), ($desk.Y + $y), $w, $h }

$desk = New-Object System.Drawing.Rectangle 300, 200, 1300, 700
[Stage]::SetCursorPos($desk.Right + 400, $desk.Bottom + 200) | Out-Null
[Stage]::Desk($desk)

# An app window shows the page with nothing of the browser around it.
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$profile = Join-Path $env:TEMP "knightsight-shots-$PID"
$page = 'file:///' + ((Join-Path $PSScriptRoot 'quest-log.html') -replace '\\', '/')
$browser = Start-Process $edge -PassThru -ArgumentList "--app=$page", "--user-data-dir=$profile", '--no-first-run', '--no-default-browser-check', '--disable-sync', '--lang=en-US', '--disable-features=Translate,msEdgeTranslate', '--window-size=700,560'
try {
    $app = [IntPtr]::Zero
    foreach ($i in 1..100) {
        $browser.Refresh()
        if ([Stage]::Title($browser.MainWindowHandle) -eq 'Quest Log') { $app = $browser.MainWindowHandle; break }
        Start-Sleep -Milliseconds 200
    }
    if ($app -eq [IntPtr]::Zero) { throw 'The app window did not show up.' }
    [Stage]::Shown = $app
    [Stage]::Launch((Resolve-Path $Exe).Path)

    if ($Only -contains 'window') {
        [Stage]::Place($app, (Rect 36 96 520 560))
        [Stage]::MovePanel($desk.X + 572, $desk.Y + 250)
        [Stage]::ChooseWindow($app)
        Start-Sleep -Milliseconds 1200
        [Stage]::Shoot($desk, "$captures\pick.png")

        [Stage]::Start()
        Start-Sleep -Milliseconds 900
        [Stage]::Ask('{"cmd":"look"}') | Out-Null
        Start-Sleep -Milliseconds 500
        Wait-Pulse
        [Stage]::Shoot($desk, "$captures\share.png")
        [Stage]::Stop()
        Start-Sleep -Milliseconds 600
    }

    if ($Only -contains 'region') {
        # The region takes the input row and the first two columns, and the cut runs through the input.
        [Stage]::Place($app, (Rect 30 40 520 620))
        [Stage]::MovePanel($desk.X + 572, $desk.Y + 380)
        $region = Rect 40 82 480 364
        [Stage]::ChooseRegion($region)
        [Stage]::Start()
        Start-Sleep -Milliseconds 900
        [Stage]::Ask('{"cmd":"click","x":200,"y":62}') | Out-Null
        Start-Sleep -Milliseconds 400
        [Stage]::Ask('{"cmd":"type","text":"Find out where the gold goes"}') | Out-Null
        Start-Sleep -Milliseconds 500
        Wait-Pulse
        [Stage]::Shoot($desk, "$captures\region.png")
        [Stage]::Stop()
        Start-Sleep -Milliseconds 600
    }

    if ($Only -contains 'pinboard') {
        # Wide enough for the bar at its bottom, with room on the desk for the note's card. The
        # panel waits outside the picture.
        [Stage]::Place($app, (Rect 30 40 860 620))
        [Stage]::MovePanel($desk.Right + 40, $desk.Y + 200)
        [Stage]::ChooseWindow($app)
        [Stage]::Start()
        Start-Sleep -Milliseconds 900
        [Stage]::OpenPinboard('blue', 'Add')
        [Stage]::Notes('Add', 'Call it Add quest, so it says what it adds.', 'Sort quests', 'By the due date of the quest or of its reward?',
            'Drawbridge', 'The tag and the date crowd each other on small screens.', 'Total gold')
        Start-Sleep -Milliseconds 1200
        [Stage]::Shoot($desk, "$captures\pinboard.png")
        [Stage]::Stop()
    }
}
finally {
    if (-not $browser.HasExited) { $browser.CloseMainWindow() | Out-Null; $browser.WaitForExit(5000) | Out-Null }
    if (-not $browser.HasExited) { Stop-Process -Id $browser.Id -Force }
    Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
