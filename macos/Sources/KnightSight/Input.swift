import Carbon.HIToolbox
import CoreGraphics
import KnightSightCore

/// Input posted straight to the process that owns the target window. It bypasses the
/// system's input stream, so the pointer stays where the person left it and no app comes
/// to the front.
enum Input {
    // A private source carries none of the modifiers the person happens to hold down.
    private static let source = CGEventSource(stateID: .privateState)

    static func click(_ target: WindowInfo, at p: CGPoint, right: Bool, twice: Bool) {
        let button: CGMouseButton = right ? .right : .left
        let down: CGEventType = right ? .rightMouseDown : .leftMouseDown
        let up: CGEventType = right ? .rightMouseUp : .leftMouseUp
        mouse(.mouseMoved, at: p, button: .left, clicks: 0, on: target).postToPid(target.pid)
        for n in 1...(twice ? 2 : 1) {
            mouse(down, at: p, button: button, clicks: n, on: target).postToPid(target.pid)
            usleep(30_000)
            mouse(up, at: p, button: button, clicks: n, on: target).postToPid(target.pid)
        }
    }

    // One notch of a wheel moves three lines, as it does on Windows.
    static func scroll(_ target: WindowInfo, at p: CGPoint, notches: Int) {
        let event = CGEvent(scrollWheelEvent2Source: source, units: .line, wheelCount: 1, wheel1: Int32(-3 * notches), wheel2: 0, wheel3: 0)!
        event.location = p
        aim(event, at: target)
        event.postToPid(target.pid)
    }

    static func type(_ text: String, to pid: pid_t) {
        for c in text {
            switch c {
            case "\r":
                continue
            case "\n", "\r\n":
                tap(KeyCode.returnKey, to: pid)
            case "\t":
                tap(KeyCode.tab, to: pid)
            default:
                let units = Array(String(c).utf16)
                for down in [true, false] {
                    let event = CGEvent(keyboardEventSource: source, virtualKey: 0, keyDown: down)!
                    event.keyboardSetUnicodeString(stringLength: units.count, unicodeString: units)
                    event.postToPid(pid)
                }
            }
            usleep(2_000)
        }
    }

    static func press(_ combo: KeyCombo, to pid: pid_t) {
        let held = modifierKeys.filter { combo.modifiers.contains($0.modifier) }
        var flags: CGEventFlags = []
        for key in held {
            flags.insert(key.flag)
            modifier(key.code, flags).postToPid(pid)
        }
        let all = flags.union(extraFlags(combo.key))
        keyboard(combo.key, down: true, all).postToPid(pid)
        usleep(15_000)
        keyboard(combo.key, down: false, all).postToPid(pid)
        for key in held.reversed() {
            flags.remove(key.flag)
            modifier(key.code, flags).postToPid(pid)
        }
    }

    private static let modifierKeys: [(modifier: Modifiers, code: UInt16, flag: CGEventFlags)] = [
        (.control, KeyCode.control, .maskControl),
        (.option, KeyCode.option, .maskAlternate),
        (.shift, KeyCode.shift, .maskShift),
        (.command, KeyCode.command, .maskCommand),
    ]

    private static func tap(_ code: UInt16, to pid: pid_t) {
        keyboard(code, down: true, []).postToPid(pid)
        keyboard(code, down: false, []).postToPid(pid)
    }

    private static func keyboard(_ code: UInt16, down: Bool, _ flags: CGEventFlags) -> CGEvent {
        let event = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: down)!
        event.flags = flags
        return event
    }

    // A modifier on its own arrives as a change of flags, not as a key press.
    private static func modifier(_ code: UInt16, _ flags: CGEventFlags) -> CGEvent {
        let event = keyboard(code, down: true, flags)
        event.type = .flagsChanged
        return event
    }

    // A real keyboard sends arrows, Home, End and the function keys with these flags set.
    private static func extraFlags(_ code: UInt16) -> CGEventFlags {
        switch code {
        case 0x7B...0x7E: return [.maskNumericPad, .maskSecondaryFn]
        case 0x73, 0x74, 0x75, 0x77, 0x79: return .maskSecondaryFn
        default: return KeyCode.function.contains(code) ? .maskSecondaryFn : []
        }
    }

    private static func mouse(_ type: CGEventType, at p: CGPoint, button: CGMouseButton, clicks: Int, on target: WindowInfo) -> CGEvent {
        let event = CGEvent(mouseEventSource: source, mouseType: type, mouseCursorPosition: p, mouseButton: button)!
        event.setIntegerValueField(.mouseEventClickState, value: Int64(clicks))
        aim(event, at: target)
        return event
    }

    // The window server fills these in for real input, and AppKit hands the event to the window they name.
    private static func aim(_ event: CGEvent, at target: WindowInfo) {
        event.setIntegerValueField(.mouseEventWindowUnderMousePointer, value: Int64(target.id))
        event.setIntegerValueField(.mouseEventWindowUnderMousePointerThatCanHandleThisEvent, value: Int64(target.id))
    }
}

/// The keyboard layout the person has chosen.
struct SystemLayout: KeyLayout {
    func key(for character: Character) -> (code: UInt16, modifiers: Modifiers)? {
        // The text input services answer on the main thread only.
        DispatchQueue.main.sync { lookUp(String(character)) }
    }

    private func lookUp(_ wanted: String) -> (code: UInt16, modifiers: Modifiers)? {
        guard let source = TISCopyCurrentKeyboardLayoutInputSource()?.takeRetainedValue(),
              let property = TISGetInputSourceProperty(source, kTISPropertyUnicodeKeyLayoutData)
        else { return nil }
        let data = Unmanaged<CFData>.fromOpaque(property).takeUnretainedValue() as Data
        return data.withUnsafeBytes { bytes -> (code: UInt16, modifiers: Modifiers)? in
            let layout = bytes.bindMemory(to: UCKeyboardLayout.self).baseAddress!
            for modifiers: Modifiers in [[], .shift, .option, [.option, .shift]] {
                // The typing keys, which come before the keypad and the function keys.
                for code in UInt16(0)...0x32 where code != KeyCode.returnKey && code != KeyCode.tab {
                    if typed(by: code, modifiers, on: layout) == wanted { return (code: code, modifiers: modifiers) }
                }
            }
            return nil
        }
    }

    private func typed(by code: UInt16, _ modifiers: Modifiers, on layout: UnsafePointer<UCKeyboardLayout>) -> String {
        var carbon = 0
        if modifiers.contains(.shift) { carbon |= shiftKey }
        if modifiers.contains(.option) { carbon |= optionKey }
        var dead: UInt32 = 0
        var length = 0
        var chars = [UniChar](repeating: 0, count: 4)
        UCKeyTranslate(
            layout, code, UInt16(kUCKeyActionDown), UInt32(carbon >> 8) & 0xFF, UInt32(LMGetKbdType()),
            OptionBits(kUCKeyTranslateNoDeadKeysMask), &dead, 4, &length, &chars)
        return String(utf16CodeUnits: chars, count: length)
    }
}
