import AppKit

/// The arrow that shows where the assistant acts, while the person's own pointer stays where
/// it is. It lies in the window order right above the window it points into, so whatever
/// covers that window covers the arrow too, and captures leave it out.
final class AssistantCursor {
    static let side: CGFloat = 60
    static let glide = 0.22, ripple = 0.4, linger = 4.0

    private struct Aim {
        let from: CGPoint?, to: CGPoint, at: Date, over: CGWindowID
    }

    let window = Marks.window()
    private let view = CursorView()
    private let lock = NSLock()
    // The threads that serve the port aim the arrow and the panel's tick draws it, so these
    // go under the lock.
    private var aim: Aim?
    private var rings: [Date] = []
    private var clicked: CGPoint?
    private var lastAction = Date.distantPast
    private var moving = true
    private var alpha = 0.0
    private var last = Date()

    init() {
        window.isOpaque = false
        window.backgroundColor = .clear
        window.sharingType = .none
        window.contentView = view
    }

    /// Moves the arrow to the point above the window and returns once it is there, so the
    /// action goes out under it. A click rings once, a double click twice.
    func point(at p: CGPoint, over id: CGWindowID, rings count: Int = 0) {
        let now = Date()
        lock.lock()
        let delay = moving ? AssistantCursor.glide : 0
        let from = moving ? aim.map { spot($0, at: now) } : nil
        aim = Aim(from: from, to: p, at: now, over: id)
        lastAction = now
        if count > 0 {
            clicked = p
            if moving { rings += (0..<count).map { now.addingTimeInterval(delay + 0.15 * Double($0)) } }
        }
        lock.unlock()
        if delay > 0 { usleep(useconds_t(delay * 1_000_000)) }
    }

    /// Where the last click in the area went, if it went there.
    func lastClick(in area: CGRect) -> CGPoint? {
        lock.lock()
        defer { lock.unlock() }
        return clicked.flatMap { area.contains($0) ? $0 : nil }
    }

    /// Runs in the panel's tick: follows the aim, fades the arrow after a quiet spell and keeps
    /// it right above its window. When the share ends it goes at once.
    func follow(sharing: Bool, marks: Set<CGWindowID>) {
        let now = Date()
        let elapsed = now.timeIntervalSince(last) * 1000
        last = now
        lock.lock()
        moving = Motion.on
        if !sharing {
            aim = nil
            rings = []
            clicked = nil
            alpha = 0
        }
        rings.removeAll { now.timeIntervalSince($0) > AssistantCursor.ripple }
        let quiet = now.timeIntervalSince(lastAction) > AssistantCursor.linger
        alpha = Motion.step(alpha, to: aim != nil && !quiet ? 1 : 0, elapsed: elapsed, duration: Motion.content)
        if quiet && alpha == 0 { aim = nil }
        let aim = self.aim, tip = aim.map { spot($0, at: now) }
        let growth = rings.map { now.timeIntervalSince($0) / AssistantCursor.ripple }.filter { $0 >= 0 }
        lock.unlock()

        guard let aim, let tip, let over = Windows.info(aim.over), over.onScreen else {
            if window.isVisible { window.orderOut(nil) }
            return
        }
        let at = Screens.flip(tip), half = AssistantCursor.side / 2
        let frame = CGRect(x: at.x - half, y: at.y - half, width: AssistantCursor.side, height: AssistantCursor.side)
        if window.frame != frame { window.setFrame(frame, display: false) }
        if growth != view.rings {
            view.rings = growth
            view.needsDisplay = true
        }
        window.alphaValue = CGFloat(alpha)
        let level = NSWindow.Level(rawValue: over.layer)
        if window.level != level { window.level = level }
        keep(above: over.id, passing: marks)
    }

    // The share's frame and badge may lie between the arrow and its window.
    private func keep(above id: CGWindowID, passing marks: Set<CGWindowID>) {
        let own = CGWindowID(window.windowNumber)
        if window.isVisible {
            for w in Windows.above(id).reversed() {
                if w.id == own { return }
                if !marks.contains(w.id) { break }
            }
        }
        window.order(.above, relativeTo: Int(id))
    }

    private func spot(_ aim: Aim, at now: Date) -> CGPoint {
        guard let from = aim.from else { return aim.to }
        let t = CGFloat(Motion.ease(min(1, now.timeIntervalSince(aim.at) / AssistantCursor.glide)))
        return CGPoint(x: from.x + (aim.to.x - from.x) * t, y: from.y + (aim.to.y - from.y) * t)
    }
}

/// The arrow with its tip in the middle of the view, and the rings of the clicks around it.
final class CursorView: NSView {
    /// How far each ring has grown, from 0 to 1.
    var rings: [Double] = []

    // A classic arrow pointer, 20 points tall, from its tip.
    private static let arrow: [(CGFloat, CGFloat)] = [(0, 0), (0, 17.2), (4.5, 13.3), (7.5, 20), (10.3, 18.8), (7.4, 12.3), (12.9, 12.3)]

    override var isFlipped: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill(using: .copy)
        let tip = CGPoint(x: bounds.midX, y: bounds.midY)
        for t in rings {
            let r = 6 + 16 * CGFloat(Motion.ease(t))
            let ring = NSBezierPath(ovalIn: CGRect(x: tip.x - r, y: tip.y - r, width: 2 * r, height: 2 * r))
            ring.lineWidth = 2
            Theme.accent.withAlphaComponent(1 - CGFloat(t)).setStroke()
            ring.stroke()
        }

        let arrow = Glyphs.line(CursorView.arrow.map { (tip.x + $0.0, tip.y + $0.1) })
        arrow.close()
        arrow.lineWidth = 1.5
        arrow.lineJoinStyle = .round
        NSGraphicsContext.saveGraphicsState()
        let shadow = NSShadow()
        shadow.shadowColor = NSColor(white: 0, alpha: 0.35)
        shadow.shadowBlurRadius = 3
        shadow.shadowOffset = NSSize(width: 0, height: -1.5)
        shadow.set()
        Theme.accent.setFill()
        arrow.fill()
        NSGraphicsContext.restoreGraphicsState()
        Theme.accentInk.setStroke()
        arrow.stroke()
    }
}
