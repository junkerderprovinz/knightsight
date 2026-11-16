import AppKit
import KnightSightCore

/// One entry of the window server's list. Bounds count in points from the top left of the
/// main display, as everything here does unless it says AppKit.
struct WindowInfo {
    let id: CGWindowID
    let pid: pid_t
    let layer: Int
    let bounds: CGRect
    let alpha: Double
    let onScreen: Bool
    let name: String?
    let owner: String?

    init?(_ entry: [String: Any]) {
        guard let id = entry[kCGWindowNumber as String] as? CGWindowID,
              let pid = entry[kCGWindowOwnerPID as String] as? pid_t,
              let layer = entry[kCGWindowLayer as String] as? Int,
              let box = entry[kCGWindowBounds as String] as? NSDictionary,
              let bounds = CGRect(dictionaryRepresentation: box as CFDictionary)
        else { return nil }
        self.id = id
        self.pid = pid
        self.layer = layer
        self.bounds = bounds
        alpha = entry[kCGWindowAlpha as String] as? Double ?? 1
        onScreen = entry[kCGWindowIsOnscreen as String] as? Bool ?? false
        name = entry[kCGWindowName as String] as? String
        owner = entry[kCGWindowOwnerName as String] as? String
    }

    // macOS hands out window titles only with Screen Recording allowed, so the app's name stands in.
    func title(_ say: Say) -> String {
        if let name, !name.isEmpty { return name }
        return owner ?? say.untitled
    }
}

enum Windows {
    static let ownPid = ProcessInfo.processInfo.processIdentifier

    static func list(_ options: CGWindowListOption, relativeTo id: CGWindowID = kCGNullWindowID) -> [WindowInfo] {
        let entries = CGWindowListCopyWindowInfo(options, id) as? [[String: Any]] ?? []
        return entries.compactMap(WindowInfo.init)
    }

    // Asked for one window, the window server leaves it out while it is minimized, so the full
    // list is searched before the window counts as closed.
    static func info(_ id: CGWindowID) -> WindowInfo? {
        list(.optionIncludingWindow, relativeTo: id).first ?? list(.optionAll).first { $0.id == id }
    }

    /// On screen, front to back.
    static func visible() -> [WindowInfo] {
        list([.optionOnScreenOnly, .excludeDesktopElements])
    }

    static func above(_ id: CGWindowID) -> [WindowInfo] {
        list([.optionOnScreenAboveWindow, .excludeDesktopElements], relativeTo: id)
    }

    /// The window a click at this point reaches, passing through KnightSight's frame and badge.
    /// The window server answers, since the list alone has windows that clicks pass through,
    /// such as the Dock's, which spans the whole screen above every app.
    static func front(at p: CGPoint, skipping marks: Set<CGWindowID>) -> WindowInfo? {
        var below = 0
        while true {
            let hit = NSWindow.windowNumber(at: Screens.flip(p), belowWindowWithWindowNumber: below)
            guard hit > 0 else { return nil }
            if !marks.contains(CGWindowID(hit)) { return info(CGWindowID(hit)) }
            below = hit
        }
    }

    /// Menus, popovers and sheets the shared window has open. They are windows of their own,
    /// so a picture of the shared window or a click aimed at it would miss them.
    static func isPopup(_ w: WindowInfo, of shared: WindowInfo) -> Bool {
        w.pid == shared.pid && w.id != shared.id && w.bounds.intersects(shared.bounds)
            && (w.layer != shared.layer || shared.bounds.contains(w.bounds))
    }

    /// Sampled on a grid, which is close enough to tell a buried window from a partly visible one.
    static func fullyCovered(_ shared: WindowInfo, skipping marks: Set<CGWindowID>) -> Bool {
        let b = shared.bounds
        for i in 0..<8 {
            for j in 0..<8 {
                let p = CGPoint(x: b.minX + (CGFloat(i) + 0.5) * b.width / 8, y: b.minY + (CGFloat(j) + 0.5) * b.height / 8)
                if let w = front(at: p, skipping: marks), w.id == shared.id || isPopup(w, of: shared) { return false }
            }
        }
        return true
    }
}

enum Processes {
    /// When the process started, in microseconds since 1970, or nil once it is gone.
    static func started(_ pid: pid_t) -> Int64? {
        var info = kinfo_proc()
        var size = MemoryLayout<kinfo_proc>.stride
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
        guard sysctl(&mib, UInt32(mib.count), &info, &size, nil, 0) == 0, size > 0 else { return nil }
        let start = info.kp_proc.p_un.__p_starttime
        return Int64(start.tv_sec) * 1_000_000 + Int64(start.tv_usec)
    }
}

enum Screens {
    static var mainHeight: CGFloat { CGDisplayBounds(CGMainDisplayID()).height }

    /// Between the window server's coordinates and AppKit's, which count from the bottom left. Either way round.
    static func flip(_ r: CGRect) -> CGRect {
        CGRect(x: r.minX, y: mainHeight - r.maxY, width: r.width, height: r.height)
    }

    static func flip(_ p: CGPoint) -> CGPoint {
        CGPoint(x: p.x, y: mainHeight - p.y)
    }

    /// The display that shows most of the area.
    static func display(for area: CGRect) -> CGDirectDisplayID {
        var ids = [CGDirectDisplayID](repeating: 0, count: 16)
        var count: UInt32 = 0
        CGGetDisplaysWithRect(area, 16, &ids, &count)
        return ids.prefix(Int(count)).max { overlap($0, area) < overlap($1, area) } ?? CGMainDisplayID()
    }

    static func overlap(_ id: CGDirectDisplayID, _ area: CGRect) -> CGFloat {
        let r = CGDisplayBounds(id).intersection(area)
        return r.isNull ? 0 : r.width * r.height
    }

    static func density(of id: CGDirectDisplayID) -> CGFloat {
        guard let mode = CGDisplayCopyDisplayMode(id) else { return 1 }
        return CGFloat(mode.pixelWidth) / CGFloat(mode.width)
    }

    /// The space for windows on the area's screen, between the menu bar and the Dock.
    static func visible(for area: CGRect) -> CGRect {
        let id = display(for: area)
        let screen = NSScreen.screens.first {
            ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == id
        }
        guard let screen else { return CGDisplayBounds(id) }
        return flip(screen.visibleFrame)
    }

    /// Where the space for windows begins on the area's screen, below the menu bar.
    static func top(of area: CGRect) -> CGFloat {
        visible(for: area).minY
    }
}
