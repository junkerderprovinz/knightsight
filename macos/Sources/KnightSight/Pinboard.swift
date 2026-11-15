import AppKit
import KnightSightCore

/// The pinboard over the share: a veil that takes the marks, a card that writes one note and
/// a card that lists them all. The cards are child windows of the veil, so they stay above it
/// wherever the veil is ordered.
final class Pinboard {
    var onClose: () -> Void = {}
    var onDone: () -> Void = {}
    var onSaveFile: () -> Void = {}
    var sending = false { didSet { refresh() } }
    private(set) var isOpen = false

    private let board: Board
    private let say: Say
    private let overlay = BoardWindow.make(), listCard = BoardWindow.make(), editorCard = BoardWindow.make()
    private let canvas = BoardView(frame: .zero)
    private let list: BoardList
    private let editor: NoteEditor
    /// The note in the editor, with nil for a new mark.
    private var editing: (number: Int?, mark: CGRect)?
    private var area = CGRect.zero

    init(board: Board, say: Say) {
        self.board = board
        self.say = say
        list = BoardList(say: say)
        editor = NoteEditor(say: say)
        overlay.contentView = canvas
        listCard.contentView = list
        editorCard.contentView = editor
        listCard.hasShadow = true
        editorCard.hasShadow = true

        canvas.onMark = { [weak self] mark in self?.create(mark) }
        canvas.onPick = { [weak self] number in self?.edit(number) }
        list.rows.onGo = { [weak self] number in
            self?.edit(number)
            self?.canvas.flash(number)
        }
        list.close.onPress = { [weak self] in self?.onClose() }
        // A note still open with text goes along, so Done never loses what was typed.
        list.saveFile.onPress = { [weak self] in
            self?.save()
            self?.onSaveFile()
        }
        list.done.onPress = { [weak self] in
            self?.save()
            self?.onDone()
        }
        editor.close.onPress = { [weak self] in self?.closeEditor() }
        editor.saveButton.onPress = { [weak self] in self?.save() }
        editor.deleteButton.onPress = { [weak self] in self?.deleteNote() }
        editor.onChange = { [weak self] in self?.refresh() }
        for window in [overlay, listCard, editorCard] {
            window.onKey = { [weak self] event in self?.key(event) ?? false }
        }
        refresh()
    }

    /// Every window of the pinboard, which pictures and clicks pass through.
    var windows: [NSWindow] { [overlay, listCard, editorCard] }

    /// The windows on the screen, the veil first.
    var shown: [NSWindow] { windows.filter(\.isVisible) }

    func open() {
        isOpen = true
        refresh()
    }

    /// The notes stay and show again on the next open.
    func close() {
        isOpen = false
        editing = nil
        hide()
        refresh()
    }

    /// Lays the veil over the share, given in points from the top left, and the cards beside it.
    func follow(_ area: CGRect) {
        self.area = area
        let frame = Screens.flip(area)
        if overlay.frame != frame { overlay.setFrame(frame, display: true) }
        if !overlay.isVisible { overlay.orderFrontRegardless() }
        let screen = Screens.visible(for: area)
        place(listCard, size: list.size, beside: area, within: screen)
        if let editing {
            let mark = editing.mark.offsetBy(dx: area.minX, dy: area.minY).insetBy(dx: -14, dy: -14)
            place(editorCard, size: NoteEditor.size, beside: mark, within: screen)
        }
        canvas.advance()
    }

    /// While the share is out of sight. The pinboard stays open.
    func hide() {
        for card in [editorCard, listCard] where card.isVisible {
            overlay.removeChildWindow(card)
            card.orderOut(nil)
        }
        if overlay.isVisible { overlay.orderOut(nil) }
    }

    private func place(_ card: NSWindow, size: CGSize, beside spot: CGRect, within screen: CGRect) {
        let frame = Screens.flip(CGRect(origin: Placement.beside(spot, size: size, within: screen), size: size))
        if card.frame != frame {
            card.setFrame(frame, display: true)
            card.invalidateShadow()
        }
        if !card.isVisible {
            card.orderFrontRegardless()
            overlay.addChildWindow(card, ordered: .above)
        }
    }

