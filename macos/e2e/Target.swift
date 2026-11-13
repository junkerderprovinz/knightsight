import AppKit

// A window with a coloured band over a text view. Every click and key it gets goes into the
// log under its title, clicks in points from the top left of the content, so the driver can
// tell where input landed. Arguments: title, colour as rrggbb, top left corner in screen
// points, log.
let args = CommandLine.arguments
let title = args[1]
let rgb = Int(args[2], radix: 16)!
let corner = CGPoint(x: Double(args[3])!, y: Double(args[4])!)
// Both targets write to the same log, so every line goes to its end.
let log = FileHandle(fileDescriptor: open(args[5], O_WRONLY | O_APPEND | O_CREAT, 0o644), closeOnDealloc: true)

func note(_ line: String) {
    log.write(Data("\(title) \(line)\n".utf8))
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)

// Select All reaches a text view through the menu, as in any document app.
let menu = NSMenu(), appItem = NSMenuItem(), editItem = NSMenuItem()
appItem.submenu = NSMenu()
appItem.submenu!.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
editItem.submenu = NSMenu(title: "Edit")
editItem.submenu!.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
menu.addItem(appItem)
menu.addItem(editItem)
app.mainMenu = menu

let window = NSWindow(contentRect: CGRect(x: 0, y: 0, width: 400, height: 300), styleMask: [.titled], backing: .buffered, defer: false)
window.title = title
window.appearance = NSAppearance(named: .aqua)
let band = NSView(frame: CGRect(x: 0, y: 200, width: 400, height: 100))
band.wantsLayer = true
band.layer?.backgroundColor = CGColor(
    srgbRed: CGFloat(rgb >> 16 & 0xFF) / 255, green: CGFloat(rgb >> 8 & 0xFF) / 255, blue: CGFloat(rgb & 0xFF) / 255, alpha: 1)
let scroll = NSScrollView(frame: CGRect(x: 0, y: 0, width: 400, height: 200))
let text = NSTextView(frame: scroll.bounds)
text.isRichText = false
text.font = .systemFont(ofSize: 18)
text.backgroundColor = .white
text.textColor = .black
scroll.documentView = text
scroll.contentView.postsBoundsChangedNotifications = true
NotificationCenter.default.addObserver(forName: NSView.boundsDidChangeNotification, object: scroll.contentView, queue: .main) { _ in
    note("scrolled \(Int(scroll.contentView.bounds.minY))")
}
window.contentView!.addSubview(band)
window.contentView!.addSubview(scroll)
window.setFrameTopLeftPoint(CGPoint(x: corner.x, y: NSScreen.screens[0].frame.height - corner.y))
window.makeFirstResponder(text)
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)

_ = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown, .keyDown]) { event in
    if event.type == .keyDown {
        note("key \(event.charactersIgnoringModifiers ?? "")\(event.modifierFlags.contains(.command) ? " cmd" : "")")
    } else if let content = event.window?.contentView {
        let p = content.convert(event.locationInWindow, from: nil)
        note("click \(Int(p.x.rounded())) \(Int((content.bounds.height - p.y).rounded()))")
    }
    return event
}

app.run()
