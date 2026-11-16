import AppKit
import ApplicationServices
import KnightSightCore

/// What the person chose: a window, or a region of the screen when window is nil.
final class Chosen {
    let window: CGWindowID?
    let owner: Owner?
    let region: CGRect
    let title: String
    let screen: Bool

    init(window: CGWindowID?, owner: Owner? = nil, region: CGRect, title: String, screen: Bool = false) {
        self.window = window
        self.owner = owner
        self.region = region
        self.title = title
        self.screen = screen
    }

    /// The chosen window as it is now. A window whose number another process holds by now
    /// counts as closed.
    var current: WindowInfo? {
        guard let window, let owner, let shared = Windows.info(window), owner.owns(shared.pid, startTime: Processes.started) else { return nil }
        return shared
    }
}

/// The state the panel and the threads serving the port share.
final class Session {
    private let lock = NSLock()
    private var storedChosen: Chosen?
    private var storedActive = false
    private var storedSerial = 0
    private var storedDoing = ""
    private var storedLastRequest = Date.distantPast
    private var storedBusyUntil = Date.distantPast
    private var storedMarks: Set<CGWindowID> = []
    private var storedOwn: [CGRect] = []
    private var storedPinboard = false
    private var storedFocus: WindowInfo?
    private var storedLent: (front: pid_t, holder: pid_t)?
    private var storedClick: (spot: CGPoint, at: Date)?

    private func locked<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    var chosen: Chosen? {
        get { locked { storedChosen } }
        set { locked { storedChosen = newValue; storedFocus = nil; storedSerial += 1 } }
    }

    var active: Bool {
        get { locked { storedActive } }
        set {
            locked {
                if newValue && !storedActive { storedSerial += 1 }
                storedActive = newValue
            }
        }
    }

    var serial: Int { locked { storedSerial } }

    var doing: String { locked { storedDoing } }
    var lastRequest: Date { locked { storedLastRequest } }
    var busyUntil: Date { locked { storedBusyUntil } }

    /// The frame, the badge and the pinboard's windows, which pictures and clicks pass through.
    var marks: Set<CGWindowID> {
        get { locked { storedMarks } }
        set { locked { storedMarks = newValue } }
    }

    /// KnightSight's windows that clicks in the share could land on, which the panel keeps up to date.
    var own: [CGRect] {
        get { locked { storedOwn } }
        set { locked { storedOwn = newValue } }
    }

