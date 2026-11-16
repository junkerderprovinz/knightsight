import CoreGraphics
import Foundation
import XCTest
@testable import KnightSightCore

struct TestLayout: KeyLayout {
    static let keys: [Character: (UInt16, Modifiers)] = [
        "a": (0x00, []), "c": (0x08, []), "l": (0x25, []), "r": (0x0F, []), "z": (0x06, []),
        "1": (0x12, []), "?": (0x2C, .shift), "@": (0x25, .option),
    ]

    func key(for character: Character) -> (code: UInt16, modifiers: Modifiers)? {
        guard let found = TestLayout.keys[character] else { return nil }
        return (code: found.0, modifiers: found.1)
    }
}

final class FakeDesk: Desk {
    enum Call: Equatable {
        case look(CGSize)
        case click(CGPoint, right: Bool, double: Bool)
        case scroll(CGPoint, Int)
        case type(String)
        case press(KeyCombo)
    }

    var share: Share? = Share(area: CGRect(x: 100, y: 200, width: 784, height: 600), pixelsPerPoint: 2, reachable: true)
    var refusal: Refused?
    var nodes: [Node]?
    var calls: [Call] = []
    var labels: [String] = []
    let layout: KeyLayout = TestLayout()
    let board = Board()

    var comesBack = false

    func currentShare() -> Share? { share }

    func bringBack() -> Bool {
        if comesBack { share?.reachable = true }
        return comesBack
    }

    func began(_ doing: String) { labels.append(doing) }

    func look(size: CGSize) throws -> Screenshot {
        calls.append(.look(size))
        return Screenshot(png: Data([1, 2, 3]), title: "Notes\nDraft", note: nil)
    }

    func controls(in area: CGRect) -> [Node]? { nodes }

    func click(at point: CGPoint, right: Bool, double: Bool) throws -> String {
        if let refusal { throw refusal }
        calls.append(.click(point, right: right, double: double))
        return "Clicked."
    }

    func scroll(at point: CGPoint, notches: Int) throws -> String {
        calls.append(.scroll(point, notches))
        return "Scrolled."
    }

    func type(_ text: String) throws -> String {
        if let refusal { throw refusal }
        calls.append(.type(text))
        return "Typed."
    }

    func press(_ combo: KeyCombo) throws -> String {
        calls.append(.press(combo))
        return "Pressed."
    }
}

final class ResponderTests: XCTestCase {
    var desk: FakeDesk!
    var responder: Responder!

    override func setUp() {
        desk = FakeDesk()
        responder = Responder(desk: desk, say: Say(german: false))
    }

