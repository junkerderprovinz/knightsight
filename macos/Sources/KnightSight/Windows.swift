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

    static func info(_ id: CGWindowID) -> WindowInfo? {
        list(.optionIncludingWindow, relativeTo: id).first
    }

    /// On screen, front to back.
    static func visible() -> [WindowInfo] {
        list([.optionOnScreenOnly, .excludeDesktopElements])
    }

    static func above(_ id: CGWindowID) -> [WindowInfo] {
        list([.optionOnScreenAboveWindow, .excludeDesktopElements], relativeTo: id)
    }

    /// The frontmost window at a point, passing through KnightSight's frame and badge as clicks do.
    static func front(at p: CGPoint, skipping marks: Set<CGWindowID>) -> WindowInfo? {
        visible().first { !marks.contains($0.id) && $0.alpha > 0 && $0.bounds.contains(p) }
    }

    /// Menus, popovers and sheets the shared window has open. They are windows of their own,
    /// so a picture of the shared window or a click aimed at it would miss them.
    static func isPopup(_ w: WindowInfo, of shared: WindowInfo) -> Bool {
        w.pid == shared.pid && w.id != shared.id && w.bounds.intersects(shared.bounds)
            && (w.layer != shared.layer || shared.bounds.contains(w.bounds))
    }

    /// Sampled on a grid, which is close enough to tell a buried window from a partly visible one.
    static func fullyCovered(_ shared: WindowInfo, skipping marks: Set<CGWindowID>) -> Bool {
        let covers = above(shared.id).filter { !marks.contains($0.id) && $0.alpha > 0 && !isPopup($0, of: shared) }.map(\.bounds)
        let b = shared.bounds
        for i in 0..<8 {
            for j in 0..<8 {
                let p = CGPoint(x: b.minX + (CGFloat(i) + 0.5) * b.width / 8, y: b.minY + (CGFloat(j) + 0.5) * b.height / 8)
                if !covers.contains(where: { $0.contains(p) }) { return false }
            }
        }
        return true
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

    /// Where the space for windows begins on the area's screen, below the menu bar.
    static func top(of area: CGRect) -> CGFloat {
        let id = display(for: area)
        let screen = NSScreen.screens.first {
            ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == id
        }
        guard let screen else { return CGDisplayBounds(id).minY }
        return flip(screen.visibleFrame).minY
    }
}