    /// Whether the pinboard lies over the share.
    var pinboard: Bool {
        get { locked { storedPinboard } }
        set { locked { storedPinboard = newValue } }
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

    /// The last click asked for, as a fraction of the share's width and height from its top left corner.
    var lastClick: (spot: CGPoint, at: Date)? { locked { storedClick } }

    func clicked(_ spot: CGPoint) {
        locked { storedClick = (spot, Date()) }
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
    let board: Board
    private let session: Session
    private let say: Say
    private let foreground: Foreground
    private let cursor: AssistantCursor

    init(session: Session, say: Say, foreground: Foreground, board: Board, cursor: AssistantCursor) {
        self.board = board
        self.session = session
        self.say = say
        self.foreground = foreground
        self.cursor = cursor
    }

    func currentShare() -> Share? {
        guard session.active, let chosen = session.chosen else { return nil }
        let serial = session.serial, own = session.own
        guard chosen.window != nil else {
            return Share(area: chosen.region, pixelsPerPoint: density(chosen.region), reachable: true, serial: serial, own: own)
        }
        guard let shared = chosen.current else { return nil }
        return Share(area: shared.bounds, pixelsPerPoint: density(shared.bounds), reachable: shared.onScreen, serial: serial, own: own)
    }

    func bringBack() -> Bool {
        guard session.active, let shared = session.chosen?.current else { return false }
        return Foreground.unminimize(shared)
    }

    func began(_ doing: String) {
        session.began(doing)
    }

    func look(size: CGSize) throws -> Screenshot {
        let shot = try picture(size: size)
        let note = shot.covered
            ? "The window is fully covered. Some programs, browsers among them, stop drawing then, so the picture may be out of date."
            : nil
        return Screenshot(png: Bitmap.png(shot.image), title: shot.title, note: note)
    }

    func controls(in area: CGRect) -> [Node]? {
        guard AXIsProcessTrusted(), let chosen = session.chosen else { return nil }
        if chosen.window != nil { return chosen.current.flatMap { ControlTree.read($0, in: area) } }
        // A region shows parts of several windows, and the one under its middle stands for it.
        guard let under = Windows.front(at: CGPoint(x: area.midX, y: area.midY), skipping: session.marks),
              under.pid != Windows.ownPid
        else { return nil }
        return ControlTree.read(under, in: area)
    }

    /// The share laid into a picture of the given size, its title, and whether a shared
    /// window lies fully covered.
    func picture(size: CGSize) throws -> (image: CGImage, title: String, covered: Bool) {
        guard CGPreflightScreenCaptureAccess() else {
            throw Refused("KnightSight is not allowed to record the screen yet. The person at the Mac can turn it on in System Settings under Privacy & Security, Screen Recording.")
        }
        let chosen = try current()
        guard chosen.window != nil else {
            return try (Capture.region(chosen.region, skipping: session.marks, size: size), chosen.title, false)
        }
        let shared = try window(chosen)
        return try (Capture.window(shared, size: size), shared.title(say), Windows.fullyCovered(shared, skipping: session.marks))
    }

    func click(at point: CGPoint, right: Bool, double: Bool) throws -> String {
        try needInput()
        try needUncovered()
        let chosen = try current()
        let target = try self.target(at: point, in: chosen)
        if chosen.window == nil { session.focus = target }
        if let area = currentShare()?.area {
            session.clicked(CGPoint(x: (point.x - area.minX) / area.width, y: (point.y - area.minY) / area.height))
        }
        let note = try foreground.run(target, at: point, mayOpenMenu: true) {
            cursor.point(at: point, over: target.id, rings: double ? 2 : 1)
            Input.click(at: point, right: right, twice: double)
        }
        return "Clicked, briefly in the foreground." + note
    }

    func scroll(at point: CGPoint, notches: Int) throws -> String {
        try needInput()
        try needUncovered()
        let target = try self.target(at: point, in: current())
        let note = try foreground.run(target, at: point) {
            cursor.point(at: point, over: target.id)
            Input.scroll(at: point, notches: notches)
        }
        return "Scrolled, briefly in the foreground." + note
    }

    func type(_ text: String) throws -> String {
        try needInput()
        let target = try keyTarget()
        aimKeys(over: target)
        session.busy()
        Input.type(text, to: target.pid)
        // A dialog that a typed Return confirms closes halfway through, with part of the text in it.
        guard Windows.info(target.id) != nil else {
            throw Refused("The window closed while the text was being typed.", delivered: true)
        }
        return "Typed."
    }

    // An app runs its Cmd shortcuts through the menu bar, which it does only while active.
    func press(_ combo: KeyCombo) throws -> String {
        try needInput()
        let target = try keyTarget()
        guard combo.modifiers.contains(.command) else {
            aimKeys(over: target)
            session.busy()
            Input.press(combo, to: .process(target.pid))
            return "Pressed."
        }
        let note = try foreground.run(target, at: nil) {
            aimKeys(over: target)
            Input.press(combo, to: .system)
        }
        return "Pressed, briefly in the foreground." + note
    }

    // The arrow shows typing at the last click, or in the middle of the share before any click.
    private func aimKeys(over target: WindowInfo) {
        guard let area = currentShare()?.area else { return }
        cursor.point(at: cursor.lastClick(in: area) ?? CGPoint(x: area.midX, y: area.midY), over: target.id)
    }

    private func density(_ area: CGRect) -> CGFloat {
        Screens.density(of: Screens.display(for: area))
    }

    private func needInput() throws {
        guard CGPreflightPostEventAccess() else {
            throw Refused("KnightSight is not allowed to send clicks and keys yet. The person at the Mac can turn it on in System Settings under Privacy & Security, Accessibility.")
        }
    }

    // A real click or wheel turn would land on the pinboard and set a pin.
    private func needUncovered() throws {
        guard !session.pinboard else {
            throw Refused("The person at the Mac has the pinboard open over the share, so clicks and scrolls would land on it. Try again once it is closed.")
        }
    }

    // The share can end between the check in the responder and the work here.
    private func current() throws -> Chosen {
        guard let chosen = session.chosen else { throw Refused.nothingShared }
        return chosen
    }

    private func window(_ chosen: Chosen) throws -> WindowInfo {
        guard let shared = chosen.current else { throw Refused.nothingShared }
        return shared
    }

    /// The window a click at this point lands on. In a region that is whatever shows there.
    private func target(at point: CGPoint, in chosen: Chosen) throws -> WindowInfo {
        if let id = chosen.window {
            let shared = try window(chosen)
            return Windows.visible().first { $0.bounds.contains(point) && ($0.id == id || Windows.isPopup($0, of: shared)) } ?? shared
        }
        guard let found = Windows.front(at: point, skipping: session.marks) else {
            throw Refused("No window that takes input lies at this point.")
        }
        guard found.pid != Windows.ownPid else { throw Refused("That point lies on KnightSight itself.") }
        return found
    }

    // In a region keys go to the window last clicked there, wherever it has moved since.
    private func keyTarget() throws -> WindowInfo {
        let chosen = try current()
        if chosen.window != nil { return try window(chosen) }
        guard let focus = session.focus.flatMap({ Windows.info($0.id) }) else {
            throw Refused("Keys go to the window last clicked inside the region, and nothing has been clicked there yet.")
        }
        return focus
    }
}
