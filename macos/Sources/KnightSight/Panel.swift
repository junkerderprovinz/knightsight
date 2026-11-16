import AppKit
import KnightSightCore
import UniformTypeIdentifiers

/// The window that owns the share: choosing it, starting and ending it, the frame and badge
/// that show it on the screen, and the pinboard over it.
final class Panel: NSObject, NSWindowDelegate {
    // A request less than this long ago counts as work in progress, so frame and badge stay
    // lit through the pauses between the steps of one task.
    static let workSpan: TimeInterval = 5
    static let pulsePeriod: TimeInterval = 1.4

    private let say = Say.current
    private let session = Session()
    private let board = Board()
    private let window: NSWindow
    private let view: PanelView
    private let frame = Frame()
    private let badge = Badge()
    private let pinboard: Pinboard
    private let foreground: Foreground
    private let desk: MacDesk
    private var hotkey: Hotkey?
    private var server: LineServer?
    private var picker: RegionPicker?
    private var picking = false, buttonWasDown = false, working = false
    private var missing = (screen: false, input: false)
    private var pulse: CGFloat = 0
    private var badgeAlpha = 0.0
    private var frameColor = Theme.neutral
    private var last = Date()
    private var lastPermissionCheck = Date.distantPast
    private var previewDue = Date.distantPast, previewBusy = false
    private var notice: String?
    private var sentRound = 0

    override init() {
        view = PanelView(say: say)
        pinboard = Pinboard(board: board, say: say)
        foreground = Foreground(session: session, say: say)
        desk = MacDesk(session: session, say: say, foreground: foreground, board: board)
        window = NSWindow(
            contentRect: CGRect(x: 0, y: 0, width: PanelView.width, height: PanelView.height),
            styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView], backing: .buffered, defer: false)
        super.init()
        window.title = "KnightSight"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        // An empty toolbar makes the title bar as tall as the panel's bar, with the window buttons in its middle.
        window.toolbar = NSToolbar()
        window.toolbarStyle = .unifiedCompact
        window.isReleasedWhenClosed = false
        window.backgroundColor = Theme.ground
        window.contentView = view
        window.delegate = self
        window.center()

        view.pickWindow.onPress = { [weak self] in self?.startPick() }
        view.pickRegion.onPress = { [weak self] in self?.pickRegion() }
        view.toggle.onPress = { [weak self] in
            guard let self else { return }
            if session.active { stop() } else { start() }
        }
        view.pin.onPress = { [weak self] in self?.togglePinboard() }
        pinboard.onClose = { [weak self] in self?.togglePinboard() }
        pinboard.onDone = { [weak self] in self?.sendNotes() }
        pinboard.onSaveFile = { [weak self] in self?.saveNotes() }
        session.marks = Set((frame.edges + [badge.window] + pinboard.windows).map { CGWindowID($0.windowNumber) })

        hotkey = Hotkey(stop: { [weak self] in self?.stop() }, pinboard: { [weak self] in self?.togglePinboard() })
        let responder = Responder(desk: desk, say: say)
        server = try? LineServer(port: Responder.port, answer: responder.answer)
        server?.start()
        let timer = Timer(timeInterval: 1.0 / 60, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
        RunLoop.main.add(timer, forMode: .common)

        checkPermissions()
        showState()
        window.makeKeyAndOrderFront(nil)
    }

    func windowWillClose(_ notification: Notification) {
        NSApp.terminate(nil)
    }

    private func checkPermissions() {
        let now = (screen: !CGPreflightScreenCaptureAccess(), input: !CGPreflightPostEventAccess())
        if now != missing {
            missing = now
            showState()
        }
    }

    private func headline() -> String {
        guard let chosen = session.chosen else { return say.nothingChosen }
        return chosen.window.flatMap { Windows.info($0)?.title(say) } ?? chosen.title
    }

    private func subline() -> String {
        if picking { return say.clickTarget }
        if missing.screen || missing.input { return say.allow(screen: missing.screen, input: missing.input) }
        guard let chosen = session.chosen else { return say.chooseTarget }
        if session.active && pinboard.isOpen { return say.pinboardOn }
        if session.active && working { return say.doing + session.doing }
        if session.active, let notice { return notice }
        if session.active { return say.shared }
        return chosen.window != nil ? say.windowChosen : say.regionChosen
    }

