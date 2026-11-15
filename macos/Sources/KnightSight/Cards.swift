import AppKit
import KnightSightCore

/// The card beside a mark where its note is written: its kind, its text and who wrote it.
final class NoteEditor: NSView, NSTextViewDelegate {
    static let size = CGSize(width: 300, height: 294)

    let close = SoftButton("", glyph: .close)
    let deleteButton: SoftButton
    let saveButton: SoftButton
    var onChange: () -> Void = {}
    private(set) var kind = NoteKind.wish
    private var title = ""
    private let kinds: [SoftButton]
    private let textBox = RoundBox(), authorBox = RoundBox()
    private let scroll = NSScrollView()
    private let textView = NoteText(frame: .zero)
    private let authorField = NSTextField()

    var text: String { textView.string }
    var author: String { authorField.stringValue }

    init(say: Say) {
        deleteButton = SoftButton(say.delete, glyph: .none)
        saveButton = SoftButton(say.save, glyph: .none, kind: .primary)
        kinds = NoteKind.allCases.map { SoftButton(say.kind($0), glyph: .none) }
        super.init(frame: CGRect(origin: .zero, size: NoteEditor.size))
        let width = NoteEditor.size.width, pad: CGFloat = 16
        close.frame = CGRect(x: width - pad - 24, y: pad, width: 24, height: 24)
        let kindWidth = (width - 2 * pad - 16) / 3
        for (i, (button, kind)) in zip(kinds, NoteKind.allCases).enumerated() {
            button.frame = CGRect(x: pad + CGFloat(i) * (kindWidth + 8), y: 52, width: kindWidth, height: 30)
            button.onPress = { [weak self] in self?.choose(kind) }
        }

        textBox.frame = CGRect(x: pad, y: 94, width: width - 2 * pad, height: 96)
        scroll.frame = textBox.bounds.insetBy(dx: 2, dy: 4)
        scroll.drawsBackground = false
        scroll.borderType = .noBorder
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        let content = scroll.contentSize
        textView.frame = CGRect(origin: .zero, size: content)
        textView.minSize = CGSize(width: 0, height: content.height)
        textView.maxSize = CGSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = CGSize(width: content.width, height: CGFloat.greatestFiniteMagnitude)
        textView.textContainerInset = CGSize(width: 2, height: 2)
        textView.drawsBackground = false
        textView.isRichText = false
        textView.allowsUndo = true
        textView.font = Theme.regular(13)
        textView.placeholder = say.notePlaceholder
        textView.delegate = self
        scroll.documentView = textView
        textBox.addSubview(scroll)

        authorBox.frame = CGRect(x: pad, y: 200, width: width - 2 * pad, height: 30)
        authorField.frame = CGRect(x: 8, y: 6, width: authorBox.frame.width - 16, height: 18)
        authorField.isBordered = false
        authorField.isBezeled = false
        authorField.drawsBackground = false
        authorField.focusRingType = .none
        authorField.usesSingleLineMode = true
        authorField.cell?.isScrollable = true
        authorField.font = Theme.regular(13)
        authorField.placeholderString = say.authorPlaceholder
        authorBox.addSubview(authorField)

        deleteButton.frame = CGRect(x: pad, y: 246, width: 96, height: 32)
        saveButton.frame = CGRect(x: width - pad - 104, y: 246, width: 104, height: 32)
        for view in [close, textBox, authorBox, deleteButton, saveButton] as [NSView] { addSubview(view) }
        for button in kinds { addSubview(button) }
        restyle()
    }

    required init?(coder: NSCoder) {
        fatalError("NoteEditor is built in code")
    }

    override var isFlipped: Bool { true }

    func load(title: String, kind: NoteKind, text: String, author: String, existing: Bool) {
        self.title = title
        self.kind = kind
        textView.string = text
        authorField.stringValue = author
        deleteButton.isHidden = !existing
        restyle()
        needsDisplay = true
    }

    func focus() {
        window?.makeFirstResponder(textView)
        textView.setSelectedRange(NSRange(location: (textView.string as NSString).length, length: 0))
    }

    func textDidChange(_ notification: Notification) {
        restyle()
        onChange()
    }

    private func choose(_ kind: NoteKind) {
        self.kind = kind
        restyle()
        onChange()
    }

