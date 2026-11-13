import AppKit
import ApplicationServices
import KnightSightCore

/// Clicks, wheel turns and Cmd shortcuts reach an app only as real input while it is active.
/// For those the window comes to the front for a moment, as Store apps do on Windows and every
/// window does on X11: after a pause in the person's own input, and with the front app and the
/// pointer given back afterwards.
final class Foreground {
    private let session: Session
    private let say: Say
    private let lock = NSLock()

    init(session: Session, say: Say) {
        self.session = session
        self.say = say
    }

    /// Runs act with the window in front and returns what the reply should add. With a point,
    /// the window has to be the one a click there reaches.
    func run(_ target: WindowInfo, at point: CGPoint?, _ act: () -> Void) throws -> String {
        lock.lock()
        defer { lock.unlock() }
        try waitForQuiet()
        let pointer = CGEvent(source: nil)!.location
        let front = session.lent?.front ?? Foreground.frontPid()
        try raise(target, at: point)
        session.busy()
        act()
        usleep(150_000)
        print("after 150 ms:", Windows.visible().filter { $0.pid == target.pid }.map { "\($0.layer) \($0.bounds)" }); fflush(stdout)
        usleep(450_000)
        print("after 600 ms:", Windows.visible().filter { $0.pid == target.pid }.map { "\($0.layer) \($0.bounds)" }); fflush(stdout)
        CGWarpMouseCursorPosition(pointer)
        // A menu that just opened would close as soon as another app takes the front.
        if Foreground.menuOpen(in: target.pid) {
            session.lent = (front: front, holder: target.pid)
            return " A menu is open, so the window stays in front until it closes."
        }
        session.lent = nil
        if front != target.pid { Foreground.activate(front) }
        return ""
    }

    /// Gives the front back once the menu that kept it is closed, unless the person has moved on.
    func giveBack() {
        guard let lent = session.lent, lock.try() else { return }
        defer { lock.unlock() }
        guard !Foreground.menuOpen(in: lent.holder) else { return }
        session.lent = nil
        if Foreground.frontPid() == lent.holder { Foreground.activate(lent.front) }
    }

    private func waitForQuiet() throws {
        guard Foreground.idle() < 1.2 else { return }
        let doing = session.doing
        session.began(say.waiting)
        defer { session.began(doing) }
        let giveUp = Date().addingTimeInterval(8)
        while Foreground.idle() < 1.2 {
            if Date() > giveUp { throw Refused("This window needs the foreground for a moment, but the mouse or keyboard is in use.") }
            usleep(100_000)
        }
    }

    private func raise(_ target: WindowInfo, at point: CGPoint?) throws {
        if let window = Foreground.axWindow(of: target) {
            AXUIElementPerformAction(window, kAXRaiseAction as CFString)
        }
        Foreground.activate(target.pid)
        for _ in 0..<50 {
            if Foreground.frontPid() == target.pid,
               point.map({ Windows.front(at: $0, skipping: session.marks)?.pid == target.pid }) ?? true {
                return
            }
            usleep(20_000)
        }
        throw Refused("The shared window cannot be brought to the front.")
    }

    private static func idle() -> Double {
        CGEventSource.secondsSinceLastEventType(.hidSystemState, eventType: CGEventType(rawValue: ~0)!)
    }

    // Accessibility answers at once and from any thread, unlike NSWorkspace, which learns of
    // a change on the main thread.
    private static func frontPid() -> pid_t {
        var app: CFTypeRef?
        var pid: pid_t = 0
        if AXUIElementCopyAttributeValue(AXUIElementCreateSystemWide(), kAXFocusedApplicationAttribute as CFString, &app) == .success {
            AXUIElementGetPid(app as! AXUIElement, &pid)
        }
        return pid
    }

    // Setting the app frontmost through accessibility works for a background app, where
    // activating it through NSRunningApplication alone may be turned down.
    private static func activate(_ pid: pid_t) {
        guard pid > 0 else { return }
        AXUIElementSetAttributeValue(AXUIElementCreateApplication(pid), kAXFrontmostAttribute as CFString, kCFBooleanTrue)
        _ = NSRunningApplication(processIdentifier: pid)?.activate(options: [])
    }

    private static func menuOpen(in pid: pid_t) -> Bool {
        let menu = Int(CGWindowLevelForKey(.popUpMenuWindow))
        return Windows.visible().contains { $0.pid == pid && $0.layer == menu }
    }

    // Accessibility does not name window numbers, so the window is found by its frame.
    private static func axWindow(of target: WindowInfo) -> AXUIElement? {
        var list: CFTypeRef?
        guard AXUIElementCopyAttributeValue(AXUIElementCreateApplication(target.pid), kAXWindowsAttribute as CFString, &list) == .success,
              let windows = list as? [AXUIElement]
        else { return nil }
        return windows.first { window in
            var position = CGPoint.zero, size = CGSize.zero
            guard let p = value(window, kAXPositionAttribute), AXValueGetValue(p as! AXValue, .cgPoint, &position),
                  let s = value(window, kAXSizeAttribute), AXValueGetValue(s as! AXValue, .cgSize, &size)
            else { return false }
            return CGRect(origin: position, size: size).insetBy(dx: -1, dy: -1).contains(target.bounds)
        }
    }

    private static func value(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
        var value: CFTypeRef?
        return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value : nil
    }
}
