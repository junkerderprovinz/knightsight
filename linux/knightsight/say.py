"""What the person reads, in English or, on a German desktop, in German.

Replies to the MCP server stay English, since an assistant reads them.
"""

import os


def _language():
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "")
        if value:
            return value.split(":")[0][:2].lower()
    return "en"


GERMAN = _language() == "de"


def pick(english, deutsch):
    return deutsch if GERMAN else english


UNTITLED = pick("Untitled window", "Fenster ohne Titel")
PICK_WINDOW = pick("Choose window", "Fenster wählen")
PICK_REGION = pick("Choose region", "Bereich wählen")
START_SHARE = pick("Start sharing", "Freigabe starten")
STOP_SHARE = pick("Stop sharing", "Freigabe beenden")
CLOSE = pick("Close", "Schließen")
MINIMISE = pick("Minimize", "Minimieren")
NOTHING_CHOSEN = pick("Nothing chosen yet", "Noch nichts gewählt")
CLICK_TARGET = pick("Now click the window you want to share.", "Klick jetzt das Fenster an, das du freigeben willst.")
CHOOSE_TARGET = pick("Choose a window or a region.", "Wähl ein Fenster oder einen Bereich.")
DOING = pick("Now: ", "Gerade: ")
SHARED = pick("Shared. Carry on as usual.", "Freigegeben. Du kannst normal weiterarbeiten.")
WINDOW_CHOSEN = pick("Window chosen, not shared yet.", "Fenster gewählt, noch nicht freigegeben.")
REGION_CHOSEN = pick("Region chosen, not shared yet.", "Bereich gewählt, noch nicht freigegeben.")
REGION = pick("Region", "Bereich")
CHOSEN_WINDOW = pick("Chosen window", "Gewähltes Fenster")
LOOKING = pick("Taking a screenshot", "Mache Screenshot")
RIGHT_CLICKING = pick("Right-clicking", "Rechtsklick")
DOUBLE_CLICKING = pick("Double-clicking", "Doppelklick")
CLICKING = pick("Clicking", "Klicke")
SCROLLING = pick("Scrolling", "Scrolle")
TYPING = pick("Typing", "Tippe")
PRESSING = pick("Pressing ", "Drücke ")
PRESSING_KEY = pick("Pressing a key", "Drücke Taste")

PICK_IN_DIALOG = pick("Choose the window in the dialog that opens.", "Wähl das Fenster im Dialog, der gleich aufgeht.")
PICK_SCREEN_IN_DIALOG = pick(
    "Choose the screen in the dialog, then drag a rectangle.",
    "Wähl im Dialog den Bildschirm und zieh dann ein Rechteck auf.")
NO_PORTAL = pick(
    "This desktop doesn't let programs share the screen.",
    "Dieser Desktop erlaubt Programmen keine Bildschirmfreigabe.")

KEY_NAMES = (
    {"ctrl": "Strg", "control": "Strg", "strg": "Strg", "shift": "Umschalt", "escape": "Esc", "pageup": "Bild auf",
     "pagedown": "Bild ab", "backspace": "Rücktaste", "delete": "Entf", "del": "Entf"}
    if GERMAN else
    {"control": "Ctrl", "strg": "Ctrl", "escape": "Esc", "pageup": "Page Up", "pagedown": "Page Down"}
)

_ENDS = pick(
    "Ctrl+Alt+Shift+X ends the share at once,\nand so does closing this window.",
    "Strg+Alt+Umschalt+X beendet die Freigabe sofort,\nSchließen beendet sie auch.")

HELP_X11 = pick(
    "Grey frame: chosen, not shared yet.\n"
    "Yellow frame: shared. Looking, clicking and typing happen\nonly inside it, and only when asked.\n"
    "A pulsing frame means something is being done in there. Its top\n"
    "right corner says what, such as \"Typing\" or \"Taking a screenshot\".\n\n"
    "Carry on working as usual. For a click or a key the window comes\n"
    "to the front once mouse and keyboard rest for about a second.\n"
    "Afterwards your own window and pointer go back to where they were.\n"
    "A minimized window is out of reach.\n\n" + _ENDS,
    "Grauer Rahmen: gewählt, aber noch nicht freigegeben.\n"
    "Gelber Rahmen: freigegeben. Angeschaut, geklickt und getippt\nwird nur darin, und erst auf Anfrage.\n"
    "Pulsiert der Rahmen, wird gerade darin gearbeitet. Was genau,\n"
    "steht oben rechts am Rahmen, etwa „Tippe“ oder „Mache Screenshot“.\n\n"
    "Du kannst nebenbei normal weiterarbeiten. Für einen Klick oder\n"
    "eine Taste kommt das Fenster kurz nach vorn, sobald du gut eine\n"
    "Sekunde lang nichts eingibst. Danach sind dein Fenster und dein\n"
    "Mauszeiger wieder da, wo sie waren.\n"
    "Minimiert ist es nicht erreichbar.\n\n" + _ENDS)

HELP_WAYLAND = pick(
    "The frame around this card shows the share. Grey: chosen,\n"
    "not shared yet. Yellow: shared. Looking, clicking and typing\nhappen only inside it, and only when asked.\n"
    "While something is being done, the frame pulses and the\nline under the title says what.\n\n"
    "The desktop moves the real pointer for a click, and keys go to\n"
    "the window last clicked in the share. Keep the shared window\n"
    "uncovered while it works.\n\n" + _ENDS,
    "Der Rahmen um diese Karte zeigt die Freigabe. Grau: gewählt,\n"
    "aber noch nicht freigegeben. Gelb: freigegeben. Angeschaut,\n"
    "geklickt und getippt wird nur darin, und erst auf Anfrage.\n"
    "Wird gerade etwas gemacht, pulsiert der Rahmen, und die Zeile\nunter dem Titel sagt, was.\n\n"
    "Für einen Klick bewegt der Desktop den echten Mauszeiger, und\n"
    "Tasten gehen an das Fenster, das zuletzt in der Freigabe\n"
    "angeklickt wurde. Lass das freigegebene Fenster deshalb\nunverdeckt, solange darin gearbeitet wird.\n\n" + _ENDS)
