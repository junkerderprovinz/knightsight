import AppKit
import KnightSightCore

/// What the person chose: a window, or a region of the screen when window is nil.
final class Chosen {
    let window: CGWindowID?
    let region: CGRect
    let title: String

    init(window: CGWindowID?, region: CGRect, title: String) {
        self.window = window
        self.region = region
        self.title = title
    }
}

/// The state the panel and the threads serving the port share.
final class Session {
    private let lock = NSLock()
    private var storedChosen: Chosen?
    private var storedActive = false
    private var storedDoing = ""
    private var storedLastRequest = Date.distantPast
    private var storedBusyUntil = Date.distantPast
    private var storedMarks: Set<CGWindowID> = []
    private var storedFocus: WindowInfo?
    private var storedLent: (front: pid_t, holder: pid_t)?

    private func locked<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    var chosen: Chosen? {
        get { locked { storedChosen } }
        set { locked { storedChosen = newValue; storedFocus = nil } }
    }

    var active: Bool {
        get { locked { storedActive } }
        set { locked { storedActive = newValue } }
    }

    var doing: String { locked { storedDoing } }
    var lastRequest: Date { locked { storedLastRequest } }
    var busyUntil: Date { locked { storedBusyUntil } }

    /// The frame and badge windows, which pictures and clicks pass through.
    var marks: Set<CGWindowID> {
        get { locked { storedMarks } }
        set { locked { storedMarks = newValue } }
    }

    /// In a region, the window last clicked there. Keys go to it.
    var focus: WindowInfo? {
        get { locked { storedFocus } }
        set { locked { storedFocus = newValue } }
    }

    /// The app that was in front when a click left a menu open in the holder, which keeps the
    /// front until the menu closes.
    var lent: (front: pid_t, holder: pid_t)? {
        get { locked { storedLent } }
        set { locked { storedLent = newValue } }
    }

    func began(_ doing: String) {
        locked {
            storedDoing = doing
            storedLastRequest = Date()
        }
    }

    /// Lights the frame in the warning colour for a moment after each action.
    func busy() {
        locked { storedBusyUntil = Date().addingTimeInterval(0.8) }
    }
}

/// The Mac side of the share. It runs on the threads that serve the port, one request at a time.
final class MacDesk: Desk {
    let layout: KeyLayout = SystemLayout()
    private let session: Session
    private let say: Say
    private let foreground: Foreground

    init(session: Session, say: Say, foreground: Foreground) {
        self.session = session
        self.say = say
        self.foreground = foreground
    }

    func currentShare() -> Share? {
        guard session.active, let chosen = session.chosen else { return nil }
        guard let id = chosen.window else {
            return Share(area: chosen.region, pixelsPerPoint: density(chosen.region), reachable: true)
        }
        guard let shared = Windows.info(id) else { return nil }
        return Share(area: shared.bounds, pixelsPerPoint: density(shared.bounds), reachable: shared.onScreen)
    }

    func began(_ doing: String) {
        session.began(doing)
    }

    func look(size: CGSize) throws -> Screenshot {
        guard CGPreflightScreenCaptureAccess() else {
            throw Refused("KnightSight is not allowed to record the screen yet. The person at the Mac can turn it on in System Settings under Privacy & Security, Screen Recording.")
        }
        let chosen = try current()
        guard let id = chosen.window else {
            let image = try Capture.region(chosen.region, skipping: session.marks, size: size)
            return Screenshot(png: Bitmap.png(image), title: chosen.title, note: nil)
        }
        let shared = try window(id)
        let image = try Capture.window(shared, size: size)
        let note = Windows.fullyCovered(shared, skipping: session.marks)
            ? "The window is fully covered. Some programs, browsers among them, stop drawing then, so the picture may be out of date."
            : nil
        return Screenshot(png: Bitmap.png(image), title: shared.title(say), note: note)
    }

    func click(at point: CGPoint, right: Bool, double: Bool) throws -> String {
        try needInput()
        let chosen = try current()
        let target = try self.target(at: point, in: chosen)
        if chosen.window == nil { session.focus = target }
        let note = try foreground.run(target, at: point) { Input.click(at: point, right: right, twice: double) }
        return "Clicked, briefly in the foreground." + note
    }

    func scroll(at point: CGPoint, notches: Int) throws -> String {
        try needInput()
        let target = try self.target(at: point, in: current())
        let note = try foreground.run(target, at: point) { Input.scroll(at: point, notches: notches) }
        return "Scrolled, briefly in the foreground." + note
    }

    func type(_ text: String) throws -> String {
        try needInput()
        let target = try keyTarget()
        session.busy()
        Input.type(text, to: target.pid)
        return "Typed."
    }

    // An app runs its Cmd shortcuts through the menu bar, which it does only while active.
    func press(_ combo: KeyCombo) throws -> String {
        try needInput()
        let target = try keyTarget()
        guard combo.modifiers.contains(.command) else {
            session.busy()
            Input.press(combo, to: .process(target.pid))
            return "Pressed."
        }
        let note = try foreground.run(target, at: nil) { Input.press(combo, to: .system) }
        return "Pressed, briefly in the foreground." + note
    }

    private func density(_ area: CGRect) -> CGFloat {
        Screens.density(of: Screens.display(for: area))
    }

    private func needInput() throws {
        guard CGPreflightPostEventAccess() else {
            throw Refused("KnightSight is not allowed to send clicks and keys yet. The person at the Mac can turn it on in System Settings under Privacy & Security, Accessibility.")
        }
    }

    // The share can end between the check in the responder and the work here.
    private func current() throws -> Chosen {
        guard let chosen = session.chosen else { throw Refused.nothingShared }
        return chosen
    }

    private func window(_ id: CGWindowID) throws -> WindowInfo {
        guard let shared = Windows.info(id) else { throw Refused.nothingShared }
        return shared
    }

    /// The window a click at this point lands on. In a region that is whatever shows there.
    private func target(at point: CGPoint, in chosen: Chosen) throws -> WindowInfo {
        if let id = chosen.window {
            let shared = try window(id)
            return Windows.visible().first { $0.bounds.contains(point) && ($0.id == id || Windows.isPopup($0, of: shared)) } ?? shared
        }
        guard let found = Windows.front(at: point, skipping: session.marks), found.pid != Windows.ownPid else {
            throw Refused("No window that takes input lies at this point.")
        }
        return found
    }

    // In a region keys go to the window last clicked there, wherever it has moved since.
    private func keyTarget() throws -> WindowInfo {
        let chosen = try current()
        if let id = chosen.window { return try window(id) }
        guard let focus = session.focus.flatMap({ Windows.info($0.id) }) else {
            throw Refused("Keys go to the window last clicked inside the region, and nothing has been clicked there yet.")
        }
        return focus
    }
}