    private func refresh() {
        let notes = board.notes
        canvas.notes = notes
        canvas.editing = editing?.number
        if let editing, editing.number == nil {
            canvas.pending = (editing.mark, editor.kind)
        } else {
            canvas.pending = nil
        }
        canvas.needsDisplay = true
        list.show(notes, typed: editing != nil && editor.saveButton.isEnabled, sending: sending)
    }

    private func create(_ mark: CGRect) {
        editing = (nil, mark)
        editor.load(title: say.newNote, kind: .wish, text: "", author: UserDefaults.standard.string(forKey: "author") ?? "", existing: false)
        showEditor()
    }

    private func edit(_ number: Int) {
        guard let note = board.notes.first(where: { $0.number == number }) else { return }
        editing = (number, note.mark)
        editor.load(title: say.noteTitle(number), kind: note.kind, text: note.text, author: note.author, existing: true)
        showEditor()
    }

    // Typing needs KnightSight in front, which a click on the veil alone does not ask for.
    private func showEditor() {
        refresh()
        follow(area)
        NSApp.activate(ignoringOtherApps: true)
        editorCard.makeKey()
        editor.focus()
    }

    private func closeEditor() {
        editing = nil
        overlay.removeChildWindow(editorCard)
        editorCard.orderOut(nil)
        refresh()
    }

    private func save() {
        guard let editing else { return }
        let text = editor.text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        let author = editor.author.trimmingCharacters(in: .whitespaces)
        UserDefaults.standard.set(author, forKey: "author")
        if let number = editing.number {
            board.update(number, kind: editor.kind, text: text, author: author)
        } else {
            board.add(editor.kind, text, author: author, mark: editing.mark)
        }
        closeEditor()
    }

    private func deleteNote() {
        if let number = editing?.number { board.remove(number) }
        closeEditor()
    }

    // Escape closes the note without saving, Cmd+Return saves it.
    private func key(_ event: NSEvent) -> Bool {
        guard editing != nil else { return false }
        if event.keyCode == 53 {
            closeEditor()
            return true
        }
        guard event.keyCode == KeyCode.returnKey || event.keyCode == 76, event.modifierFlags.contains(.command) else { return false }
        if editor.saveButton.isEnabled { save() }
        return true
    }
}

/// A window of the pinboard. Unlike the marks it takes the mouse, and it can become key, so a
/// note can be typed. onKey sees each key first and says whether it took it.
final class BoardWindow: NSWindow {
    var onKey: (NSEvent) -> Bool = { _ in false }

    static func make() -> BoardWindow {
        let window = BoardWindow(contentRect: .zero, styleMask: .borderless, backing: .buffered, defer: false)
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        // A window that is clear in places would let the mouse through there.
        window.ignoresMouseEvents = false
        window.acceptsMouseMovedEvents = true
        window.isReleasedWhenClosed = false
        window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle, .fullScreenAuxiliary]
        return window
    }

    override var canBecomeKey: Bool { true }

    override func sendEvent(_ event: NSEvent) {
        if event.type == .keyDown && onKey(event) { return }
        super.sendEvent(event)
    }

    // The app has no Edit menu, which is what turns these keys into editing in a text field.
    private static let editing: [String: Selector] = [
        "x": #selector(NSText.cut(_:)), "c": #selector(NSText.copy(_:)),
        "v": #selector(NSText.paste(_:)), "a": #selector(NSText.selectAll(_:)),
    ]

    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        if onKey(event) { return true }
        if event.modifierFlags.intersection(.deviceIndependentFlagsMask) == .command,
           let action = event.charactersIgnoringModifiers.flatMap({ BoardWindow.editing[$0] }),
           NSApp.sendAction(action, to: nil, from: self) {
            return true
        }
        return super.performKeyEquivalent(with: event)
    }
}

/// The veil over the share. It shows the marks and takes new ones: a drag of at least six
/// points draws a rectangle, anything shorter sets a pin, and a click on a mark opens its note.
final class BoardView: NSView {
    static let flashTime: TimeInterval = 0.9