    private func showState() {
        let active = session.active
        view.show(headline(), subline())
        view.chosen = session.chosen != nil
        view.shared = active
        view.working = working
        view.pickWindow.isEnabled = !active
        view.pickRegion.isEnabled = !active
        view.toggle.isEnabled = session.chosen != nil
        view.toggle.title = active ? say.stopShare : say.startShare
        view.toggle.glyph = active ? .stop : .start
        view.toggle.outline = active
        view.pin.isEnabled = active
        hotkey?.pinboardKey = active
        view.pin.filled = pinboard.isOpen ? Theme.accent : nil
    }

    private func startPick() {
        picking = true
        buttonWasDown = NSEvent.pressedMouseButtons & 1 != 0
        showState()
    }

    // Watching the button instead of the clicks needs no permission, and the click still reaches the window.
    private func pollPick() {
        let down = NSEvent.pressedMouseButtons & 1 != 0
        if buttonWasDown && !down,
           let w = Windows.front(at: Screens.flip(NSEvent.mouseLocation), skipping: session.marks),
           w.pid != Windows.ownPid, w.layer == 0 {
            picking = false
            choose(Chosen(window: w.id, region: .zero, title: w.title(say)))
            showState()
        }
        buttonWasDown = down
    }

    private func pickRegion() {
        picking = false
        window.orderOut(nil)
        picker = RegionPicker { [weak self] area in
            guard let self else { return }
            if let area {
                choose(Chosen(window: nil, region: area, title: "\(say.region) \(Int(area.width)) x \(Int(area.height))"))
            }
            picker = nil
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            showState()
        }
        picker?.show()
    }

    // Notes belong to what they were written on.
    private func choose(_ chosen: Chosen) {
        if session.chosen.map({ $0.window != chosen.window || $0.region != chosen.region }) ?? true { board.clear() }
        session.chosen = chosen
        notice = nil
        view.preview = nil
        previewDue = .distantPast
    }

    // macOS asks the person itself, the first time an app wants a permission.
    private func start() {
        guard session.chosen != nil else { return }
        session.active = true
        if missing.screen { CGRequestScreenCaptureAccess() }
        if missing.input { CGRequestPostEventAccess() }
        showState()
    }

    private func stop() {
        session.active = false
        notice = nil
        closePinboard()
        showState()
    }

    private func togglePinboard() {
        guard session.active else { return }
        if pinboard.isOpen {
            closePinboard()
        } else {
            notice = nil
            pinboard.open()
            session.pinboard = true
        }
        showState()
    }

    private func closePinboard() {
        pinboard.close()
        session.pinboard = false
    }

    private func sendNotes() {
        capture { [self] round in
            board.send(round)
            closePinboard()
            notice = say.sent(round.entries.count)
            sentRound = round.number
            showState()
        }
    }

    private func saveNotes() {
        capture { [self] round in
            let panel = NSSavePanel()
            panel.title = say.fileKind
            panel.nameFieldStringValue = say.fileName
            panel.allowedContentTypes = [.html]
            NSApp.activate(ignoringOtherApps: true)
            guard panel.runModal() == .OK, let url = panel.url else { return }
            do {
                try Data(round.page(say).utf8).write(to: url, options: .atomic)
            } catch {
                NSAlert(error: error).runModal()
            }
        }
    }

    /// Pictures the share away from the main thread, so the panel keeps moving, and builds the
    /// next round from the notes on the board. The pinboard's windows stay out of the picture.
    private func capture(then use: @escaping (Round) -> Void) {
        let notes = board.notes
        guard !notes.isEmpty, !pinboard.sending, let share = desk.currentShare() else { return }
        let number = board.nextRound
        pinboard.sending = true
        DispatchQueue.global(qos: .userInitiated).async { [self] in
            // Crops keep the screen's own density, so the share is pictured at that and scaled down after.
            let full = CGSize(width: (share.area.width * share.pixelsPerPoint).rounded(), height: (share.area.height * share.pixelsPerPoint).rounded())
            let shot = try? desk.picture(size: full)
            DispatchQueue.main.async { [self] in
                pinboard.sending = false
                guard let shot else { return NSSound.beep() }
                use(RoundPictures.round(number, notes: notes, share: share, shot: shot.image, title: shot.title))
            }
        }
    }

