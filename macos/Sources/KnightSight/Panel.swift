import AppKit
import KnightSightCore

/// The window that owns the share: choosing it, starting and ending it, and the frame and
/// badge that show it on the screen.
final class Panel: NSObject, NSWindowDelegate {
    // A request less than this long ago counts as work in progress, so frame and badge stay
    // lit through the pauses between the steps of one task.
    static let workSpan: TimeInterval = 5
    static let pulsePeriod: TimeInterval = 1.4

    private let say = Say.current
    private let session = Session()
    private let window: NSWindow
    private let view: PanelView
    private let frame = Frame()
    private let badge = Badge()
    private let foreground: Foreground
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

    override init() {
        view = PanelView(say: say)
        foreground = Foreground(session: session, say: say)
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
        session.marks = Set((frame.edges + [badge.window]).map { CGWindowID($0.windowNumber) })

        hotkey = Hotkey { [weak self] in self?.stop() }
        let responder = Responder(desk: MacDesk(session: session, say: say, foreground: foreground), say: say)
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
        if session.active && working { return say.doing + session.doing }
        if session.active { return say.shared }
        return chosen.window != nil ? say.windowChosen : say.regionChosen
    }

    private func showState() {
        let active = session.active
        view.show(headline(), subline())
        view.pickWindow.isEnabled = !active
        view.pickRegion.isEnabled = !active
        view.toggle.isEnabled = session.chosen != nil
        view.toggle.title = active ? say.stopShare : say.startShare
        view.toggle.glyph = active ? .stop : .start
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
            session.chosen = Chosen(window: w.id, region: .zero, title: w.title(say))
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
                session.chosen = Chosen(window: nil, region: area, title: "\(say.region) \(Int(area.width)) x \(Int(area.height))")
            }
            picker = nil
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            showState()
        }
        picker?.show()
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
        showState()
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
            showState()
        } else if working && view.subline != subline() {
            showState()
        }
        view.dotColor = !active ? Theme.neutral : working ? Motion.mix(Theme.accent, Theme.warning, pulse) : Theme.accent
        view.halo = working && Motion.on ? pulse : 0

        guard let chosen = session.chosen else { return hideMarks() }
        var shared: WindowInfo?
        var area = chosen.region
        if let id = chosen.window {
            guard let w = Windows.info(id) else {
                session.chosen = nil
                session.active = false
                hideMarks()
                return showState()
            }
            guard w.onScreen else { return hideMarks() }
            shared = w
            area = w.bounds
        }

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
        stack(on: shared)
    }

    private func hideMarks() {
        frame.hide()
        badge.hide()
    }

    // Frame and badge sit right above a shared window: high enough to show, and no higher, so
    // a window the person lays over the share stays clear of them. A region gets them on top.
    private func stack(on shared: WindowInfo?) {
        let marks = frame.edges + (badge.window.isVisible ? [badge.window] : [])
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
        for mark in marks { mark.order(.above, relativeTo: Int(shared.id)) }
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
    static let width: CGFloat = 580, height: CGFloat = 212, bar: CGFloat = 40, gutter: CGFloat = 16

    let pickWindow: SoftButton, pickRegion: SoftButton, toggle: SoftButton, info: SoftButton
    private(set) var headline = "", subline = ""
    private var oldHeadline = "", oldSubline = ""
    private var swap = 1.0
    private var logo: (pixels: Int, image: NSImage)?

    var dotColor = Theme.neutral { didSet { if dotColor != oldValue { needsDisplay = true } } }
    var halo: CGFloat = 0 { didSet { if halo != oldValue { needsDisplay = true } } }

    var card: CGRect {
        CGRect(x: PanelView.gutter, y: PanelView.bar, width: PanelView.width - 2 * PanelView.gutter, height: PanelView.height - PanelView.bar - PanelView.gutter)
    }

    init(say: Say) {
        pickWindow = SoftButton(say.pickWindow, glyph: .window)
        pickRegion = SoftButton(say.pickRegion, glyph: .region)
        toggle = SoftButton(say.startShare, glyph: .start, kind: .primary)
        info = SoftButton("", glyph: .info)
        super.init(frame: CGRect(x: 0, y: 0, width: PanelView.width, height: PanelView.height))
        let card = self.card
        let buttonsY = card.maxY - 20 - 40
        pickWindow.frame = CGRect(x: card.minX + 20, y: buttonsY + 2, width: 148, height: 36)
        pickRegion.frame = CGRect(x: card.minX + 176, y: buttonsY + 2, width: 148, height: 36)
        toggle.frame = CGRect(x: card.maxX - 20 - 176, y: buttonsY, width: 176, height: 40)
        info.frame = CGRect(x: card.maxX - 20 - 28, y: card.minY + 18, width: 28, height: 28)
        info.radius = 14
        info.toolTip = say.help
        info.setAccessibilityLabel(say.help)
        for button in [pickWindow, pickRegion, toggle, info] { addSubview(button) }
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
        guard swap < 1 else { return }
        swap = Motion.step(swap, to: 1, elapsed: elapsed, duration: Motion.content)
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        Theme.ground.setFill()
        bounds.fill()
        let card = self.card
        Theme.surface.setFill()
        NSBezierPath(roundedRect: card, xRadius: 10, yRadius: 10).fill()

        let spot = CGRect(x: card.minX + 20, y: card.minY + 18, width: 52, height: 52)
        logoImage().draw(in: spot, from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
        let textX = spot.maxX + 16
        let area = CGRect(x: textX, y: card.minY + 20, width: info.frame.minX - 12 - textX, height: 48)

        // The state dot: grey until shared, accent while shared, pulsing while work goes on.
        let d: CGFloat = 8, dy = area.minY + 26 + 10
        if halo > 0 {
            Theme.warning.withAlphaComponent(80 / 255 * halo).setFill()
            NSBezierPath(ovalIn: CGRect(x: area.minX + d / 2 - d, y: dy - d, width: d * 2, height: d * 2)).fill()
        }
        dotColor.setFill()
        NSBezierPath(ovalIn: CGRect(x: area.minX, y: dy - d / 2, width: d, height: d)).fill()

        let t = CGFloat(Motion.ease(swap)), shift: CGFloat = 6
        if t < 1 { texts(area, oldHeadline, oldSubline, alpha: 1 - t, dy: -shift * t) }
        texts(area, headline, subline, alpha: t, dy: shift * (1 - t))
    }

    private func texts(_ area: CGRect, _ head: String, _ sub: String, alpha: CGFloat, dy: CGFloat) {
        let style = NSMutableParagraphStyle()
        style.lineBreakMode = .byTruncatingTail
        let indent: CGFloat = 16
        head.draw(
            with: CGRect(x: area.minX, y: area.minY + dy, width: area.width, height: 24),
            options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine],
            attributes: [.font: Theme.semiBold(16), .foregroundColor: Theme.text.withAlphaComponent(alpha), .paragraphStyle: style])
        sub.draw(
            with: CGRect(x: area.minX + indent, y: area.minY + 26 + dy, width: area.width - indent, height: 20),
            options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine],
            attributes: [.font: Theme.regular(13), .foregroundColor: Theme.secondary.withAlphaComponent(alpha), .paragraphStyle: style])
    }

    private func logoImage() -> NSImage {
        let pixels = Int((52 * (window?.backingScaleFactor ?? 2)).rounded())
        if let logo, logo.pixels == pixels { return logo.image }
        let image = NSImage(cgImage: Logo.render(pixels), size: CGSize(width: 52, height: 52))
        logo = (pixels, image)
        return image
    }
}
