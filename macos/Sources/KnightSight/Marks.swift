import AppKit

/// The windows that mark the share: they follow it onto every desktop, ignore the mouse and
/// stay out of the window cycle.
enum Marks {
    static func window() -> NSWindow {
        let window = NSWindow(contentRect: .zero, styleMask: .borderless, backing: .buffered, defer: false)
        window.hasShadow = false
        window.ignoresMouseEvents = true
        window.isReleasedWhenClosed = false
        window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle, .fullScreenAuxiliary]
        return window
    }
}

/// Four thin windows around the share, so nothing covers what is shared.
final class Frame {
    let edges = (0..<4).map { _ -> NSWindow in
        let edge = Marks.window()
        edge.alphaValue = 0.9
        return edge
    }

    /// In AppKit coordinates.
    func show(_ r: CGRect, color: NSColor, width: CGFloat) {
        let o = r.insetBy(dx: -width, dy: -width)
        let sides = [
            CGRect(x: o.minX, y: o.maxY - width, width: o.width, height: width),
            CGRect(x: o.minX, y: o.minY, width: o.width, height: width),
            CGRect(x: o.minX, y: r.minY, width: width, height: r.height),
            CGRect(x: o.maxX - width, y: r.minY, width: width, height: r.height),
        ]
        for (edge, side) in zip(edges, sides) {
            if edge.backgroundColor != color { edge.backgroundColor = color }
            if edge.frame != side { edge.setFrame(side, display: true) }
            if !edge.isVisible { edge.orderFrontRegardless() }
        }
    }

    func hide() {
        for edge in edges where edge.isVisible { edge.orderOut(nil) }
    }
}

/// The label at the top right of the share that says what is being done in it.
final class Badge {
    static let shadow: CGFloat = 8
    static let font = Theme.semiBold(13)
    let window = Marks.window()
    private let label = BadgeView()

    init() {
        window.isOpaque = false
        window.backgroundColor = .clear
        window.contentView = label
    }

    func size(for text: String) -> CGSize {
        let width = text.size(withAttributes: [.font: Badge.font]).width
        return CGSize(width: ceil(width + 40 + 2 * Badge.shadow), height: ceil(30 + 2 * Badge.shadow))
    }

    /// The pulse runs from 0 to 1 and back and lights the dot while something is being done.
    func show(_ text: String, in rect: CGRect, alpha: CGFloat, pulse: CGFloat) {
        label.text = text
        label.pulse = pulse
        label.needsDisplay = true
        if window.frame != rect { window.setFrame(rect, display: true) }
        window.alphaValue = alpha
        if !window.isVisible { window.orderFrontRegardless() }
    }

    func hide() {
        if window.isVisible { window.orderOut(nil) }
    }
}

final class BadgeView: NSView {
    var text = ""
    var pulse: CGFloat = 0

    override var isFlipped: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill(using: .copy)
        let m = Badge.shadow
        let pill = bounds.insetBy(dx: m, dy: m)
        NSColor(white: 0, alpha: 14 / 255).setFill()
        for i in stride(from: 4, through: 1, by: -1) {
            let g = CGFloat(i) * 1.5
            let soft = CGRect(x: pill.minX - g, y: pill.minY - g + 2, width: pill.width + 2 * g, height: pill.height + 2 * g)
            NSBezierPath(roundedRect: soft, xRadius: pill.height / 2 + g, yRadius: pill.height / 2 + g).fill()
        }
        Theme.surface.setFill()
        NSBezierPath(roundedRect: pill, xRadius: pill.height / 2, yRadius: pill.height / 2).fill()

        let d: CGFloat = 8, cx = pill.minX + 14, cy = pill.midY
        Theme.warning.withAlphaComponent(90 / 255 * pulse).setFill()
        NSBezierPath(ovalIn: CGRect(x: cx - d * 0.9, y: cy - d * 0.9, width: d * 1.8, height: d * 1.8)).fill()
        Motion.mix(Theme.accent, Theme.warning, pulse).setFill()
        NSBezierPath(ovalIn: CGRect(x: cx - d / 2, y: cy - d / 2, width: d, height: d)).fill()

        let attributes: [NSAttributedString.Key: Any] = [.font: Badge.font, .foregroundColor: Theme.text]
        let height = text.size(withAttributes: attributes).height
        text.draw(at: CGPoint(x: pill.minX + 26, y: cy - height / 2), withAttributes: attributes)
    }
}
