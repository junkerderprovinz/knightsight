import AppKit

/// The GlimStone palette for both appearances, and Noto Sans, which the bundle carries.
enum Theme {
    static let accent = rgb(252, 196, 25)
    static let accentHover = rgb(253, 214, 94)
    static let accentInk = rgb(22, 22, 22)
    static let warning = rgb(255, 131, 43)
    static let neutral = rgb(141, 141, 141)

    static var dark: Bool { NSApp.effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua }
    static var ground: NSColor { dark ? rgb(22, 22, 22) : rgb(244, 244, 244) }
    static var surface: NSColor { dark ? rgb(38, 38, 38) : rgb(255, 255, 255) }
    static var surface2: NSColor { dark ? rgb(57, 57, 57) : rgb(232, 232, 232) }
    static var surface3: NSColor { dark ? rgb(82, 82, 82) : rgb(209, 209, 209) }
    static var text: NSColor { dark ? rgb(244, 244, 244) : rgb(22, 22, 22) }
    static var secondary: NSColor { dark ? rgb(198, 198, 198) : rgb(82, 82, 82) }
    static var muted: NSColor { dark ? rgb(141, 141, 141) : rgb(111, 111, 111) }

    static func rgb(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat) -> NSColor {
        NSColor(srgbRed: r / 255, green: g / 255, blue: b / 255, alpha: 1)
    }

    // Run outside the bundle, as with swift run, the fonts are missing and the system font stands in.
    static func regular(_ size: CGFloat) -> NSFont {
        NSFont(name: "NotoSans-Regular", size: size) ?? .systemFont(ofSize: size)
    }

    static func semiBold(_ size: CGFloat) -> NSFont {
        NSFont(name: "NotoSans-SemiBold", size: size) ?? .systemFont(ofSize: size, weight: .semibold)
    }
}

/// The motion engine's lively numbers, in milliseconds. With Reduce Motion on every duration
/// is zero, so a change lands at once instead of being skipped.
enum Motion {
    static var on: Bool { !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }
    static var control: Double { on ? 150 : 0 }
    static var content: Double { on ? 220 : 0 }
    static let pressScale: CGFloat = 0.96

    static func step(_ from: Double, to: Double, elapsed: Double, duration: Double) -> Double {
        guard duration > 0 else { return to }
        let d = elapsed / duration
        return from < to ? min(to, from + d) : max(to, from - d)
    }

    static func ease(_ t: Double) -> Double { 1 - pow(1 - t, 3) }

    static func mix(_ a: NSColor, _ b: NSColor, _ t: CGFloat) -> NSColor {
        let a = a.usingColorSpace(.sRGB)!, b = b.usingColorSpace(.sRGB)!
        return NSColor(
            srgbRed: a.redComponent + (b.redComponent - a.redComponent) * t,
            green: a.greenComponent + (b.greenComponent - a.greenComponent) * t,
            blue: a.blueComponent + (b.blueComponent - a.blueComponent) * t,
            alpha: 1)
    }
}