    var notes: [Note] = []
    var editing: Int?
    var pending: (mark: CGRect, kind: NoteKind)?
    var onMark: (CGRect) -> Void = { _ in }
    var onPick: (Int) -> Void = { _ in }
    private var hovered: Int?
    private var start: CGPoint?
    private var draft: CGRect?
    private var flashing: (number: Int, until: Date)?

    override init(frame: NSRect) {
        super.init(frame: frame)
        addTrackingArea(NSTrackingArea(rect: .zero, options: [.mouseMoved, .mouseEnteredAndExited, .cursorUpdate, .activeAlways, .inVisibleRect], owner: self))
    }

    required init?(coder: NSCoder) {
        fatalError("BoardView is built in code")
    }

    override var isFlipped: Bool { true }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    func flash(_ number: Int) {
        flashing = (number, Date().addingTimeInterval(BoardView.flashTime))
        needsDisplay = true
    }

    /// Called every tick, so the flash fades.
    func advance() {
        guard let flashing else { return }
        if flashing.until < Date() { self.flashing = nil }
        needsDisplay = true
    }

    private func point(_ event: NSEvent) -> CGPoint {
        let p = convert(event.locationInWindow, from: nil)
        return CGPoint(x: min(max(p.x, 0), bounds.width), y: min(max(p.y, 0), bounds.height))
    }

    private func near(_ a: CGPoint, _ b: CGPoint, _ distance: CGFloat) -> Bool {
        let dx = a.x - b.x, dy = a.y - b.y
        return dx * dx + dy * dy <= distance * distance
    }

    /// The topmost mark at the point: a pin or a number badge, or anywhere on a rectangle.
    private func note(at p: CGPoint) -> Int? {
        notes.last { note in
            near(p, note.mark.origin, 14) || (!note.isPin && note.mark.insetBy(dx: -4, dy: -4).contains(p))
        }?.number
    }

    private func cursor(at p: CGPoint) -> NSCursor {
        note(at: p) == nil ? .crosshair : .pointingHand
    }

    override func cursorUpdate(with event: NSEvent) {
        cursor(at: point(event)).set()
    }

    override func mouseMoved(with event: NSEvent) {
        let p = point(event)
        let over = note(at: p)
        if over != hovered {
            hovered = over
            needsDisplay = true
        }
        cursor(at: p).set()
    }

    override func mouseExited(with event: NSEvent) {
        hovered = nil
        needsDisplay = true
    }

    override func mouseDown(with event: NSEvent) {
        start = point(event)
    }

    override func mouseDragged(with event: NSEvent) {
        guard let start else { return }
        let p = point(event)
        guard draft != nil || !near(p, start, 6) else { return }
        draft = CGRect(x: min(start.x, p.x), y: min(start.y, p.y), width: max(1, abs(p.x - start.x)), height: max(1, abs(p.y - start.y)))
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        guard let start else { return }
        self.start = nil
        if let draft {
            self.draft = nil
            onMark(draft)
        } else if let hit = note(at: start) {
            onPick(hit)
        } else {
            onMark(CGRect(origin: start, size: .zero))
        }
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.black.withAlphaComponent(0.08).setFill()
        bounds.fill(using: .copy)
        for note in notes {
            Markers.draw(note.mark, kind: note.kind, number: note.number, wide: note.number == editing || note.number == hovered)
        }
        if let pending { Markers.draw(pending.mark, kind: pending.kind, number: nil, wide: true) }
        if let draft { Markers.draft(draft) }
        guard let flashing, let note = notes.first(where: { $0.number == flashing.number }) else { return }
        let left = Motion.on ? max(0, flashing.until.timeIntervalSinceNow / BoardView.flashTime) : 1
        Theme.kind(note.kind).withAlphaComponent(0.6 * CGFloat(left)).setStroke()
        let m = note.mark
        let ring = note.isPin
            ? NSBezierPath(ovalIn: CGRect(x: m.minX - 20, y: m.minY - 20, width: 40, height: 40))
            : NSBezierPath(roundedRect: m.insetBy(dx: -6, dy: -6), xRadius: 4, yRadius: 4)
        ring.lineWidth = 4
        ring.stroke()
    }
}