    // Theme follows the appearance, which the text views do not ask it about on their own.
    private func restyle() {
        for (button, kind) in zip(kinds, NoteKind.allCases) {
            button.filled = kind == self.kind ? Theme.kind(kind) : nil
        }
        textView.textColor = Theme.text
        textView.insertionPointColor = Theme.text
        textView.typingAttributes = [.font: Theme.regular(13), .foregroundColor: Theme.text]
        textView.needsDisplay = true
        authorField.textColor = Theme.text
        saveButton.isEnabled = !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    override func viewDidChangeEffectiveAppearance() {
        restyle()
        needsDisplay = true
        for view in subviews { view.needsDisplay = true }
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill(using: .copy)
        Theme.surface.setFill()
        NSBezierPath(roundedRect: bounds, xRadius: 10, yRadius: 10).fill()
        let attributes: [NSAttributedString.Key: Any] = [.font: Theme.semiBold(15), .foregroundColor: Theme.text]
        let height = title.size(withAttributes: attributes).height
        title.draw(at: CGPoint(x: 16, y: 16 + (24 - height) / 2), withAttributes: attributes)
    }
}

/// The card that lists the notes on the board, with Save as file and Done below them.
final class BoardList: NSView {
    static let width: CGFloat = 300, row: CGFloat = 44, maxRows = 6

    let close = SoftButton("", glyph: .close)
    let saveFile: SoftButton
    let done: SoftButton
    let rows: NoteRows
    private let say: Say
    private let scroll = NSScrollView()
    private var count = 0

    init(say: Say) {
        self.say = say
        rows = NoteRows(say: say)
        saveFile = SoftButton(say.saveFile, glyph: .none)
        done = SoftButton(say.done, glyph: .none, kind: .primary)
        super.init(frame: CGRect(x: 0, y: 0, width: BoardList.width, height: 200))
        close.toolTip = say.closePinboard
        close.setAccessibilityLabel(say.closePinboard)
        scroll.drawsBackground = false
        scroll.borderType = .noBorder
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.documentView = rows
        for view in [close, scroll, saveFile, done] as [NSView] { addSubview(view) }
    }

    required init?(coder: NSCoder) {
        fatalError("BoardList is built in code")
    }

    override var isFlipped: Bool { true }

    /// Grows with the notes up to a few rows, which then scroll.
    var size: CGSize {
        let list = count == 0 ? 56 : CGFloat(min(count, BoardList.maxRows)) * BoardList.row
        return CGSize(width: BoardList.width, height: 52 + list + 60)
    }

    /// Typed says whether the open note has text, which Done and Save as file take along.
    func show(_ notes: [Note], typed: Bool, sending: Bool) {
        count = notes.count
        rows.notes = notes
        let size = self.size, width = BoardList.width
        close.frame = CGRect(x: width - 16 - 24, y: 16, width: 24, height: 24)
        scroll.frame = CGRect(x: 8, y: 52, width: width - 16, height: size.height - 112)
        scroll.isHidden = notes.isEmpty
        rows.frame = CGRect(x: 0, y: 0, width: scroll.contentSize.width, height: CGFloat(count) * BoardList.row)
        let footer = size.height - 16 - 32
        saveFile.frame = CGRect(x: 16, y: footer, width: 164, height: 32)
        done.frame = CGRect(x: width - 16 - 92, y: footer, width: 92, height: 32)
        saveFile.isEnabled = (!notes.isEmpty || typed) && !sending
        done.isEnabled = (!notes.isEmpty || typed) && !sending
        needsDisplay = true
    }

    override func viewDidChangeEffectiveAppearance() {
        needsDisplay = true
        rows.needsDisplay = true
        for view in subviews { view.needsDisplay = true }
    }

    override func draw(_ dirtyRect: NSRect) {
        NSColor.clear.setFill()
        dirtyRect.fill(using: .copy)
        Theme.surface.setFill()
        NSBezierPath(roundedRect: bounds, xRadius: 10, yRadius: 10).fill()
        let head: [NSAttributedString.Key: Any] = [.font: Theme.semiBold(15), .foregroundColor: Theme.text]
        let small: [NSAttributedString.Key: Any] = [.font: Theme.regular(13), .foregroundColor: Theme.muted]
        let title = say.pinboard, titleSize = title.size(withAttributes: head)
        title.draw(at: CGPoint(x: 16, y: 16 + (24 - titleSize.height) / 2), withAttributes: head)
        let number = "\(count)", numberSize = number.size(withAttributes: small)
        number.draw(at: CGPoint(x: 16 + titleSize.width + 8, y: 16 + (24 - numberSize.height) / 2), withAttributes: small)
        if count == 0 {
            say.emptyBoard.draw(with: CGRect(x: 16, y: 56, width: BoardList.width - 32, height: 48), options: .usesLineFragmentOrigin, attributes: small, context: nil)
        }
    }
}

/// The notes of the list, a row each. A click on a row goes to its note.
final class NoteRows: NSView {
    var notes: [Note] = [] { didSet { needsDisplay = true } }
    var onGo: (Int) -> Void = { _ in }
    private let say: Say
    private var hovered: Int?
    private var pressed: Int?