    @objc private func tick() {
        let now = Date()
        let elapsed = now.timeIntervalSince(last) * 1000
        last = now
        view.advance(elapsed)
        if picking { pollPick() }
        foreground.giveBack()
        if now.timeIntervalSince(lastPermissionCheck) > 1 {
            lastPermissionCheck = now
            checkPermissions()
        }

        let active = session.active
        let nowWorking = active && now.timeIntervalSince(session.lastRequest) < Panel.workSpan
        let phase = now.timeIntervalSince1970.truncatingRemainder(dividingBy: Panel.pulsePeriod) / Panel.pulsePeriod
        pulse = Motion.on ? CGFloat(0.5 - 0.5 * cos(2 * .pi * phase)) : 1
        if nowWorking != working {
            working = nowWorking
            if working { notice = nil }
            showState()
        } else if working && view.subline != subline() {
            showState()
        }
        if sentRound > 0 && board.fetched(sentRound) {
            sentRound = 0
            notice = say.fetched
            showState()
        }
        view.dotColor = !active ? Theme.neutral : working ? Motion.mix(Theme.accent, Theme.warning, pulse) : Theme.accent
        view.halo = working && Motion.on ? pulse : 0
        view.click = session.lastClick

        guard let chosen = session.chosen else { return hideMarks() }
        var shared: WindowInfo?
        var area = chosen.region
        if let id = chosen.window {
            guard let w = Windows.info(id) else {
                session.chosen = nil
                session.active = false
                closePinboard()
                hideMarks()
                return showState()
            }
            guard w.onScreen else { return hideMarks() }
            shared = w
            area = w.bounds
        }
        refreshPreview(chosen, area: area, now: now)

        var width: CGFloat = 3
        let target: NSColor
        if !active {
            target = Theme.neutral
        } else if now < session.busyUntil {
            target = Theme.warning
        } else if working {
            target = Motion.mix(Theme.accent, Theme.warning, pulse)
            width += (2 * pulse).rounded()
        } else {
            target = Theme.accent
        }
        let step = !Motion.on || working ? 1 : min(1, elapsed / Motion.control)
        frameColor = Motion.mix(frameColor, target, CGFloat(step))
        frame.show(Screens.flip(area), color: frameColor, width: width)

        badgeAlpha = Motion.step(badgeAlpha, to: working ? 1 : 0, elapsed: elapsed, duration: Motion.content)
        if badgeAlpha > 0 {
            let text = session.doing, size = badge.size(for: text)
            let spot = CGRect(origin: badgeSpot(area, size), size: size)
            badge.show(text, in: Screens.flip(spot), alpha: CGFloat(Motion.ease(badgeAlpha)), pulse: pulse)
        } else {
            badge.hide()
        }
        if pinboard.isOpen { pinboard.follow(area) }
        stack(on: shared)
    }

    // Picturing a busy window takes a moment, so the finder's picture is taken off the main thread.
    private func refreshPreview(_ chosen: Chosen, area: CGRect, now: Date) {
        guard now >= previewDue, !previewBusy else { return }
        previewDue = now.addingTimeInterval(1)
        previewBusy = true
        let room = view.viewfinder, fit = min(room.width / area.width, room.height / area.height) * window.backingScaleFactor
        let size = CGSize(width: max(1, (area.width * fit).rounded()), height: max(1, (area.height * fit).rounded()))
        DispatchQueue.global(qos: .utility).async { [self] in
            let shot = try? desk.picture(size: size).image
            DispatchQueue.main.async { [self] in
                previewBusy = false
                if let shot, session.chosen === chosen { view.preview = shot }
            }
        }
    }

    private func hideMarks() {
        frame.hide()
        badge.hide()
        pinboard.hide()
    }

    // Frame, badge and pinboard sit right above a shared window: high enough to show, and no
    // higher, so a window the person lays over the share stays clear of them. A region gets
    // them on top. The pinboard's veil is ordered first and so ends up above the frame, and its
    // cards move along with it as its child windows.
    private func stack(on shared: WindowInfo?) {
        let marks = pinboard.shown + frame.edges + (badge.window.isVisible ? [badge.window] : [])
        let level = shared.map { NSWindow.Level(rawValue: $0.layer) } ?? .floating
        for mark in marks where mark.level != level { mark.level = level }
        guard let shared else { return }
        let ids = Set(marks.map { CGWindowID($0.windowNumber) })
        var seen = 0
        for w in Windows.above(shared.id).reversed() {
            if ids.contains(w.id) {
                seen += 1
            } else if !Windows.isPopup(w, of: shared) {
                break
            }
        }
        if seen == ids.count { return }
        for mark in marks where mark.parent == nil { mark.order(.above, relativeTo: Int(shared.id)) }
    }

