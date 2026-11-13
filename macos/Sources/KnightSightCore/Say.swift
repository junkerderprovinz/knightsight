import Foundation

/// What the person reads, in English or, on a Mac set to German, in German.
public struct Say {
    public let german: Bool

    public init(german: Bool) {
        self.german = german
    }

    public static let current = Say(german: Locale.preferredLanguages.first?.hasPrefix("de") ?? false)

    private func pick(_ english: String, _ deutsch: String) -> String { german ? deutsch : english }

    public var untitled: String { pick("Untitled window", "Fenster ohne Titel") }
    public var pickWindow: String { pick("Choose window", "Fenster wählen") }
    public var pickRegion: String { pick("Choose region", "Bereich wählen") }
    public var startShare: String { pick("Start sharing", "Freigabe starten") }
    public var stopShare: String { pick("Stop sharing", "Freigabe beenden") }
    public var quit: String { pick("Quit KnightSight", "KnightSight beenden") }
    public var nothingChosen: String { pick("Nothing chosen yet", "Noch nichts gewählt") }
    public var clickTarget: String { pick("Now click the window you want to share.", "Klick jetzt das Fenster an, das du freigeben willst.") }
    public var chooseTarget: String { pick("Choose a window or a region.", "Wähl ein Fenster oder einen Bereich.") }
    public var doing: String { pick("Now: ", "Gerade: ") }
    public var shared: String { pick("Shared. Carry on as usual.", "Freigegeben. Du kannst normal weiterarbeiten.") }
    public var windowChosen: String { pick("Window chosen, not shared yet.", "Fenster gewählt, noch nicht freigegeben.") }
    public var regionChosen: String { pick("Region chosen, not shared yet.", "Bereich gewählt, noch nicht freigegeben.") }
    public var region: String { pick("Region", "Bereich") }
    public var looking: String { pick("Taking a screenshot", "Mache Screenshot") }
    public var rightClicking: String { pick("Right-clicking", "Rechtsklick") }
    public var doubleClicking: String { pick("Double-clicking", "Doppelklick") }
    public var clicking: String { pick("Clicking", "Klicke") }
    public var scrolling: String { pick("Scrolling", "Scrolle") }
    public var typing: String { pick("Typing", "Tippe") }
    public var pressing: String { pick("Pressing ", "Drücke ") }
    public var pressingKey: String { pick("Pressing a key", "Drücke Taste") }
    public var waiting: String { pick("Waiting for a quiet moment", "Warte auf einen ruhigen Moment") }

    /// The line the panel shows while macOS still holds back a permission.
    public func allow(screen: Bool, input: Bool) -> String {
        switch (screen, input) {
        case (true, true): return pick("Please allow Screen Recording and Accessibility.", "Erlaub bitte Bildschirmaufnahme und Bedienungshilfen.")
        case (true, false): return pick("Please allow Screen Recording.", "Erlaub bitte Bildschirmaufnahme.")
        default: return pick("Please allow Accessibility.", "Erlaub bitte Bedienungshilfen.")
        }
    }

    var keyNames: [String: String] {
        german
            ? ["ctrl": "Ctrl", "control": "Ctrl", "strg": "Ctrl", "alt": "Alt", "option": "Alt", "opt": "Alt",
               "cmd": "Cmd", "command": "Cmd", "meta": "Cmd", "shift": "Umschalt", "escape": "Esc",
               "pageup": "Bild auf", "pagedown": "Bild ab", "backspace": "Rücktaste", "delete": "Entf", "del": "Entf"]
            : ["ctrl": "Ctrl", "control": "Ctrl", "strg": "Ctrl", "alt": "Option", "option": "Option", "opt": "Option",
               "cmd": "Cmd", "command": "Cmd", "meta": "Cmd", "escape": "Esc", "pageup": "Page Up", "pagedown": "Page Down"]
    }

    public var help: String {
        pick(
            "Grey frame: chosen, not shared yet.\n" +
                "Yellow frame: shared. Looking, clicking and typing happen\nonly inside it, and only when asked.\n" +
                "A pulsing frame means something is being done in there. Its top\nright corner says what, such as \"Typing\" or \"Taking a screenshot\".\n\n" +
                "Carry on working as usual. Typing reaches the window even while\nit is covered. For a click, a scroll or a shortcut with Cmd, the window\n" +
                "comes to the front once mouse and keyboard rest for about a second.\nAfterwards your own window and pointer go back to where they were.\n" +
                "A window that is minimized, hidden or on another desktop is out of reach.\n\n" +
                "KnightSight needs Screen Recording and Accessibility, both\nunder System Settings, Privacy & Security.\n\n" +
                "Ctrl+Option+Shift+X ends the share at once,\nand so does closing this window.",
            "Grauer Rahmen: gewählt, aber noch nicht freigegeben.\n" +
                "Gelber Rahmen: freigegeben. Angeschaut, geklickt und getippt\nwird nur darin, und erst auf Anfrage.\n" +
                "Pulsiert der Rahmen, wird gerade darin gearbeitet. Was genau,\nsteht oben rechts am Rahmen, etwa „Tippe“ oder „Mache Screenshot“.\n\n" +
                "Du kannst nebenbei normal weiterarbeiten. Getippt wird auch, wenn\ndas Fenster zugedeckt ist. Für einen Klick, zum Scrollen oder für ein\n" +
                "Kürzel mit Cmd kommt das Fenster kurz nach vorn, sobald du gut eine\nSekunde lang nichts eingibst. Danach sind dein Fenster und dein\nMauszeiger wieder da, wo sie waren.\n" +
                "Minimiert, ausgeblendet oder auf einem anderen Schreibtisch ist es\nnicht erreichbar.\n\n" +
                "KnightSight braucht Bildschirmaufnahme und Bedienungshilfen, beides\nunter Systemeinstellungen, Datenschutz & Sicherheit.\n\n" +
                "Ctrl+Alt+Umschalt+X beendet die Freigabe sofort,\nSchließen beendet sie auch."
        )
    }

    func describe(_ cmd: String, _ request: Request) -> String {
        switch cmd {
        case "look": return looking
        case "click": return request.flag("right") ? rightClicking : request.flag("double") ? doubleClicking : clicking
        case "scroll": return scrolling
        case "type": return typing
        case "key":
            guard let keys = try? request.text("keys") else { return pressingKey }
            return pressing + keyName(keys)
        default: return cmd
        }
    }

    func keyName(_ combo: String) -> String {
        let names = keyNames
        return combo.split(separator: "+", omittingEmptySubsequences: false).map { raw in
            let part = raw.trimmingCharacters(in: .whitespaces).lowercased()
            return names[part] ?? part.prefix(1).uppercased() + String(part.dropFirst())
        }.joined(separator: "+")
    }
}