/// The numbered marks, drawn alike on the pinboard and into a round's pictures, at k pixels
/// per point. They draw into the current context, which counts from the top left.
enum Markers {
    static func draw(_ mark: CGRect, kind: NoteKind, number: Int?, scale k: CGFloat = 1, wide: Bool = false) {
        let color = Theme.kind(kind), line = (wide ? 3 : 2) * k
        guard mark.size != .zero else {
            NSColor(white: 0, alpha: 0.1).setFill()
            for i in 1...3 {
                let r = (14 + CGFloat(i) * 1.2) * k
                NSBezierPath(ovalIn: CGRect(x: mark.minX - r, y: mark.minY - r + 1.5 * k, width: 2 * r, height: 2 * r)).fill()
            }
            disc(at: mark.origin, diameter: 24 * k, color: color, number: number, scale: k, ring: line)
            return
        }
        color.withAlphaComponent(0.14).setFill()
        NSBezierPath(rect: mark).fill()
        color.setStroke()
        let edge = NSBezierPath(rect: mark)
        edge.lineWidth = line
        edge.stroke()
        if let number { disc(at: mark.origin, diameter: 22 * k, color: color, number: number, scale: k, ring: 2 * k) }
    }

    /// A number in a disc of the kind's colour, inside a white ring of the given width.
    static func disc(at c: CGPoint, diameter d: CGFloat, color: NSColor, number: Int?, scale k: CGFloat = 1, ring: CGFloat) {
        if ring > 0 {
            NSColor.white.setFill()
            NSBezierPath(ovalIn: CGRect(x: c.x - d / 2 - ring, y: c.y - d / 2 - ring, width: d + 2 * ring, height: d + 2 * ring)).fill()
        }
        color.setFill()
        NSBezierPath(ovalIn: CGRect(x: c.x - d / 2, y: c.y - d / 2, width: d, height: d)).fill()
        guard let number else { return }
        let attributes: [NSAttributedString.Key: Any] = [.font: Theme.semiBold(12 * k), .foregroundColor: Theme.accentInk]
        let text = "\(number)", size = text.size(withAttributes: attributes)
        text.draw(at: CGPoint(x: c.x - size.width / 2, y: c.y - size.height / 2), withAttributes: attributes)
    }

    /// The rectangle being dragged out.
    static func draft(_ r: CGRect) {
        Theme.accent.withAlphaComponent(0.1).setFill()
        NSBezierPath(rect: r).fill()
        Theme.accent.setStroke()
        let edge = NSBezierPath(rect: r)
        edge.lineWidth = 2
        edge.setLineDash([6, 4], count: 2, phase: 0)
        edge.stroke()
    }
}

/// The pictures of a round, all cut from one capture of the share at the screen's own density.
enum RoundPictures {
    static func round(_ number: Int, notes: [Note], share: Share, shot: CGImage, title: String) -> Round {
        let whole = CGRect(origin: .zero, size: share.area.size)
        let image = picture(shot, of: share, box: whole, scale: share.scale, marks: notes)
        return Round(number: number, sent: Date(), title: title, share: share, image: image, notes: notes) { note, box in
            picture(shot, of: share, box: box, scale: share.cropScale(box), marks: [note])
        }
    }

    /// The box of the share, in points from its top left, at k pixels per point and with the
    /// marks on top.
    private static func picture(_ shot: CGImage, of share: Share, box: CGRect, scale k: CGFloat, marks: [Note]) -> Data {
        let width = max(1, Int((box.width * k).rounded())), height = max(1, Int((box.height * k).rounded()))
        let context = Bitmap.context(width: width, height: height)
        context.interpolationQuality = .high
        let size = share.area.size
        context.draw(shot, in: CGRect(x: -box.minX * k, y: (box.maxY - size.height) * k, width: size.width * k, height: size.height * k))
        context.translateBy(x: 0, y: CGFloat(height))
        context.scaleBy(x: 1, y: -1)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: true)
        for note in marks {
            let m = note.mark
            let place = CGRect(x: (m.minX - box.minX) * k, y: (m.minY - box.minY) * k, width: m.width * k, height: m.height * k)
            Markers.draw(place, kind: note.kind, number: note.number, scale: k)
        }
        NSGraphicsContext.restoreGraphicsState()
        return Bitmap.png(context.makeImage()!)
    }
}
