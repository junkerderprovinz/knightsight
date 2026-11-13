import Carbon.HIToolbox

/// Ctrl+Option+Shift+X from anywhere. A Carbon hot key needs no permission, unlike watching
/// the keyboard.
final class Hotkey {
    private static var pressed: () -> Void = {}
    private var ref: EventHotKeyRef?

    init(_ pressed: @escaping () -> Void) {
        Hotkey.pressed = pressed
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            Hotkey.pressed()
            return OSStatus(noErr)
        }, 1, &spec, nil, nil)
        let id = EventHotKeyID(signature: 0x4B53_4854, id: 1)
        RegisterEventHotKey(UInt32(kVK_ANSI_X), UInt32(controlKey | optionKey | shiftKey), id, GetApplicationEventTarget(), 0, &ref)
    }
}