    // Above the top right corner of the frame, or inside it when the share reaches the top of its screen.
    private func badgeSpot(_ area: CGRect, _ size: CGSize) -> CGPoint {
        let shadow = Badge.shadow, gap: CGFloat = 6, outer: CGFloat = 5
        let above = CGPoint(x: area.maxX + outer - size.width + shadow, y: area.minY - outer - gap - size.height + shadow)
        if above.y >= Screens.top(of: area) { return above }
        return CGPoint(x: area.maxX - 10 - size.width + shadow, y: area.minY + 10 - shadow)
    }
}

final class PanelView: NSView {
    static let width: CGFloat = 600, height: CGFloat = 244, bar: CGFloat = 40, gutter: CGFloat = 16, finderWidth: CGFloat = 176

    let pickWindow: SoftButton, pickRegion: SoftButton, toggle: SoftButton, pin: SoftButton, info: SoftButton
    private(set) var headline = "", subline = ""
    private var oldHeadline = "", oldSubline = ""
    private var swap = 1.0
    private var logo: (pixels: Int, image: NSImage)?
    private let noTarget: String

    var dotColor = Theme.neutral { didSet { if dotColor != oldValue { needsDisplay = true } } }
    var halo: CGFloat = 0 { didSet { if halo != oldValue { needsDisplay = true } } }

    var chosen = false { didSet { if chosen != oldValue { setNeedsDisplay(finder) } } }
    var shared = false
    var working = false
    var click: (spot: CGPoint, at: Date)?
    var preview: CGImage? {
        didSet {
            pictures = preview.map { (colour: NSImage(cgImage: $0, size: .zero), grey: NSImage(cgImage: PanelView.grey($0), size: .zero)) }
            setNeedsDisplay(finder)
        }
    }
    private var pictures: (colour: NSImage, grey: NSImage)?
    // The finder's corners stand wide and breathe until the share starts, then snap in close.
    private var lit = 0.0, corners = 14.0, cornerSpeed = 0.0

    var card: CGRect {
        CGRect(x: PanelView.gutter, y: PanelView.bar, width: PanelView.width - 2 * PanelView.gutter, height: PanelView.height - PanelView.bar - PanelView.gutter)
    }

    var finder: CGRect {
        let card = self.card
        return CGRect(x: card.minX + 16, y: card.minY + 16, width: PanelView.finderWidth, height: card.height - 32)
    }

    var viewfinder: CGRect { finder.insetBy(dx: 14, dy: 14) }

    init(say: Say) {
        pickWindow = SoftButton(say.pickWindow, glyph: .window)
        pickRegion = SoftButton(say.pickRegion, glyph: .region)
        toggle = SoftButton(say.startShare, glyph: .start, kind: .primary)
        pin = SoftButton(say.pinboard, glyph: .pin)
        info = SoftButton("", glyph: .info)
        noTarget = say.noTarget
        super.init(frame: CGRect(x: 0, y: 0, width: PanelView.width, height: PanelView.height))
        let card = self.card
        let side = finder.maxX + 18, sideWidth = card.maxX - 16 - side
        let small = (sideWidth - 16) / 3, rowY = card.maxY - 16 - 48 - 8 - 36
        pickWindow.frame = CGRect(x: side, y: rowY, width: small, height: 36)
        pickRegion.frame = CGRect(x: side + small + 8, y: rowY, width: small, height: 36)
        pin.frame = CGRect(x: side + 2 * (small + 8), y: rowY, width: small, height: 36)
        toggle.frame = CGRect(x: side, y: card.maxY - 16 - 48, width: sideWidth, height: 48)
        toggle.radius = 10
        toggle.label = Theme.semiBold(15)
        info.frame = CGRect(x: card.maxX - 28, y: (PanelView.bar - 28) / 2, width: 28, height: 28)
        info.radius = 14
        info.toolTip = say.help
        info.setAccessibilityLabel(say.help)
        pickWindow.toolTip = say.pickWindowTip
        pickRegion.toolTip = say.pickRegionTip
        pin.toolTip = say.pinboardTip
        pin.setAccessibilityLabel(say.pinboardTip)
        for button in [pickWindow, pickRegion, toggle, pin, info] { addSubview(button) }
    }

