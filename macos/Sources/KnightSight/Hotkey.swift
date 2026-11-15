import Carbon.HIToolbox

/// Ctrl+Option+Shift+X from anywhere, and Cmd+Shift+A while the pinboard may open. A Carbon
/// hot key needs no permission, unlike watching the keyboard.
final class Hotkey {
    private static var actions: [UInt32: () -> Void] = [:]
    private var pinboardRef: EventHotKeyRef?

    init(stop: @escaping () -> Void, pinboard: @escaping () -> Void) {
        Hotkey.actions = [1: stop, 2: pinboard]
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
            var id = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size, nil, &id)
            Hotkey.actions[id.id]?()
            return OSStatus(noErr)
        }, 1, &spec, nil, nil)
        Hotkey.register(1, key: kVK_ANSI_X, modifiers: controlKey | optionKey | shiftKey)
    }

    /// Cmd+Shift+A is a common shortcut in other apps, so KnightSight holds it only while
    /// something is shared.
    var pinboardKey = false {
        didSet {
            guard pinboardKey != oldValue else { return }
            if pinboardKey {
                pinboardRef = Hotkey.register(2, key: kVK_ANSI_A, modifiers: cmdKey | shiftKey)
            } else if let ref = pinboardRef {
                UnregisterEventHotKey(ref)
                pinboardRef = nil
            }
        }
    }

    @discardableResult
    private static func register(_ number: UInt32, key: Int, modifiers: Int) -> EventHotKeyRef? {
        var ref: EventHotKeyRef?
        RegisterEventHotKey(UInt32(key), UInt32(modifiers), EventHotKeyID(signature: 0x4B53_4854, id: number), GetApplicationEventTarget(), 0, &ref)
        return ref
    }
}
