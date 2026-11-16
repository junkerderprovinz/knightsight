import AppKit

/// A dimmed sheet over every screen that asks which one to share. The screen under the pointer
/// wears an accent outline and a click takes it. Escape or a right click ends it without one.
final class ScreenPicker {
    private var sheets: [ScreenSheet] = []
    private let done: ((number: Int, bounds: CGRect)?) -> Void

    /// Screens count from 1 in the system's order, and their bounds are in points from the top
    /// left of the main display.
    init(hint: String, done: @escaping ((number: Int, bounds: CGRect)?) -> Void) {
        self.done = done
        sheets = NSScreen.screens.map { screen in
            let sheet = ScreenSheet(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
            sheet.level = .screenSaver
            sheet.isOpaque = false
            sheet.backgroundColor = .clear
            sheet.hasShadow = false
            sheet.isReleasedWhenClosed = false
            sheet.setFrame(screen.frame, display: false)
            sheet.view.hint = hint
            sheet.contentView = sheet.view
            return sheet
        }
        for (i, sheet) in sheets.enumerated() {
            let picked = (number: i + 1, bounds: Screens.flip(sheet.frame))
            sheet.view.picked = { [weak self] chose in self?.finish(chose ? .some(picked) : nil) }
        }
    }

    func show() {
        NSApp.activate(ignoringOtherApps: true)
        let mouse = NSEvent.mouseLocation
        for sheet in sheets {
            sheet.orderFrontRegardless()
            sheet.view.lit = sheet.frame.contains(mouse)
            if sheet.view.lit { sheet.makeKey() }
        }
    }

    private func finish(_ picked: (number: Int, bounds: CGRect)?) {
        guard !sheets.isEmpty else { return }
        sheets.forEach { $0.orderOut(nil) }
        sheets = []
        done(picked)
    }
}

final class ScreenSheet: NSWindow {
    let view = ScreenChoice(frame: .zero)

    override var canBecomeKey: Bool { true }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 53 { view.picked?(false) } else { super.keyDown(with: event) }
    }
}

final class ScreenChoice: NSView {
    var picked: ((Bool) -> Void)?
    var hint = ""
    var lit = false { didSet { if lit != oldValue { needsDisplay = true } } }
    private var pressed = false

    override init(frame: NSRect) {
        super.init(frame: frame)
        addTrackingArea(NSTrackingArea(rect: .zero, options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect], owner: self))
    }

    required init?(coder: NSCoder) {
        fatalError("ScreenChoice is built in code")
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.black.withAlphaComponent(0.4).setFill()
        bounds.fill(using: .copy)
        if lit {
            let edge = NSBezierPath(rect: bounds.insetBy(dx: 3, dy: 3))
            edge.lineWidth = 6
            Theme.accent.setStroke()
            edge.stroke()
        }
        let attributes: [NSAttributedString.Key: Any] = [.font: Theme.semiBold(22), .foregroundColor: NSColor.white]
        let size = hint.size(withAttributes: attributes)
        hint.draw(at: CGPoint(x: bounds.midX - size.width / 2, y: bounds.midY - size.height / 2), withAttributes: attributes)
    }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func mouseEntered(with event: NSEvent) { lit = true }

    override func mouseExited(with event: NSEvent) { lit = false }

    override func mouseDown(with event: NSEvent) { pressed = true }

    override func mouseUp(with event: NSEvent) {
        guard pressed else { return }
        pressed = false
        picked?(true)
    }

    override func rightMouseDown(with event: NSEvent) {
        picked?(false)
    }
}