    required init?(coder: NSCoder) {
        fatalError("PanelView is built in code")
    }

    override var isFlipped: Bool { true }

    override func viewDidChangeEffectiveAppearance() {
        window?.backgroundColor = Theme.ground
        needsDisplay = true
        for button in subviews { button.needsDisplay = true }
    }

    /// A new text slides up into place while the old one fades out above it.
    func show(_ head: String, _ sub: String) {
        guard head != headline || sub != subline else { return }
        oldHeadline = headline
        oldSubline = subline
        headline = head
        subline = sub
        swap = 0
        needsDisplay = true
    }

    func advance(_ elapsed: Double) {
        if swap < 1 {
            swap = Motion.step(swap, to: 1, elapsed: elapsed, duration: Motion.content)
            needsDisplay = true
        }
        let moving = Motion.on, litTo: Double = shared ? 1 : 0
        let breathe = moving ? 0.5 - 0.5 * cos(2 * .pi * Date().timeIntervalSince1970.truncatingRemainder(dividingBy: 2.4) / 2.4) : 0
        let cornersTo = shared ? 6 : 14 + 6 * breathe
        if moving || lit != litTo { setNeedsDisplay(finder) }
        lit = Motion.step(lit, to: litTo, elapsed: elapsed, duration: Motion.content)
        if moving {
            // A spring, so the corners overshoot a little as they lock on.
            let dt = min(elapsed, 50) / 1000
            cornerSpeed += ((cornersTo - corners) * 260 - cornerSpeed * 20) * dt
            corners += cornerSpeed * dt
        } else {
            corners = cornersTo
        }
    }

