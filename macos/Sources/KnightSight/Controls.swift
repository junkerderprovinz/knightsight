import AppKit

enum Glyph { case none, window, region, start, stop, info }

/// A rounded button: neutral on the card, or the one filled accent button of the view.
/// Hover fades in and a press sinks it a little, both as transitions over Motion.control.
final class SoftButton: NSButton {
    enum Kind { case neutral, primary }

    let kind: Kind
    var glyph: Glyph { didSet { needsDisplay = true } }
    var radius: CGFloat = 6
    var onPress: () -> Void = {}
    private let label = Theme.semiBold(14)
    private var hovering = false, pressing = false
    private var lit = 0.0, sink = 0.0
    private var clock: Timer?
    private var last = Date()

    init(_ title: String, glyph: Glyph, kind: Kind = .neutral) {
        self.kind = kind
        self.glyph = glyph
        super.init(frame: .zero)
        self.title = title
        isBordered = false
        target = self
        action = #selector(pressed)
        addTrackingArea(NSTrackingArea(rect: .zero, options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect], owner: self))
    }

    required init?(coder: NSCoder) {
        fatalError("SoftButton is built in code")
    }

    override var isFlipped: Bool { true }

    override var title: String { didSet { needsDisplay = true } }

    override var isEnabled: Bool { didSet { animate() } }

    @objc private func pressed() { onPress() }

    override func mouseEntered(with event: NSEvent) {
        hovering = true
        animate()
    }

    override func mouseExited(with event: NSEvent) {
        hovering = false
        pressing = false
        animate()
    }

    // The button tracks the press inside super until the mouse comes up.
    override func mouseDown(with event: NSEvent) {
        pressing = true
        animate()
        super.mouseDown(with: event)
        pressing = false
        animate()
    }

    private func animate() {
        guard clock == nil else { return }
        last = Date()
        let timer = Timer(timeInterval: 1.0 / 60, target: self, selector: #selector(advance), userInfo: nil, repeats: true)
        RunLoop.main.add(timer, forMode: .common)
        clock = timer
        advance()
    }

    @objc private func advance() {
        let now = Date()
        let elapsed = now.timeIntervalSince(last) * 1000
        last = now
        let litTo: Double = hovering && isEnabled ? 1 : 0, sinkTo: Double = pressing && isEnabled ? 1 : 0
        lit = Motion.step(lit, to: litTo, elapsed: elapsed, duration: Motion.control)
        sink = Motion.step(sink, to: sinkTo, elapsed: elapsed, duration: Motion.control)
        if lit == litTo && sink == sinkTo {
            clock?.invalidate()
            clock = nil
        }
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        let t = CGFloat(Motion.ease(lit))
        let fill: NSColor, ink: NSColor
        if !isEnabled {
            fill = Theme.surface2
            ink = Theme.muted
        } else if kind == .primary {
            fill = Motion.mix(Theme.accent, Theme.accentHover, t)
            ink = Theme.accentInk
        } else {
            fill = Motion.mix(Theme.surface2, Theme.surface3, t)
            ink = Theme.text
        }
        let scale = 1 - (1 - Motion.pressScale) * CGFloat(Motion.ease(sink))
        let w = bounds.width * scale, h = bounds.height * scale
        let r = CGRect(x: (bounds.width - w) / 2, y: (bounds.height - h) / 2, width: w, height: h)
        fill.setFill()
        NSBezierPath(roundedRect: r, xRadius: radius * scale, yRadius: radius * scale).fill()

        let attributes: [NSAttributedString.Key: Any] = [.font: label, .foregroundColor: ink]
        let text = title.isEmpty ? CGSize.zero : title.size(withAttributes: attributes)
        let icon: CGFloat = glyph == .none ? 0 : 16 * scale
        let gap: CGFloat = icon > 0 && !title.isEmpty ? 8 : 0
        let x = r.minX + (r.width - icon - gap - text.width) / 2
        if icon > 0 { Glyphs.draw(glyph, in: CGRect(x: x, y: r.midY - icon / 2, width: icon, height: icon), ink: ink, scale: scale) }
        if !title.isEmpty { title.draw(at: CGPoint(x: x + icon + gap, y: r.midY - text.height / 2), withAttributes: attributes) }
    }

    override func drawFocusRingMask() {
        NSBezierPath(roundedRect: bounds, xRadius: radius, yRadius: radius).fill()
    }

    override var focusRingMaskBounds: NSRect { bounds }
}

/// Line icons drawn in the button's ink, so they follow hover, appearance and the disabled state.
enum Glyphs {
    static func draw(_ glyph: Glyph, in b: CGRect, ink: NSColor, scale k: CGFloat) {
        ink.set()
        let s = b.width
        func stroke(_ path: NSBezierPath) {
            path.lineWidth = 1.6 * k
            path.lineCapStyle = .round
            path.lineJoinStyle = .round
            path.stroke()
        }
        switch glyph {
        case .none:
            break
        case .window:
            let frame = CGRect(x: b.minX + s * 0.06, y: b.minY + s * 0.14, width: s * 0.88, height: s * 0.72)
            stroke(NSBezierPath(roundedRect: frame, xRadius: 2.5 * k, yRadius: 2.5 * k))
            stroke(line([(frame.minX, frame.minY + s * 0.24), (frame.maxX, frame.minY + s * 0.24)]))
        case .region:
            let a = s * 0.3, l = b.minX + s * 0.08, t = b.minY + s * 0.08, r = b.maxX - s * 0.08, bt = b.maxY - s * 0.08
            stroke(line([(l, t + a), (l, t), (l + a, t)]))
            stroke(line([(r - a, t), (r, t), (r, t + a)]))
            stroke(line([(r, bt - a), (r, bt), (r - a, bt)]))
            stroke(line([(l + a, bt), (l, bt), (l, bt - a)]))
        case .start:
            let triangle = line([(b.minX + s * 0.22, b.minY + s * 0.14), (b.minX + s * 0.86, b.minY + s * 0.5), (b.minX + s * 0.22, b.minY + s * 0.86)])
            triangle.close()
            triangle.fill()
            stroke(triangle)
        case .stop:
            NSBezierPath(roundedRect: b.insetBy(dx: s * 0.18, dy: s * 0.18), xRadius: 2 * k, yRadius: 2 * k).fill()
        case .info:
            stroke(NSBezierPath(ovalIn: b.insetBy(dx: 0.8 * k, dy: 0.8 * k)))
            let cx = b.midX, d = 2.2 * k
            NSBezierPath(ovalIn: CGRect(x: cx - d / 2, y: b.minY + s * 0.27 - d / 2, width: d, height: d)).fill()
            stroke(line([(cx, b.minY + s * 0.45), (cx, b.minY + s * 0.73)]))
        }
    }

    static func line(_ points: [(CGFloat, CGFloat)]) -> NSBezierPath {
        let path = NSBezierPath()
        path.move(to: CGPoint(x: points[0].0, y: points[0].1))
        for p in points.dropFirst() { path.line(to: CGPoint(x: p.0, y: p.1)) }
        return path
    }
}
