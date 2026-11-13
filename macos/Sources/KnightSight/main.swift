import AppKit
import KnightSightCore

// build.sh draws the app icon with the same code as the logo in the panel.
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--icon-set" {
    try Logo.writeIconSet(to: URL(fileURLWithPath: CommandLine.arguments[2]))
    exit(0)
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panel: Panel?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu(), item = NSMenuItem(), appMenu = NSMenu()
        appMenu.addItem(withTitle: Say.current.quit, action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = appMenu
        menu.addItem(item)
        NSApp.mainMenu = menu
        panel = Panel()
        NSApp.activate(ignoringOtherApps: true)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