    func reply(_ line: String) throws -> [String: Any] {
        let text = responder.answer(line)
        XCTAssertFalse(text.contains("\n"), "a reply is one line")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any])
    }

    func ask(_ request: [String: Any]) throws -> [String: Any] {
        let data = try JSONSerialization.data(withJSONObject: request)
        return try reply(String(decoding: data, as: UTF8.self))
    }

    func assertRefused(_ request: [String: Any], _ message: String, file: StaticString = #filePath, line: UInt = #line) throws {
        let r = try ask(request)
        XCTAssertEqual(r["ok"] as? Bool, false, file: file, line: line)
        XCTAssertEqual(r["error"] as? String, message, file: file, line: line)
    }

    func testRefusesEverythingWhileNothingIsShared() throws {
        desk.share = nil
        try assertRefused(["cmd": "look"], "Nothing is shared right now. Choose a window or a region in the KnightSight window and start sharing.")
        try assertRefused(["cmd": "click", "x": 10, "y": 10], Refused.nothingShared.message)
        XCTAssertEqual(desk.calls, [])
    }

    func testRefusesAWindowOutOfReach() throws {
        desk.share?.reachable = false
        try assertRefused(["cmd": "type", "text": "hi"], "The shared window is minimized, hidden or on another desktop.")
        XCTAssertEqual(desk.calls, [])
    }

    func testBringsAMinimizedWindowBackBeforeActing() throws {
        desk.share?.reachable = false
        desk.comesBack = true
        XCTAssertEqual(try ask(["cmd": "type", "text": "hi"])["ok"] as? Bool, true)
        XCTAssertEqual(desk.calls, [.type("hi")])
    }

    func testRefusesALineThatIsNoJSONObject() throws {
        for line in ["not json", "[1, 2]", "\"look\"", ""] {
            let r = try reply(line)
            XCTAssertEqual(r["ok"] as? Bool, false)
            XCTAssertEqual(r["error"] as? String, "The request is not a JSON object.")
        }
    }

    func testNamesWhatIsMissing() throws {
        try assertRefused(["x": 1], "Missing cmd.")
        try assertRefused(["cmd": "click", "y": 1], "Missing x.")
        try assertRefused(["cmd": "click", "x": "5", "y": 1], "Missing x.")
        try assertRefused(["cmd": "scroll", "x": 1, "y": 1], "Missing amount.")
        try assertRefused(["cmd": "type"], "Missing text.")
        try assertRefused(["cmd": "key"], "Missing keys.")
    }

    func testRefusesAnUnknownCommand() throws {
        try assertRefused(["cmd": "dance"], "Unknown command: dance")
        XCTAssertEqual(desk.labels, ["dance"])
    }

    func testLookReturnsThePictureAndItsSize() throws {
        let r = try ask(["cmd": "look"])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["image"] as? String, "AQID")
        XCTAssertEqual(r["width"] as? Int, 1568)
        XCTAssertEqual(r["height"] as? Int, 1200)
        XCTAssertEqual(r["title"] as? String, "Notes\nDraft")
        XCTAssertNil(r["note"])
        XCTAssertNil(r["error"])
        XCTAssertEqual(desk.calls, [.look(CGSize(width: 1568, height: 1200))])
        XCTAssertEqual(desk.labels, ["Taking a screenshot"])
    }

    func testPictureKeepsItsLongerEdgeWithinTheLimit() {
        let wide = Share(area: CGRect(x: 0, y: 0, width: 3136, height: 1000), pixelsPerPoint: 2, reachable: true)
        XCTAssertEqual(wide.pictureSize, CGSize(width: 1568, height: 500))
        let small = Share(area: CGRect(x: 0, y: 0, width: 800, height: 600), pixelsPerPoint: 1, reachable: true)
        XCTAssertEqual(small.pictureSize, CGSize(width: 800, height: 600))
    }

    func testClickTurnsPictureCoordinatesIntoScreenPoints() throws {
        let r = try ask(["cmd": "click", "x": 200, "y": 100])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["message"] as? String, "Clicked.")
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 200, y: 250), right: false, double: false)])
        XCTAssertEqual(desk.labels, ["Clicking"])
    }

    func testRefusesAPointOutsideTheShare() throws {
        for (x, y) in [(-2, 10), (1568, 10), (10, 1200), (10, -1)] {
            try assertRefused(["cmd": "click", "x": x, "y": y], "The point lies outside the share.")
            try assertRefused(["cmd": "scroll", "x": x, "y": y, "amount": 1], "The point lies outside the share.")
        }
        XCTAssertEqual(desk.calls, [])
    }

    func testTheTopLeftCornerBelongsToTheShare() throws {
        _ = try ask(["cmd": "click", "x": 0, "y": 0])
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 100, y: 200), right: false, double: false)])
    }

    func testRightAndDoubleClicks() throws {
        _ = try ask(["cmd": "click", "x": 2, "y": 2, "right": true])
        _ = try ask(["cmd": "click", "x": 2, "y": 2, "double": true])
        XCTAssertEqual(desk.calls, [
            .click(CGPoint(x: 101, y: 201), right: true, double: false),
            .click(CGPoint(x: 101, y: 201), right: false, double: true),
        ])
        XCTAssertEqual(desk.labels, ["Right-clicking", "Double-clicking"])
    }

    func testOnlyTrueCountsAsAFlag() throws {
        _ = try ask(["cmd": "click", "x": 2, "y": 2, "right": 1, "double": "yes"])
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 101, y: 201), right: false, double: false)])
    }

    func testScrollRoundsAndBoundsTheAmount() throws {
        for amount in [2.5, -1.5, 3.4, 1e9, -1e9] {
            _ = try ask(["cmd": "scroll", "x": 0, "y": 0, "amount": amount])
        }
        let notches = desk.calls.map { call -> Int in
            guard case .scroll(_, let n) = call else { return 0 }
            return n
        }
        XCTAssertEqual(notches, [2, -2, 3, 100, -100])
    }

    func testTypePassesTheTextUnchanged() throws {
        let r = try ask(["cmd": "type", "text": "Grüße\nzweite Zeile"])
        XCTAssertEqual(r["message"] as? String, "Typed.")
        XCTAssertEqual(desk.calls, [.type("Grüße\nzweite Zeile")])
    }

    func testKeyIsParsedBeforeItReachesTheDesk() throws {
        let r = try ask(["cmd": "key", "keys": "cmd+shift+z"])
        XCTAssertEqual(r["message"] as? String, "Pressed.")
        XCTAssertEqual(desk.calls, [.press(KeyCombo(modifiers: [.command, .shift], key: 0x06))])
        XCTAssertEqual(desk.labels, ["Pressing Cmd+Shift+Z"])
    }

    func testRefusedKeysNeverReachTheDesk() throws {
        try assertRefused(["cmd": "key", "keys": "win+r"], "A Mac has no Windows key. App shortcuts use cmd.")
        XCTAssertEqual(desk.calls, [])
    }

    func testRefusesAPointOnKnightSightsOwnWindows() throws {
        desk.share?.own = [CGRect(x: 300, y: 300, width: 720, height: 304)]
        desk.nodes = [Node(role: "AXButton", title: "Start sharing", frame: CGRect(x: 400, y: 400, width: 100, height: 40))]
        _ = try ask(["cmd": "look"])
        for request: [String: Any] in [
            ["cmd": "click", "x": 400, "y": 200],
            ["cmd": "click", "ref": "e1"],
            ["cmd": "scroll", "x": 1500, "y": 400, "amount": 1],
        ] {
            let r = try ask(request)
            XCTAssertEqual(r["error"] as? String, "That point lies on KnightSight itself.")
            XCTAssertNil(r["delivered"])
        }
        _ = try ask(["cmd": "click", "x": 398, "y": 198])
        XCTAssertEqual(desk.calls.dropFirst(), [.click(CGPoint(x: 299, y: 299), right: false, double: false)])
    }

    func testARefusalFromTheDeskIsPassedOn() throws {
        desk.refusal = Refused("No window that takes input lies at this point.")
        try assertRefused(["cmd": "click", "x": 2, "y": 2], "No window that takes input lies at this point.")
    }

    let quest = [
        Node(role: "AXTextField", label: "New quest", text: "Slay the dragon", frame: CGRect(x: 110, y: 220, width: 180, height: 30)),
        Node(role: "AXButton", title: "Add", frame: CGRect(x: 300, y: 220, width: 60, height: 30)),
        Node(role: "AXGroup", frame: CGRect(x: 100, y: 200, width: 784, height: 600)),
    ]

    func testLookListsTheControlsWithTheirRefs() throws {
        desk.nodes = quest
        let r = try ask(["cmd": "look"])
        let elements = try XCTUnwrap(r["elements"] as? [[String: Any]])
        XCTAssertEqual(elements.map { $0["ref"] as? String }, ["e1", "e2"])
        XCTAssertEqual(elements.map { $0["role"] as? String }, ["edit", "button"])
        XCTAssertEqual(elements.map { $0["name"] as? String }, ["New quest", "Add"])
        XCTAssertEqual([elements[1]["x"], elements[1]["y"], elements[1]["width"], elements[1]["height"]].map { $0 as? Int }, [400, 40, 120, 60])
        XCTAssertFalse(responder.answer("{\"cmd\": \"look\"}").contains("Slay the dragon"), "what is typed in a field stays in it")
    }

    func testANamelessControlComesWithoutAName() throws {
        desk.nodes = [Node(role: "AXButton", frame: CGRect(x: 110, y: 220, width: 20, height: 20))]
        let elements = try XCTUnwrap(try ask(["cmd": "look"])["elements"] as? [[String: Any]])
        XCTAssertEqual(elements.count, 1)
        XCTAssertNil(elements[0]["name"])
    }

    func testALookWhoseControlsCannotBeReadStillHasItsPicture() throws {
        let r = try ask(["cmd": "look"])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["image"] as? String, "AQID")
        XCTAssertNil(r["elements"])
    }

    func testClickAndScrollByRefAimAtTheMiddleOfTheElement() throws {
        desk.nodes = quest
        _ = try ask(["cmd": "look"])
        XCTAssertEqual(try ask(["cmd": "click", "ref": "e2"])["message"] as? String, "Clicked.")
        _ = try ask(["cmd": "scroll", "ref": "e1", "amount": 2])
        XCTAssertEqual(desk.calls.dropFirst(), [.click(CGPoint(x: 330, y: 235), right: false, double: false), .scroll(CGPoint(x: 200, y: 235), 2)])
    }

    func testARefMustComeFromTheLastLookAtThisShare() throws {
        try assertRefused(["cmd": "click", "ref": "e1"], "There is no element e1 from the last look. Take a new look.")
        desk.nodes = quest
        _ = try ask(["cmd": "look"])
        try assertRefused(["cmd": "click", "ref": "e12"], "There is no element e12 from the last look. Take a new look.")
        desk.share?.serial = 1
        try assertRefused(["cmd": "click", "ref": "e1"], "There is no element e1 from the last look. Take a new look.")
        XCTAssertEqual(desk.calls, [.look(CGSize(width: 1568, height: 1200))])
    }

    func testALookWithoutControlsForgetsTheRefsBeforeIt() throws {
        desk.nodes = quest
        _ = try ask(["cmd": "look"])
        desk.nodes = nil
        _ = try ask(["cmd": "look"])
        try assertRefused(["cmd": "scroll", "ref": "e1", "amount": 1], "There is no element e1 from the last look. Take a new look.")
    }

    func testClickAndScrollNeedAPointOrARef() throws {
        try assertRefused(["cmd": "click"], "Click needs x and y or a ref from look.")
        try assertRefused(["cmd": "scroll", "amount": 1], "Scroll needs x and y or a ref from look.")
    }

    func testARefusalAfterInputWentOutSaysItMayHaveArrived() throws {
        desk.refusal = Refused("The window closed while the text was being typed.", delivered: true)
        let r = try ask(["cmd": "type", "text": "hi\n"])
        XCTAssertEqual(r["ok"] as? Bool, false)
        XCTAssertEqual(r["delivered"] as? String, "maybe")
    }

    func testARefusalBeforeAnyInputSaysNothingAboutDelivery() throws {
        XCTAssertNil(try ask(["cmd": "click", "x": 5000, "y": 10])["delivered"])
        desk.refusal = Refused("No window that takes input lies at this point.")
        XCTAssertNil(try ask(["cmd": "click", "x": 2, "y": 2])["delivered"])
    }

    func testLabelsFollowTheLanguage() throws {
        responder = Responder(desk: desk, say: Say(german: true))
        _ = try ask(["cmd": "key", "keys": "ctrl+alt+delete"])
        _ = try ask(["cmd": "look"])
        _ = try ask(["cmd": "key", "keys": "shift+pageup"])
        XCTAssertEqual(desk.labels, ["Drücke Ctrl+Alt+Entf", "Mache Screenshot", "Drücke Umschalt+Bild auf"])
    }

    func send(_ notes: [Note], round number: Int = 1) {
        let round = Round(number: number, sent: Date(timeIntervalSince1970: 0), title: "notes.txt", share: desk.share!, image: Data([7]), notes: notes) { _, _, box in
            Data("\(box)".utf8)
        }
        desk.board.send(round)
    }

    func testNotesBeforeTheFirstRoundAnswerRoundZeroEvenWhileNothingIsShared() throws {
        desk.share = nil
        let r = try ask(["cmd": "notes"])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["round"] as? Int, 0)
        XCTAssertNil(r["notes"])
        XCTAssertNil(r["image"])
    }

    func testNotesComeInPictureCoordinatesAndByNumber() throws {
        send([
            Note(number: 4, kind: .question, text: "Why two scrollbars?", author: "Junker", marks: [CGRect(x: 200.3, y: 150, width: 0, height: 0)]),
            Note(number: 3, kind: .bug, text: "The button is cut off.", author: "Junker", marks: [CGRect(x: 60, y: 40, width: 80, height: 20)]),
        ], round: 2)
        let r = try ask(["cmd": "notes"])
        XCTAssertEqual(r["ok"] as? Bool, true)
        XCTAssertEqual(r["round"] as? Int, 2)
        XCTAssertEqual(r["sent"] as? String, "1970-01-01T00:00:00Z")
        XCTAssertEqual(r["title"] as? String, "notes.txt")
        XCTAssertEqual(r["width"] as? Int, 1568)
        XCTAssertEqual(r["height"] as? Int, 1200)
        XCTAssertEqual(r["image"] as? String, "Bw==")
        let notes = try XCTUnwrap(r["notes"] as? [[String: Any]])
        XCTAssertEqual(notes.map { $0["number"] as? Int }, [3, 4])

        let bug = notes[0]
        XCTAssertEqual(bug["kind"] as? String, "bug")
        XCTAssertEqual(bug["text"] as? String, "The button is cut off.")
        XCTAssertEqual(bug["author"] as? String, "Junker")
        for gone in ["x", "y", "width", "height", "pin", "image"] { XCTAssertNil(bug[gone]) }
        let box = try XCTUnwrap((bug["marks"] as? [[String: Any]])?.first)
        XCTAssertEqual(box["label"] as? String, "3")
        XCTAssertEqual([box["x"], box["y"], box["width"], box["height"]].map { $0 as? Int }, [120, 80, 160, 40])
        XCTAssertNil(box["pin"])
        XCTAssertNotNil(box["image"])

        let pin = try XCTUnwrap((notes[1]["marks"] as? [[String: Any]])?.first)
        XCTAssertEqual(notes[1]["kind"] as? String, "question")
        XCTAssertEqual([pin["x"], pin["y"]].map { $0 as? Int }, [401, 300])
        XCTAssertEqual(pin["pin"] as? Bool, true)
        XCTAssertNil(pin["width"])
        XCTAssertNil(pin["height"])
    }

    func testANoteBringsItsMarksInOrderWithTheirLabels() throws {
        send([Note(number: 3, kind: .bug, text: "Both are cut off.", author: "", marks: [
            CGRect(x: 60, y: 40, width: 80, height: 20), CGRect(x: 200, y: 150, width: 0, height: 0),
        ])])
        let notes = try XCTUnwrap(try ask(["cmd": "notes"])["notes"] as? [[String: Any]])
        let marks = try XCTUnwrap(notes[0]["marks"] as? [[String: Any]])
        XCTAssertEqual(marks.map { $0["label"] as? String }, ["3a", "3b"])
        XCTAssertEqual(marks.map { $0["x"] as? Int }, [120, 400])
        XCTAssertEqual(marks.map { $0["pin"] as? Bool }, [nil, true])
        XCTAssertEqual(marks.map { $0["image"] == nil }, [false, false])
    }

    func testFetchingNotesIsNoWork() throws {
        send([Note(number: 1, kind: .wish, text: "Bigger, please.", author: "", marks: [CGRect(x: 10, y: 10, width: 20, height: 20)])])
        _ = try ask(["cmd": "notes"])
        _ = try ask(["cmd": "notes", "unread": true])
        XCTAssertEqual(desk.labels, [])
        XCTAssertEqual(desk.calls, [])
    }

    func testUnreadHandsOutARoundOnce() throws {
        send([Note(number: 1, kind: .wish, text: "Bigger, please.", author: "", marks: [CGRect(x: 10, y: 10, width: 20, height: 20)])])
        XCTAssertNotNil(try ask(["cmd": "notes", "unread": true])["notes"])
        let again = try ask(["cmd": "notes", "unread": true])
        XCTAssertEqual(again["round"] as? Int, 1)
        XCTAssertNil(again["notes"])
        XCTAssertNotNil(try ask(["cmd": "notes"])["notes"])
    }

    func testAMarkOutsideTheShareComesWithoutACrop() throws {
        send([Note(number: 1, kind: .bug, text: "Gone.", author: "", marks: [CGRect(x: 900, y: 10, width: 20, height: 20)])])
        let notes = try XCTUnwrap(try ask(["cmd": "notes"])["notes"] as? [[String: Any]])
        let mark = try XCTUnwrap((notes[0]["marks"] as? [[String: Any]])?.first)
        XCTAssertEqual(mark["x"] as? Int, 1800)
        XCTAssertNil(mark["image"])
    }

    func testRepliesStayEnglishInGerman() throws {
        responder = Responder(desk: desk, say: Say(german: true))
        desk.share = nil
        try assertRefused(["cmd": "look"], Refused.nothingShared.message)
    }
}
