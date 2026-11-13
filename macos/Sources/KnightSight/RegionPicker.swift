import AppKit

/// A dimmed sheet over every screen, on which the person drags out the region to share.
/// Escape, a right click or a rectangle under 20 points ends it without a region.
final class RegionPicker {
    private var sheets: [PickerSheet] = []
    private let done: (CGRect?) -> Void

    init(done: @escaping (CGRect?) -> Void) {
        self.done = done
        sheets = NSScreen.screens.map { screen in
            let sheet = PickerSheet(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
            sheet.level = .screenSaver
            sheet.isOpaque = false
            sheet.backgroundColor = .clear
            sheet.hasShadow = false
            sheet.isReleasedWhenClosed = false
            sheet.setFrame(screen.frame, display: false)
            sheet.contentView = sheet.view
            return sheet
        }
        for sheet in sheets {
            sheet.view.picked = { [weak self] area in self?.finish(area) }
        }
    }

    func show() {
        NSApp.activate(ignoringOtherApps: true)
        let mouse = NSEvent.mouseLocation
        for sheet in sheets {
            sheet.orderFrontRegardless()
            if sheet.frame.contains(mouse) { sheet.makeKey() }
        }
    }

    private func finish(_ area: CGRect?) {
        guard !sheets.isEmpty else { return }
        sheets.forEach { $0.orderOut(nil) }
        sheets = []
        done(area)
    }
}

final class PickerSheet: NSWindow {
    let view = PickerView()

    override var canBecomeKey: Bool { true }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 53 { view.picked?(nil) } else { super.keyDown(with: event) }
    }
}

final class PickerView: NSView {
    var picked: ((CGRect?) -> Void)?
    private var start: CGPoint?
    private var selection = CGRect.zero

    override func draw(_ dirtyRect: NSRect) {
        NSColor.black.withAlphaComponent(0.4).setFill()
        bounds.fill(using: .copy)
        guard !selection.isEmpty else { return }
        NSColor.clear.setFill()
        selection.fill(using: .copy)
        NSColor.white.setStroke()
        let edge = NSBezierPath(rect: selection.insetBy(dx: 1, dy: 1))
        edge.lineWidth = 2
        edge.stroke()
    }

    override func mouseDown(with event: NSEvent) {
        start = convert(event.locationInWindow, from: nil)
    }

    override func mouseDragged(with event: NSEvent) {
        guard let start else { return }
        let p = convert(event.locationInWindow, from: nil)
        selection = CGRect(x: min(start.x, p.x), y: min(start.y, p.y), width: abs(p.x - start.x), height: abs(p.y - start.y))
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        guard start != nil, let window else { return }
        start = nil
        guard selection.width >= 20, selection.height >= 20 else {
            picked?(nil)
            return
        }
        picked?(Screens.flip(window.convertToScreen(convert(selection, to: nil))).integral)
    }

    override func rightMouseDown(with event: NSEvent) {
        picked?(nil)
    }

    override func resetCursorRects() {
        addCursorRect(bounds, cursor: .crosshair)
    }
}
