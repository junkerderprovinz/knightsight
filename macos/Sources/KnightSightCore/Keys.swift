import Foundation

/// The modifier keys a combination holds down.
public struct Modifiers: OptionSet, Hashable {
    public let rawValue: Int

    public init(rawValue: Int) {
        self.rawValue = rawValue
    }

    public static let control = Modifiers(rawValue: 1)
    public static let option = Modifiers(rawValue: 2)
    public static let shift = Modifiers(rawValue: 4)
    public static let command = Modifiers(rawValue: 8)
}

/// Finds the key that types a character on the keyboard layout in use, so that cmd+z
/// presses the key that says Z on a German keyboard too.
public protocol KeyLayout {
    func key(for character: Character) -> (code: UInt16, modifiers: Modifiers)?
}

/// Virtual key codes of a Mac keyboard. They name a place on the keyboard, whatever the layout.
public enum KeyCode {
    public static let returnKey: UInt16 = 0x24
    public static let tab: UInt16 = 0x30
    public static let command: UInt16 = 0x37
    public static let shift: UInt16 = 0x38
    public static let option: UInt16 = 0x3A
    public static let control: UInt16 = 0x3B

    public static let named: [String: UInt16] = [
        "enter": 0x24, "return": 0x24, "tab": 0x30, "esc": 0x35, "escape": 0x35, "space": 0x31,
        "backspace": 0x33, "delete": 0x75, "del": 0x75,
        "home": 0x73, "end": 0x77, "pageup": 0x74, "pagedown": 0x79,
        "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    ]

    /// F1 to F20. A Mac keyboard stops there.
    public static let function: [UInt16] = [
        0x7A, 0x78, 0x63, 0x76, 0x60, 0x61, 0x62, 0x64, 0x65, 0x6D,
        0x67, 0x6F, 0x69, 0x6B, 0x71, 0x6A, 0x40, 0x4F, 0x50, 0x5A,
    ]
}

public struct KeyCombo: Equatable {
    public var modifiers: Modifiers
    public var key: UInt16

    public init(modifiers: Modifiers, key: UInt16) {
        self.modifiers = modifiers
        self.key = key
    }

    static let modifierNames: [String: Modifiers] = [
        "ctrl": .control, "control": .control, "strg": .control,
        "alt": .option, "option": .option, "opt": .option,
        "shift": .shift,
        "cmd": .command, "command": .command, "meta": .command,
    ]

    /// Reads cmd+l, shift+tab or a single key into the modifiers and the key.
    public init(parsing combo: String, layout: KeyLayout) throws {
        var held: Modifiers = []
        var key: UInt16?
        for raw in combo.lowercased().split(separator: "+", omittingEmptySubsequences: false) {
            let part = raw.trimmingCharacters(in: .whitespaces)
            if part == "win" || part == "windows" {
                throw Refused("A Mac has no Windows key. App shortcuts use cmd.")
            }
            if let modifier = KeyCombo.modifierNames[part] {
                held.insert(modifier)
                continue
            }
            if key != nil { throw Refused("Only one key besides Ctrl, Option, Shift and Cmd: \(combo)") }
            if let code = KeyCode.named[part] {
                key = code
            } else if let n = KeyCombo.functionNumber(part) {
                guard n <= KeyCode.function.count else { throw Refused("This keyboard has no such key: \(part)") }
                key = KeyCode.function[n - 1]
            } else if part == "insert" {
                throw Refused("This keyboard has no such key: \(part)")
            } else if part.count == 1 {
                guard let found = layout.key(for: Character(part)) else { throw Refused("This keyboard has no such key: \(part)") }
                key = found.code
                held.formUnion(found.modifiers)
            } else {
                throw Refused("Unknown key: \(part)")
            }
        }
        guard let key else { throw Refused("The key itself is missing: \(combo)") }
        self.init(modifiers: held, key: key)
    }

    static func functionNumber(_ part: String) -> Int? {
        guard part.count > 1, part.first == "f", let n = Int(part.dropFirst()), (1...24).contains(n) else { return nil }
        return n
    }
}