    override func draw(_ dirtyRect: NSRect) {
        Theme.ground.setFill()
        bounds.fill()
        let card = self.card
        Theme.surface.setFill()
        NSBezierPath(roundedRect: card, xRadius: 10, yRadius: 10).fill()

        let finder = self.finder
        drawFinder(finder)
        let side = finder.maxX + 18, sideWidth = card.maxX - 16 - side
        logoImage().draw(in: CGRect(x: side, y: card.minY + 16, width: 28, height: 28), from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
        let head = CGRect(x: side + 38, y: card.minY + 19, width: sideWidth - 38, height: 24)
        let sub = CGRect(x: side + 16, y: card.minY + 52, width: sideWidth - 16, height: 20)

        // The state dot: grey until shared, accent while shared, pulsing while work goes on.
        let d: CGFloat = 8, mx = side, my = sub.minY + 10
        if halo > 0 {
            Theme.warning.withAlphaComponent(80 / 255 * halo).setFill()
            NSBezierPath(ovalIn: CGRect(x: mx + d / 2 - d, y: my - d, width: d * 2, height: d * 2)).fill()
        }
        dotColor.setFill()
        NSBezierPath(ovalIn: CGRect(x: mx, y: my - d / 2, width: d, height: d)).fill()

        let t = CGFloat(Motion.ease(swap)), shift: CGFloat = 6
        if t < 1 { texts(head, sub, oldHeadline, oldSubline, alpha: 1 - t, dy: -shift * t) }
        texts(head, sub, headline, subline, alpha: t, dy: shift * (1 - t))
    }

    // The finder shows the share itself, grey while it is only chosen and in colour once it is
    // shared. A line sweeps over it while the assistant works, and a dot marks its last click.
    private func drawFinder(_ finder: CGRect) {
        (Theme.dark ? Theme.rgb(18, 17, 16) : Theme.surface2).setFill()
        NSBezierPath(roundedRect: finder, xRadius: 10, yRadius: 10).fill()
        let view = viewfinder, t = CGFloat(Motion.ease(lit))
        if !chosen {
            let attributes: [NSAttributedString.Key: Any] = [.font: Theme.regular(13), .foregroundColor: Theme.muted]
            let size = noTarget.size(withAttributes: attributes)
            noTarget.draw(at: CGPoint(x: finder.midX - size.width / 2, y: finder.midY - size.height / 2), withAttributes: attributes)
        } else if let pictures {
            let shot = pictures.colour.size
            let fit = min(view.width / shot.width, view.height / shot.height) * (0.94 + 0.06 * t)
            let at = CGRect(x: view.midX - shot.width * fit / 2, y: view.midY - shot.height * fit / 2, width: shot.width * fit, height: shot.height * fit)
            NSGraphicsContext.saveGraphicsState()
            NSBezierPath(roundedRect: at, xRadius: 5, yRadius: 5).addClip()
            // Colour over grey in one layer, so the layer fades as a whole.
            let context = NSGraphicsContext.current!.cgContext
            context.saveGState()
            context.setAlpha(0.55 + 0.45 * t)
            context.beginTransparencyLayer(auxiliaryInfo: nil)
            pictures.grey.draw(in: at, from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
            pictures.colour.draw(in: at, from: .zero, operation: .sourceOver, fraction: t, respectFlipped: true, hints: nil)
            context.endTransparencyLayer()
            context.restoreGState()
            if working && Motion.on { drawWork(at) }
            NSGraphicsContext.restoreGraphicsState()
        }

        let box = finder.insetBy(dx: corners, dy: corners), arm: CGFloat = 16
        let brackets = NSBezierPath()
        let ends: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [(box.minX, box.minY, 1, 1), (box.maxX, box.minY, -1, 1), (box.minX, box.maxY, 1, -1), (box.maxX, box.maxY, -1, -1)]
        for (x, y, sx, sy) in ends {
            brackets.move(to: CGPoint(x: x, y: y + sy * arm))
            brackets.line(to: CGPoint(x: x, y: y))
            brackets.line(to: CGPoint(x: x + sx * arm, y: y))
        }
        brackets.lineWidth = 2
        brackets.lineCapStyle = .round
        brackets.lineJoinStyle = .round
        Motion.mix(Theme.muted, Theme.accent, t).setStroke()
        brackets.stroke()
    }

    private func drawWork(_ at: CGRect) {
        let now = Date()
        let sweep = CGFloat(now.timeIntervalSince1970.truncatingRemainder(dividingBy: 1.6) / 1.6)
        let alpha = 230 / 255 * min(1, min(sweep, 1 - sweep) * 6)
        let line = NSGradient(colors: [Theme.accent.withAlphaComponent(0), Theme.accent.withAlphaComponent(alpha), Theme.accent.withAlphaComponent(0)])
        line?.draw(in: CGRect(x: at.minX, y: at.minY + at.height * sweep - 1, width: at.width, height: 2), angle: 0)

        guard let click else { return }
        let age = now.timeIntervalSince(click.at) * 1000
        guard age <= 2500 else { return }
        let cx = at.minX + at.width * click.spot.x, cy = at.minY + at.height * click.spot.y, d: CGFloat = 8
        Theme.warning.setFill()
        NSBezierPath(ovalIn: CGRect(x: cx - d / 2, y: cy - d / 2, width: d, height: d)).fill()
        if age < 600 {
            let ring = d / 2 + 10 * CGFloat(age / 600)
            let path = NSBezierPath(ovalIn: CGRect(x: cx - ring, y: cy - ring, width: ring * 2, height: ring * 2))
            path.lineWidth = 2
            Theme.warning.withAlphaComponent(150 / 255 * CGFloat(1 - age / 600)).setStroke()
            path.stroke()
        }
    }

    private static func grey(_ image: CGImage) -> CGImage {
        let context = CGContext(
            data: nil, width: image.width, height: image.height, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
        context.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
        return context.makeImage()!
    }

    private func texts(_ head: CGRect, _ sub: CGRect, _ headText: String, _ subText: String, alpha: CGFloat, dy: CGFloat) {
        let style = NSMutableParagraphStyle()
        style.lineBreakMode = .byTruncatingTail
        headText.draw(
            with: head.offsetBy(dx: 0, dy: dy),
            options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine],
            attributes: [.font: Theme.semiBold(16), .foregroundColor: Theme.text.withAlphaComponent(alpha), .paragraphStyle: style])
        subText.draw(
            with: sub.offsetBy(dx: 0, dy: dy),
            options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine],
            attributes: [.font: Theme.regular(13), .foregroundColor: Theme.secondary.withAlphaComponent(alpha), .paragraphStyle: style])
    }

    private func logoImage() -> NSImage {
        let pixels = Int((28 * (window?.backingScaleFactor ?? 2)).rounded())
        if let logo, logo.pixels == pixels { return logo.image }
        let image = NSImage(cgImage: Logo.render(pixels), size: CGSize(width: 28, height: 28))
        logo = (pixels, image)
        return image
    }
}
