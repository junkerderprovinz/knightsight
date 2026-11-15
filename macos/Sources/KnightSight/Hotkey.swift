import Carbon.HIToolbox

/// Ctrl+Option+Shift+X and Ctrl+Option+Shift+P from anywhere. A Carbon hot key needs no
/// permission, unlike watching the keyboard.
final class Hotkey {
    private static var actions: [UInt32: () -> Void] = [:]
    private var refs: [EventHotKeyRef?] = []

    init(stop: @escaping () -> Void, pinboard: @escaping () -> Void) {
        Hotkey.actions = [1: stop, 2: pinboard]
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
            var id = EventHotKeyID()
            GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size, nil, &id)
            Hotkey.actions[id.id]?()
            return OSStatus(noErr)
        }, 1, &spec, nil, nil)
        for (number, key) in [(UInt32(1), kVK_ANSI_X), (2, kVK_ANSI_P)] {
            var ref: EventHotKeyRef?
            RegisterEventHotKey(UInt32(key), UInt32(controlKey | optionKey | shiftKey), EventHotKeyID(signature: 0x4B53_4854, id: number), GetApplicationEventTarget(), 0, &ref)
            refs.append(ref)
        }
    }
}