    init(say: Say) {
        self.say = say
        super.init(frame: .zero)
        addTrackingArea(NSTrackingArea(rect: .zero, options: [.mouseMoved, .mouseEnteredAndExited, .activeAlways, .inVisibleRect], owner: self))
    }

    required init?(coder: NSCoder) {
        fatalError("NoteRows is built in code")
    }

    override var isFlipped: Bool { true }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    private func row(_ event: NSEvent) -> Int? {
        let p = convert(event.locationInWindow, from: nil)
        guard bounds.contains(p) else { return nil }
        let i = Int(p.y / BoardList.row)
        return i < notes.count ? i : nil
    }

    private func hover(_ i: Int?) {
        guard i != hovered else { return }
        hovered = i
        needsDisplay = true
    }

    override func mouseMoved(with event: NSEvent) { hover(row(event)) }

    override func mouseExited(with event: NSEvent) { hover(nil) }

    override func mouseDown(with event: NSEvent) { pressed = row(event) }

    override func mouseUp(with event: NSEvent) {
        if let i = row(event), i == pressed { onGo(notes[i].number) }
        pressed = nil
    }

    override func draw(_ dirtyRect: NSRect) {
        let line = NSMutableParagraphStyle()
        line.lineBreakMode = .byTruncatingTail
        let go: [NSAttributedString.Key: Any] = [.font: Theme.semiBold(12), .foregroundColor: Theme.secondary]
        let goSize = say.goThere.size(withAttributes: go)
        for (i, note) in notes.enumerated() {
            let r = CGRect(x: 0, y: CGFloat(i) * BoardList.row, width: bounds.width, height: BoardList.row)
            guard r.intersects(dirtyRect) else { continue }
            let lit = i == hovered
            if lit {
                Theme.surface2.setFill()
                NSBezierPath(roundedRect: r.insetBy(dx: 0, dy: 2), xRadius: 6, yRadius: 6).fill()
                say.goThere.draw(at: CGPoint(x: r.maxX - 8 - goSize.width, y: r.midY - goSize.height / 2), withAttributes: go)
            }
            Markers.disc(at: CGPoint(x: r.minX + 19, y: r.midY), diameter: 22, color: Theme.kind(note.kind), number: note.number, ring: 0)
            let x = r.minX + 40, width = r.maxX - 8 - x - (lit ? goSize.width + 8 : 0)
            say.kind(note.kind).draw(
                with: CGRect(x: x, y: r.minY + 5, width: width, height: 16), options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine],
                attributes: [.font: Theme.regular(11), .foregroundColor: Theme.muted, .paragraphStyle: line], context: nil)
            note.text.replacingOccurrences(of: "\n", with: " ").draw(
                with: CGRect(x: x, y: r.minY + 21, width: width, height: 18), options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine],
                attributes: [.font: Theme.regular(13), .foregroundColor: Theme.text, .paragraphStyle: line], context: nil)
        }
    }
}

/// The sunken field behind a text input.
final class RoundBox: NSView {
    override var isFlipped: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        Theme.surface2.setFill()
        NSBezierPath(roundedRect: bounds, xRadius: 6, yRadius: 6).fill()
    }
}

/// A text view that shows a hint while it is empty, as a text field does.
final class NoteText: NSTextView {
    var placeholder = ""

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        guard string.isEmpty else { return }
        let x = textContainerInset.width + (textContainer?.lineFragmentPadding ?? 0)
        placeholder.draw(
            with: CGRect(x: x, y: textContainerInset.height, width: bounds.width - 2 * x, height: bounds.height),
            options: .usesLineFragmentOrigin,
            attributes: [.font: font ?? Theme.regular(13), .foregroundColor: Theme.muted], context: nil)
    }
}
